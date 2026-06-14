from typing import Any

from Bio import Entrez
from Bio.Entrez.Parser import DictionaryElement, ListElement, StringElement

from bioseq_dl.constants.databases import REFSEQ
from bioseq_dl.constants.refseq import databases
from bioseq_dl.core.credentials import is_valid_secret, load_environment_files, resolve_secret
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.refseq")

REFSEQ_EMAIL_ENV_VARS = (
    "BIOSEQ_DL_REFSEQ_EMAIL",
    "NCBI_EMAIL",
    "ENTREZ_EMAIL",
)


class RefSeqInterface(BaseAPIInterface):
    API_NAME = "RefSeq"
    DB_CONFIG = REFSEQ
    METHODS = {
        "protein": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "id": (str, None, True),
            },
            "group_queries": [None],
            "separator": None,
        },
        "gene": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "id": (str, None, True),
            },
            "group_queries": [None],
            "separator": None,
        },
        "popset": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "id": (str, None, True),
            },
            "group_queries": [None],
            "separator": None,
        },
    }

    def __init__(
        self, email: str = "", cache_dir: str | None = None, config_dir: str | None = None, **kwargs: Any
    ) -> None:
        """Initialize the RefSeqInterface class.

        Args:
            email (str): Email address for NCBI Entrez.
            cache_dir (str): Directory to cache API responses. If None, defaults to the cache directory defined in constants.
            config_dir (str): Directory for configuration files. If None, defaults to the config directory defined in constants.
            output_dir (str): Directory to save downloaded files. If None, defaults to the cache directory.

        """
        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)

        load_environment_files(config_dir=self.config_dir)

        self.email = resolve_secret(email, REFSEQ_EMAIL_ENV_VARS)
        if is_valid_secret(self.email):
            Entrez.email = self.email

    def to_native(self, obj: Any) -> Any:
        """Convert EntrezDict to native Python types.

        Args:
            obj (EntrezDict): EntrezDict object to convert.

        Returns:
            dict: Converted object.

        """
        if isinstance(obj, DictionaryElement):
            return {k: self.to_native(v) for k, v in obj.items()}
        if isinstance(obj, ListElement):
            return [self.to_native(item) for item in obj]
        if isinstance(obj, StringElement):
            return str(obj)
        return obj

    def fetch(self, query: str | dict | list, *, method: str = "protein", **kwargs: Any) -> dict | list:
        """Fetch data from NCBI Entrez for a given ID.

        Args:
            id (str): ID to fetch data for.
            method (str): Database to query (default: "protein").
            retmode (str): Return mode (default: "xml").

        Returns:
            list: Fetched data.

        """
        retmode = kwargs.get("retmode", "xml")

        if not is_valid_secret(self.email):
            msg = "Missing RefSeq email. Set BIOSEQ_DL_REFSEQ_EMAIL or pass email explicitly."
            raise ValueError(msg)

        Entrez.email = self.email

        if method not in databases:
            log.error(f"Database '{method}' is not supported. Supported databases: {', '.join(databases)}")
            return {}

        ids = query.get("id") if isinstance(query, dict) else query

        handle = Entrez.efetch(db=method, id=ids, retmode=retmode)
        records = Entrez.read(handle)
        handle.close()

        return self.to_native(records)

    def parse(self, data: list | dict, fields_to_extract: list | dict | None, **kwargs: Any) -> list | dict:
        """Parse the fetched data into a DataFrame.

        Args:
            data (dict): Fetched data from NCBI Entrez.

        Returns:
            dict: Parsed data.

        """
        # Check input data type
        if not isinstance(data, (list, dict)):
            log.error(
                "Tried to parse data but the type is not supported. Data should be a list or a dictionary."
            )
            return {}

        return self._extract_fields(data, fields_to_extract)

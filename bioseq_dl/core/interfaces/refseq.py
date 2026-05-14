import os, logging
from typing import Optional, Union, Any, List, Dict
from Bio import Entrez, SeqIO
from Bio.Entrez.Parser import ListElement, DictionaryElement, StringElement

from .base import BaseAPIInterface
from ...constants.databases import REFSEQ
from ..utils.base_auxiliary_methods import get_nested
from ...constants.refseq import databases
from bioseq_dl.core.interfacesconfig import ConfigLoader

from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.interfaces.refseq")

class RefSeqInterface(BaseAPIInterface):
    API_NAME = "RefSeq"
    METHODS = {
        "protein": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "id": (str, None, True),
            },
            "group_queries": [None],
            "separator": None
        },
        "gene": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "id": (str, None, True),
            },
            "group_queries": [None],
            "separator": None
        },
        "popset": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "id": (str, None, True),
            },
            "group_queries": [None],
            "separator": None
        }
    }

    def __init__(
            self,
            email: str = "",
            cache_dir: Optional[str] = None,
            config_dir: Optional[str] = None,
            **kwargs
    ):
        """
        Initialize the RefSeqInterface class.
        Args:
            email (str): Email address for NCBI Entrez.
            cache_dir (str): Directory to cache API responses. If None, defaults to the cache directory defined in constants.
            config_dir (str): Directory for configuration files. If None, defaults to the config directory defined in constants.
            output_dir (str): Directory to save downloaded files. If None, defaults to the cache directory.
        """
        if cache_dir:
            cache_dir = os.path.abspath(cache_dir)
        else:
            cache_dir = REFSEQ.CACHE_DIR if REFSEQ.CACHE_DIR is not None else ""
        
        if config_dir is None:
            config_dir = REFSEQ.CONFIG_DIR if REFSEQ.CONFIG_DIR is not None else ""

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)

        config = ConfigLoader(config_dir=self.config_dir)
        config.load_config("init")

        # Set Entrez email
        Entrez.email = email or config.get_parameter("email")

    def to_native(self, obj):
        """
        Convert EntrezDict to native Python types.
        Args:
            obj (EntrezDict): EntrezDict object to convert.
        Returns:
            dict: Converted object.
        """
        if isinstance(obj, DictionaryElement):
            return {k: self.to_native(v) for k, v in obj.items()}
        elif isinstance(obj, ListElement):
            return [self.to_native(item) for item in obj]
        elif isinstance(obj, StringElement):
            return str(obj)
        else:
            return obj

    def fetch(self, query: Union[str, dict, list], *, method: str = "protein",**kwargs):
        """
        Fetch data from NCBI Entrez for a given ID.
        Args:
            id (str): ID to fetch data for.
            method (str): Database to query (default: "protein").
            retmode (str): Return mode (default: "xml").
        Returns:
            list: Fetched data.
        """
        retmode = kwargs.get('retmode', 'xml')

        if method not in databases:
            log.error(f"Database '{method}' is not supported. Supported databases: {', '.join(databases)}")
            return {}


        ids = query.get("id") if isinstance(query, dict) else query

        handle = Entrez.efetch(db=method, id=ids, retmode=retmode)
        records = Entrez.read(handle)
        handle.close()

        return self.to_native(records)

    
    def parse(
            self, 
            data: Union[List, Dict],
            fields_to_extract: Optional[Union[list, dict]],
            **kwargs
        ) -> Union[List, Dict]:
        """
        Parse the fetched data into a DataFrame.
        Args:
            data (dict): Fetched data from NCBI Entrez.
        Returns:
            dict: Parsed data.
        """
        # Check input data type
        if not isinstance(data, (List, Dict)):
            log.error("Tried to parse data but the type is not supported. Data should be a list or a dictionary.")
            return {}

        return self._extract_fields(data, fields_to_extract)
    
    def query_usage(self) -> str:
        return (
            "RefSeq Interface allows you to fetch and parse data from the NCBI RefSeq database. "
            "You can specify fields to extract from the fetched records, and it supports both single "
            "and batch queries. The results can be saved in a specified output directory."
            "Example usage:\n"
            "refseq_instance.fetch_single('NP_001301717')\n"
            "This will return the parsed data for the specified RefSeq ID."
        )
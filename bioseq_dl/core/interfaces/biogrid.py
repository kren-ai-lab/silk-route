"""BioGRID API interface."""

from typing import Any, ClassVar

import niquests

from bioseq_dl.constants.databases import BIOGRID
from bioseq_dl.core.credentials import is_valid_secret, load_environment_files, resolve_secret
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.biogrid")

BIOGRID_ENV_VARS = (
    "BIOSEQ_DL_BIOGRID_API_KEY",
    "BIOGRID_API_KEY",
    "biogrid_api_key",
)

# Rest documentation: https://wiki.thebiogrid.org/doku.php/biogridrest


class BioGRIDInterface(BaseAPIInterface):
    """BioGRID protein interaction database API interface."""

    API_NAME = "BioGRID"
    DB_CONFIG = BIOGRID
    METHODS: ClassVar[dict[str, Any]] = {
        "interactions": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "accessKey": (str, None, False),
                "id": (str, None, True),
                "start": (int, 0, True),
                "max": (int, 10000, True),
                "interSpeciesExclude": (bool, False, True),
                "selfInteractionsExclude": (bool, False, True),
                "evidenceList": (str, None, True),
                "includeEvidence": (bool, False, True),
                "geneList": (str, None, True),
                "searchBiogridIds": (bool, False, False),
                "taxId": (str, "All", True),
                "searchIds": (bool, False, False),
                "format": (str, "json", False),
            },
            "group_queries": ["geneList"],
            "separator": "|",
        }
    }

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: str | None = None,
        config_dir: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the BioGRIDInterface class.

        Args:
            api_key (str | None): BioGRID API key. Falls back to environment variable.
            cache_dir (str | None): Directory to cache results.
            config_dir (str | None): Directory for configuration files.
            **kwargs: Passed through to the base class.

        """
        cache_dir, config_dir = self._resolve_dirs(cache_dir, config_dir)
        load_environment_files(config_dir=config_dir)

        self.api_key = resolve_secret(api_key, BIOGRID_ENV_VARS)

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)

    # Critiacl to ignore the accessKey when caching
    def get_cache_ignore_keys(self) -> set[str]:
        """Get the keys to ignore when caching.

        Returns:
            set[str]: Set of keys to ignore (adds ``accessKey`` to the base set).

        """
        return super().get_cache_ignore_keys().union({"accessKey"})

    def fetch(self, query: str | dict | list, *, method: str = "interactions", **kwargs: Any) -> dict | list:
        """Fetch data from the BioGRID API.

        Resolves the API key (from the query, instance, or environment) and raises if
        none is available. For the ``interactions`` method, an id-keyed dict response is
        normalized into a list of interactions.

        Args:
            query (str | dict | list): Identifier(s) or structured query to fetch.
            method (str): Method to use for the request.
            **kwargs: Additional parameters passed to the request.

        Returns:
            dict | list: Response from the API.

        Raises:
            ValueError: If no valid BioGRID API key is available.

        """
        if isinstance(query, dict):
            access_key = query.get("accessKey")
            if not is_valid_secret(access_key) and is_valid_secret(self.api_key):
                query["accessKey"] = self.api_key
            if not is_valid_secret(query.get("accessKey")):
                msg = "Missing BioGRID API key. Set BIOSEQ_DL_BIOGRID_API_KEY or pass api_key explicitly."
                raise ValueError(msg)
        elif not is_valid_secret(self.api_key):
            msg = "Missing BioGRID API key. Set BIOSEQ_DL_BIOGRID_API_KEY or pass api_key explicitly."
            raise ValueError(msg)

        response = super()._do_request(query, method=method, api_url=BIOGRID.API_URL, **kwargs)
        response = response.json() if isinstance(response, niquests.models.Response) else response
        match method:
            case "interactions":
                # Special case for BioGRID
                if isinstance(response, dict) and all(str(key).isdigit() for key in response):
                    # Convert to list of interactions
                    response = list(response.values())
            case _:
                log.warning("Method %s not recognized for special parsing. Returning raw response.", method)

        return response

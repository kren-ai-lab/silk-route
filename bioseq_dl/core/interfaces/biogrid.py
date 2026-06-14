from typing import Any

import requests

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


# TODO add more from docs
# TODO ISSUES:
# For some reason, running this query:
# query={
#     "accessKey": biogrid_api_key,
#     "geneList": ['1148170', '1148186', '112090'],
#     "searchBiogridIds" : True,
#     "format": "tab2"
# },
# gives an error:
# Error fetching data for {...}: Extra data: line 1 column 8 (char 7). Tried URL: https://webservice.thebiogrid.org/interactions?accessKey={ACCESS_KEY}&geneList=1148170|1148186|112090&searchBiogridIds=True&format=tab2
# This error will go to a low priority issue, as it is not as used as the JSON format.
class BioGRIDInterface(BaseAPIInterface):
    API_NAME = "BioGRID"
    DB_CONFIG = BIOGRID
    METHODS = {
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
        **kwargs,
    ):
        """Initialize the BioGRIDInterface class.

        Args:
            cache_dir (str): Directory to cache results.
            config_dir (str): Directory for configuration files.
            output_dir (str): Directory to save output files.

        """
        cache_dir, config_dir = self._resolve_dirs(cache_dir, config_dir)
        load_environment_files(config_dir=config_dir)

        self.api_key = resolve_secret(api_key, BIOGRID_ENV_VARS)

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)

    # Critiacl to ignore the accessKey when caching
    def get_cache_ignore_keys(self) -> set[str]:
        """Get the keys to ignore when caching.

        Returns:
            Set[str]: Set of keys to ignore.

        """
        return super().get_cache_ignore_keys().union({"accessKey"})

    def fetch(self, query: str | dict | list, *, method: str = "interactions", **kwargs):
        """Fetch data from the BioGRID API.

        Args:
            query (str): Query string to search for.
            **kwargs: Additional parameters for the request.
            - `method`: Method to use for the request. Default is "interactions".

        Returns:
            any: response from the API.

        """
        if isinstance(query, dict):
            access_key = query.get("accessKey")
            if not is_valid_secret(access_key) and is_valid_secret(self.api_key):
                query["accessKey"] = self.api_key
            if not is_valid_secret(query.get("accessKey")):
                raise ValueError(
                    "Missing BioGRID API key. Set BIOSEQ_DL_BIOGRID_API_KEY or pass api_key explicitly."
                )
        elif not is_valid_secret(self.api_key):
            raise ValueError(
                "Missing BioGRID API key. Set BIOSEQ_DL_BIOGRID_API_KEY or pass api_key explicitly."
            )

        response = super()._do_request(query, method=method, api_url=BIOGRID.API_URL, **kwargs)
        response = response.json() if isinstance(response, requests.models.Response) else response
        match method:
            case "interactions":
                # Special case for BioGRID
                if isinstance(response, dict) and all(str(key).isdigit() for key in response.keys()):
                    # Convert to list of interactions
                    response = list(response.values())
            case _:
                log.warning(f"Method {method} not recognized for special parsing. Returning raw response.")

        return response

    def parse(self, data: Any, fields_to_extract: list | dict | None, **kwargs) -> dict | list:
        """Parse the response from the BioGRID API.

        Args:
            data (dict): The fetched data.
            fields_to_extract (List|Dict): Fields to keep from the original response.
                - If List: Keep those keys.
                - If Dict: Maps {desired_name: real_field_name}.

        Returns:
            any: Parsed data from the response.

        """
        if not data:
            log.warning("Tried to parse data but the data is empty or None.")
            return {}

        if isinstance(data, requests.models.Response):
            data = data.json()
        elif not isinstance(data, (dict, list)):
            log.error(
                "Tried to parse data but the type is not supported. Response should be a dict or a requests.Response object."
            )
            return {}

        return self._extract_fields(data, fields_to_extract)

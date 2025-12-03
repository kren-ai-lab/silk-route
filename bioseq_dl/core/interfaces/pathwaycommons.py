import os
import json
import logging
from typing import Union, List, Dict, Optional
from requests import Request, Response
from requests.exceptions import RequestException

import pandas as pd

from .base import BaseAPIInterface
# Add the import for your database in constants
from ...constants.databases import PATHWAYCOMMONS
from ..utils.base_auxiliary_methods import validate_parameters
from ...constants.pathwaycommons import OUTPUT_FORMATS, PATTERNS

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

log = get_logger("bioseq_dl.interfaces.pathwaycommons")
# -------------------------------------------------


class PathwayCommonsInterface(BaseAPIInterface):
    API_NAME = "PathwayCommons"
    METHODS = {
        "fetch": {
            "http_method": "POST",
            "path_param": None,
            "parameters": {
                "uri": (list, None, True),
                "format": (str, "jsonld", True),
                "pattern": (list, ["interacts-with"], True),
                "subpw": (bool, False, True),
            },
            "group_queries": [None],
            "separator": None
        },
        "top_pathways": {
            "http_method": "POST",
            "path_param": None,
            "parameters": {
                "q": (str, None, True),
                "organism": (list, None, True),
                "datasource": (list, None, True),
            },
            "group_queries": [None],
            "separator": None
        },
        "neighborhood": {
            "http_method": "POST",
            "path_param": None,
            "parameters": {
                "source": (list, None, True),
                "limit": (int, 1, True),
                "format": (str, "jsonld", True),
                "organism": (list, None, True),
                "datasource": (list, None, True),
                "pattern": (list, ["interacts-with"], True),
                "subpw": (bool, False, True),
                "direction": (str, "undirected", True),
            },
            "group_queries": [None],
            "separator": None
        }
    }

    def __init__(
            self,  
            cache_dir: Optional[str] = None,
            config_dir: Optional[str] = None,
            **kwargs
        ):

        if cache_dir:
            cache_dir = os.path.abspath(cache_dir)
        else:
            cache_dir = PATHWAYCOMMONS.CACHE_DIR if PATHWAYCOMMONS.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = PATHWAYCOMMONS.CONFIG_DIR if PATHWAYCOMMONS.CONFIG_DIR is not None else ""

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)

    def fetch(
            self, 
            query: Union[str, dict, list], 
            *, 
            method: str = "SOME_DEFAULT", 
            **kwargs
        ):
        if method not in self.METHODS:
            log.error(f"Method {method} is not supported. Available methods: {list(self.METHODS.keys())}")
            return {}
        if method == "fetch" and "uri" not in query:
            log.error("The 'uri' parameter is required for the 'fetch' method.")
            return {}
        elif method == "top_pathways" and "q" not in query:
            log.error("The 'q' parameter is required for the 'top_pathways' method.")
            return {}
        elif method == "neighborhood" and "source" not in query:
            log.error("The 'source' parameter is required for the 'neighborhood' method.")
            return {}

        http_method, path_param, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError as e:
            log.error(f"Invalid parameters for method '{method}': {e}")
            return {}
        
        if "format" in validated_params and validated_params["format"] not in OUTPUT_FORMATS:
            log.error(f"Invalid format '{validated_params['format']}'. Allowed formats: {OUTPUT_FORMATS}")
            return {}
        if "pattern" in validated_params and any(p not in PATTERNS for p in validated_params["pattern"]):
            log.error(f"Invalid pattern '{validated_params['pattern']}'. Allowed patterns: {PATTERNS}")
            return {}

        url = f"{PATHWAYCOMMONS.API_URL}{method}"

        headers = {
            "accept": "*/*",
            "Content-Type": "application/json"
        }
 
        response = Request(
            url=url,
            headers=headers,
            method=http_method,
            data=json.dumps(validated_params),
        )

        prepared = self.session.prepare_request(response)
        log.debug(f"Prepared request: {prepared.url}")

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()
            if response.content == b"":
                return {}
            response = response.json()
            if "searchHit" in response.keys():
                response = response["searchHit"]
            elif "@graph" in response.keys():
                response = response["@graph"]
            else:
                response = response

            return response
        except RequestException as e:
            log.error(f"Error fetching data from {url}: {e}")
            return {}



    def parse(
            self, 
            data: Union[List, Dict],
            fields_to_extract: Optional[Union[list, dict]],
            **kwargs
        ) -> Union[List, Dict]:
        if not data:
            return {}

        if isinstance(data, Response):
            data = data.json()
        elif isinstance(data, dict):
            data = data
        else:
            log.error("Tried to parse data but the type is not supported. Response should be a dict or a requests.Response object.")
            return {}

        return self._extract_fields(data, fields_to_extract, **kwargs)

    def get_dummy(self, **kwargs) -> Dict:
        return {
            "message": "This is a dummy response.",
            "status": "success"
        }
    
    def query_usage(self) -> str:
        return """
        This is a dummy query usage for YourDatabaseInterface.
        """
    
import os, json, logging
from requests import Request
from requests.exceptions import RequestException
from requests.models import Response
from urllib.parse import quote

from typing import Union, List, Dict, Set, Optional

import pandas as pd

from .base import BaseAPIInterface
from ...constants.databases import CHEBI
from ..utils.base_auxiliary_methods import validate_parameters

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

log = get_logger("bioseq_dl.interfaces.chebi")
# -------------------------------------------------

# Definition of methods for ChEBI API
# Each paramether is a tuple with (type, default_value, primary_key)

class ChEBIInterface(BaseAPIInterface):
    API_NAME = "ChEBI"
    METHODS = {
        "compound": {
            "http_method": "GET",
            "path_param": "chebi_id",
            "parameters": {
                "chebi_id": (str, None, True),
                "only_ontology_parents": (bool, False, False),
                "only_ontology_children": (bool, False, False)
            },
            "group_queries": [None],
            "separator": None
        },
        "compounds": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "chebi_ids": (list, None, True),
            },
            "group_queries": [None],
            "separator": ","
        },
        "es_search": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "term": (str, None, True),
                "page": (int, 1, False),
                "size": (int, 15, False),
            },
            "group_queries": [None],
            "separator": None
        },
        "ontology-children": {
            "http_method": "GET",
            "path_param": "chebi_id",
            "parameters": {
                "chebi_id": (str, None, True),
            },
            "group_queries": [None],
            "separator": None
        },
        "ontology-parents": {
            "http_method": "GET",
            "path_param": "chebi_id",
            "parameters": {
                "chebi_id": (str, None, True),
            },
            "group_queries": [None],
            "separator": None
        },
        # Not implemented yet, requires pagination handling
        # "structure_search": {
        #     "http_method": "GET",
        #     "path_param": None,
        #     "parameters": {
        #         "smiles": (str, None, True),
        #         "search_type": (str, "connectivity", False),
        #         "similarity": (float, 0.7, False),
        #         "three_star_only": (bool, True, False),
        #         "page": (int, 1, False),
        #         "size": (int, 15, False),
        #         "download": (bool, False, False)
        #     }
        # }
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
            cache_dir = CHEBI.CACHE_DIR if CHEBI.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = CHEBI.CONFIG_DIR if CHEBI.CONFIG_DIR is not None else ""

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)

    def fetch(
            self, 
            query: Union[str, dict, list], 
            *, 
            method: str = "compound", 
            **kwargs
        ):
        if method not in self.METHODS.keys():
            log.error(f"Method {method} is not supported. Available methods: {list(self.METHODS.keys())}")
            return {}

        http_method, path_param, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        try:
            validated_params = validate_parameters(inputs, parameters)
        except (ValueError, TypeError) as e:
            log.error(f"Parameter validation failed: {e}")
            return {}

        # Get ids if available
        chebi_ids = []
        id_key = next((k for k in ("chebi_id", "chebi_ids") if k in validated_params), None)

        if id_key:
            chebi_ids = validated_params.pop(id_key)
            if isinstance(chebi_ids, str):
                chebi_ids = [chebi_ids]
            elif not isinstance(chebi_ids, list):
                log.error(f"Expected '{id_key}' to be str or list, got {type(chebi_ids)}")
                return {}

            validated_params[id_key] = ",".join(id for id in chebi_ids)
        

        # Make URL
        url = f"{CHEBI.API_URL}{method.replace('-', '/')}/"
        if path_param and path_param in validated_params:
            path_value = validated_params.pop(path_param)
            if path_param == "chebi_id":
                path_value = quote(path_value, safe="")
            url += f"{path_value}"
        
        req = Request(http_method, url, params=validated_params)
        prepared = self.session.prepare_request(req)

        log.debug(f"Prepared url: {prepared.url}")
        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()
            try:
                response = json.loads(response.text)
            except json.JSONDecodeError:
                log.error(f"Failed to decode JSON response for method '{method}' with query '{query}'. Response text: {response.text}")
                return {}

            # If the keys are the same of the query, return the response directly
            if isinstance(response, dict) and set(response.keys()) <= set(chebi_ids):
                # Convert to list of interactions
                response = list(response.values())

            if isinstance(response, dict) and "results" in response.keys():
                response = response["results"]

            return response
        except RequestException as e:
            log.error(f"Error fetching {query} for method '{method}': {e}")
            return {}
        
    def parse(
            self, 
            data: Union[List, Dict],
            fields_to_extract: Optional[Union[list, dict]],
            **kwargs
        ) -> Union[List, Dict]:
        if not data:
            log.warning("Tried to parse data but the data is empty or None.")
            return {}

        if isinstance(data, Response):
            data = data.json()
        elif isinstance(data, dict):
            data = data
        else:
            log.error("Tried to parse data but the type is not supported. Response should be a dict or a requests.Response object.")
            return {}
        
        return self._extract_fields(data, fields_to_extract)
    
    def get_dummy(self, **kwargs) -> Dict:
        return {
            "message": "This is a dummy response.",
            "status": "success"
        }
    
    def query_usage(self) -> str:
        return "Query usage information for ChEBI API"

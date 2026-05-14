import os, logging
from typing import Union, List, Dict, Set, Optional
from requests import Request
from requests.exceptions import RequestException
from requests.models import Response

import pandas as pd

from .base import BaseAPIInterface
# Add the import for your database in constants
from ...constants.databases import PANTHER
from ..utils.base_auxiliary_methods import validate_parameters

from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.interfaces.panther")

class PantherInterface(BaseAPIInterface):
    API_NAME = "PANTHER"
    # Definition of methods for PANTHER API
    # Each parameter is a tuple with (type, default_value, primary_key)
    METHODS = {
        "geneinfo": {
            "http_method": "POST",
            "path_param": None,
            "parameters": {
                "geneInputList": (str, None, True),
                "organism": (str, None, True),
            },
            "group_queries": ["geneInputList"],
            "separator": ","
        },
        "familyortholog": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "family": (str, None, True),
                "taxonFltr": (str, None, False) 
            },
            "group_queries": ["taxonFltr"],
            "separator": ","
        },
        "familymsa": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "family": (str, None, True),
                "taxonFltr": (str, None, False)
            },
            "group_queries": ["taxonFltr"],
            "separator": ","
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
            cache_dir = PANTHER.CACHE_DIR if PANTHER.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = PANTHER.CONFIG_DIR if PANTHER.CONFIG_DIR is not None else ""

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)

    def fetch(
            self, 
            query: Union[str, dict, list], 
            *, 
            method: str = "geneinfo", 
            **kwargs
        ):
        http_method, path_param, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError as e:
            log.error(f"Invalid parameters for method '{method}': {e}")
            return {}
        
        url = f"{PANTHER.API_URL}{method}"

        if path_param:
            path_value = validated_params.pop(path_param)
            url += f"{path_value}"
        
        req = Request(
            method=http_method,
            url=url,
            params=validated_params
        )
        prepared = self.session.prepare_request(req)
        log.debug(f"Prepared request: {prepared.url}")

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()

            match method:
                case "geneinfo":
                    response = response.json()
                    response = response.get("search", {}).get("mapped_genes", {}).get("gene", [])
                case "familyortholog":
                    response = response.json()
                    response = response.get("search", {}).get("ortholog_list", {}).get("ortholog", [])
                case "familymsa":
                    response = response.json()
                    response = response.get("search", {}).get("MSA_list", {}).get("sequence_info", [])
                case _:
                    response = response.json()

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
        return """
        This is a dummy query usage for PantherInterface.
        """
    

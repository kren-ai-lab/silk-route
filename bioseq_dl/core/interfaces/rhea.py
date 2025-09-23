import os
import html

from typing import Union, List, Dict, Set, Optional
from requests import Request
from requests.exceptions import RequestException
from requests.models import Response
from bs4 import BeautifulSoup

import pandas as pd

from .base import BaseAPIInterface
# Add the import for your database in constants
from ...constants.databases import RHEA
from ..utils.base_auxiliary_methods import validate_parameters, get_primary_keys


class RheaInterface(BaseAPIInterface):
    METHODS = {
        "rhea": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "query": (str, None, True),
                "columns": (str, "rhea-id,equation,chebi,chebi-id,ec,uniprot,go", False),
                "format": (str, "json", False),
                "limit": (int, 100, False),
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
            cache_dir = RHEA.CACHE_DIR if RHEA.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = RHEA.CONFIG_DIR if RHEA.CONFIG_DIR is not None else ""

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)

    def fetch(
            self, 
            query: Union[str, dict, list], 
            *, 
            method: str = "rhea", 
            **kwargs
        ):
        if method not in self.METHODS.keys():
            raise ValueError(f"Method '{method}' is not supported. Available methods: {list(self.METHODS.keys())}")

        http_method, path_param, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError as e:
            raise ValueError(f"Invalid parameters for method '{method}': {e}")
        
        url = f"{RHEA.API_URL}{method}/"
        if path_param:
            path_value = validated_params.pop(path_param)
            url += f"{path_value}"
        
        req = Request(
            method=http_method,
            url=url,
            params=validated_params
        )
        prepared = self.session.prepare_request(req)
        print(f"Prepared request: {prepared.url}")

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()
            response = response.json()

            if "results" in response:
                response = response["results"]  

            return response
        except RequestException as e:
            print(f"Error fetching prediction for {query}: {e}")
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
        elif isinstance(data, (dict, list)):
            data = data
        else:
            raise ValueError("Response must be a requests.Response object or a dictionary.")

        return self._extract_fields(data, fields_to_extract, **kwargs)
    
    def get_dummy(self, **kwargs) -> Dict:
        return {
            "message": "This is a dummy response.",
            "status": "success"
        }
    
    def query_usage(self) -> str:
        return """
        This is a dummy query usage for the RheaInterface.
        """    
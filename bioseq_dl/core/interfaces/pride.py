import os

from typing import Union, List, Dict, Set, Optional
from requests import Request, Response
from requests.exceptions import RequestException

import pandas as pd

from .base import BaseAPIInterface
# Add the import for your database in constants
from ...constants.databases import PRIDE
from ..utils.base_auxiliary_methods import validate_parameters

class PrideInterface(BaseAPIInterface):
    METHODS = {
        "search": {
            "projects": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "keyword": (str, None, True),
                    "filter": (str, None, True),
                    "page": (int, 0, True),
                    "dateGap": (str, None, True),
                    "sortDirection": (str, "DESC", False),
                    "sortFields": (str, "submissionDate", False)
                },
                "group_queries": [None],
                "separator": None
            },

        },
        "projects": {
            "default": {
                "http_method": "GET",
                "path_param": ["projectAccession"],
                "parameters": {
                    "projectAccession": (str, None, True),
                },
                "group_queries": [None],
                "separator": None
            },
            "similarProjects": {
                "http_method": "GET",
                "path_param": ["accession"],
                "parameters": {
                    "accession": (str, None, True),
                    "page": (int, 0, True),
                    "pageSize": (int, 10, True)
                },
                "group_queries": [None],
                "separator": None
            }
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
            cache_dir = PRIDE.CACHE_DIR if PRIDE.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = PRIDE.CONFIG_DIR if PRIDE.CONFIG_DIR is not None else ""

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)

    def fetch(
            self, 
            query: Union[str, dict, list], 
            *, 
            method: str = "search", 
            **kwargs
        ):
        if method not in self.METHODS.keys():
            raise ValueError(f"Method '{method}' is not defined in the interface.")
        option = kwargs.pop("option", "default")
        
        http_method, path_param, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, option=option, **kwargs)

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError as e:
            raise ValueError(f"Invalid parameters for method '{method}': {e}")

        url = f"{PRIDE.API_URL}{method.replace('-', '/')}"

        if path_param:
            if isinstance(path_param, list):
                url += "/" + "/".join(str(validated_params.pop(param)) for param in path_param if param in validated_params)
            else:
                url += f"/{validated_params.pop(path_param)}"
 
        if option and option != "default":
            url += f"/{option}"

        response = Request(
            url=url,
            method=http_method,
            params=validated_params,
        )

        prepared = self.session.prepare_request(response)
        print(f"Prepared request: {prepared.url}")

        print(f"Fetching data with parameters: {validated_params}")

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()

            return response.json()
        except RequestException as e:
            raise RequestException(f"Error fetching data from {url}: {e}")
        
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
            raise ValueError("Response must be a requests.Response object or a dictionary.")

        return self._extract_fields(data, fields_to_extract, **kwargs)

    def fetch_single(self, query: Union[str, dict], parse: bool = False, *args, **kwargs) -> Union[List, Dict, pd.DataFrame]:
        option = kwargs.pop("option", "default")
        return super().fetch_single(query=query, parse=parse, option=option, *args, **kwargs)
    
    def get_dummy(self, **kwargs) -> Dict:
        return {
            "message": "This is a dummy response.",
            "status": "success"
        }
    
    def query_usage(self) -> str:
        return """
        This is a dummy query usage for YourDatabaseInterface.
        """
    
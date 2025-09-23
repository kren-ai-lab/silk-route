import os
import requests
from typing import Optional, Union, Any, Dict, List

from .base import BaseAPIInterface
from ...constants.databases import REACTOME
from ...constants.reactome import methods

# TODO - Need to review other methods besides data-discover

class ReactomeInterface(BaseAPIInterface):
    METHODS = {
        "data-discover": {
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
            cache_dir: Optional[str] = None,
            config_dir: Optional[str] = None,
            **kwargs
        ):
        """
        Initialize the ReactomeInstance.
        Args:
            cache_dir (str): Directory to cache API responses. If None, defaults to the cache directory defined in constants.
            config_dir (str): Directory for configuration files. If None, defaults to the config directory defined in constants.
            output_dir (str): Directory to save downloaded files. If None, defaults to the cache directory.
        """
        if cache_dir:
            cache_dir = os.path.abspath(cache_dir)
        else:
            cache_dir = REACTOME.CACHE_DIR if REACTOME.CACHE_DIR is not None else ""
        
        if config_dir is None:
            config_dir = REACTOME.CONFIG_DIR if REACTOME.CONFIG_DIR is not None else ""
        
        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)
    
    def validate_query(self, query: Dict):
        """
        Validate the query parameters.
        Args:
            method (str): The method to validate against.
            query (dict): The query parameters to validate.
        Raises:
            ValueError: If the query parameters are invalid.
        """
        rules = {
            'id': lambda v: isinstance(v, str) and v.strip() != "",
            'species': lambda v: isinstance(v, str) and v.strip() != "",
            'onlyDiagrammed': lambda v: isinstance(v, bool),
        }

        for key, check in rules.items():
            if key in query and not check(query[key]):
                if key == 'id':
                    raise ValueError(f"Invalid ID: {query['id']}. It should be a non-empty string.")
                elif key == 'species':
                    raise ValueError(f"Invalid species: {query['species']}. It should be a non-empty string.")
                elif key == 'onlyDiagrammed':
                    raise ValueError(f"Invalid onlyDiagrammed: {query['onlyDiagrammed']}. It should be a boolean value.")

    def fetch(self, query: Union[str, dict, list], *, method: str = "data", **kwargs):
        """
        Download pathways from a given Reactome pathway ID.
        Args:
            pathway_id (str): Reactome pathway ID.
            method (str): Method to use for fetching data (e.g., 'discover', 'complex', etc.).
        kwargs:
            option (str): Additional options for the method.
        Returns:
            dict: Pathway data.
        """
        option = kwargs.get("option", "")
  
        if not method:
            raise ValueError("Method must be specified in the query parameters.")
        
        if option and not isinstance(option, str):
            raise ValueError("Option must be a string if provided.")
        
        primary_method = method.split("-")[0]
        secondary_method = "/".join(method.split("-")[1:])
        if primary_method not in methods.keys():
            raise ValueError(f"Method '{primary_method}' is not supported. Supported methods are: {list(methods.keys())}")
        if secondary_method not in methods[primary_method]:
            raise ValueError(f"Method '{secondary_method}' is not supported. Supported methods are: {methods[primary_method]}")

        q = ""
        if isinstance(query, str):
            q = query.strip()
        if isinstance(query, dict):
            self.validate_query(query)
            q = query.get("id", "").strip()
        
        url = f"{REACTOME.API_URL}{method.replace('-', '/')}/{q}/{option}"

        if isinstance(query, dict):
            url += "?"
            for key, value in query.items():
                if key != "id":
                    url += f"{key}={value}&"
            url = url.rstrip("&")

        try:
            response = self.session.get(url)
            self._delay()
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching prediction for {query}: {e}")
            return {}
        
    
    def parse(
            self, 
            data: Union[List, Dict],
            fields_to_extract: Optional[Union[list, dict]],
            **kwargs
        ) -> Union[List, Dict]:
        """
        Parse the pathway data.
        Args:
            data (Union[List, Dict]): Data to parse.
            fields_to_extract (list|dict): Fields to keep from the original response.
                - If list: Keep those keys.
                - If dict: Maps {desired_name: real_field_name}.
        Returns:
            Union[List, Dict]: Parsed data with specified fields or the entire structure.
        """
        # Check input data type
        if not isinstance(data, (List, Dict)):
            raise ValueError("Data must be a list or a dictionary.")
        
        return self._extract_fields(
            data, 
            fields_to_extract
        )
        
    
    def query_usage(self) -> str:
        return (
            "To query Reactome, use the pathway ID as a string. "
            "Example usage:\n"
            "reactome_instance.fetch('R-HSA-123456')\n"
            "This will return the pathway data for the specified Reactome pathway ID."
        )
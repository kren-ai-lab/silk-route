import os, re, logging
from typing import Optional, Union, Dict, List, Any
import requests

from .base import BaseAPIInterface
from ...constants.databases import CHEMBL
from ..utils.base_auxiliary_methods import validate_parameters

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

log = get_logger("bioseq_dl.interfaces.chembl")
# -------------------------------------------------

# For the moment, only activity is necessary, but more methods can be added later.
class ChEMBLInterface(BaseAPIInterface):
    METHODS = {
        "activity": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "target_chembl_id": (str, None, True),
                "pchembl_value": (float, None, False),
                "format": (str, "json", False),
            },
            "group_queries": [None],
            "separator": None
        },
        "binding_site": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "target_chembl_id": (str, None, True),
                "format": (str, "json", False),
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
        Initialize the ChEMBLInterface class.
        Args:
            cache_dir (str): Directory to cache results.
            config_dir (str): Directory for configuration files.
            output_dir (str): Directory to save output files.
        """
        if cache_dir:
            cache_dir = os.path.abspath(cache_dir)
        else:
            cache_dir = CHEMBL.CACHE_DIR if CHEMBL.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = CHEMBL.CONFIG_DIR if CHEMBL.CONFIG_DIR is not None else ""

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)

    # DEPRECATED - Use validate_parameters instead
    def validate_query(self, method: str, query: Dict):
        """
        Validate the query parameters.
        Args:
            method (str): The method to validate against.
            query (dict): The query parameters to validate.
        Raises:
            ValueError: If the query parameters are invalid.
        """
        # TODO - Add more validation rules based on the method and query structure.
        rules = {
            'target_chembl_id': lambda v: isinstance(v, str) and v.strip() != "",
            'pchembl_value': lambda v: isinstance(v, (int, float)),
        }

        for key, check in rules.items():
            if key in query and not check(query[key]):
                if key == 'target_chembl_id':
                    log.error(f"Invalid target_chembl_id: {query['target_chembl_id']}. It should be a non-empty string.")
                    return {}
                elif key == 'pchembl_value':
                    log.error(f"Invalid pchembl_value: {query['pchembl_value']}. It should be a number (int or float).")
                    return {}

    def fetch_pages(self, next_url: str, method: str, pages_to_fetch: int = 1):
        """
        Fetch the next page of results from the ChEMBL API.
        Args:
            next_url (str): The URL for the next page of results.
            method (str): The method used for the initial request.
        Returns:
            dict: The fetched data from the next page.
        """
        log.debug(f"Fetching page: {next_url} for method {method} with pages_to_fetch={pages_to_fetch}")
        responses = []
        try:
            response = self.session.get(next_url, headers={"Content-Type": "application/json"})
            self._delay()
            response.raise_for_status() 
            
            if response.status_code == 204:
                log.warning(f"No content returned for URL {next_url}.")
                return {}

            data = response.json()

            if 'activities' in data.keys() and isinstance(data['activities'], list):
                responses.extend(data['activities'])
            elif 'binding_sites' in data.keys() and isinstance(data['binding_sites'], list):
                responses.extend(data['binding_sites'])
            else:
                responses.append(data)

            next = None
            if 'page_meta' in data and data['page_meta'].get('next'):
                next = self.fetch_pages(
                    "https://www.ebi.ac.uk" + data['page_meta']['next'],
                    method,
                    pages_to_fetch - 1
                ) if pages_to_fetch > 1 else None
                if next:
                    responses.extend(next)

            return responses
        except requests.exceptions.RequestException as e:
            
            log.error(f"Error fetching next page for method {method}: {e}")
            return {}
    
    def fetch(self, query: Union[str, dict, list], *, method: str = "activity", **kwargs):
        """
        Fetch data from the ChEMBL API.
        Args:
            query (str): Query string to search for.
            **kwargs: Additional parameters for the request.
            - `method`: Method to use for the request. Default is "compound".
        Returns:
            any: response from the API.
        """
        pages_to_fetch = kwargs.get("pages_to_fetch", 1)
        
        # Validate method and format
        if method not in self.METHODS.keys():
            log.error(f"Method {method} is not supported. Supported methods are: {', '.join(self.METHODS.keys())}.")
            return {}

        if not isinstance(query, (str, dict)):
            log.error("Query must be a string or a dictionary.")
            return {}
        
        _, _, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError as e:
            log.error(f"Invalid parameters for method '{method}': {e}")
            return {}

        # Convert dictionary to a query string
        query = "&".join(f"{key}={value}" for key, value in validated_params.items())

        # Generate url
        url = f"{CHEMBL.API_URL}{method}?{query}"

        return self.fetch_pages(url, method, pages_to_fetch)

    def parse(
            self,
            data: Any,
            fields_to_extract: Optional[Union[list, dict]],
            **kwargs
    ) -> Union[Dict, List]:
        """
        Parse the response from the ChEMBL API.
        Args:
            data (Any): Raw data from the API response.
            fields_to_extract (List|Dict): Fields to keep from the original response.
                - If List: Keep those keys.
                - If Dict: Maps {desired_name: real_field_name}.
        Returns:
            dict: Parsed response.
        """
        if not data:
            log.warning("Tried to parse data but the data is empty or None.")
            return {}

        if isinstance(data, requests.models.Response):
            data = data.json()
        elif isinstance(data, dict):
            data = data
        else:
            log.error("Tried to parse data but the type is not supported. Response should be a dict or a list.")
            return {}
        
        parsed = self._extract_fields(data, fields_to_extract)

        return parsed
    
    def query_usage(self) -> str:
        return (
            "ChEMBL API allows you to search for compounds, activities, and other chemical data.\n"
            "You can use methods like 'activity' and 'activity-search' to fetch data.\n"
            "For example, to search for activities, use:\n"
            "`fetch(query='CHEMBL1824', method='activity-search')`"
        )
    
    def get_dummy(self, *, method: Optional[str] = None, **kwargs) -> Dict:
        """Get dummy data for the ChEMBL API.
        Args:
            method (str): Method to use for the dummy data. Default is "activity-search".
        Returns:
            Dict: Dummy data with example fields.
        """
        query = {"target_chembl_id": "CHEMBL1824", "pchembl_value": 5.62}

        if method is None:
            method = "activity"
        if method not in self.METHODS.keys():
            log.error(f"Method {method} is not supported. Supported methods are: {', '.join(self.METHODS.keys())}.")
            return {}

        return super().get_dummy(
            query=query,
            method=method,
            **kwargs
        )

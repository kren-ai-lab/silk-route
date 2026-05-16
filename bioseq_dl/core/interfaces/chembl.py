import os, re, logging
from typing import Optional, Union, Dict, List, Any
import requests

from .base import BaseAPIInterface
from ...constants.databases import CHEMBL
from ..utils.base_auxiliary_methods import validate_parameters

from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.interfaces.chembl")

# For the moment, only activity is necessary, but more methods can be added later.

# The main methods that are used in the webUI version of ChEMBL are 'Target', 'Assay', 'Cell Line' and 'Molecule'.
# These methods allow for searching ChEMBL for targets, assays, cell lines and molecules respectively
# These methods accept query search or filtering by parameters.
# Filter rules are described in https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services
# Also filter rules are implemented in constants file as FILTER_RULES

# The 'Substructure and 'Similarity' allow for chemical content of ChEMBL to be searched.
# Similar to the other resources, these search based resources except filtering, 
# paging and ordering arguments.
# These methods accept SMILES, InChI Key and molecule ChEMBL_ID as arguments and in the case
# of similarity searches an additional identity cut-off is needed.
class ChEMBLInterface(BaseAPIInterface):
    API_NAME = "ChEMBL"
    METHODS = {
        "target": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "query": (str, None, True),
                "filters": (list, None, True),
                "format": (str, "json", False),
            },
            "group_queries": [None],
            "separator": None
        },
        "assay": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "query": (str, None, True),
                "filters": (list, None, True),
                "format": (str, "json", False),
            },
            "group_queries": [None],
            "separator": None
        },
        "cell_line": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "query": (str, None, True),
                "filters": (list, None, True),
                "format": (str, "json", False),
            },
            "group_queries": [None],
            "separator": None
        },
        "molecule": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "query": (str, None, True),
                "filters": (list, None, True),
                "format": (str, "json", False),
            },
            "group_queries": [None],
            "separator": None
        },
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
        },
        "substructure": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "query": (str, None, True),
            },
            "group_queries": [None],
            "separator": None
        },
        "similarity": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "query": (str, None, True),
                "cutoff": (int, 80, True),
            },
            "group_queries": [None],
            "separator": None
        },
        "activity-search": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "query": (str, None, True),
            },
            "group_queries": [None],
            "separator": None
        },
        "target-search": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "query": (str, None, True),
            },
            "group_queries": [None],
            "separator": None
        },
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
            pages_to_fetch (int): Number of pages to fetch. Default is 1. If -1, fetch all pages.
        Returns:
            dict: The fetched data from the next page.
        """
        log.debug(f"Fetching page: {next_url} for method {method} with pages_to_fetch={pages_to_fetch}")
        log.info(f"Fetching page: {next_url} for method {method} with pages_to_fetch={pages_to_fetch}")

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
            elif 'molecules' in data.keys() and isinstance(data['molecules'], list):
                responses.extend(data['molecules'])
            elif 'targets' in data.keys() and isinstance(data['targets'], list):
                responses.extend(data['targets'])
            elif 'assays' in data.keys() and isinstance(data['assays'], list):
                responses.extend(data['assays'])
            else:
                responses.append(data)

            next = None
            if 'page_meta' in data and data['page_meta'].get('next'):
                # Determine whether to recurse: if pages_to_fetch == -1 we want to fetch ALL pages,
                # so keep -1 for the recursive call. Otherwise only recurse when pages_to_fetch > 1
                # and pass pages_to_fetch - 1 to the next call.
                if pages_to_fetch == -1 or pages_to_fetch > 1:
                    next_pages_to_fetch = pages_to_fetch if pages_to_fetch == -1 else pages_to_fetch - 1
                    next_res = self.fetch_pages(
                        "https://www.ebi.ac.uk" + data['page_meta']['next'],
                        method,
                        next_pages_to_fetch
                    )
                    if next_res:
                        responses.extend(next_res)

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
            - `pages_to_fetch`: Number of pages to fetch. Default is 1.
            - `limit`: Maximum number of results to return. Default is None (no limit).
        Returns:
            any: response from the API.
        """
        pages_to_fetch = kwargs.get("pages_to_fetch", 1)
        limit = kwargs.get("limit", None)
        
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

        if method in ["activity", "binding_site"]:
            # Convert dictionary to a query string
            query = "&".join(f"{key}={value}" for key, value in validated_params.items())
            if limit is not None:
                query += f"&limit={limit}"

            # Generate url
            url = f"{CHEMBL.API_URL}{method}?{query}"
        elif method in ["substructure", "similarity"]:
            query = "/".join(f"{value}" for _, value in validated_params.items())
            url = f"{CHEMBL.API_URL}{method}/{query}?format=json"
        elif method in ["target", "assay", "cell_line", "molecule"]:
            if "query" in validated_params:
                query_str = validated_params.pop("query")
                url = f"{CHEMBL.API_URL}{method}/search.json?limit={limit if limit is not None else 20}&q={query_str}"
            else:
                url = f"{CHEMBL.API_URL}{method}?"
                if self.validate_filter_rules(validated_params['filters']):
                    query_str = "&".join(f"{item['field']}__{item['filter_type']}={item['value']}" for item in validated_params['filters'])
                    url += query_str
                    url += f"limit={limit if limit is not None else 20}&format=json"
        elif method in ["activity-search", "target-search"]:
            query_str = validated_params.get("query", "")
            url = f"{CHEMBL.API_URL}{method.replace('-', '/')}.json?limit={limit if limit is not None else 20}&q={query_str.replace(' ', '%20')}"
        else:
            log.error(f"Method {method} is not implemented in fetch.")
            return {}

        return self.fetch_pages(url, method, pages_to_fetch)

    def validate_filter_rules(self, filters: Dict) -> bool:
        """
        Validate filter rules based on predefined rules.
        Args:
            filters (Dict): Filters to validate.
        Returns:
            bool: True if all filters are valid, False otherwise.
        """
        allowed_filter_types = {"iexact", "gte", "lte", "icontains", "istartswith", "iendswith", "iregex", "range", "in", "isnull"}

        # Expect a list of filter dicts
        if not isinstance(filters, (list, tuple)):
            log.error("Filters must be provided as a list of dict items.")
            return False

        for item in filters:
            if not isinstance(item, dict):
                log.error("Each filter must be a dict with keys 'field', 'filter_type' and 'value'.")
                return False

            # Check presence of required keys
            for key in ("field", "filter_type", "value"):
                if key not in item:
                    log.error(f"Filter is missing required key '{key}'.")
                    return False

            # Validate types
            if not isinstance(item["field"], str):
                log.error(f"Filter 'field' must be a string, got {type(item['field']).__name__}.")
                return False

            if not isinstance(item["value"], (str, int, float)):
                log.error(f"Filter 'value' must be a string or number, got {type(item['value']).__name__}.")
                return False

            if not isinstance(item["filter_type"], str) or item["filter_type"] not in allowed_filter_types:
                log.error(f"Filter 'filter_type' is not valid: {item['filter_type']}. Allowed: {sorted(allowed_filter_types)}")
                return False

        return True

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
        elif isinstance(data, list):
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

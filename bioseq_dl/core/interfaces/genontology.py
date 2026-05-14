import os, logging
from typing import Optional, Union, List, Dict, Any
import requests
from requests import Request
from requests.exceptions import RequestException

import pandas as pd

from .base import BaseAPIInterface
from ...constants.databases import GENONTOLOGY
from ..utils.base_auxiliary_methods import validate_parameters

from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.interfaces.genontology")

class GenOntologyInterface(BaseAPIInterface):
    API_NAME = "GenOntology"
    METHODS = {
        "ontology-term": {
            "default": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "goid": (str, None, True),
                },
                "group_queries": [None],
                "separator": None
            },
            "graph": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "goid": (str, None, True),
                },
                "group_queries": [None],
                "separator": None

            }
        },
        "go": {
            "default": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "goid": (str, None, True),
                },
                "group_queries": [None],
                "separator": None
            }
        },
        "bioentity-function": {
            "default": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "goid": (str, None, True),
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
        """
        Initialize the GenOntologyInterface class.
        Args:
            cache_dir (str): Directory to cache results.
            config_dir (str): Directory for configuration files.
            output_dir (str): Directory to save output files.
        """
        if cache_dir:
            cache_dir = os.path.abspath(cache_dir)
        else:
            cache_dir = GENONTOLOGY.CACHE_DIR if GENONTOLOGY.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = GENONTOLOGY.CONFIG_DIR if GENONTOLOGY.CONFIG_DIR is not None else ""

        super().__init__(cache_dir=cache_dir, config_dir=config_dir,**kwargs)

    def fetch(self, query: Union[str, dict, list], *, method: str = "ontology-term", **kwargs):
        """
        Fetch data from the GenOntology API.
        Args:
            query (str): Query string to search for.
            method (str): Method to use for the request. Used methods are 'ontology-term' and 'go'.
            **kwargs: Additional parameters for the request.
            - `option`: Additional options for the request. 
        Returns:
            any: response from the API.
        """
        if method not in self.METHODS.keys():
            log.error(f"Method {method} is not supported. Available methods: {list(self.METHODS.keys())}")
            return {}
        
        option = kwargs.pop("option", "default")

        http_method, _, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, option=option, **kwargs)

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError as e:
            log.error(f"Invalid parameters for method '{method}': {e}")
            return {}
        
        
        url = f"{GENONTOLOGY.API_URL}{method.replace('-', '/')}/"
        for param in validated_params:
            if param in validated_params:
                url += f"{validated_params[param].upper().replace(':', '%3A')}"

        if option and option != "default":
            url += f"/{option}"

        response = Request(
            url=url,
            method=http_method,
        )

        prepared = self.session.prepare_request(response)
        log.debug(f"Prepared request: {prepared.url}")

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()

            return response.json()
        except RequestException as e:
            log.error(f"Error fetching data from {url}: {e}")
            return {}

    def parse(
            self,
            data: Any,
            fields_to_extract: Optional[Union[list, dict]],
            **kwargs
    ) -> Union[Dict, List]:
        """
        Parse the response from the GenOntology API.
        Args:
            data (Any): Raw data from the API response.
            fields_to_extract (List|Dict): Fields to keep from the original response.
                - If List: Keep those keys.
                - If Dict: Maps {desired_name: real_field_name}.
            **kwargs: Additional parameters for parsing.
            - `look_for_relationships`: If True, fetch related ontology terms.
        Returns:
            dict: Parsed response.
        """
        look_for_relationships = kwargs.get("look_for_relationships")
        if not data:
            log.warning("Tried to parse data but the data is empty or None.")
            return {}

        if isinstance(data, requests.models.Response):
            data = data.json()
        elif isinstance(data, dict):
            data = data
        else:
            log.error("Tried to parse data but the type is not supported. Response should be a dict or a requests.Response object.")
            return {}
        
        parsed = self._extract_fields(data, fields_to_extract)

        if look_for_relationships:
            if isinstance(parsed, list):
                parsed = [self.fetch_related_ontology_terms(item) for item in parsed]
            else:
                parsed =  self.fetch_related_ontology_terms(parsed)

        return parsed

    def fetch_related_ontology_terms(self, parsed: Dict) -> Dict:
        """
        Fetch related ontology terms for a given ontology term.
        Args:
            parsed (dict): Parsed ontology term data.
        Returns:
            dict: Updated parsed data with relationships.
        """
        try:
            rel_response = self.fetch(method="ontology-term", query=parsed.get("goid", ""), option="graph")
            if isinstance(rel_response, requests.models.Response) and rel_response.status_code == 200:
                graph_json = rel_response.json()
                nodes = graph_json.get("topology_graph_json", {}).get("nodes", [])
                relationships = [node.get("id") for node in nodes if "id" in node]
                parsed["relationships"] = relationships
            else:
                parsed["relationships"] = []
        except Exception as e:
            log.error(f"Error fetching relationships for GO term {parsed.get('goid', '')}: {e}")
        return parsed

    def get_dummy(self, *, method: Optional[str] = None, **kwargs) -> Dict:
        """
        Get example data returned by the API.

        Args:
            method (str, optional): Specific API method to test (e.g., "ontology-term", "subgraph").
                If None, returns dummy data for all available methods.

        Returns:
            dict: A dictionary where each key is a method name and each value is example data.
        """
        dummy_results = {}

        query = "GO:0008150"

        if method:
            dummy_results = super().get_dummy(query=query, method=method, **kwargs)
        else:
            for method in self.METHODS.keys():
                for option in self.METHODS[method]:
                        dummy_results[
                            f"{method}_{option}" if option else method
                        ] = super().get_dummy(query=query, method=method, option=option, **kwargs)

        return dummy_results
    
    # Patch Solution
    def fetch_single(self, query: Union[str, dict], parse: bool = False, *args, **kwargs) -> Union[List, Dict, pd.DataFrame]:
        option = kwargs.pop("option", "default")
        return super().fetch_single(query=query, parse=parse, option=option, *args, **kwargs)
    
    # Patch Solution
    def fetch_batch(self, queries: List[Union[str, dict]], parse: bool = False, *args, **kwargs) -> Union[List, pd.DataFrame]:
        option = kwargs.pop("option", "default")
        return super().fetch_batch(queries=queries, parse=parse, option=option, *args, **kwargs)

    def query_usage(self) -> str:
        return (
            "GenOntology API allows you to fetch ontology terms and their relationships.\n"
            "Available methods:\n"
            "- ontology-term: Fetch ontology term details.\n"
            "- go: Fetch Gene Ontology hierarchy or models.\n"
            "Options for 'ontology-term': graph, subgraph.\n"
            "Options for 'go': hierarchy, models.\n"
            "Example usage:\n"
            "  - Fetch ontology term: fetch_single('GO:0008150', method='ontology-term')\n"
            "  - Fetch GO hierarchy: fetch_single('GO:0008150', method='go', option='hierarchy')\n"
        )
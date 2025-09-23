import os
from typing import Optional, Set, Union, List, Dict, Any
import requests

from .base import BaseAPIInterface
from ...constants.databases import BIOGRID

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
                "format": (str, "json", False)
            },
            "group_queries": ["geneList"],
            "separator": "|"
        }
    }

    def __init__(
            self,
            cache_dir: Optional[str] = None,
            config_dir: Optional[str] = None,
            **kwargs
    ):
        """
        Initialize the BioGRIDInterface class.
        Args:
            cache_dir (str): Directory to cache results.
            config_dir (str): Directory for configuration files.
            output_dir (str): Directory to save output files.
        """
        if cache_dir:
            cache_dir = os.path.abspath(cache_dir)
        else:
            cache_dir = BIOGRID.CACHE_DIR if BIOGRID.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = BIOGRID.CONFIG_DIR if BIOGRID.CONFIG_DIR is not None else ""

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)

    # Critiacl to ignore the accessKey when caching
    def get_cache_ignore_keys(self) -> Set[str]:
        """
        Get the keys to ignore when caching.
        Returns:
            Set[str]: Set of keys to ignore.
        """
        return super().get_cache_ignore_keys().union({"accessKey"})
    
    def fetch(self, query: Union[str, dict, list], *, method: str = "interactions", **kwargs):
        """
        Fetch data from the BioGRID API.
        Args:
            query (str): Query string to search for.
            **kwargs: Additional parameters for the request.
            - `method`: Method to use for the request. Default is "interactions".
        Returns:
            any: response from the API.
        """
        response = super()._do_request(query, method=method, api_url=BIOGRID.API_URL, **kwargs)
        response = response.json() if isinstance(response, requests.models.Response) else response
        match method:
            case "interactions":
                # Special case for BioGRID
                if isinstance(response, dict) and all(str(key).isdigit() for key in response.keys()):
                    # Convert to list of interactions
                    response = list(response.values())
            case _:
                pass

        return response

    def parse(
            self,
            data: Any,
            fields_to_extract: Optional[Union[list, dict]],
            **kwargs
    ) -> Union[Dict, List]:
        """
        Parse the response from the BioGRID API.
        Args:
            data (dict): The fetched data.
            fields_to_extract (List|Dict): Fields to keep from the original response.
                - If List: Keep those keys.
                - If Dict: Maps {desired_name: real_field_name}.
        Returns:
            any: Parsed data from the response.
        """
        if not data:
            return {}

        if isinstance(data, requests.models.Response):
            data = data.json()
        elif isinstance(data, (dict, list)):
            data = data
        else:
            raise ValueError("Response must be a requests.Response object, list or a dictionary.")

        # # Check if all keys are numbers (indicating a list of interactions)
        # if isinstance(data, dict) and all(str(key).isdigit() for key in data.keys()):
        #     # Convert to list of interactions
        #     data = list(data.values())

        return self._extract_fields(data, fields_to_extract)

    
    def get_dummy(self, access_key: str = "", method: str = "", **kwargs) -> Dict:
        """
        Get a dummy response.
        Useful for knowing the structure of the data returned by the API.
        Args:
            access_key (str): Your BioGRID access key.
        Returns:
            Dict: Dummy response with example fields.
        """
        parse = kwargs.get("parse", False)

        if not access_key:
            raise ValueError("Access key must be provided to get dummy data.")
        if method != "" and method not in self.METHODS.keys():
            raise ValueError(f"Method {method} is not supported. Supported methods are: {', '.join(self.METHODS.keys())}.")
        dummy_results = {}
        query = {
            "accessKey": access_key,
            "geneList": ["cdc27", "apc1", "apc2"],
            "taxId": "559292",
            'max': 1,
            "format": "json"
        }

        if method:
            dummy_results = super().get_dummy(
                query=query,
                method=method,
                parse=parse
            )
        else:
            for method in self.METHODS.keys():
                dummy_results[method] = super().get_dummy(
                    query=query,
                    method=method,
                    parse=parse
                )
        return dummy_results

        
    def query_usage(self):
        """
        Get usage information for the BioGRID API query parameters.
        Returns:
            str: Usage information.
        """

        usage = """Usage: To fetch interactions, use the BioGRID API with the following parameters.
        Example:
            - fetch_single(method="interactions", query={})
        Available methods: """ + ", ".join(self.METHODS.keys()) + "\n\n"
        usage += "\n\nExample Query:\n"
        usage += """
        {
            "accessKey": "YOUR_ACCESS_KEY",
            "geneList": ["P53"],
            "max": 10,
            "format": "json"
        }
        """
        usage += "\n\nResponse Format:\n"
        usage += """
        {
            "BIOGRID_INTERACTION_ID": "int",
            "ENTREZ_GENE_A": "str",
            "ENTREZ_GENE_B": "str",
            "BIOGRID_ID_A": "int",
            "BIOGRID_ID_B": "int",
            "SYSTEMATIC_NAME_A": "str",
            "SYSTEMATIC_NAME_B": "str",
            "OFFICIAL_SYMBOL_A": "str",
            "OFFICIAL_SYMBOL_B": "str",
            "SYNONYMS_A": "str",
            "SYNONYMS_B": "str",
            "EXPERIMENTAL_SYSTEM": "str",
            "EXPERIMENTAL_SYSTEM_TYPE": "str",
            "PUBMED_AUTHOR": "str",
            "PUBMED_ID": "int",
            "ORGANISM_A": "int",
            "ORGANISM_B": "int",
            "THROUGHPUT": "str",
            "QUANTITATION": "str",
            "MODIFICATION": "str",
            "ONTOLOGY_TERMS": {},
            "QUALIFICATIONS": "",
            "TAGS": "",
            "SOURCEDB": ""
        }"""

        return usage
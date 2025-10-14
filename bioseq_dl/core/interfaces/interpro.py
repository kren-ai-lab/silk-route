import requests, os, logging
from typing import Optional, Union, List, Any, Dict

from .base import BaseAPIInterface
from ...constants.databases import INTERPRO
from ...constants.interpro import db_types, entry_integration_types, filter_types

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

log = get_logger("bioseq_dl.interfaces.interpro")
# -------------------------------------------------

# TODO add modifiers definitions
# TODO Because this API uses an unique type of query
# I did not updated the METHODS with fetch()

class InterproInterface(BaseAPIInterface):
    METHODS = {
        "entry": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "id": (str, None, True),
                "db": (str, None, True),
                "modifiers": (dict, None, True),
                "filters": (list, None, True),
                "entry_integration": (str, None, True),
                "filter_type": (str, None, True),
                "filter_db": (str, None, True),
                "filter_value": (str, None, True)
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
        Initialize the InterproInstance.
        Args:
            cache_dir (str): Directory to cache results.
            config_dir (str): Directory for configuration files.
            output_dir (str): Directory to save output files.
            **kwargs: Additional keyword arguments.
        """
        if cache_dir:
            cache_dir = os.path.abspath(cache_dir)
        else:
            cache_dir = INTERPRO.CACHE_DIR if INTERPRO.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = INTERPRO.CONFIG_DIR if INTERPRO.CONFIG_DIR is not None else ""
            
        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)
    
    def validate_query(self, method: str, query: Dict):
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
            'db': lambda v: v in db_types[method],
            'entry_integration': lambda v: v in entry_integration_types,
            'modifiers': lambda v: isinstance(v, dict),
            # Example of a valid filters:
                # "filters" : [
                #     {
                #         "type": "protein",
                #         "db": "reviewed",
                #         "value": "Q29537"
                #     }
                # ]
            'filters': lambda filters: (
                    isinstance(filters, list) and all(
                        isinstance(f, dict)
                        and all(k in f for k in ('type', 'db', 'value'))
                        and f['type'] in filter_types and f['type'] != method
                        for f in filters
                    )
                )
        }

        for key, check in rules.items():
            if key in query and not check(query[key]):
                if key == 'id':
                    log.error(f"Invalid ID: {query['id']}. It should be a non-empty string.")
                    return {}
                elif key == 'filters':
                    valid = [ftype for ftype in filter_types if ftype != method]
                    log.error(f"Invalid filter type: {query[key].get('type')}. Valid types are: {valid}")
                    return {}
                elif key == 'db':
                    log.error(f"Invalid database type: {query['db']} for method {method}. Valid types are: {db_types[method]}")
                    return {}
                elif key == 'entry_integration':
                    log.error(f"Invalid entry integration type: {query['entry_integration']}. Valid types are: {entry_integration_types}")
                    return {}
                elif key == 'modifiers':
                    log.error(f"Invalid modifiers type: {type(query['modifiers'])}. Modifiers should be a dictionary.")
                    return {}
                
    def fetch_pages(self, next_url: str, method: str, pages_to_fetch: int = 1):
        """
        Fetch the next page of results from the InterPro API.
        Args:
            next_url (str): The URL for the next page of results.
            method (str): The method used for the initial request.
        Returns:
            dict: The fetched data from the next page.
        """
        responses = []
        try:
            response = self.session.get(next_url, headers={"Content-Type": "application/json"})
            self._delay()
            response.raise_for_status() 
            
            if response.status_code == 204:
                log.warning(f"No content returned for URL {next_url}.")
                return {}

            data = response.json()

            if not isinstance(data, dict) and "detail" in data.keys():
                if data['detail'].startswith("There is no data associated with the requested URL"):
                    return {}

            if 'results' in data.keys() and isinstance(data['results'], list):
                responses.extend(data['results'])
            else:
                responses.append(data)

            next = None
            if 'next' in data and data['next']:
                next = self.fetch_pages(
                    data['next'],
                    method,
                    pages_to_fetch - 1
                ) if pages_to_fetch > 1 else None
                if next:
                    responses.extend(next)

            return responses
        except requests.exceptions.RequestException as e:
            log.error(f"Error fetching next page for method {method}: {e}")
            return {}

    def fetch(self, query: Union[str, dict, list], *, method: str = "entry", **kwargs):
        """
        Fetch data from InterPro API.
        Args:
            query (str|dict|list): The query parameters to fetch data.
            method (str): The method to use for the request.
        Returns:
            dict: The fetched data.
        """
        pages_to_fetch = kwargs.get("pages_to_fetch", 1)
  
        if method not in self.METHODS.keys():
            log.error(f"Method {method} is not supported. Available methods: {list(self.METHODS.keys())}")
            return {}

        if not isinstance(query, dict):
            log.error("Query must be a dictionary containing 'db', 'entry_integration', 'modifiers', 'filter_type', 'filter_db', and 'filter_value' keys.")
            return {}
        
        # Validate the query parameters
        self.validate_query(method, query)

        # Construct the base URL
        url = f"{INTERPRO.API_URL}{method}/"
           
        if 'db' in query.keys() and query['db']:
            url += f"{query['db']}/"
        if 'id' in query.keys() and query['id']:
            url += f"{query['id']}/"
        if 'entry_integration' in query.keys() and query['entry_integration']:
            url += f"{query['entry_integration']}/"
        if 'filters' in query.keys() and isinstance(query['filters'], list):
            for f in query['filters']:
                if f['type'] in filter_types and f['db'] in db_types[f['type']] and f['value']:
                    url += f"{f['type']}/{f['db']}/{f['value']}/"
                else:
                    log.error(f"Invalid filter: {f}. Valid filters are of type {filter_types} with databases {db_types[f['type']]}.")
                    return {}

        if 'modifiers' in query.keys() and query['modifiers']:
            url += "?"
            for key, value in query['modifiers'].items():
                if value is not None and value != "":
                    url += f"{key}={value}&"
            #remove the last '&'
            url = url[:-1]
        
        log.debug(f"Prepared url: {url}")
        return self.fetch_pages(url, method, pages_to_fetch)

    def parse(self, data: Any, fields_to_extract: Optional[Union[list, dict]], **kwargs) -> Union[Dict, List]:
        """
        Parse the fetched data.
        Args:
            data (dict): The fetched data.
            fields_to_extract (List|Dict): Fields to keep from the original response.
                - If List: Keep those keys.
                - If Dict: Maps {desired_name: real_field_name}.
        Returns:
            dict: The parsed data.
        """
        if not isinstance(data, (List, Dict)):
            log.error("Tried to parse data but the type is not supported. Response should be a dict or a list.")
            return {}
        if (isinstance(data, Dict) and not data) or \
              (isinstance(data, List) and not data):
            return {}
        
        return self._extract_fields(data, fields_to_extract)
    

    def get_dummy(self, *, method: Optional[str] = None, **kwargs) -> Dict:
        """
        Return a dummy response for testing purposes.
        Args:
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        Returns:
            dict: A dummy response.
        """
        # TODO - Implement a dummy response for InterPro API
        raise NotImplementedError(
            "Dummy response is not implemented for InterPro API. "
        )

    def query_usage(self) -> str:
        return (
            ""
            "Available methods: \n"
            f"{', '.join(data_types)}\n"
            "Available databases: \n"
            f"{', '.join(db_types['entry'])}\n"
            "Available entry integration types: \n"
            f"{', '.join(entry_integration_types)}\n"

            "Example query:\n"
            "interpro_instance.fetch(\n"
            "    query={\n"
            "        'db': 'InterPro',\n"
            "        'entry_integration': 'all',\n"
            "        'modifiers': {'page_size': 10, 'page': 1},\n"
            "        'filters': {'type': 'protein', 'db': 'UniProt', 'value': 'P12345'}\n"
            "    },\n"
            "    method='entry'\n"
            ")\n"
            "This will fetch InterPro entries with the specified filters and modifiers.\n"
            "You can also specify the number of pages to fetch using the 'pages_to_fetch' parameter.\n"
            "For more information, refer to the InterPro API documentation.\n"
        )
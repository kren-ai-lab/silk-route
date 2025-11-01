import time, random, os, hashlib, json, re, ast
import logging
import requests
import itertools
import yaml
from collections import defaultdict
from typing import Any, Set, Dict, List, Tuple, Union, ClassVar
from requests.models import Response, Request
from requests.adapters import HTTPAdapter, Retry
from requests.exceptions import RequestException
import pandas as pd
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Union, List, Dict, Optional
from itertools import permutations

from ..utils.base_auxiliary_methods import get_feature_keys, get_nested, get_primary_keys, validate_parameters

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

log = get_logger("bioseq_dl.interfaces.base")
# -------------------------------------------------

class BaseAPIInterface(ABC):
    METHODS: ClassVar[Dict[str, Any]] = {}

    cache_key_ignore_args: Set[str] = {
        "parse", "to_dataframe", "fields_to_extract", "config_key", "pages_to_fetch", "outfmt", "format", "download"}
    subquery_match_keys: Set[str] = set()

    def __init__(
        self,
        cache_dir: str = "./cache",
        config_dir: Optional[str] = None,
        max_workers: int = 5,
        min_wait: float = 1.0,
        max_wait: float = 2.0,
        total_retries: int = 5,
        headers: Optional[Dict] = None,
        use_config: bool = True
    ):
        """
        Initialize the BaseAPIInterface class.
        
        Args:
            cache_dir (str): Directory to store cached data.
            config_dir (Optional[str]): Directory to load configuration files.
            max_workers (int): Maximum number of parallel requests.
            min_wait (float): Minimum wait time between requests.
            max_wait (float): Maximum wait time between requests.
            total_retries (int): Total number of retries for requests.
            headers (Dict, optional): Headers to include in requests.
            use_config (bool): Whether to use a configuration file for initialization.
        """
        self.cache_dir = os.path.abspath(cache_dir)
        self.config_dir = config_dir
        self.max_workers = max_workers
        self.min_wait = min_wait
        self.max_wait = max_wait
        self.total_retries = total_retries
        self.headers = headers or {}
        self.use_config = use_config

        self.configs: Dict[str, dict] = {}
        self.fields_config: Dict[str, dict] = {}

        if self.use_config and self.config_dir:
            self._load_all_configs(self.config_dir)

        log.debug(f"Parent class BaseAPIInterface initialized. {self.__class__.__name__}")
        log.debug(f"Cache directory set to: {self.cache_dir}")
        log.debug(f"Configuration directory set to: {self.config_dir}")

        os.makedirs(self.cache_dir, exist_ok=True)

        # Init session
        self.session = requests.Session()
        retrues = Retry(
            total=self.total_retries,
            backoff_factor=0.25,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retrues)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
        self.session.headers.update(self.headers or {"Content-Type": "application/json"})

    def _load_all_configs(self, config_dir: str) -> None:
        """
        Load all configuration files from the specified directory.
        
        Args:
            config_dir (str): Directory containing configuration files.
        """
        if not os.path.exists(config_dir):
            raise FileNotFoundError(f"Configuration directory not found: {config_dir}")
        
        self.configs = {}

        for fname in os.listdir(config_dir):
            path = os.path.join(config_dir, fname)
            if os.path.isfile(path):
                name, ext = os.path.splitext(fname)
                with open(path, "r") as f:
                    try:
                        if ext == ".json":
                            self.configs[name] = json.load(f)
                        elif ext in [".yaml", ".yml"]:
                            self.configs[name] = yaml.safe_load(f)
                    except Exception as e:
                        log.error(f"Error loading config {fname}: {e}")

    def _delay(self):
        """
        Introduce a random delay between min_wait and max_wait.
        """
        time.sleep(random.uniform(self.min_wait, self.max_wait))

    def get_cache_ignore_keys(self) -> Set[str]:
        """
        Get the set of keys to ignore when generating cache keys.
        
        Returns:
            Set[str]: Set of keys to ignore.
        """
        return self.cache_key_ignore_args
    
    # Higly Encouraged to override this method in subclasses that can handle
    # multiple queries at once, such as BioGRID or KEGG.
    def get_subquery_match_keys(self) -> Set[str]:
        """
        Get the set of keys used for matching queries.
        This is used to determine which keys in the query should be used for generating subqueries.
        Returns:
            Set[str]: Set of keys used for matching queries.
        """
        return self.subquery_match_keys
    
    def _filter_dict_keys(self, input_dict: dict, sort_lists: bool = True) -> dict:
        """
        Filters out keys from a dictionary based on `get_cache_ignore_keys()`.

        Args:
            input_dict (dict): The dictionary to filter.
            sort_lists (bool): If True, sort values that are lists.
        Returns:
            dict: Filtered and optionally transformed dictionary.
        """
        result = {}
        for k, v in sorted(input_dict.items()):
            if k in self.get_cache_ignore_keys():
                continue
            if sort_lists and isinstance(v, list):
                # Solo ordena si los elementos son comparables (no dict)
                if all(not isinstance(item, dict) for item in v):
                    v = sorted(v)
            result[k] = v
        return result
        # result = {
        #     k: sorted(v) if sort_lists and isinstance(v, list) else v
        #     for k, v in sorted(input_dict.items())
        #     if k not in self.get_cache_ignore_keys()
        # }
        # return result
    
    def _make_cache_key(self, input_obj: Union[str, dict], **kwargs) -> str:
        """Generate a string key from the input object."""
        # Serialize input_obj based on its type
        if isinstance(input_obj, dict):
            base = json.dumps(self._filter_dict_keys(input_obj), sort_keys=True)
        elif isinstance(input_obj, str):
            base = input_obj
        else:
            base = json.dumps(input_obj, sort_keys=True)

        # Filter kwargs to exclude cache_key_ignore_args
        relevant_kwargs = self._filter_dict_keys(kwargs)
        extra = ""

        # Include relevant kwargs (like 'operation') in the cache key
        if relevant_kwargs:
            #extra = json.dumps(relevant_kwargs, sort_keys=True)
            extra = "_".join(f"{v}" for _, v in relevant_kwargs.items())
        
        if base and extra:
            #log.debug(f"Cache_key: {base}_{extra}")
            return f"{base}_{extra}"
        elif base:
            #log.debug(f"Cache_key: {base}")
            return base
        # A rarer case where input_obj is empty or None
        else:
            return extra
            

    def _hash_key(self, key: str) -> str:
        # TODO change it to hash
        return hashlib.md5(key.encode("utf-8")).hexdigest()
        #return key
    
    def _get_cache_path(self, identifier: str) -> str:
        """
        Generate a cache file path based on the identifier.
        """
        hashed_key = self._hash_key(identifier)
        return os.path.join(self.cache_dir, f"{hashed_key}.json")
    
    def has_results(self, identifier: str) -> bool:
        """
        Check if results for a given identifier are cached.
        """
        cache_path = self._get_cache_path(identifier)
        return os.path.exists(cache_path)
    
    def _load_file(self, path: str) -> Union[Dict, pd.DataFrame]:
        """
        Load a file from the cache path.
        Supports both JSON and CSV formats.
        """
        if path.endswith('.csv'):
            return pd.read_csv(path)
        else:
            with open(path, 'r') as f:
                return json.load(f)
    
    def load_cache(self, identifier: str) -> Optional[Dict|pd.DataFrame]:
        """
        Load cached results for a given identifier.
        """
        # Try directly loading from the cache
        cache_path = self._get_cache_path(identifier)
        if os.path.exists(cache_path):
            return self._load_file(cache_path)

        return None

    def save_cache(self, identifier: str, data: Union[List, Dict, pd.DataFrame]) -> None:
        """Save results to cache."""
        path = self._get_cache_path(identifier)

        if isinstance(data, pd.DataFrame):
            data.to_csv(path, index=False)
        else:
            with open(path, 'w') as f:
                json.dump(data, f)

    
    def get_config(self, key: str) -> dict:
        """
        Return the configuration dictionary for a given key (config filename without extension).
        """
        return self.configs.get(key, {})

    #def _resolve_fields_from_kwargs(self, include_defaults_from=None, **kwargs) -> Optional[Dict]:
    def _resolve_fields_from_kwargs(self, **kwargs) -> Optional[Dict]:
        """
        Resolve fields_to_extract by matching kwargs against keys in fields.yml.

        Automatically checks if any value in kwargs or combination like f"{value}_{mode}" matches a known config key.
        """
        fields_config = self.get_config("fields") if self.use_config else {}

        if not fields_config:
            return None

        known_keys = set(fields_config.keys())

        method = kwargs.get("method", "NOT_GIVEN")

        values = [method]
        values.extend([str(v) for v in kwargs.values() if isinstance(v, str)])

        # 1. Check if any value in kwargs matches a known key
        for v in values:
            #print(f"Trying to resolve fields from kwargs: {v}")
            #print(f"Known keys: {known_keys}")
            if v in known_keys:
                return fields_config[v]
    
        # 2. Check combinations of values in kwargs
        for v1, v2 in permutations(values, 2):
            composite = f"{v1}_{v2}"
            if composite in known_keys:
                return fields_config[composite]
        
        return None

    def _maybe_parse(self, data, parse: bool, to_dataframe: bool = False, **kwargs) -> Union[List, Dict, pd.DataFrame]:
        config_key = kwargs.pop("config_key", None)
        fields_to_extract = kwargs.pop("fields_to_extract", None)

        log.debug("_maybe_parse called with parse={}, to_dataframe={}, config_key={}, fields_to_extract={}".format(
            parse, to_dataframe, config_key, fields_to_extract
        ))
        if parse:
            if not fields_to_extract and self.use_config:
                log.debug("No fields_to_extract provided, trying to resolve from kwargs.")
                # 1. Try to resolve fields from kwargs
                #fields_to_extract = self._resolve_fields_from_kwargs(include_defaults_from=self.fetch, **kwargs)
                fields_to_extract = self._resolve_fields_from_kwargs(**kwargs)

                # 2. If not found, try to get from config
                if not fields_to_extract and config_key:
                    log.debug(f"No fields_to_extract resolved from kwargs, trying config_key: {config_key}")
                    fields_to_extract = self.get_config(config_key) or None
                
            if isinstance(data, list):
                log.debug("Data is a list, parsing each item")
                result = [self.parse(data=d, fields_to_extract=fields_to_extract, **kwargs) for d in data]
            elif isinstance(data, (dict, str)):
                log.debug("Data is a dict or str, parsing directly")
                # str is the case of KEGG API, which returns a string, parse method should handle it
                result =  self.parse(data=data, fields_to_extract=fields_to_extract, **kwargs)
            elif data is None:
                log.debug("Data is None, returning empty list")
                result = []
            else:
                log.error("Could not parse data. Data must be a list, dictionary, or string.")
                raise ValueError("Data must be a list, dictionary, or string for parsing. Received: {}".format(type(data)))
        else:
            result = data
        
        # Convert to DataFrame if requested
        if to_dataframe:
            log.debug("Converting result to DataFrame")
            # TODO: Make sure parse method returns a consistent structure
            if isinstance(result, list):
                return pd.DataFrame(result)
            elif isinstance(result, dict):
                return pd.DataFrame([result])
            elif result is None or result == []:
                return pd.DataFrame()
            else:
                log.error(f"Cannot convert to DataFrame, unsupported type.")
                raise ValueError(f"Cannot convert to DataFrame: unsupported type {type(result)}")

        return result
    
    ##################
    # Methods to handle complex queries and making subqueries using METHODS
    ##################

    def _get_method_spec(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.get("method", None)
        if method not in self.METHODS:
            raise ValueError(f"Unknown method '{method}'")
        option = kwargs.get("option", None)

        if option:
            return self.METHODS[method].get(option, {}) 
        else:
            return self.METHODS[method]

    def _prepare_params(self, query, spec, **overrides) -> dict:
        """
        - Validates types and defaults from spec["parameters"]
        - If value is a list and name is in spec["group_queries"], joins with spec["separator"]
        """
        params = {}
        separator = spec.get("separator", ",")

        for name, (typ, default, is_id) in spec["parameters"].items():
            val = default
            # Override from query dict or direct string/list
            if isinstance(query, dict) and name in query:
                val = query[name]
            elif not isinstance(query, dict) and is_id:
                # If a string or list is provided, map to the primary parameter
                val = query
            # Override with explicit overrides
            if name in overrides:
                val = overrides[name]

            if val is None and default is None:
                continue

            # Handle lists for group_queries
            if isinstance(val, list) and name in spec.get("group_queries", []):
                val = separator.join(val)

            params[name] = val

        return params

    def _make_identifier(self, query, spec) -> str:
        """
        Construye un identificador único a partir de las keys is_id=True,
        usado para nombrar el cache key.
        """
        keys = [k for k, (_, _, is_id) in spec["parameters"].items() if is_id]
        parts = []
        if isinstance(query, dict):
            for k in keys:
                if k in query:
                    parts.append(str(query[k]))
        else:
            # query str o list
            parts.append(str(query))
        return "_".join(parts)

    def initialize_method_parameters(self, query: Union[str, dict, list], method: str, method_definition: dict, **kwargs):
        if method not in method_definition:
            raise ValueError(f"Method '{method}' is not defined in the method definition. Available methods: {list(method_definition.keys())}")
       
        option = kwargs.get("option") if "option" in kwargs else None

        method_info = method_definition.get(method, {})

        if option and option not in method_info.keys():
            raise ValueError(f"Option '{option}' is not valid for method '{method}'. Allowed options: {method_info.keys()}")

        method_info = method_info.get(option, {}) if option else method_info

        # Redundant
        #if not all(k in method_info.keys() for k in ["http_method", "path_param", "parameters", "group_queries", "separator"]):
        #    raise ValueError(f"Method '{method}' with option '{option}' is not defined correctly in the method definition. Defined method: {method_info.keys()}")
        http_method = method_info["http_method"]
        path_param = method_info["path_param"]
        parameters = method_info["parameters"]
        group_queries = method_info["group_queries"]
        separator = method_info.get("separator", ",")

        primary_keys = get_primary_keys(parameters)
        
        if not primary_keys:
            raise ValueError(f"No primary keys defined for method '{method}'. Please check the method definition.")
        
        if len(primary_keys) > 1:
            if not isinstance(query, dict):
                raise ValueError(f"Query must be a dictionary when multiple primary keys are defined for method '{method}'. "
                             f"Received: {type(query)} with value {query}")
            # if not all(key in query.keys() for key in primary_keys):
            #     raise ValueError(f"Query must contain primary keys {primary_keys} for method '{method}'. "
            #                  f"Received: {query.keys()} with value {query}")
        
        inputs = {}

        if isinstance(query, (dict)):
            if group_queries:
                for key in group_queries:
                    if key in query and isinstance(query[key], list):
                        inputs[key] = separator.join(query[key])
                        print(f"Joined {key} with separator '{separator}': {inputs[key]}")
                    # TODO Changed else for elif, check
                    elif key in query:
                        inputs[key] = query.get(key, "")
                inputs.update({k: v for k, v in query.items() if k not in group_queries})
            else:
                inputs.update(query)
        elif isinstance(query, list):
            # Asume that the list contains or a single value or a list of values for the primary key
            if group_queries and primary_keys[0] in group_queries:
                inputs[primary_keys[0]] = separator.join(query)
            else:
                inputs[primary_keys[0]] = query
        elif isinstance(query, str):
            inputs[primary_keys[0]] = query
        else:
            raise ValueError(f"Unsupported query type: {type(query)}. Expected str, dict, or list.")
        
        # Probably this line is not needed. All inputs should be in the query 
        # TODO TRY IF IN OTHER APIS THIS CHANGE MAKE ERRORS
        # inputs.update([(k, v) for k, v in kwargs.items() if k not in self.get_cache_ignore_keys()])

        return http_method, path_param, parameters, inputs
    
    ##################
    # These 3 methods, decompose_query, get_matching_values, and split_results_by_subquery
    # are used to handle complex queries that can be decomposed into subqueries.
    # They allow the API to handle queries that can be split into smaller parts,
    # fetch results for each part, and then combine them back.

    # These are used by special cases of APIs that can handle complex queries,
    # such as BioGRID, which can take a list of genes and return interactions for each
    # gene separately.
    ##################

    def multiple_queries_supported(self, method: str, method_definition: dict) -> bool:
        """
        Check if the API method supports multiple queries based on the method definition.
        """
        if method not in method_definition:
            return False

        if method_definition[method].get("group_queries"):
            return True
        else:
            return False

    def decompose_query(self, query: dict, method: str, option: str) -> Optional[List[Tuple[str, dict]]]:
        """
        Decompose a query into multiple subqueries if any of the identity keys contain lists.
        Returns:
            List of (identifier, subquery) tuples or None if no decomposition is needed.
        """
        if method not in self.METHODS:
            raise ValueError(f"Method '{method}' is not supported. Available methods: {list(self.METHODS.keys())}")
        if option and option not in self.METHODS[method]:
            raise ValueError(f"Option '{option}' is not valid for method '{method}'. Allowed options: {self.METHODS[method].keys()}")

        method_spec = self.METHODS[method].get(option, self.METHODS[method])
        param_spec = method_spec.get("parameters", {})
        group_queries = method_spec.get("group_queries", [])

        # Identify ID keys
        keys = [k for k, (_, _, is_id) in param_spec.items() if is_id and k in query]
        
        # If no keys are found in group_queries, return None
        if not any(k in group_queries for k in keys):
            return [] # No decomposition needed
        
        # Collect values for product
        value_combinations = list(itertools.product(*(query[k] for k in group_queries if k in query and isinstance(query[k], list))))

        subqueries = []
        for combo in value_combinations:
            subquery = query.copy()
            identifier_parts = []

            # Set values from the group_queries
            for key, value in zip(group_queries, combo):
                subquery[key] = value
                identifier_parts.append(str(value))

            # Include other keys in identifier
            for key in keys:
                if key not in group_queries:
                    identifier_parts.append(str(query[key]))

            identifier = "_".join(identifier_parts)
            subqueries.append((identifier, subquery))

        return subqueries
            
    def get_matching_values(self, query: dict) -> List[str]:
        """
        Extract values from the subquery that will be used for matching items
        in the full result. Relies on self.subquery_match_keys defined in subclass.
        """
        keys = self.get_subquery_match_keys()

        if not keys:
            keys = [k for k in query if k not in self.get_cache_ignore_keys()]

        return [
            str(query[k]).lower() for k in keys if k in query and query[k] is not None
        ]

    def split_results_by_subquery(
        self, full_result: Any, subqueries: List[Tuple[str, dict]]
    ) -> Dict[str, List[dict]]:
        """
        Generic implementation: for each result, check if any subquery's values appear in the result
        using token-based partial matching.

        Returns a mapping {id_: [results]}.
        """
        if isinstance(full_result, dict):
            full_result = [full_result]
        elif not isinstance(full_result, list):
            raise ValueError("Expected full_result to be a list of dicts")
        

        mapping = {identifier: [] for identifier, _ in subqueries}

        def normalize(val):
            """Split and lowercase input values for loose token matching."""
            if not val:
                return []
            if isinstance(val, str) and val.startswith("[") and val.endswith("]"):
                try:
                    val = ast.literal_eval(val)
                except Exception:
                    pass
            if isinstance(val, (list, tuple)):
                tokens = []
                for elem in val:
                    tokens.extend(normalize(elem))
                return tokens
            return [t.lower() for t in re.split(r"[\s:\-/|]", str(val)) if t]

        def extract_all_values(obj):
            """Recursively extract all string-like values from a nested structure."""
            result = []
            if isinstance(obj, dict):
                for v in obj.values():
                    result.extend(extract_all_values(v))
            elif isinstance(obj, list):
                for item in obj:
                    result.extend(extract_all_values(item))
            elif isinstance(obj, (str, int, float)):
                result.append(str(obj))
            return result

        subquery_values = {}
        for identifier, query in subqueries:
            values = self.get_matching_values(query)
            norm = sum((normalize(v) for v in values), [])
            subquery_values[identifier] = norm

        for i, item in enumerate(full_result):
            tokens = extract_all_values(item)
            item_tokens = set(normalize(tokens))

            for identifier, expected_tokens in subquery_values.items():
                # Match if there's any overlap
                if expected_tokens and (set(expected_tokens) & item_tokens):
                    mapping[identifier].append(item)

        return mapping
    
    def merge_dicts(self, dicts):
        merged = {}
        for d in dicts:
            for k, v in d.items():
                if k not in merged:
                    merged[k] = v
                else:
                    # Si ya hay una lista, añade solo si es distinto
                    if isinstance(merged[k], list):
                        if v not in merged[k]:
                            merged[k].append(v)
                    else:
                        if merged[k] != v:
                            merged[k] = [merged[k], v]
        return merged
    ###################
    # General-purpose fetch methods
    # These methods are used to fetch data from the API, either for a single query or
    # a batch of queries. They handle caching, parsing, and optional DataFrame conversion.
    ###################
    
    def fetch_single(self, query: Union[str, dict], parse: bool = False, *args, **kwargs) -> Union[List, Dict, pd.DataFrame]:
        """
        General-purpose fetch method with optional parsing and cache handling.

        Args:
            query (Union[str, dict]): Query to fetch data for.
            parse (bool): Whether to parse the fetched data.
        
        kwargs:
            config_key (str): Key to use for configuration settings.
            fields_to_extract (Optional[Union[list, dict]]): Fields to extract from the fetched data.
            to_dataframe (bool): Whether to convert the result to a DataFrame.
        Returns:
            Any: Fetched data, parsed if requested.
        """
        # Extract flags and avoid passing twice to _maybe_parse
        to_dataframe = kwargs.pop("to_dataframe", False)
        method       = kwargs.get("method", "NOT_GIVEN")
        option       = kwargs.get("option", None)
        
        # Get method specification
        spec = self._get_method_spec(**kwargs)
        if spec is None:
            log.error(f"Method '{method}' is not supported")
            raise ValueError(f"Method '{method}' is not supported. Available: {list(self.METHODS)}")
        log.debug("Checking if multiple queries are supported")
        group_key = spec.get('group_queries', [None])[0] 

        # If group_key is present and value is list: check cache per element
        if isinstance(query, dict) and group_key and isinstance(query.get(group_key), list):
            log.debug("Multiple queries detected in the input.")
            log.debug(f"Generated a group of queries based on key '{group_key}' with multiple values.")
            results = {}
            remaining = []
            # values = list(query[group_key])
            subqueries = self.decompose_query(query, method, option)
            # Check cache per individual
            log.debug(f"Subqueries generated: {subqueries}")
            for identifier, subq in subqueries:
                log.debug(f"Checking cache for identifier: {identifier}")
                cache_key = self._make_cache_key(identifier, **kwargs)
                if self.has_results(cache_key):
                    log.debug(f"Cache hit for identifier: {identifier}, loading from cache.")
                    raw = self.load_cache(cache_key)
                    parsed = self._maybe_parse(data=raw, parse=parse, to_dataframe=to_dataframe, **kwargs)
                    results[identifier] = parsed
                else:
                    log.debug(f"No cache found for identifier: {identifier}, will fetch.")
                    remaining.append((identifier, subq)) 

            # If some remain, fetch them together
            if remaining:
                log.debug(f"Fetching remaining {len(remaining)} subqueries in a single request.")
                combined = self.merge_dicts([subq for _, subq in remaining])
                params = self._prepare_params(combined, spec, **kwargs)
                full = self.fetch(query=params, *args, **kwargs)
                mapping = self.split_results_by_subquery(full, remaining)
                for identifier, _ in remaining:
                    partial_result = mapping.get(identifier, [])
                    if not partial_result:
                        log.debug(f"No results found for identifier {identifier}. Skipping.")
                        continue
                    log.debug(f"Fetched {len(partial_result)} items for identifier {identifier}. Caching result.")
                    cache_key = self._make_cache_key(identifier, **kwargs)
                    self.save_cache(cache_key, partial_result)
                    parsed = self._maybe_parse(data=partial_result, parse=parse, to_dataframe=to_dataframe, **kwargs)
                    results[identifier] = parsed

            if to_dataframe:
                dfs = []
                log.debug("Converting results to DataFrames")
                for data in results.values():
                    df = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
                    dfs.append(df)
                # TODO Check if this line of code works as intended
                if dfs:
                    return pd.concat(dfs, ignore_index=True)
                else:
                    return pd.DataFrame()
            
            return list(results.values())
        else:
            log.debug("Single query detected, proceeding with fetch.")
            params     = self._prepare_params(query, spec, **kwargs)
            identifier = self._make_identifier(query, spec)
            cache_key  = self._make_cache_key(identifier, **kwargs)
            if self.has_results(cache_key):
                log.debug(f"Cache hit for identifier: {identifier}, loading from cache.")
                raw = self.load_cache(cache_key)
            else:
                log.debug(f"No cache found for identifier: {identifier}, fetching from API.")
                raw = self.fetch(query=params, *args, **kwargs)
                if raw:  # only save non-empty
                    self.save_cache(cache_key, raw)
            return self._maybe_parse(data=raw, parse=parse, to_dataframe=to_dataframe, **kwargs)

    
    def fetch_batch(self, queries: List[Union[str, dict]], parse: bool = False, *args, **kwargs) -> Union[List, pd.DataFrame]:
        """
        Fetch data in parallel for a batch of queries.
        Args:
            queries (List[Union[str, dict, list[str]]]): List of queries to fetch data for.
            parse (bool): Whether to parse the fetched data.

        kwargs:
            config_key (str): Key to use for configuration settings.
            fields_to_extract (Optional[Union[list, dict]]): Fields to extract from the fetched data.
            to_dataframe (bool): Whether to convert the result to a DataFrame.
        Returns:
            List: List of fetched data, parsed if requested.
        """
        method       = kwargs.get("method", "NOT_GIVEN")
        option       = kwargs.get("option", None)
        results: List[Any] = []

        # Separate queries in cache and not in cache
        queries_to_fetch = []
        index_query_map = {}

        ###############################
        ## Cache handling
        ###############################
        log.debug("Checking cache for each query in the batch.")
        for i, query in enumerate(queries):
            if isinstance(query, dict):
                subqueries = self.decompose_query(query, method, option)
            elif isinstance(query, list) and all(isinstance(q, str) for q in query):
                subqueries = [(q, {"identifiers": [q]}) for q in query]
            else:
                subqueries = None
            if subqueries:
                for identifier, subquery in subqueries:
                    cache_key = self._make_cache_key(identifier, **kwargs)
                    if self.has_results(cache_key):
                        log.debug(f"Cache hit for subquery identifier: {identifier}, loading from cache.")
                        cached = self.load_cache(cache_key)
                        result = cached.to_dict(orient='records') if isinstance(cached, pd.DataFrame) else cached
                        results.append(self._maybe_parse(data=result, parse=parse, **kwargs))
                    else:
                        log.debug(f"No cache found for subquery identifier: {identifier}, will fetch.")
                        index_query_map[i] = query
                        queries_to_fetch.append(query)

            else:
                # No subqueries, use the classic key
                cache_key = self._make_cache_key(query, **kwargs)
                if self.has_results(cache_key):
                    log.debug(f"Cache hit for query at index {i}, loading from cache.")
                    cached = self.load_cache(cache_key)
                    result = cached.to_dict(orient='records') if isinstance(cached, pd.DataFrame) else cached
                    results.append(self._maybe_parse(data=result, parse=parse, **kwargs))
                else:
                    log.debug(f"No cache found for query at index {i}, will fetch.")
                    index_query_map[i] = query
                    queries_to_fetch.append(query)

        #############################
        # If all queries are cached, return the results
        # It's important to note that creating threads takes time, so if all queries are cached,
        # it's better to return the results directly.
        # If there is an incorrect cache key handling then it's better to do a better implementation
        #############################
        # Fetch missing ones in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {
                executor.submit(self.fetch_single, query, parse, *args, **kwargs): i
                # Change it to index_query_map.items() if That part is needed
                for i, query in index_query_map.items()
            }
            for future in future_to_index:
                log.debug(f"Waiting for future result for query at index {future_to_index[future]}")
                i = future_to_index[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    log.error(f"Error fetching query at index {i} ({queries[i]}): {e}")
                self._delay()

        # Patch solution. Make sure that it works as intended
        # If it's a list of dataframes, concatenate them
        if all(isinstance(r, pd.DataFrame) for r in results) and len(results) > 0:
            batch_data = pd.concat(results, ignore_index=True)
        else:
            batch_data = results
        
        return batch_data
    
    ###################
    # Auxiliary methods
    ###################

    def get_dummy(self, *args, **kwargs) -> dict:
        """
        Get a dummy object for the API interface.
        This is useful for knowing the structure of the data returned by the API.
        """
        query = kwargs.pop('query', None)
        parse = kwargs.pop('parse', False)

        if not query:
            raise ValueError("Query must be provided to get dummy data.")

        response = self.fetch_single(query=query, parse=parse, *args, **kwargs)
        if isinstance(response, list):
            return get_feature_keys(response[0] if response else {})
        elif isinstance(response, dict):
            return get_feature_keys(response)
        else:
            raise ValueError("Response must be a list or a dictionary.")

    def _extract_fields(self, data: Union[dict, list], fields_to_extract: Optional[Union[list, dict]] = None, **kwargs) -> Union[dict, list]:
        """
        Extract specified fields from the data.
        
        Args:
            data (Union[List, Dict]): Data to parse.
            fields_to_extract (List|Dict): Fields to keep from the original response.
                - If List: Keep those keys.
                - If Dict: Maps {desired_name: real_field_name}.
        Returns:
            Union[dict, list]: Data with only the specified fields.
        """
        option = kwargs.get("option", "default")

        if option and isinstance(fields_to_extract, dict) and option in fields_to_extract.keys():
            fields_to_extract = fields_to_extract[option]
        
        parsed = {}
        if isinstance(fields_to_extract, List):
            if isinstance(data, List):
                parsed = [
                    {key: get_nested(item, key) for key in fields_to_extract}
                    for item in data
                ]
            elif isinstance(data, Dict):
                parsed = {key: get_nested(data, key) for key in fields_to_extract}
        elif isinstance(fields_to_extract, Dict):
            if isinstance(data, List):
                parsed = [
                    {new_key: get_nested(item, path) for new_key, path in fields_to_extract.items()}
                    for item in data
                ]
            elif isinstance(data, Dict):
                parsed = {new_key: get_nested(data, path) for new_key, path in fields_to_extract.items()}
        # If no fields to extract, return the entire structure
        elif fields_to_extract is None and isinstance(data, List):
            parsed = [get_nested(item, "") for item in data]
        elif fields_to_extract is None and isinstance(data, Dict):
            parsed = get_nested(data, "")
        
        return parsed

    def _do_request(self, query: Union[str, dict, list], *, method: str, **kwargs) -> Union[dict, list, Response]:
        """
        Fetch data from the API based on the provided query and method.
        Args:
            query (Union[str, dict, list]): Query to fetch data for.
            method (str): Method to use for fetching data.
        kwargs:
            api_url (str): API URL to use for the request.
        Returns:
            dict: Fetched data from the API.
        Raises:
            ValueError: If the method is not defined in the METHODS.
            RequestException: If there is an error during the HTTP request. 
        """
        api_url = kwargs.pop("api_url", None)

        if not api_url:
            raise ValueError("API URL must be provided in kwargs.")
        http_method, path_param, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError as e:
            raise ValueError(f"Invalid parameters for method '{method}': {e}")

        url = f"{api_url}{method}"

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

            return response
        except RequestException as e:
            log.error(f"Error fetching {query} for method '{method}': {e}")
            return {}
    
    @abstractmethod
    def fetch(self, query: Union[str, dict, list], *, method: str, **kwargs):
        raise NotImplementedError
    
    @abstractmethod
    def query_usage(self) -> str:
        raise NotImplementedError
    
    @abstractmethod
    def parse(self, data: Any, fields_to_extract: Optional[Union[list, dict]], **kwargs):
        raise NotImplementedError
      
        
"""Abstract base class for all API interfaces."""

import ast
import contextlib
import functools
import hashlib
import itertools
import json
import operator
import random
import re
import time
from abc import ABC
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Literal

import niquests
import pandas as pd
from dicttoxml import dicttoxml
from niquests.adapters import HTTPAdapter, Retry
from niquests.exceptions import RequestException
from niquests.models import Request, Response

from bioseq_dl.core.dbconfig import DBConfig
from bioseq_dl.core.exceptions import RequestError
from bioseq_dl.core.interfacesconfig import load_packaged_config, read_config_file
from bioseq_dl.core.metadata import FetchMetadata
from bioseq_dl.core.utils.base_auxiliary_methods import get_nested, get_primary_keys, validate_parameters
from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.interfaces.base")


def _normalize_matching_tokens(value: object) -> list[str]:
    """Split and lowercase input values for loose token matching."""
    if not value:
        return []
    if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
        with contextlib.suppress(Exception):
            value = ast.literal_eval(value)
    if isinstance(value, (list, tuple)):
        tokens = []
        for item in value:
            tokens.extend(_normalize_matching_tokens(item))
        return tokens
    return [token.lower() for token in re.split(r"[\s:\-/|]", str(value)) if token]


def _extract_nested_values(value: object) -> list[str]:
    """Recursively extract string-like values from a nested structure."""
    result = []
    if isinstance(value, dict):
        for item in value.values():
            result.extend(_extract_nested_values(item))
    elif isinstance(value, list):
        for item in value:
            result.extend(_extract_nested_values(item))
    elif isinstance(value, (str, int, float)):
        result.append(str(value))
    return result


# noinspection D
class BaseAPIInterface(ABC):  # noqa: B024  # base by intent; fetch/parse have concrete defaults
    """Abstract base class for all BioSeqDownloader API interfaces."""

    API_NAME: ClassVar[str] = "BaseAPI"
    METHODS: ClassVar[dict[str, Any]] = {}
    DB_CONFIG: ClassVar[DBConfig | None] = None
    # Default `option` injected into fetch_single/fetch_batch when the caller
    # omits it. Only set on interfaces whose METHODS are option-keyed (e.g.
    # {"default": {...}, ...}); leave None otherwise.
    DEFAULT_OPTION: ClassVar[str | None] = None
    # Suffix appended after ``{api_url}{method}`` by the default ``_build_request``
    # (e.g. ``"/"`` for APIs whose endpoints are ``{method}/{id}``).
    _METHOD_SUFFIX: ClassVar[str] = ""
    # Response envelope keys the default ``_unwrap_response`` unwraps, in order;
    # the first present key's value is returned. Empty = return data unchanged.
    _RESPONSE_ENVELOPE_KEYS: ClassVar[tuple[str, ...]] = ()

    cache_key_ignore_args: ClassVar[set[str]] = {
        "parse",
        "to_dataframe",
        "fields_to_extract",
        "config_key",
        "pages_to_fetch",
        "outfmt",
        "format",
        "download",
    }
    subquery_match_keys: ClassVar[set[str]] = set()

    @classmethod
    def _resolve_dirs(cls, cache_dir: str | None, config_dir: str | None) -> tuple[str, str | None]:
        """Resolve cache_dir/config_dir, falling back to the class ``DB_CONFIG``.

        An explicit ``cache_dir`` is made absolute; otherwise the value from
        ``DB_CONFIG.CACHE_DIR`` is used (already absolute), falling back to
        ``"./cache"``. ``config_dir`` defaults to ``DB_CONFIG.CONFIG_DIR`` when
        not given. Subclasses that need the resolved dirs before ``super().__init__``
        (e.g. to read an ``init`` config) can call this directly.
        """
        db = cls.DB_CONFIG
        if not cache_dir:
            cache_dir = db.CACHE_DIR if db is not None and db.CACHE_DIR is not None else "./cache"
        # Always normalize to an absolute path so caches don't land relative to
        # the current working directory (DB_CONFIG/env values may be relative).
        cache_dir = str(Path(cache_dir).resolve())

        if config_dir is None and db is not None:
            config_dir = db.CONFIG_DIR

        return cache_dir, config_dir

    def _resolve_output_dir(self, output_dir: str | None, *, init_subdir: str | None = None) -> str:
        """Resolve a download output dir and ensure it exists.

        Precedence: explicit ``output_dir`` > packaged ``init.yml`` ``download_folder``
        (when ``init_subdir`` is given) > ``self.cache_dir``. Shared by the
        file-downloading interfaces (AlphaFold / PDB / SABIO-RK). Call after
        ``super().__init__`` so ``self.cache_dir`` is set.
        """
        fallback = self.cache_dir
        if init_subdir:
            packaged_init = load_packaged_config(init_subdir, "init.yml") or {}
            fallback = packaged_init.get("download_folder") or self.cache_dir
        out_dir = output_dir or fallback
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        return out_dir

    def __init__(
        self,
        cache_dir: str | None = None,
        config_dir: str | None = None,
        max_workers: int = 5,
        min_wait: float = 1.0,
        max_wait: float = 2.0,
        total_retries: int = 5,
        headers: dict | None = None,
        use_config: bool = True,
    ) -> None:
        """Initialize the BaseAPIInterface class.

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
        cache_dir, config_dir = self._resolve_dirs(cache_dir, config_dir)
        self.cache_dir = cache_dir
        self.config_dir = config_dir
        self.max_workers = max_workers
        self.min_wait = min_wait
        self.max_wait = max_wait
        self.total_retries = total_retries
        self.headers = headers or {}
        self.use_config = use_config

        self.configs: dict[str, dict] = {}

        if self.use_config:
            # Optional user-provided extra configs (never required).
            if self.config_dir:
                self._load_all_configs(self.config_dir)
            # Field-extraction maps are library internals: always load the
            # packaged version, which overrides any user copy (no overrides).
            packaged_fields = self._load_packaged_fields()
            if packaged_fields:
                self.configs["fields"] = packaged_fields

        log.debug("Parent class BaseAPIInterface initialized. %s", self.__class__.__name__)
        log.debug("Cache directory set to: %s", self.cache_dir)
        log.debug("Configuration directory set to: %s", self.config_dir)

        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

        # Init session
        self.session = niquests.Session()
        retries = Retry(total=self.total_retries, backoff_factor=0.25, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(self.headers or {"Content-Type": "application/json"})

    def _load_packaged_fields(self) -> dict:
        """Load the packaged ``fields.yml`` for this interface from package resources.

        Field maps are library internals, not user config: the bundled version is
        authoritative and always in sync with the parse code. The package subdir is
        derived from ``DB_CONFIG.CONFIG_DIR`` (e.g. ``.../go`` -> ``go``).
        """
        db = self.DB_CONFIG
        if db is None or not db.CONFIG_DIR:
            return {}
        subdir = Path(db.CONFIG_DIR).name
        return load_packaged_config(subdir, "fields.yml") or {}

    def _load_all_configs(self, config_dir: str) -> None:
        """Load optional user-provided configuration files from a directory.

        A missing directory is not an error: the library falls back to packaged
        defaults, so interfaces work on a clean machine without ``bioseq-dl-init``.

        Args:
            config_dir (str): Directory containing configuration files.

        """
        if not Path(config_dir).exists():
            log.debug("Config directory not found, using packaged defaults only: %s", config_dir)
            return

        for entry in Path(config_dir).iterdir():
            if entry.is_file():
                if entry.suffix.lower() not in (".json", ".yaml", ".yml"):
                    continue
                try:
                    self.configs[entry.stem] = read_config_file(entry)
                except Exception:
                    log.exception("Error loading config %s", entry.name)

    def _delay(self) -> None:
        """Introduce a random delay between min_wait and max_wait."""
        time.sleep(random.uniform(self.min_wait, self.max_wait))  # noqa: S311  # jittered rate-limit delay, not cryptographic

    @staticmethod
    def _tool_metadata() -> dict[str, str]:
        """Return the ``tool`` provenance block (library name + version).

        Imported lazily to avoid a circular import: ``base`` is only loaded
        after the ``bioseq_dl`` package has finished initializing.
        """
        from bioseq_dl import __version__  # noqa: PLC0415  # lazy to avoid a circular import

        return {"name": "bioseq_dl", "version": __version__}

    def _stamp_metadata(self, metadata: FetchMetadata, *, method: str, option: Any) -> None:
        """Stamp the API/method/option fields shared by every fetch return path."""
        metadata.tool = self._tool_metadata()
        metadata.api_name = self.API_NAME
        metadata.method = method
        metadata.option = option

    def _apply_default_option(self, kwargs: dict) -> None:
        """Inject ``DEFAULT_OPTION`` into ``kwargs`` when the caller omitted ``option``."""
        if self.DEFAULT_OPTION is not None:
            kwargs.setdefault("option", self.DEFAULT_OPTION)

    @staticmethod
    def _build_columns_info(df: pd.DataFrame) -> list[dict]:
        """Build the per-column ``data_info`` block (name / dtype / n_missing)."""
        return [
            {"name": col, "dtype": str(df[col].dtype), "n_missing": int(df[col].isna().sum())}
            for col in df.columns
        ]

    @classmethod
    def _build_data_info(cls, data: Any) -> dict:
        """Build the ``data_info`` metadata block for any result shape.

        Single source of truth shared by ``fetch_single``/``fetch_batch`` (and the
        workflow). ``data_type`` is the result type name (a string, so the
        metadata stays serializable); ``total_entries`` and the per-column block
        are derived from a DataFrame view of the data.
        """
        if isinstance(data, pd.DataFrame):
            df = data
        elif isinstance(data, list):
            df = pd.DataFrame(data) if len(data) > 0 else pd.DataFrame()
        elif isinstance(data, dict):
            df = pd.DataFrame([data]) if len(data) > 0 else pd.DataFrame()
        elif data is None:
            df = pd.DataFrame()
        else:
            df = pd.DataFrame([data])

        # The DataFrame view above faithfully represents the row count for every
        # input shape (list, dict, scalar, None), so derive the count from it.
        return {
            "total_entries": df.shape[0],
            "data_type": type(data).__name__,
            "columns": cls._build_columns_info(df),
        }

    def get_cache_ignore_keys(self) -> set[str]:
        """Get the set of keys to ignore when generating cache keys.

        Returns:
            Set[str]: Set of keys to ignore.

        """
        return self.cache_key_ignore_args

    # Higly Encouraged to override this method in subclasses that can handle
    # multiple queries at once, such as BioGRID or KEGG.
    def get_subquery_match_keys(self) -> set[str]:
        """Get the set of keys used for matching queries and generating subqueries.

        Returns:
            Set[str]: Set of keys used for matching queries.

        """
        return self.subquery_match_keys

    def _filter_dict_keys(self, input_dict: dict, sort_lists: bool = True) -> dict:
        """Filter out keys from a dictionary based on `get_cache_ignore_keys()`.

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
            val = (
                sorted(v)
                if sort_lists and isinstance(v, list) and all(not isinstance(item, dict) for item in v)
                else v
            )
            result[k] = val
        return result

    def _make_cache_key(self, input_obj: str | dict, **kwargs: Any) -> str:
        """Generate a string key from the input object."""
        # Serialize input_obj based on its type
        if isinstance(input_obj, dict):
            base = json.dumps(self._filter_dict_keys(input_obj), sort_keys=True)
        elif isinstance(input_obj, str):
            base = input_obj
        else:
            base = json.dumps(input_obj, sort_keys=True)

        # Include relevant kwargs (like 'operation') in the cache key, excluding
        # cache_key_ignore_args. Empty parts drop out of the join.
        relevant_kwargs = self._filter_dict_keys(kwargs)
        extra = "_".join(map(str, relevant_kwargs.values()))
        return "_".join(part for part in (base, extra) if part)

    def _hash_key(self, key: str) -> str:
        return hashlib.md5(key.encode("utf-8"), usedforsecurity=False).hexdigest()

    def _get_cache_path(self, identifier: str) -> str:
        """Generate a cache file path based on the identifier."""
        hashed_key = self._hash_key(identifier)
        return str(Path(self.cache_dir) / f"{hashed_key}.json")

    def has_results(self, identifier: str) -> bool:
        """Check if results for a given identifier are cached."""
        cache_path = self._get_cache_path(identifier)
        return Path(cache_path).exists()

    def _load_file(self, path: str) -> dict | pd.DataFrame:
        """Load a file from the cache path, supporting JSON and CSV formats."""
        if path.endswith(".csv"):
            return pd.read_csv(path)
        with Path(path).open() as f:
            return json.load(f)

    def load_cache(self, identifier: str) -> dict | pd.DataFrame | None:
        """Load cached results for a given identifier."""
        # Try directly loading from the cache
        cache_path = self._get_cache_path(identifier)
        if Path(cache_path).exists():
            return self._load_file(cache_path)

        return None

    def save_cache(self, identifier: str, data: list | dict | pd.DataFrame | str) -> None:
        """Save results to cache."""
        path = self._get_cache_path(identifier)

        if isinstance(data, pd.DataFrame):
            data.to_csv(path, index=False)
        elif isinstance(data, str):
            with Path(path).open("w") as f:
                f.write(data)
        else:
            with Path(path).open("w") as f:
                json.dump(data, f)

    def get_config(self, key: str) -> dict:
        """Return the configuration dictionary for a given key (config filename without extension)."""
        return self.configs.get(key, {})

    def _resolve_fields_from_kwargs(self, **kwargs: Any) -> dict | None:
        """Resolve fields_to_extract by matching kwargs values against keys in fields.yml.

        Returns the config entry whose key matches the ``method`` (or any string
        kwarg). Returns ``None`` if nothing matches.
        """
        fields_config = self.get_config("fields") if self.use_config else {}

        if not fields_config:
            return None

        known_keys = set(fields_config.keys())

        method = kwargs.get("method", "NOT_GIVEN")

        values = [method]
        values.extend([str(v) for v in kwargs.values() if isinstance(v, str)])

        for v in values:
            if v in known_keys:
                return fields_config[v]

        return None

    def _maybe_parse(
        self, data: Any, parse: bool, fmt: Literal["dataframe", "json", "xml"], **kwargs: Any
    ) -> list | dict | pd.DataFrame | bytes | str:
        config_key = kwargs.pop("config_key", None)
        fields_to_extract = kwargs.pop("fields_to_extract", None)

        log.debug(
            "_maybe_parse called with parse=%s, format=%s, config_key=%s, fields_to_extract=%s",
            parse,
            fmt,
            config_key,
            fields_to_extract,
        )
        if parse:
            if not fields_to_extract and self.use_config:
                log.debug("No fields_to_extract provided, trying to resolve from kwargs.")
                # 1. Try to resolve fields from kwargs
                fields_to_extract = self._resolve_fields_from_kwargs(**kwargs)

                # 2. If not found, try to get from config
                if not fields_to_extract and config_key:
                    log.debug("No fields_to_extract resolved from kwargs, trying config_key: %s", config_key)
                    fields_to_extract = self.get_config(config_key) or None

            if isinstance(data, list):
                log.debug("Data is a list, parsing each item")
                result = [self.parse(data=d, fields_to_extract=fields_to_extract, **kwargs) for d in data]
            elif isinstance(data, (dict, str)):
                log.debug("Data is a dict or str, parsing directly")
                # str is the case of KEGG API, which returns a string, parse method should handle it
                result = self.parse(data=data, fields_to_extract=fields_to_extract, **kwargs)
            elif data is None:
                log.debug("Data is None, returning empty list")
                result = []
            else:
                log.error("Could not parse data. Data must be a list, dictionary, or string.")
                msg = f"Data must be a list, dictionary, or string for parsing. Received: {type(data)}"
                raise ValueError(msg)
        else:
            result = data

        # Convert to DataFrame if requested
        if fmt == "dataframe":
            log.debug("Converting result to DataFrame")
            # TODO(diego): Make sure parse method returns a consistent structure
            if isinstance(result, list):
                return pd.DataFrame(result)
            if isinstance(result, dict):
                return pd.DataFrame([result])
            if result is None or result == []:
                return pd.DataFrame()
            log.error("Cannot convert to DataFrame, unsupported type.")
            msg = f"Cannot convert to DataFrame: unsupported type {type(result)}"
            raise ValueError(msg)
        if fmt == "xml":
            log.debug("Converting result to XML")
            if isinstance(result, dict):
                return dicttoxml(result, custom_root="results", item_func=lambda _: "entry", attr_type=False)
            if isinstance(result, list):
                return dicttoxml(
                    {"item": result}, custom_root="results", item_func=lambda _: "entry", attr_type=False
                )
            log.error("Cannot convert to XML, unsupported type.")
            msg = f"Cannot convert to XML: unsupported type {type(result)}"
            raise ValueError(msg)
        # json (and any other format) returns the result unchanged.
        return result

    ##################
    # Methods to handle complex queries and making subqueries using METHODS
    ##################

    def _get_method_spec(self, **kwargs: Any) -> dict[str, Any]:
        method = kwargs.get("method")
        if method not in self.METHODS:
            msg = f"Unknown method '{method}'"
            raise ValueError(msg)
        option = kwargs.get("option")

        if option:
            return self.METHODS[method].get(option, {})
        return self.METHODS[method]

    def _prepare_params(self, query: str | dict | list, spec: dict, **overrides: Any) -> dict:
        """Validate types and defaults from spec["parameters"].

        - Applies defaults from ``spec["parameters"]`` for any key absent from the query.
        - If a value is a list and its name is in ``spec["group_queries"]``, joins it with
          ``spec["separator"]``.
        """
        params = {}
        separator = spec.get("separator", ",")

        for name, (_typ, default, is_id) in spec["parameters"].items():
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

    def _make_identifier(self, query: str | dict | list, spec: dict) -> str:
        """Build a unique identifier from is_id=True keys for use as a cache key."""
        keys = [k for k, (_, _, is_id) in spec["parameters"].items() if is_id]
        parts = [str(query[k]) for k in keys if k in query] if isinstance(query, dict) else [str(query)]
        return "_".join(parts)

    def initialize_method_parameters(
        self, query: str | dict | list, method: str, method_definition: dict, **kwargs: Any
    ) -> tuple:
        """Initialize HTTP method params and build query inputs."""
        if method not in method_definition:
            msg = (
                f"Method '{method}' is not defined in the method definition. Available methods: "
                f"{list(method_definition.keys())}"
            )
            raise ValueError(msg)

        option = kwargs.get("option") if "option" in kwargs else None

        method_info = method_definition.get(method, {})

        if option and option not in method_info:
            msg = (
                f"Option '{option}' is not valid for method '{method}'. Allowed options: {method_info.keys()}"
            )
            raise ValueError(msg)

        method_info = method_info.get(option, {}) if option else method_info

        http_method = method_info["http_method"]
        path_param = method_info["path_param"]
        parameters = method_info["parameters"]
        group_queries = method_info["group_queries"]
        separator = method_info.get("separator", ",")

        primary_keys = get_primary_keys(parameters)

        if not primary_keys:
            msg = f"No primary keys defined for method '{method}'. Please check the method definition."
            raise ValueError(msg)

        if len(primary_keys) > 1 and not isinstance(query, dict):
            msg = (
                f"Query must be a dictionary when multiple primary keys are defined for method '{method}'. "
                f"Received: {type(query)} with value {query}"
            )
            raise ValueError(msg)

        inputs = {}

        if isinstance(query, dict):
            if group_queries:
                for key in group_queries:
                    if key in query and isinstance(query[key], list):
                        inputs[key] = separator.join(query[key])
                        log.debug("Joined %s with separator '%s': %s", key, separator, inputs[key])
                    elif key in query:
                        inputs[key] = query.get(key, "")
                inputs.update({k: v for k, v in query.items() if k not in group_queries})
            else:
                inputs.update(query)
        elif isinstance(query, list):
            # Assume the list contains a single value or a list of values for the primary key
            if group_queries and primary_keys[0] in group_queries:
                inputs[primary_keys[0]] = separator.join(query)
            else:
                inputs[primary_keys[0]] = query
        elif isinstance(query, str):
            inputs[primary_keys[0]] = query
        else:
            msg = f"Unsupported query type: {type(query)}. Expected str, dict, or list."
            raise TypeError(msg)

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

    def decompose_query(self, query: dict, method: str, option: str | None) -> list[tuple[str, dict]] | None:
        """Decompose a query into multiple subqueries if any of the identity keys contain lists.

        Returns:
            List of (identifier, subquery) tuples or None if no decomposition is needed.

        """
        if method not in self.METHODS:
            msg = f"Method '{method}' is not supported. Available methods: {list(self.METHODS.keys())}"
            raise ValueError(msg)
        if option and option not in self.METHODS[method]:
            msg = (
                f"Option '{option}' is not valid for method '{method}'. Allowed options: "
                f"{self.METHODS[method].keys()}"
            )
            raise ValueError(msg)

        method_spec = self.METHODS[method].get(option, self.METHODS[method])
        param_spec = method_spec.get("parameters", {})
        group_queries = method_spec.get("group_queries", [])

        # Identify ID keys
        keys = [k for k, (_, _, is_id) in param_spec.items() if is_id and k in query]

        # If no keys are found in group_queries, return None
        if not any(k in group_queries for k in keys):
            return []  # No decomposition needed

        # Collect values for product
        value_combinations = list(
            itertools.product(*(query[k] for k in group_queries if k in query and isinstance(query[k], list)))
        )

        subqueries = []
        for combo in value_combinations:
            subquery = query.copy()
            identifier_parts = []

            # Set values from the group_queries
            for key, value in zip(group_queries, combo, strict=False):
                subquery[key] = value
                identifier_parts.append(str(value))

            identifier_parts.extend(str(query[key]) for key in keys if key not in group_queries)

            identifier = "_".join(identifier_parts)
            subqueries.append((identifier, subquery))

        return subqueries

    def get_matching_values(self, query: dict) -> list[str]:
        """Extract values from the subquery used to match items, per self.subquery_match_keys."""
        keys = self.get_subquery_match_keys()

        if not keys:
            keys = [k for k in query if k not in self.get_cache_ignore_keys()]

        return [str(query[k]).lower() for k in keys if k in query and query[k] is not None]

    def split_results_by_subquery(
        self, full_result: Any, subqueries: list[tuple[str, dict]]
    ) -> dict[str, list[dict]]:
        """Check if any subquery's values appear in each result using token-based partial matching.

        Returns a mapping {id_: [results]}.
        """
        if isinstance(full_result, dict):
            full_result = [full_result]
        elif not isinstance(full_result, list):
            msg = "Expected full_result to be a list of dicts"
            raise TypeError(msg)

        mapping = {identifier: [] for identifier, _ in subqueries}

        subquery_values = {}
        for identifier, query in subqueries:
            values = self.get_matching_values(query)
            norm = functools.reduce(
                operator.iadd, (_normalize_matching_tokens(value) for value in values), []
            )
            subquery_values[identifier] = norm

        for _i, item in enumerate(full_result):
            tokens = _extract_nested_values(item)
            item_tokens = set(_normalize_matching_tokens(tokens))

            for identifier, expected_tokens in subquery_values.items():
                # Match if there's any overlap
                if expected_tokens and (set(expected_tokens) & item_tokens):
                    mapping[identifier].append(item)

        return mapping

    def merge_dicts(self, dicts: list[dict]) -> dict:
        """Deep-merge a list of dicts, collecting conflicting values into lists."""
        merged = {}
        for d in dicts:
            for k, v in d.items():
                if k not in merged:
                    merged[k] = v
                # If already a list, append only if different
                elif isinstance(merged[k], list):
                    if v not in merged[k]:
                        merged[k].append(v)
                elif merged[k] != v:
                    merged[k] = [merged[k], v]
        return merged

    ###################
    # General-purpose fetch methods
    # These methods are used to fetch data from the API, either for a single query or
    # a batch of queries. They handle caching, parsing, and optional DataFrame conversion.
    ###################

    def fetch_single(
        self, query: str | dict | list, parse: bool = False, *args: Any, **kwargs: Any
    ) -> tuple[list | dict | pd.DataFrame | bytes | str, dict]:
        """General-purpose fetch method with optional parsing and cache handling.

        Args:
            query (Union[str, dict]): Query to fetch data for.
            parse (bool): Whether to parse the fetched data.
            *args: Positional arguments for subclass compatibility.
            **kwargs: Keyword arguments; notable keys: config_key, fields_to_extract, format, method, option.

        Returns:
            Tuple[Union[List, Dict, pd.DataFrame], Dict]: Fetched (and optionally parsed) data and metadata.

        """
        metadata = FetchMetadata()
        # Extract flags and avoid passing twice to _maybe_parse
        self._apply_default_option(kwargs)
        fmt = kwargs.pop("format", "json")
        method = kwargs.get("method", "NOT_GIVEN")
        option = kwargs.get("option")

        # Get method specification
        spec = self._get_method_spec(**kwargs)
        log.debug("Checking if multiple queries are supported")
        group_key = spec.get("group_queries", [None])[0]

        # If group_key is present and value is list: check cache per element
        metadata.started_at = datetime.now(UTC).isoformat()
        if isinstance(query, dict) and group_key and isinstance(query.get(group_key), list):
            log.debug("Multiple queries detected in the input.")
            log.debug("Generated a group of queries based on key '%s' with multiple values.", group_key)
            results = {}
            remaining = []
            subqueries = self.decompose_query(query, method, option) or []
            # Check cache per individual
            log.debug("Subqueries generated: %s", subqueries)
            for identifier, subq in subqueries:
                log.debug("Checking cache for identifier: %s", identifier)
                cache_key = self._make_cache_key(identifier, **kwargs)
                if self.has_results(cache_key):
                    log.debug("Cache hit for identifier: %s, loading from cache.", identifier)
                    metadata.cached_ids.append(identifier)
                    metadata.cached_subqueries.append(subq)
                    raw = self.load_cache(cache_key)
                    parsed = self._maybe_parse(data=raw, parse=parse, fmt=fmt, **kwargs)
                    results[identifier] = parsed
                else:
                    log.debug("No cache found for identifier: %s, will fetch.", identifier)
                    remaining.append((identifier, subq))

            # If some remain, fetch them together
            if remaining:
                log.debug("Fetching remaining %s subqueries in a single request.", len(remaining))
                metadata.fetched_ids = [identifier for identifier, _ in remaining]
                metadata.fetched_subqueries = [subq for _, subq in remaining]
                combined = self.merge_dicts([subq for _, subq in remaining])
                params = self._prepare_params(combined, spec, **kwargs)
                try:
                    full = self.fetch(params, *args, **kwargs)
                except RequestError:
                    log.exception("Request failed for method '%s'", method)
                    full = {}
                mapping = self.split_results_by_subquery(full, remaining) if full else {}
                for identifier, _ in remaining:
                    partial_result = mapping.get(identifier, [])
                    if not partial_result:
                        log.debug("No results found for identifier %s. Skipping.", identifier)
                        metadata.failed_ids.append(identifier)
                        continue
                    log.debug(
                        "Fetched %s items for identifier %s. Caching result.", len(partial_result), identifier
                    )
                    cache_key = self._make_cache_key(identifier, **kwargs)
                    self.save_cache(cache_key, partial_result)
                    parsed = self._maybe_parse(data=partial_result, parse=parse, fmt=fmt, **kwargs)
                    results[identifier] = parsed

            # Flatten the per-subquery results into a single structured view,
            # used for metadata (data_info / fetched_length)
            flat: list = []
            for data in results.values():
                if isinstance(data, list):
                    flat.extend(data)
                else:
                    flat.append(data)

            # Serialize the per-subquery results to the requested output format.
            if fmt == "dataframe":
                log.debug("Converting results to DataFrames")
                dfs = [d if isinstance(d, pd.DataFrame) else pd.DataFrame(d) for d in results.values()]
                export_data: Any = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
            elif fmt == "xml":
                log.debug("Converting results to XML format")
                export_data = dicttoxml(
                    {"item": flat},
                    custom_root="results",
                    item_func=lambda _: "entry",
                    attr_type=False,
                )
            else:
                export_data = list(results.values())
                if len(export_data) == 1:
                    export_data = export_data[0]

            metadata.fetched_length = len(flat)
            metadata.data_info = self._build_data_info(export_data if fmt == "dataframe" else flat)
            metadata.finished_at = datetime.now(UTC).isoformat()
            self._stamp_metadata(metadata, method=method, option=option)

            return export_data, metadata.to_dict()
        log.debug("Single query detected, proceeding with fetch.")
        params = self._prepare_params(query, spec, **kwargs)
        identifier = self._make_identifier(query, spec)
        cache_key = self._make_cache_key(identifier, **kwargs)
        if self.has_results(cache_key):
            log.debug("Cache hit for identifier: %s, loading from cache.", identifier)
            metadata.cached_ids = [identifier]
            metadata.cached_subqueries = [query]
            raw = self.load_cache(cache_key)
        else:
            # TODO(diego): Probably is necesary to give the user the option to not save empty results, check
            # if it is a problem in some APIs
            log.debug("No cache found for identifier: %s, fetching from API.", identifier)
            try:
                raw = self.fetch(params, *args, **kwargs)
            except RequestError:
                log.exception("Request failed for identifier %s", identifier)
                raw = {}
            # Save to cache even if empty, to avoid refetching known empty results
            metadata.fetched_ids = [identifier]
            metadata.fetched_subqueries = [query]
            metadata.fetched_length = len(raw) if isinstance(raw, list) else 1
            self.save_cache(cache_key, raw)
            if not raw:
                metadata.failed_ids = [identifier]

        parsed = self._maybe_parse(data=raw, parse=parse, fmt=fmt, **kwargs)

        metadata.data_info = self._build_data_info(parsed)
        metadata.finished_at = datetime.now(UTC).isoformat()
        self._stamp_metadata(metadata, method=method, option=option)

        return parsed, metadata.to_dict()

    def fetch_batch(
        self, queries: Sequence[str | dict], parse: bool = False, *args: Any, **kwargs: Any
    ) -> tuple[list | pd.DataFrame | bytes | str, dict]:
        """Fetch data in parallel for a batch of queries.

        Args:
            queries (List[Union[str, dict, list[str]]]): List of queries to fetch data for.
            parse (bool): Whether to parse the fetched data.
            *args: Positional arguments for subclass compatibility.
            **kwargs: Keyword arguments; notable keys: config_key, fields_to_extract, format, method, option.

        Returns:
            Tuple[Union[List, pd.DataFrame, bytes, str], Dict]: Fetched (and optionally parsed) data and
            metadata.

        """
        metadata = FetchMetadata()
        self._apply_default_option(kwargs)
        method = kwargs.get("method", "NOT_GIVEN")
        fmt = kwargs.pop("format", "json")
        option = kwargs.get("option")
        results: list[Any] = []

        # Separate queries in cache and not in cache
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
                # Only use the cache for this query if *every* subquery is cached.
                # If any subquery is missing we delegate the whole query to
                # fetch_single, which loads the cached subqueries and fetches only
                # the missing ones. Appending the cached subqueries here as well
                # would duplicate them (fetch_single returns them too).
                cached_subquery_results = []
                missing = False
                for identifier, _ in subqueries:
                    cache_key = self._make_cache_key(identifier, **kwargs)
                    if self.has_results(cache_key):
                        cached = self.load_cache(cache_key)
                        result = (
                            cached.to_dict(orient="records") if isinstance(cached, pd.DataFrame) else cached
                        )
                        cached_subquery_results.append((identifier, result))
                    else:
                        log.debug("No cache found for subquery identifier: %s, will fetch.", identifier)
                        missing = True
                        break

                if missing:
                    index_query_map[i] = query
                else:
                    for identifier, subquery in subqueries:
                        metadata.cached_ids.append(identifier)
                        metadata.cached_subqueries.append(subquery)
                    for _identifier, result in cached_subquery_results:
                        log.debug("Cache hit for subquery identifier: %s, loading from cache.", _identifier)
                        results.append(self._maybe_parse(data=result, parse=parse, fmt=fmt, **kwargs))

            else:
                # No subqueries, use the classic key
                cache_key = self._make_cache_key(query, **kwargs)
                if self.has_results(cache_key):
                    log.debug("Cache hit for query at index %s, loading from cache.", i)
                    metadata.cached_ids.append(cache_key)
                    metadata.cached_subqueries.append(query)
                    cached = self.load_cache(cache_key)
                    result = cached.to_dict(orient="records") if isinstance(cached, pd.DataFrame) else cached
                    results.append(self._maybe_parse(data=result, parse=parse, fmt=fmt, **kwargs))
                else:
                    log.debug("No cache found for query at index %s, will fetch.", i)
                    index_query_map[i] = query

        #############################
        # If all queries are cached, return the results
        # It's important to note that creating threads takes time, so if all queries are cached,
        # it's better to return the results directly.
        # If there is an incorrect cache key handling then it's better to do a better implementation
        #############################
        # Fetch missing ones in parallel
        metadata.started_at = datetime.now(UTC).isoformat()
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {
                executor.submit(self.fetch_single, query, parse, *args, **kwargs): i
                # Change it to index_query_map.items() if That part is needed
                for i, query in index_query_map.items()
            }
            for future, i in future_to_index.items():
                log.debug("Waiting for future result for query at index %s", i)
                metadata.fetched_ids.append(i)
                metadata.fetched_subqueries.append(index_query_map[i])
                try:
                    result = future.result()

                    if isinstance(result, tuple) and len(result) == 2:  # noqa: PLR2004  # (data, metadata) pair
                        data, _ = result
                        results.append(data)
                    else:
                        results.append(result)

                except Exception:
                    log.exception("Error fetching query at index %s (%s)", i, queries[i])
                self._delay()
        metadata.finished_at = datetime.now(UTC).isoformat()
        metadata.fetched_length = sum(len(r) if isinstance(r, list) else 1 for r in results)

        # If it's a list of dataframes, concatenate them
        if all(isinstance(r, pd.DataFrame) for r in results) and len(results) > 0:
            batch_data = pd.concat(results, ignore_index=True)
        else:
            batch_data = results

        metadata.data_info = self._build_data_info(batch_data)
        self._stamp_metadata(metadata, method=method, option=option)

        return batch_data, metadata.to_dict()

    ###################
    # Auxiliary methods
    ###################

    def _extract_fields(
        self, data: dict | list, fields_to_extract: list | dict | None = None, **kwargs: Any
    ) -> dict | list:
        """Extract specified fields from the data.

        Args:
            data (Union[List, Dict]): Data to parse.
            fields_to_extract (List|Dict): Fields to keep from the original response.
                - If List: Keep those keys.
                - If Dict: Maps {desired_name: real_field_name}.
            **kwargs: Supports `option` key to select a sub-section of fields_to_extract.

        Returns:
            Union[dict, list]: Data with only the specified fields.

        """
        option = kwargs.get("option", "default")

        if option and isinstance(fields_to_extract, dict) and option in fields_to_extract:
            fields_to_extract = fields_to_extract[option]

        parsed = {}
        if isinstance(fields_to_extract, list):
            if isinstance(data, list):
                parsed = [{key: get_nested(item, key) for key in fields_to_extract} for item in data]
            elif isinstance(data, dict):
                parsed = {key: get_nested(data, key) for key in fields_to_extract}
        elif isinstance(fields_to_extract, dict):
            if isinstance(data, list):
                parsed = [
                    {new_key: get_nested(item, path) for new_key, path in fields_to_extract.items()}
                    for item in data
                ]
            elif isinstance(data, dict):
                parsed = {new_key: get_nested(data, path) for new_key, path in fields_to_extract.items()}
        # If no fields to extract, return the entire structure
        elif fields_to_extract is None and isinstance(data, list):
            parsed = [get_nested(item, "") for item in data]
        elif fields_to_extract is None and isinstance(data, dict):
            parsed = get_nested(data, "")

        return parsed

    def _build_request(
        self,
        *,
        method: str,
        http_method: str,
        path_param: str | None,
        validated_params: dict,
        **kwargs: Any,
    ) -> Request:
        """Assemble the niquests ``Request`` for a fetch.

        Default implementation: ``f"{api_url}{method}{_METHOD_SUFFIX}"`` plus an
        optional path parameter, with the remaining validated params as the query
        string. ``api_url`` is taken from kwargs, falling back to
        ``DB_CONFIG.API_URL``. Subclasses override this to build API-specific URLs
        (path layouts, option suffixes, POST bodies, …) or set ``_METHOD_SUFFIX``.
        """
        api_url = kwargs.get("api_url") or (self.DB_CONFIG.API_URL if self.DB_CONFIG else None)
        if not api_url:
            msg = "API URL must be provided in kwargs or via DB_CONFIG."
            raise ValueError(msg)

        url = f"{api_url}{method}{self._METHOD_SUFFIX}"
        if path_param:
            url += f"{validated_params.pop(path_param)}"

        return Request(method=http_method, url=url, params=validated_params)

    @staticmethod
    def _unwrap_envelope(data: Any, *keys: str) -> Any:
        """Return the first present envelope key's value from a dict, else ``data``."""
        if isinstance(data, dict):
            for key in keys:
                if key in data:
                    return data[key]
        return data

    @staticmethod
    def _append_path_params(url: str, path_param: Any, validated_params: dict) -> str:
        """Append ``/``-prefixed path segment(s) for a str or list ``path_param``.

        Shared by the PRIDE/PDB ``_build_request`` overrides. Not used by the
        default ``_build_request`` (whose scalar branch omits the leading slash).
        """
        if not path_param:
            return url
        if isinstance(path_param, list):
            return (
                url
                + "/"
                + "/".join(
                    str(validated_params.pop(param)) for param in path_param if param in validated_params
                )
            )
        return url + f"/{validated_params.pop(path_param)}"

    def _unwrap_response(self, data: Any, **_kwargs: Any) -> Any:
        """Shape a parsed JSON response by unwrapping ``_RESPONSE_ENVELOPE_KEYS``."""
        return self._unwrap_envelope(data, *self._RESPONSE_ENVELOPE_KEYS)

    def _do_request(self, query: str | dict | list, *, method: str, **kwargs: Any) -> Response:
        """Run a validated HTTP request and return the raw response.

        Args:
            query (Union[str, dict, list]): Query to fetch data for.
            method (str): Method to use for fetching data.
            **kwargs: Forwarded to ``_build_request`` (e.g. ``api_url``, ``option``).

        Returns:
            Response: The raw HTTP response from the API.

        Raises:
            ValueError: If the method or parameters are invalid.
            RequestError: If the HTTP request fails. Raised instead of silently
                returning an empty result so callers can distinguish a failed
                request from a successful empty response.

        """
        http_method, path_param, parameters, inputs = self.initialize_method_parameters(
            query, method, self.METHODS, **kwargs
        )

        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError as e:
            msg = f"Invalid parameters for method '{method}': {e}"
            raise ValueError(msg) from e

        req = self._build_request(
            method=method,
            http_method=http_method,
            path_param=path_param,
            validated_params=validated_params,
            **kwargs,
        )
        prepared = self.session.prepare_request(req)
        log.debug("Prepared request: %s", prepared.url)

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()
        except RequestException as e:
            log.exception("Error fetching %s for method '%s'", query, method)
            msg = f"Request failed for method '{method}': {e}"
            raise RequestError(msg) from e
        else:
            return response

    def fetch(self, query: str | dict | list, *, method: str, **kwargs: Any) -> Any:
        """Fetch and shape data via the standard request template.

        Runs ``_do_request`` (validate → build → send → raise) and passes the
        parsed JSON through ``_unwrap_response``. Interfaces customise behaviour
        by overriding ``_build_request`` / ``_unwrap_response``; outliers with
        non-standard flows (pagination, SOAP, Entrez, text payloads) override
        ``fetch`` directly.
        """
        self._apply_default_option(kwargs)
        response = self._do_request(query, method=method, **kwargs)
        return self._unwrap_response(response.json(), method=method, **kwargs)

    def parse(self, data: Any, fields_to_extract: list | dict | None, **kwargs: Any) -> Any:
        """Parse raw API response into the requested format.

        Default implementation: guard the input type (unwrapping a niquests
        ``Response`` into JSON) and delegate field extraction to
        ``_extract_fields``. Subclasses with response-specific shaping override
        this method.

        Args:
            data (Any): Raw data from the API response (dict, list or Response).
            fields_to_extract (list|dict|None): Fields to keep from the original
                response.
                - If list: Keep those keys.
                - If dict: Maps {desired_name: real_field_name}.
            **kwargs: Forwarded to ``_extract_fields`` (e.g. `option`).

        Returns:
            Any: Parsed data with only the specified fields.

        """
        if not data:
            log.warning("Tried to parse data but the data is empty or None.")
            return {}

        if isinstance(data, Response):
            data = data.json()

        if not isinstance(data, (dict, list)):
            log.error(
                "Tried to parse data but the type is not supported. "
                "Expected a dict, list or niquests.Response object."
            )
            return {}

        return self._extract_fields(data, fields_to_extract, **kwargs)

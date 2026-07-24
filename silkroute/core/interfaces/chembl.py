"""ChEMBL API interface."""

import math
import re
from typing import Any, ClassVar
from urllib.parse import urlencode

import niquests

from silkroute.constants.databases import CHEMBL
from silkroute.core.utils.base_auxiliary_methods import validate_parameters
from silkroute.core.workflow.chembl_query_catalog import (
    OPERATOR_SUFFIXES,
    get_chembl_query_builder_field_catalog,
)
from silkroute.core.workflow.query_interpreter import normalize_standard_units
from silkroute.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("silkroute.interfaces.chembl")

CHEMBL_DEFAULT_PAGE_SIZE = 1000

# Methods whose URL is built without a page-size parameter; every other method in
# METHODS pages, so the effective default page size belongs in its cache key.
_CHEMBL_UNPAGED_METHODS = {"substructure", "similarity"}

# Reverse of OPERATOR_SUFFIXES ("__gte" -> "gte"), longest suffix first so
# "__gte" wins over a would-be "__gt" prefix when splitting a param key.
_OPERATOR_BY_SUFFIX = tuple(
    sorted(
        ((suffix, operator) for operator, suffix in OPERATOR_SUFFIXES.items() if suffix),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)

# Envelope keys whose list value holds the paginated records, in priority order.
_PAGINATED_LIST_KEYS = ("activities", "binding_sites", "molecules", "targets", "assays")


def _extract_chembl_records(data: Any) -> list:
    """Pull the record list out of one ChEMBL page (the page itself if not enveloped)."""
    for key in _PAGINATED_LIST_KEYS:
        if isinstance(data, dict) and isinstance(data.get(key), list):
            return data[key]
    return [data]


def _next_chembl_page(data: Any) -> str | None:
    """Return the absolute URL of the next ChEMBL page, or None when exhausted."""
    next_path = data.get("page_meta", {}).get("next") if isinstance(data, dict) else None
    return f"https://www.ebi.ac.uk{next_path}" if next_path else None


def _chembl_page_meta(data: Any) -> Any:
    """Return the ChEMBL page metadata of one parsed page, or an empty dict."""
    page_meta = data.get("page_meta") if isinstance(data, dict) else None
    return page_meta if isinstance(page_meta, dict) else {}


def _chembl_response_page_size_from_data(data: Any) -> int | None:
    """Return the ChEMBL response page size from page metadata, when valid."""
    try:
        limit = int(_chembl_page_meta(data).get("limit"))
    except (TypeError, ValueError):
        return None
    return limit if limit > 0 else None


def _chembl_total_pages_from_data(data: Any) -> int | None:
    """Return the ChEMBL API total page count from page metadata, when valid."""
    limit = _chembl_response_page_size_from_data(data)
    if limit is None:
        return None
    try:
        total_count = int(_chembl_page_meta(data).get("total_count"))
    except (TypeError, ValueError):
        return None
    if total_count < 0:
        return None
    return math.ceil(total_count / limit)


class _ChEMBLPageExtractor:
    """Extract page records, reporting first-page page-size details once."""

    def __init__(self, requested_page_size: int) -> None:
        self.requested_page_size = requested_page_size
        self.first_page_seen = False

    def __call__(self, data: Any) -> list:
        """Return the records of one page, logging page-size details for the first."""
        records = _extract_chembl_records(data)
        if not self.first_page_seen:
            self.first_page_seen = True
            self._log_first_page(data, records)
        return records

    def _log_first_page(self, data: Any, page_records: list) -> None:
        """Log first-page ChEMBL page-size details and warn if the API lowers it."""
        response_page_size = _chembl_response_page_size_from_data(data)
        log.debug(
            "ChEMBL first page: requested_page_size=%s, response_page_size=%s, records=%s",
            self.requested_page_size,
            response_page_size,
            len(page_records),
        )
        if response_page_size is not None and response_page_size != self.requested_page_size:
            log.warning(
                "ChEMBL API returned page size %s after requesting %s",
                response_page_size,
                self.requested_page_size,
            )


def _chembl_cache_kwargs_with_page_size(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Ensure ChEMBL cache keys include the effective default page size."""
    if kwargs.get("method") in _CHEMBL_UNPAGED_METHODS or "limit" in kwargs:
        return kwargs
    updated = dict(kwargs)
    updated["limit"] = CHEMBL_DEFAULT_PAGE_SIZE
    return updated


# For the moment, only activity is necessary, but more methods can be added later.

# The main methods that are used in the webUI version of ChEMBL are 'Target', 'Assay', 'Cell Line' and
# 'Molecule'.
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
    """ChEMBL bioactivity database API interface."""

    API_NAME = "ChEMBL"
    DB_CONFIG = CHEMBL
    METHODS: ClassVar[dict[str, Any]] = {
        "target": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "query": (str, None, True),
                "filters": (list, None, True),
                "format": (str, "json", False),
            },
            "group_queries": [None],
            "separator": None,
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
            "separator": None,
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
            "separator": None,
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
            "separator": None,
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
            "separator": None,
        },
        "binding_site": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "target_chembl_id": (str, None, True),
                "format": (str, "json", False),
            },
            "group_queries": [None],
            "separator": None,
        },
        "substructure": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "query": (str, None, True),
            },
            "group_queries": [None],
            "separator": None,
        },
        "similarity": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "query": (str, None, True),
                "cutoff": (int, 80, True),
            },
            "group_queries": [None],
            "separator": None,
        },
        "activity-search": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "query": (str, None, True),
            },
            "group_queries": [None],
            "separator": None,
        },
        "target-search": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "query": (str, None, True),
            },
            "group_queries": [None],
            "separator": None,
        },
    }

    def get_cache_ignore_keys(self) -> set[str]:
        """Return ChEMBL cache-ignore keys while preserving pagination in cache keys."""
        return super().get_cache_ignore_keys() - {"pages_to_fetch"}

    def _make_cache_key(self, input_obj: str | dict | list, **kwargs: Any) -> str:
        """Build a cache key that includes ChEMBL's effective page size."""
        return super()._make_cache_key(input_obj, **_chembl_cache_kwargs_with_page_size(kwargs))

    def _is_activity_spec(self, spec: dict) -> bool:
        """Return whether ``spec`` is the open flat-parameter ``activity`` method."""
        return spec is self.METHODS.get("activity")

    def _prepare_params(self, query: str | dict | list, spec: dict, **overrides: Any) -> dict:
        """Prepare request params, preserving activity's catalog-defined flat filters.

        The base implementation keeps only keys declared in ``spec["parameters"]``.
        The activity endpoint accepts an open set of catalog filter fields (with
        operator suffixes), so those extra dict keys are carried through and later
        validated against the query catalog in :meth:`fetch`.
        """
        params = super()._prepare_params(query, spec, **overrides)
        if self._is_activity_spec(spec) and isinstance(query, dict):
            for key, value in query.items():
                params.setdefault(key, value)
        return params

    def _make_identifier(self, query: str | dict | list, spec: dict) -> str:
        """Build a cache identifier, keying activity on its full flat filter set.

        Activity filters live outside ``spec``'s ``is_id`` keys, so the base
        identifier would collide across distinct filter combinations; key on the
        whole query dict instead.
        """
        if self._is_activity_spec(spec) and isinstance(query, dict):
            return "_".join(f"{key}={query[key]}" for key in sorted(query))
        return super()._make_identifier(query, spec)

    @staticmethod
    def _parse_filter_number(value: str) -> float | None:
        """Parse a numeric ChEMBL activity filter value."""
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_filter_number(value: float | None) -> str | None:
        """Format a numeric activity filter value for a URL parameter."""
        if value is None:
            return None
        if float(value).is_integer():
            return str(int(value))
        return str(value)

    @classmethod
    def extract_ic50_activity_filter(cls, query: object) -> dict[str, Any] | None:
        """Extract an IC50 activity filter from an interpreted ChEMBL query.

        The workflow interpreter emits IC50 searches as standard_type plus
        standard_value comparisons. The legacy ic50 comparison form is also
        recognized so cached or direct interface use can still be guarded.
        """
        if not isinstance(query, str):
            return None

        query_text = query.strip()
        if not query_text:
            return None

        standard_type_is_ic50 = bool(
            re.search(
                r"\bstandard_type\s*[:=]\s*['\"]?IC50['\"]?(?=\s|$|\))", query_text, flags=re.IGNORECASE
            )
        )
        uses_ic50_macro = bool(re.search(r"\bic50\s*(?:[:=<>]|>=|<=)", query_text, flags=re.IGNORECASE))
        if not standard_type_is_ic50 and not uses_ic50_macro:
            return None

        number_pattern = r"([-+]?\d+(?:\.\d+)?)"
        activity_filter: dict[str, Any] = {
            "standard_type": "IC50",
            "standard_value_min": None,
            "standard_value_max": None,
            "standard_units": None,
            "standard_value_min_inclusive": False,
            "standard_value_max_inclusive": False,
        }

        if re.search(
            r"\bstandard_units\s*[:=]\s*(?=$|\b(?:AND|OR)\b|\))",
            query_text,
            flags=re.IGNORECASE,
        ):
            msg = "standard_units must be a non-empty value."
            raise ValueError(msg)

        units_match = re.search(
            r"\bstandard_units\s*[:=]\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s()]+))",
            query_text,
            flags=re.IGNORECASE,
        )
        if units_match:
            units_value = next((value for value in units_match.groups() if value is not None), "")
            activity_filter["standard_units"] = normalize_standard_units(units_value)

        range_match = re.search(
            rf"\b(?:ic50|standard_value)\s*:\s*{number_pattern}\s*-\s*{number_pattern}\b",
            query_text,
            flags=re.IGNORECASE,
        )
        if range_match:
            activity_filter["standard_value_min"] = cls._parse_filter_number(range_match.group(1))
            activity_filter["standard_value_max"] = cls._parse_filter_number(range_match.group(2))

        comparison_pattern = re.compile(
            rf"\b(?:ic50\s*:?|standard_value)\s*(>=|<=|>|<|=)\s*{number_pattern}",
            flags=re.IGNORECASE,
        )
        for match in comparison_pattern.finditer(query_text):
            operator = match.group(1)
            number = cls._parse_filter_number(match.group(2))
            if number is None:
                continue
            if operator in {">", ">="}:
                activity_filter["standard_value_min"] = number
                activity_filter["standard_value_min_inclusive"] = operator == ">="
            elif operator in {"<", "<="}:
                activity_filter["standard_value_max"] = number
                activity_filter["standard_value_max_inclusive"] = operator == "<="
            elif operator == "=":
                activity_filter["standard_value"] = number

        if not range_match:
            exact_macro_match = re.search(
                rf"\bic50\s*:\s*{number_pattern}(?!\s*-)",
                query_text,
                flags=re.IGNORECASE,
            )
            if exact_macro_match:
                activity_filter["standard_value"] = cls._parse_filter_number(exact_macro_match.group(1))

        return activity_filter

    @classmethod
    def build_activity_filter_params(
        cls, activity_filter: dict[str, Any], limit: int | None
    ) -> dict[str, Any]:
        """Build ChEMBL activity endpoint query parameters from an activity filter."""
        params: dict[str, Any] = {
            "standard_type": activity_filter["standard_type"],
            "format": "json",
        }
        if limit is not None:
            params["limit"] = limit
        if activity_filter.get("standard_units") is not None:
            params["standard_units"] = activity_filter["standard_units"]

        exact_value = activity_filter.get("standard_value")
        if exact_value is not None:
            params["standard_value"] = cls._format_filter_number(exact_value)
            return params

        min_value = activity_filter.get("standard_value_min")
        max_value = activity_filter.get("standard_value_max")
        if min_value is not None:
            min_key = (
                "standard_value__gte"
                if activity_filter.get("standard_value_min_inclusive")
                else "standard_value__gt"
            )
            params[min_key] = cls._format_filter_number(min_value)
        if max_value is not None:
            max_key = (
                "standard_value__lte"
                if activity_filter.get("standard_value_max_inclusive")
                else "standard_value__lt"
            )
            params[max_key] = cls._format_filter_number(max_value)
        return params

    @staticmethod
    def _split_activity_param_key(key: str) -> tuple[str, str]:
        """Split an activity flat-param key into its (field, operator) pair.

        Bare keys map to the ``exact`` operator; suffixed keys such as
        ``standard_value__lte`` map to ``(standard_value, lte)``.
        """
        for suffix, operator in _OPERATOR_BY_SUFFIX:
            if key.endswith(suffix):
                return key[: -len(suffix)], operator
        return key, "exact"

    @classmethod
    def _validate_activity_flat_params(cls, inputs: dict) -> dict:
        """Validate flat ChEMBL activity params against the query catalog.

        Accepts every catalog activity field with the operator suffixes that field
        allows (e.g. ``standard_type``, ``standard_value__lte``, ``pchembl_value__gte``);
        ``format`` passes through as a control parameter.

        Raises:
            ValueError: If a field is unknown or an operator is not allowed for it.

        """
        fields = get_chembl_query_builder_field_catalog("activity")
        validated = {}
        for key, value in inputs.items():
            if key == "format":
                validated[key] = value
                continue
            field, operator = cls._split_activity_param_key(key)
            if field not in fields:
                msg = f"Unknown ChEMBL activity field '{field}'."
                raise ValueError(msg)
            if operator not in fields[field].allowed_operators:
                msg = f"Operator '{operator}' is not allowed for ChEMBL activity field '{field}'."
                raise ValueError(msg)
            validated[key] = value
        validated.setdefault("format", "json")
        return validated

    def fetch(self, query: str | dict | list, *, method: str = "activity", **kwargs: Any) -> list:
        """Fetch data from the ChEMBL API.

        Args:
            query (str | dict | list): Query string or structured query to search for.
            method (str): Method to use for the request. Default is "activity".
            **kwargs: Additional parameters; notable keys: ``pages_to_fetch``, ``limit``.

        Returns:
            dict | list: Response from the API.

        """
        pages_to_fetch = kwargs.get("pages_to_fetch", 1)
        limit = kwargs.get("limit")
        if limit is None:
            limit = CHEMBL_DEFAULT_PAGE_SIZE
        try:
            pages_to_fetch = int(pages_to_fetch)
        except (TypeError, ValueError):
            log.exception("pages_to_fetch must be -1 or a positive integer. Received: %s", pages_to_fetch)
            return []
        # Bounds (0 / <-1) are enforced by _fetch_paginated, which every path below routes through.

        # Validate method and format
        if method not in self.METHODS:
            log.error(
                "Method %s is not supported. Supported methods are: %s.",
                method,
                ", ".join(self.METHODS.keys()),
            )
            return []

        if not isinstance(query, (str, dict)):
            log.error("Query must be a string or a dictionary.")
            return []

        _, _, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        # Validate and clean parameters. Activity accepts catalog-defined flat
        # filters (field + operator suffix), so it validates against the query
        # catalog instead of the rigid per-key schema used by other methods.
        try:
            if method == "activity":
                validated_params = self._validate_activity_flat_params(inputs)
            else:
                validated_params = validate_parameters(inputs, parameters)
        except (TypeError, ValueError):
            log.exception("Invalid parameters for method '%s'", method)
            return []

        configured_endpoint = method
        if method in ["activity", "binding_site"]:
            # Convert dictionary to a query string
            query = "&".join(f"{key}={value}" for key, value in validated_params.items())
            query += f"&limit={limit}"

            # Generate url
            url = f"{CHEMBL.API_URL}{method}?{query}"
        elif method in ["substructure", "similarity"]:
            query = "/".join(f"{value}" for _, value in validated_params.items())
            url = f"{CHEMBL.API_URL}{method}/{query}?format=json"
        elif method in ["target", "assay", "cell_line", "molecule"]:
            if "query" in validated_params:
                query_str = validated_params.pop("query")
                url = f"{CHEMBL.API_URL}{method}/search.json?limit={limit}&q={query_str}"
            else:
                url = f"{CHEMBL.API_URL}{method}?"
                if self.validate_filter_rules(validated_params["filters"]):
                    query_str = "&".join(
                        f"{item['field']}__{item['filter_type']}={item['value']}"
                        for item in validated_params["filters"]
                    )
                    url += f"{query_str}&limit={limit}&format=json"
        elif method in ["activity-search", "target-search"]:
            query_str = validated_params.get("query", "")
            activity_filter = (
                self.extract_ic50_activity_filter(query_str) if method == "activity-search" else None
            )
            if activity_filter:
                filter_params = self.build_activity_filter_params(activity_filter, limit)
                url = f"{CHEMBL.API_URL}activity.json?{urlencode(filter_params)}"
                configured_endpoint = "activity"
            else:
                url = (
                    f"{CHEMBL.API_URL}{method.replace('-', '/')}.json"
                    f"?limit={limit}&q={query_str.replace(' ', '%20')}"
                )
        else:
            log.error("Method %s is not implemented in fetch.", method)
            return []

        log.debug(
            "ChEMBL request configuration: endpoint=%s, page_size=%s, pages_to_fetch=%s",
            configured_endpoint,
            limit,
            pages_to_fetch,
        )
        return self._fetch_paginated(
            url,
            next_link=_next_chembl_page,
            extract_records=_ChEMBLPageExtractor(limit),
            pages_to_fetch=pages_to_fetch,
            total_pages_from_data=_chembl_total_pages_from_data,
            log_progress=True,
        )

    def validate_filter_rules(self, filters: dict) -> bool:
        """Validate filter rules based on predefined rules.

        Args:
            filters (dict): Filters to validate.

        Returns:
            bool: True if all filters are valid, False otherwise.

        """
        allowed_filter_types = {
            "exact",
            "iexact",
            "contains",
            "icontains",
            "startswith",
            "istartswith",
            "iendswith",
            "iregex",
            "gt",
            "gte",
            "lt",
            "lte",
            "range",
            "in",
            "isnull",
        }

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
                    log.error("Filter is missing required key '%s'.", key)
                    return False

            # Validate types
            if not isinstance(item["field"], str):
                log.error("Filter 'field' must be a string, got %s.", type(item["field"]).__name__)
                return False

            if not isinstance(item["value"], (str, int, float)):
                log.error("Filter 'value' must be a string or number, got %s.", type(item["value"]).__name__)
                return False

            if not isinstance(item["filter_type"], str) or item["filter_type"] not in allowed_filter_types:
                log.error(
                    "Filter 'filter_type' is not valid: %s. Allowed: %s",
                    item["filter_type"],
                    sorted(allowed_filter_types),
                )
                return False

        return True

    def parse(self, data: Any, fields_to_extract: list | dict | None, **_kwargs: Any) -> dict | list:
        """Parse the response from the ChEMBL API.

        Args:
            data (Any): Raw data from the API response.
            fields_to_extract (list | dict | None): Fields to keep from the original response.
                - If list: Keep those keys.
                - If dict: Maps ``{desired_name: real_field_name}``.
            **_kwargs: Additional keyword arguments (unused).

        Returns:
            dict | list: Parsed response.

        """
        if not data:
            log.warning("Tried to parse data but the data is empty or None.")
            return {}

        if isinstance(data, niquests.models.Response):
            data = data.json()
        elif not isinstance(data, (dict, list)):
            log.error(
                "Tried to parse data but the type is not supported. Response should be a dict or a list."
            )
            return {}

        return self._extract_fields(data, fields_to_extract)

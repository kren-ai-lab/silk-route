"""ChEMBL API interface."""

import re
from http import HTTPStatus
from typing import Any, ClassVar
from urllib.parse import urlencode

import requests

from bioseq_dl.constants.databases import CHEMBL
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.chembl")

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

        range_match = re.search(
            rf"\b(?:ic50|standard_value)\s*:\s*{number_pattern}\s*-\s*{number_pattern}\b",
            query_text,
            flags=re.IGNORECASE,
        )
        if range_match:
            activity_filter["standard_value_min"] = cls._parse_filter_number(range_match.group(1))
            activity_filter["standard_value_max"] = cls._parse_filter_number(range_match.group(2))

        comparison_pattern = re.compile(
            rf"\b(?:ic50|standard_value)\s*(>=|<=|>|<|=)\s*{number_pattern}",
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

    # DEPRECATED - Use validate_parameters instead
    def validate_query(self, method: str, query: dict) -> None:  # noqa: ARG002  # deprecated; signature kept
        """Validate the query parameters.

        Args:
            method (str): The method to validate against.
            query (dict): The query parameters to validate.

        Raises:
            ValueError: If the query parameters are invalid.

        """
        # TODO(diego): Add more validation rules based on the method and query structure.
        rules = {
            "target_chembl_id": lambda v: isinstance(v, str) and v.strip() != "",
            "pchembl_value": lambda v: isinstance(v, (int, float)),
        }

        for key, check in rules.items():
            if key in query and not check(query[key]):
                if key == "target_chembl_id":
                    log.error(
                        "Invalid target_chembl_id: %s. It should be a non-empty string.",
                        query["target_chembl_id"],
                    )
                    return
                if key == "pchembl_value":
                    log.error(
                        "Invalid pchembl_value: %s. It should be a number (int or float).",
                        query["pchembl_value"],
                    )
                    return
        return

    def fetch_pages(self, next_url: str, method: str, pages_to_fetch: int = 1) -> dict | list:
        """Fetch the next page of results from the ChEMBL API.

        Args:
            next_url (str): The URL for the next page of results.
            method (str): The method used for the initial request.
            pages_to_fetch (int): Number of pages to fetch. Default is 1. If -1, fetch all pages.

        Returns:
            dict: The fetched data from the next page.

        """
        responses = []
        if pages_to_fetch == 0 or pages_to_fetch < -1:
            log.error("pages_to_fetch must be -1 or a positive integer. Received: %s", pages_to_fetch)
            return {}

        current_url = next_url
        pages_remaining = pages_to_fetch

        while current_url:
            page_label = f"{pages_remaining} (all pages)" if pages_remaining == -1 else str(pages_remaining)
            log.debug(
                "Fetching page: %s for method %s with pages_to_fetch=%s", current_url, method, page_label
            )
            log.info(
                "Fetching page: %s for method %s with pages_to_fetch=%s", current_url, method, page_label
            )

            try:
                response = self.session.get(current_url, headers={"Content-Type": "application/json"})
                self._delay()
                response.raise_for_status()

                if response.status_code == HTTPStatus.NO_CONTENT:
                    log.warning("No content returned for URL %s.", current_url)
                    break

                data = response.json()
            except requests.exceptions.RequestException:
                log.exception("Error fetching page for method %s", method)
                break

            if "activities" in data and isinstance(data["activities"], list):
                responses.extend(data["activities"])
            elif "binding_sites" in data and isinstance(data["binding_sites"], list):
                responses.extend(data["binding_sites"])
            elif "molecules" in data and isinstance(data["molecules"], list):
                responses.extend(data["molecules"])
            elif "targets" in data and isinstance(data["targets"], list):
                responses.extend(data["targets"])
            elif "assays" in data and isinstance(data["assays"], list):
                responses.extend(data["assays"])
            else:
                responses.append(data)

            if pages_remaining > 0:
                pages_remaining -= 1
                if pages_remaining == 0:
                    break

            next_path = data.get("page_meta", {}).get("next") if isinstance(data, dict) else None
            if not next_path:
                break
            current_url = "https://www.ebi.ac.uk" + next_path

        return responses

    def fetch(self, query: str | dict | list, *, method: str = "activity", **kwargs: Any) -> dict | list:
        """Fetch data from the ChEMBL API.

        Args:
            query (str): Query string to search for.
            method (str): Method to use for the request. Default is "activity".
            **kwargs: Additional parameters; notable keys: pages_to_fetch, limit.

        Returns:
            any: response from the API.

        """
        pages_to_fetch = kwargs.get("pages_to_fetch", 1)
        limit = kwargs.get("limit")
        try:
            pages_to_fetch = int(pages_to_fetch)
        except (TypeError, ValueError):
            log.exception("pages_to_fetch must be -1 or a positive integer. Received: %s", pages_to_fetch)
            return {}
        if pages_to_fetch == 0 or pages_to_fetch < -1:
            log.error("pages_to_fetch must be -1 or a positive integer. Received: %s", pages_to_fetch)
            return {}

        # Validate method and format
        if method not in self.METHODS:
            log.error(
                "Method %s is not supported. Supported methods are: %s.",
                method,
                ", ".join(self.METHODS.keys()),
            )
            return {}

        if not isinstance(query, (str, dict)):
            log.error("Query must be a string or a dictionary.")
            return {}

        _, _, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError:
            log.exception("Invalid parameters for method '%s'", method)
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
                url = (
                    f"{CHEMBL.API_URL}{method}/search.json"
                    f"?limit={limit if limit is not None else 20}&q={query_str}"
                )
            else:
                url = f"{CHEMBL.API_URL}{method}?"
                if self.validate_filter_rules(validated_params["filters"]):
                    query_str = "&".join(
                        f"{item['field']}__{item['filter_type']}={item['value']}"
                        for item in validated_params["filters"]
                    )
                    url += query_str
                    url += f"limit={limit if limit is not None else 20}&format=json"
        elif method in ["activity-search", "target-search"]:
            query_str = validated_params.get("query", "")
            activity_filter = (
                self.extract_ic50_activity_filter(query_str) if method == "activity-search" else None
            )
            if activity_filter:
                filter_params = self.build_activity_filter_params(
                    activity_filter, limit if limit is not None else 20
                )
                url = f"{CHEMBL.API_URL}activity.json?{urlencode(filter_params)}"
            else:
                url = (
                    f"{CHEMBL.API_URL}{method.replace('-', '/')}.json"
                    f"?limit={limit if limit is not None else 20}&q={query_str.replace(' ', '%20')}"
                )
        else:
            log.error("Method %s is not implemented in fetch.", method)
            return {}

        return self.fetch_pages(url, method, pages_to_fetch)

    def validate_filter_rules(self, filters: dict) -> bool:
        """Validate filter rules based on predefined rules.

        Args:
            filters (Dict): Filters to validate.

        Returns:
            bool: True if all filters are valid, False otherwise.

        """
        allowed_filter_types = {
            "iexact",
            "gte",
            "lte",
            "icontains",
            "istartswith",
            "iendswith",
            "iregex",
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
            fields_to_extract (List|Dict): Fields to keep from the original response.
                - If List: Keep those keys.
                - If Dict: Maps {desired_name: real_field_name}.
            **kwargs: Additional keyword arguments.

        Returns:
            dict: Parsed response.

        """
        if not data:
            log.warning("Tried to parse data but the data is empty or None.")
            return {}

        if isinstance(data, requests.models.Response):
            data = data.json()
        elif not isinstance(data, (dict, list)):
            log.error(
                "Tried to parse data but the type is not supported. Response should be a dict or a list."
            )
            return {}

        return self._extract_fields(data, fields_to_extract)

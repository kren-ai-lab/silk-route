"""KEGG API interface."""

import re
from typing import Any

import requests

from bioseq_dl.constants.databases import KEGG
from bioseq_dl.constants.kegg import DATABASES, METHOD_OPTIONS
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.kegg")

# More info about KEGG API: https://www.kegg.jp/kegg/rest/keggapi.html
# TODO Solve known problem with KEGG API:
# For the queries that have more than one search like
# ["hsa:10458", "ece:Z5100"] It saves in cache a response for both entries
# But if you try to fetch only one of them, it saves another cache file.
# What it should do is to get the response from the cache file
# and return it without saving another cache file.

# TODO Should I make the method query for multiple entries or do one entry at a time?
# Doing multiple entries at a time is more efficient, but it requires more complex coding.


class KEGGInterface(BaseAPIInterface):
    """KEGG pathway and compound database API interface."""

    API_NAME = "KEGG"
    DB_CONFIG = KEGG
    # TODO add more methods from KEGG API. DDI and Link should be added.
    METHODS = {
        "get": {
            "http_method": "GET",
            "path_param": DATABASES,
            "parameters": {
                "entries": (str, None, True),
                "db": (str, None, False),
                "option": (str, None, False),
            },
            "group_queries": ["entries"],
            "separator": "+",
        },
        "link": {
            "http_method": "GET",
            "path_param": DATABASES,
            "parameters": {"entries": (str, None, True), "db": (str, None, False)},
            "group_queries": ["entries"],
            "separator": "+",
        },
        "pathways": {
            "http_method": "GET",
            "path_param": [],
            "parameters": {"entries": (str, None, True)},
            "group_queries": ["entries"],
            "separator": "+",
        },
    }

    def get_subquery_match_keys(self) -> set[str]:
        """Return keys used to match subqueries across KEGG results."""
        return super().get_subquery_match_keys().union({"entries"})

    def validate_query(self, method: str, query: dict) -> None:
        """Validate the query parameters.

        Args:
            method (str): The method to validate against.
            query (Union[str, tuple, dict]): The query parameters to validate.

        Raises:
            ValueError: If the query parameters are invalid.

        """
        rules = {
            "entries": lambda v: isinstance(v, (str, list)),
            "db": lambda v: v in DATABASES,
            "option": lambda v: v in METHOD_OPTIONS.get(method, []),
        }

        for key, check in rules.items():
            if key in query and not check(query[key]):
                if key == "entries":
                    log.error(f"Invalid entries: {query['entries']}. Must be a string or a list of strings.")
                    return {}
                if key == "db":
                    log.error(
                        f"Invalid database type: {query['db']}. Valid types are: {', '.join(DATABASES)}."
                    )
                    return {}
                if key == "option":
                    log.error(
                        f"Invalid option: {query['option']} for method {method}. Supported options are: {', '.join(METHOD_OPTIONS.get(method, []))}."
                    )
                    return {}
        return None

    def fetch(self, query: str | dict | list, *, method: str = "get", **kwargs: Any) -> dict | list | str:
        """Fetch data from the KEGG API.

        Args:
            query (str): Query string to search for.
            method (str): Method to use for the request. Used methods are
                'info', 'list', 'find', 'get', 'conv', 'link', 'ddi'.
            **kwargs: Additional parameters for the request.
            - `database`: Database to use for the request. Used databases are
                'pathway', 'brite', 'module', 'genome', 'compound',
                'glycan', 'reaction', 'enzyme', 'network', 'disease',
                'drug', 'genes', 'ligand', 'kegg'.
            - `option`: Additional options for the request. Used options are
                'aaseq', 'ntseq', 'mol', 'kcf', 'image', 'conf', 'kml', 'json'
                for method 'get' and 'turtle', 'n-triple' for method 'link'.

        Raises:
            ValueError: If the method or option is not supported.

        Returns:
            any: Response from the API.

        """
        if not method:
            log.error("Method must be specified. Supported methods are: " + ", ".join(self.METHODS.keys()))
            return {}

        _, _, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError:
            log.exception(f"Invalid parameters for method '{method}'")
            return {}

        if method == "pathways":
            url = f"{KEGG.API_URL}/link"
            url += "/pathway"
            if validated_params.get("entries"):
                q = str(validated_params["entries"])
                url += f"/{q}"
        else:
            url = f"{KEGG.API_URL}{method}"
            if validated_params.get("db"):
                url += f"/{validated_params['db']}"
            if validated_params.get("entries"):
                q = str(validated_params["entries"])
                url += f"/{q}"

            if validated_params.get("option"):
                if method not in METHOD_OPTIONS or validated_params["option"] not in METHOD_OPTIONS[method]:
                    log.error(
                        f"Option {validated_params['option']} is not supported for method {method}. Supported options are: {', '.join(METHOD_OPTIONS.get(method, []))}."
                    )
                    return {}
                url += f"/{validated_params['option']}"

        try:
            r = None
            response = self.session.get(url)
            self._delay()
            response.raise_for_status()
            if not response or not hasattr(response, "text"):
                log.warning(f"No response or invalid response for query {query} with method {method}.")
                return {}

            if method == "get":
                r = response.text.strip()
                if r and "///" in r:
                    # Split entries by "///" and remove the last empty entry
                    r = r.split("\n///\n\n")
                    r[-1] = r[-1].replace("\n///", "")
                else:
                    r = r.split("\n")
            elif method == "link":
                r = response.text
                r = [
                    {"from": line.split("\t")[0], validated_params["db"]: line.split("\t")[1]}
                    for line in r.split("\n")
                    if line
                ]
            elif method == "pathways":
                link_response = response.text
                link_response = [line.split("\t")[1] for line in link_response.split("\n") if line]
                r = self.fetch(
                    query=link_response,
                    method="get",
                )

        except requests.exceptions.RequestException:
            log.exception(f"Error fetching data for {query} with method {method}")
            return {}
        else:
            return r  # TODO check if for other functions we need to return json or text

    def parse(self, data: Any, fields_to_extract: list | dict | None = None, **kwargs: Any) -> dict | list:
        r"""Parse the response from the KEGG API.

        Args:
            data (Any): Raw data from the API response.
            fields_to_extract (list or dict): Fields to extract from the response.
                - If list: Keep those keys.
                - If dict: Maps {desired_name: real_field_name}.

            **kwargs: Additional parameters for parsing.
            - `type_response`: Type of data to parse. It can be "table" or "entry".
            - `columns`: List of column names to use for parsing.
            - `delimiter`: Delimiter used in the response. Default is tab ("\t").
            - `header`: Whether the first line contains headers. Default is True.

        Raises:
            ValueError: If the type_response is not supported.

        Returns:
            list: Parsed data as a list of dictionaries.

        """
        method = kwargs.get("method", "get")
        if not data:
            log.warning("Tried to parse data but the data is empty or None.")
            return {}

        if method in {"get", "pathways"}:
            # Primary field: no indentation, KEGG key + value
            primary_key_val_pattern = re.compile(r"^(\w+)\s+(.+)$")
            # Secondary (nested) field: leading spaces + key + value
            secondary_key_val_pattern = re.compile(r"^(\s+)(\w+)\s+(.+)$")
            # Implicit nested item: only leading spaces + text (no key),
            # used for extra items under the last secondary key (e.g. ELEMENT list)
            implicit_secondary_item_pattern = re.compile(r"^(\s+)(\S.*)$")

            parsed_entry = {}

            # State variables
            current_main_key = None  # Last top-level key (no indentation)
            current_subkey = None  # Last secondary key under current_main_key
            current_key = None  # Last key where we attach continuations

            for line in data.strip().split("\n"):
                if not line.strip():
                    # Skip completely empty lines
                    continue

                # 1) Try secondary (indented key)
                sec_match = secondary_key_val_pattern.match(line)
                if sec_match:
                    indent, key, value = sec_match.groups()

                    if indent == "":
                        # This is actually a primary key that matched the secondary pattern
                        # because of the regex definition; treat as primary.
                        prim_match = primary_key_val_pattern.match(line)
                        if prim_match:
                            key, value = prim_match.groups()
                            current_main_key = key
                            current_subkey = None
                            current_key = key

                            existing = parsed_entry.get(key)
                            if existing is None:
                                parsed_entry[key] = value
                            elif isinstance(existing, list):
                                existing.append(value)
                            else:
                                parsed_entry[key] = [existing, value]

                            continue
                    # Proper secondary key (nested)
                    elif current_main_key is None:
                        # Fallback: no main key yet, treat as primary
                        prim_match = primary_key_val_pattern.match(line)
                        if prim_match:
                            key, value = prim_match.groups()
                            current_main_key = key
                            current_subkey = None
                            current_key = key

                            existing = parsed_entry.get(key)
                            if existing is None:
                                parsed_entry[key] = value
                            elif isinstance(existing, list):
                                existing.append(value)
                            else:
                                parsed_entry[key] = [existing, value]

                            continue
                    else:
                        # Nested under current_main_key
                        parent_value = parsed_entry.get(current_main_key)

                        # If parent is not a dict, convert its current value into "_value"
                        if not isinstance(parent_value, dict):
                            parent_dict = {"_value": parent_value}
                            parsed_entry[current_main_key] = parent_dict
                        else:
                            parent_dict = parent_value

                        # For secondary keys (like ELEMENT), we store as list by default,
                        # because they usually appear multiple times.
                        existing = parent_dict.get(key)
                        if existing is None:
                            parent_dict[key] = [value]
                        elif isinstance(existing, list):
                            existing.append(value)
                        else:
                            parent_dict[key] = [existing, value]

                        current_subkey = key
                        current_key = key
                        continue

                # 2) Try primary (non-indented key) if not matched as secondary
                prim_match = primary_key_val_pattern.match(line)
                if prim_match:
                    key, value = prim_match.groups()
                    current_main_key = key
                    current_subkey = None
                    current_key = key

                    existing = parsed_entry.get(key)
                    if existing is None:
                        parsed_entry[key] = value
                    elif isinstance(existing, list):
                        existing.append(value)
                    else:
                        parsed_entry[key] = [existing, value]

                    continue

                # 3) Try implicit secondary item: extra rows under the last secondary key
                imp_match = implicit_secondary_item_pattern.match(line)
                if imp_match and current_main_key is not None and current_subkey is not None:
                    indent, text = imp_match.groups()
                    parent_value = parsed_entry.get(current_main_key)

                    if isinstance(parent_value, dict):
                        sub_value = parent_value.get(current_subkey)
                        # Only treat as "item list" if the current subkey holds a list
                        if isinstance(sub_value, list):
                            sub_value.append(text)
                            continue

                # 4) Fallback: treat as continuation of the last key's text
                continuation = line.strip()
                if not continuation:
                    continue

                if current_main_key is not None and current_subkey is not None:
                    # Continuation for a nested key (when it is not a list)
                    parent_value = parsed_entry.get(current_main_key)
                    if isinstance(parent_value, dict):
                        sub_value = parent_value.get(current_subkey)
                        if isinstance(sub_value, list):
                            # Append as extra line to the last item in the list
                            last_idx = len(sub_value) - 1
                            sub_value[last_idx] = sub_value[last_idx] + " " + continuation
                        else:
                            parent_value[current_subkey] = str(sub_value) + " " + continuation
                elif current_key is not None:
                    # Continuation for a top-level key
                    value = parsed_entry.get(current_key)
                    if isinstance(value, list):
                        last_idx = len(value) - 1
                        value[last_idx] = value[last_idx] + " " + continuation
                    else:
                        parsed_entry[current_key] = str(value) + " " + continuation

            # Special KEGG sequence handling
            if "AASEQ" in parsed_entry:
                aaseq_tokens = parsed_entry["AASEQ"].split(" ")
                parsed_entry["AALEN"] = aaseq_tokens[0]
                parsed_entry["AASEQ"] = "".join(aaseq_tokens[1:])

            if "NTSEQ" in parsed_entry:
                ntseq_tokens = parsed_entry["NTSEQ"].split(" ")
                parsed_entry["NTLEN"] = ntseq_tokens[0]
                parsed_entry["NTSEQ"] = "".join(ntseq_tokens[1:])

            return self._extract_fields(parsed_entry, fields_to_extract)

        if method == "link":
            return data
        log.error(f"Parsing method '{method}' is not supported.")
        return {}

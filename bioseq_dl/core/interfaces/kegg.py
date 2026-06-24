"""KEGG API interface."""

import re
from typing import Any, ClassVar

import niquests

from bioseq_dl.constants.databases import KEGG
from bioseq_dl.constants.kegg import DATABASES, METHOD_OPTIONS
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.kegg")


def _add(container: dict, key: str, value: Any, *, as_list: bool = False) -> None:
    """Insert ``value`` at ``key``, promoting to a list when the key already exists.

    With ``as_list=True`` the first value is stored as a single-element list (used
    for nested secondary keys that usually repeat).
    """
    existing = container.get(key)
    if existing is None:
        container[key] = [value] if as_list else value
    elif isinstance(existing, list):
        existing.append(value)
    else:
        container[key] = [existing, value]


# More info about KEGG API: https://www.kegg.jp/kegg/rest/keggapi.html


class KEGGInterface(BaseAPIInterface):
    """KEGG pathway and compound database API interface."""

    API_NAME = "KEGG"
    DB_CONFIG = KEGG
    METHODS: ClassVar[dict[str, Any]] = {
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

    def fetch(self, query: str | dict | list, *, method: str = "get", **kwargs: Any) -> dict | list | str:
        """Fetch data from the KEGG API.

        Args:
            query (str | dict | list): Query string or structured query to fetch.
            method (str): Method to use for the request, one of ``get``, ``link``,
                ``pathways``.
            **kwargs: Additional parameters for the request. Notable keys:
                ``db`` (database to query, e.g. ``pathway``, ``compound``, ``genes``)
                and ``option`` (extra format option such as ``aaseq``, ``ntseq``,
                ``mol``, ``json`` for ``get``, or ``turtle``, ``n-triple`` for ``link``).

        Returns:
            dict | list | str: Response from the API; empty dict on error.

        """
        if not method:
            log.error("Method must be specified. Supported methods are: %s", ", ".join(self.METHODS.keys()))
            return {}

        _, _, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError:
            log.exception("Invalid parameters for method '%s'", method)
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
                        "Option %s is not supported for method %s. Supported options are: %s.",
                        validated_params["option"],
                        method,
                        ", ".join(METHOD_OPTIONS.get(method, [])),
                    )
                    return {}
                url += f"/{validated_params['option']}"

        try:
            r = None
            response = self.session.get(url)
            self._delay()
            response.raise_for_status()
            if not response or not hasattr(response, "text"):
                log.warning("No response or invalid response for query %s with method %s.", query, method)
                return {}

            text = response.text or ""
            if method == "get":
                r = text.strip()
                if r and "///" in r:
                    # Split entries by "///" and remove the last empty entry
                    r = r.split("\n///\n\n")
                    r[-1] = r[-1].replace("\n///", "")
                else:
                    r = r.split("\n")
            elif method == "link":
                r = [
                    {"from": line.split("\t")[0], validated_params["db"]: line.split("\t")[1]}
                    for line in text.split("\n")
                    if line
                ]
            elif method == "pathways":
                link_response = [line.split("\t")[1] for line in text.split("\n") if line]
                r = self.fetch(
                    query=link_response,
                    method="get",
                )

        except niquests.exceptions.RequestException:
            log.exception("Error fetching data for %s with method %s", query, method)
            return {}
        else:
            return r if r is not None else {}

    def parse(self, data: Any, fields_to_extract: list | dict | None = None, **kwargs: Any) -> dict | list:
        r"""Parse the response from the KEGG API.

        For ``get``/``pathways`` responses the flat KEGG flat-file text is parsed into a
        nested dict of primary and secondary keys; ``link`` responses are returned as-is.

        Args:
            data (Any): Raw data from the API response.
            fields_to_extract (list | dict | None): Fields to extract from the response.
                If a list, keep those keys; if a dict, map ``{desired_name: real_field_name}``.
            **kwargs: Additional parameters for parsing. Notable key: ``method``
                (one of ``get``, ``pathways``, ``link``; defaults to ``get``).

        Returns:
            dict | list: Parsed data; empty dict if the method is unsupported.

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

                            _add(parsed_entry, key, value)

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

                            _add(parsed_entry, key, value)

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
                        _add(parent_dict, key, value, as_list=True)

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

                    _add(parsed_entry, key, value)

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
        log.error("Parsing method '%s' is not supported.", method)
        return {}

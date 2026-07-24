"""SABIO-RK kinetics database API interface."""

from __future__ import annotations

import contextlib
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar

import niquests
from niquests import Request

from silkroute.constants.databases import SABIORK
from silkroute.core.interfaces.base import BaseAPIInterface
from silkroute.core.utils.base_auxiliary_methods import validate_parameters
from silkroute.logging import get_logger

if TYPE_CHECKING:
    from niquests.models import Response

log = get_logger("silkroute.interfaces.sabiork")

KINETICLAWS_ENDPOINT = "kinlaw-entry/json"
MAX_PAGE_SIZE = 1000
DEFAULT_PAGE_SIZE = 1000
SPECIES_KEY_PARTS = 3
_EMPTY_MAPPING: Mapping[str, Any] = MappingProxyType({})
KINETICLAW_COLUMNS = (
    "EntryID",
    "Organism",
    "UniprotID",
    "ECNumber",
    "parameter.name",
    "parameter.type",
    "parameter.associatedSpecies",
    "parameter.startValue",
    "parameter.endValue",
    "parameter.standardDeviation",
    "parameter.unit",
    "Reaction",
    "Temperature",
    "pH",
    "Tissue",
)

# --- Export API source paths -------------------------------------------------
# The dot-paths below are the contract with the Export API: every column of
# KINETICLAW_COLUMNS is read from one of them. They are declared once so the
# flattening code and the structural drift test share a single source of truth.

#: Output column -> path within one kinetic-law entry.
ENTRY_FIELD_PATHS: Mapping[str, str] = MappingProxyType(
    {
        "EntryID": "id",
        "Organism": "general.organism.name",
        "ECNumber": "enzyme_description.ec_number",
        "Reaction": "reaction.equation",
        "Temperature": "experimental_conditions.envvar_temperature.start_value",
        "pH": "experimental_conditions.envvar_ph.start_value",
        "Tissue": "general.tissue.name",
    }
)

#: Output column -> path within one kinetic-law parameter.
PARAMETER_FIELD_PATHS: Mapping[str, str] = MappingProxyType(
    {
        "parameter.name": "name",
        "parameter.type": "parameter_type.name",
    }
)

#: Output column -> (normalized path, raw fallback path) within one parameter.
PARAMETER_VALUE_PATHS: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        "parameter.startValue": ("n_start_value", "start_value"),
        "parameter.endValue": ("n_end_value", "end_value"),
        "parameter.standardDeviation": ("n_standard_deviation", "standard_deviation"),
    }
)

#: Normalized and raw unit-name paths within one parameter, in preference order.
UNIT_NAME_PATHS = ("unit.n_name", "unit.name")
#: Path to the species key a parameter's associated-species label is parsed from.
SPECIES_KEY_PATH = "species.species_key"
#: Cross-reference paths an entry's UniProt accessions are read from, in order.
UNIPROT_LINK_PATH = "external_links.kinlaw_entry"
UNIPROT_PROTEIN_PATH = "enzyme_description.proteins"
UNIPROT_PROTEIN_ID_KEY = "uniprot_id"


def _escape_solr_value(value: str) -> str:
    """Escape one Solr query value, quoting values that need it."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    if any(char.isspace() for char in value) or "\\" in value or '"' in value:
        return f'"{escaped}"'
    return escaped


def _build_solr_query(parameters: Mapping[str, str]) -> str:
    """Build a SABIO-RK Solr query from validated public parameters."""
    return " AND ".join(f"{key}:{_escape_solr_value(value)}" for key, value in parameters.items())


def _order_validated_parameters(inputs: Mapping[str, Any], validated: Mapping[str, str]) -> dict[str, str]:
    """Keep caller parameter order after validation, then append defaults."""
    ordered = {key: validated[key] for key in inputs if key in validated}
    ordered.update({key: value for key, value in validated.items() if key not in ordered})
    return ordered


def _mapping(value: Any) -> Mapping[str, Any]:
    """Return value as a mapping for read-only access, or an empty mapping."""
    return value if isinstance(value, Mapping) else _EMPTY_MAPPING


def _list(value: Any) -> list[Any]:
    """Return value as a list, or an empty list."""
    return value if isinstance(value, list) else []


def _nested_value(data: Mapping[str, Any], *keys: str) -> Any:
    """Safely read a nested value from mappings."""
    current: Any = data
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _path_value(data: Mapping[str, Any], path: str) -> Any:
    """Safely read a dot-separated path from nested mappings."""
    return _nested_value(data, *path.split("."))


def _normalized_value(parameter: Mapping[str, Any], normalized_path: str, fallback_path: str) -> Any:
    """Prefer normalized SABIO-RK parameter values, preserving zero."""
    value = _path_value(parameter, normalized_path)
    return _path_value(parameter, fallback_path) if value is None else value


def _normalized_unit(parameter: Mapping[str, Any]) -> Any:
    """Prefer the normalized unit name, preserving empty strings if supplied."""
    return _normalized_value(parameter, *UNIT_NAME_PATHS)


def _associated_species(parameter: Mapping[str, Any]) -> Any:
    """Extract the species label from SABIO-RK species keys when possible."""
    species_key = _path_value(parameter, SPECIES_KEY_PATH)
    if not isinstance(species_key, str):
        return species_key

    parts = [part.strip() for part in species_key.split("|")]
    if len(parts) == SPECIES_KEY_PARTS and parts[1]:
        return parts[1]
    return species_key


def _append_unique(values: list[str], value: Any) -> None:
    """Append a non-empty string value once, preserving source order."""
    if value is None:
        return
    text = str(value).strip()
    if text and text not in values:
        values.append(text)


def _extract_uniprot_accessions(entry: Mapping[str, Any]) -> str:
    """Extract UniProt accessions from export links, with proteins as fallback."""
    accessions: list[str] = []
    for link in _list(_path_value(entry, UNIPROT_LINK_PATH)):
        link_map = _mapping(link)
        if link_map.get("key") != "UniProtKB_AC":
            continue
        for field in ("value", "id", "identifier", "accession"):
            if field in link_map:
                _append_unique(accessions, link_map[field])
                break

    if not accessions:
        for protein in _list(_path_value(entry, UNIPROT_PROTEIN_PATH)):
            _append_unique(accessions, _mapping(protein).get(UNIPROT_PROTEIN_ID_KEY))

    if len(accessions) == 1:
        return accessions[0]
    return ";".join(accessions)


def _flatten_kineticlaw_entry(entry: Any) -> list[dict[str, Any]]:
    """Flatten one SABIO-RK kinetic-law entry into compatible tabular rows."""
    if not isinstance(entry, Mapping):
        log.debug("Skipping malformed SABIO-RK entry: expected mapping, got %s", type(entry).__name__)
        return []

    parameters = _list(_nested_value(entry, "kineticlaw", "parameter"))
    if not parameters:
        log.debug("Skipping SABIO-RK entry without kinetic parameters: %s", entry.get("id"))
        return []

    rows = []
    base_values = {column: _path_value(entry, path) for column, path in ENTRY_FIELD_PATHS.items()}
    base_values["UniprotID"] = _extract_uniprot_accessions(entry)

    for parameter in parameters:
        if not isinstance(parameter, Mapping):
            log.debug(
                "Skipping malformed SABIO-RK parameter for entry %s: expected mapping, got %s",
                entry.get("id"),
                type(parameter).__name__,
            )
            continue
        row = {
            **base_values,
            **{column: _path_value(parameter, path) for column, path in PARAMETER_FIELD_PATHS.items()},
            **{
                column: _normalized_value(parameter, *paths)
                for column, paths in PARAMETER_VALUE_PATHS.items()
            },
            "parameter.associatedSpecies": _associated_species(parameter),
            "parameter.unit": _normalized_unit(parameter),
        }
        rows.append({column: row.get(column) for column in KINETICLAW_COLUMNS})

    return rows


def _flatten_kineticlaw_entries(entries: list[Any]) -> list[dict[str, Any]]:
    """Flatten a page of SABIO-RK kinetic-law entries."""
    rows: list[dict[str, Any]] = []
    for entry in entries:
        rows.extend(_flatten_kineticlaw_entry(entry))
    return rows


def _retry_after_seconds(response: Response) -> float | None:
    """Parse an HTTP Retry-After header as seconds, when present."""
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return None
    with contextlib.suppress(ValueError):
        seconds = float(retry_after)
        return max(0.0, seconds)

    try:
        retry_at = parsedate_to_datetime(retry_after)
    except (TypeError, ValueError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())


def _validate_bounded_int(value: Any, msg: str, *, maximum: int | None = None) -> int:
    """Coerce a positive integer option, rejecting bools and out-of-range values."""
    if isinstance(value, bool):
        raise TypeError(msg)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(msg) from exc
    if parsed < 1 or (maximum is not None and parsed > maximum):
        raise ValueError(msg)
    return parsed


def _validate_page_size(value: Any) -> int:
    """Validate the internal SABIO-RK page size option."""
    return _validate_bounded_int(
        value,
        f"page_size must be an integer between 1 and {MAX_PAGE_SIZE}.",
        maximum=MAX_PAGE_SIZE,
    )


def _validate_max_pages(value: Any) -> int | None:
    """Validate the optional local smoke-test page cap."""
    if value is None:
        return None
    return _validate_bounded_int(value, "max_pages must be a positive integer.")


def _parse_page_envelope(payload: Any, page: int) -> tuple[list[Any], int] | None:
    """Validate one SABIO-RK response envelope and return entries plus total pages."""
    if not isinstance(payload, Mapping):
        log.warning("Malformed SABIO-RK response for page %s: expected JSON object.", page)
        return None

    data = payload.get("data")
    meta = payload.get("meta")
    if not isinstance(data, list) or not isinstance(meta, Mapping):
        log.warning("Malformed SABIO-RK response for page %s: missing data list or meta object.", page)
        return None

    try:
        total_pages = int(meta.get("total_pages"))
    except (TypeError, ValueError):
        total_pages = -1
    if total_pages < 0:
        log.warning("Malformed SABIO-RK response for page %s: invalid total_pages.", page)
        return None

    return data, total_pages


class SabiorkInterface(BaseAPIInterface):
    """SABIO-RK biochemical kinetics database API interface."""

    API_NAME = "Sabio-RK"
    DB_CONFIG = SABIORK
    METHODS: ClassVar[dict[str, Any]] = {
        "kineticlaws": {
            "http_method": "POST",
            "path_param": None,
            "parameters": {
                "ECNumber": (str, None, True),
                "Organism": (str, None, True),
                "UniProtKB_AC": (str, None, True),
            },
            "group_queries": [None],
            "separator": None,
        }
    }

    def __init__(
        self,
        cache_dir: str | None = None,
        config_dir: str | None = None,
        output_dir: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the SabiorkInterface."""
        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)
        self.output_dir = self._resolve_output_dir(output_dir)

    def _send_page(self, url: str, payload: dict[str, Any], http_method: str) -> Response | None:
        """Send one SABIO-RK Export API page request with local 429 recovery."""
        request = Request(
            url=url,
            method=http_method,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        prepared = self.session.prepare_request(request)
        log.debug("SABIO-RK query=%s page=%s", payload["q"], payload["page"])

        for attempt in range(self.total_retries + 1):
            try:
                response = self.session.send(prepared)
                self._delay()
                response.raise_for_status()
            except niquests.exceptions.RequestException as exc:
                response = getattr(exc, "response", None)
                status_code = getattr(response, "status_code", None)
                if status_code == HTTPStatus.TOO_MANY_REQUESTS and attempt < self.total_retries:
                    wait = _retry_after_seconds(response)
                    if wait is None:
                        wait = 0.25 * (2**attempt)
                    log.warning(
                        "SABIO-RK rate limit on page %s; retrying after %.2f seconds.",
                        payload["page"],
                        wait,
                    )
                    time.sleep(wait)
                    continue
                log.warning(
                    "Recoverable SABIO-RK page failure for query %s page %s: %s",
                    payload["q"],
                    payload["page"],
                    exc,
                )
                return None
            else:
                return response

        return None

    def fetch(
        self, query: str | dict | list, *, method: str = "kineticlaws", **kwargs: Any
    ) -> dict | list | str:
        """Fetch compatible flat kinetic-law rows from the SABIO-RK Export API.

        The public logical method remains ``kineticlaws``. Internally, validated
        parameters are converted to a Solr query and sent to the Export API's
        ``kinlaw-entry/json`` endpoint with one-based JSON pagination.
        """
        if method not in self.METHODS:
            msg = f"Method '{method}' is not supported. Available methods: {list(self.METHODS.keys())}"
            raise ValueError(msg)

        page_size = _validate_page_size(kwargs.get("page_size", DEFAULT_PAGE_SIZE))
        max_pages = _validate_max_pages(kwargs.get("max_pages"))

        http_method, _, parameters, inputs = self.initialize_method_parameters(
            query, method, self.METHODS, **kwargs
        )

        try:
            validated_params = validate_parameters(inputs, parameters)
        except (TypeError, ValueError):
            log.exception("Invalid parameters for method '%s'", method)
            return []

        query_string = _build_solr_query(_order_validated_parameters(inputs, validated_params))
        url = SABIORK.API_URL + KINETICLAWS_ENDPOINT
        rows: list[dict[str, Any]] = []
        fetched_entries = 0
        page = 1

        while True:
            payload = {"q": query_string, "page": page, "pageSize": page_size}
            response = self._send_page(url, payload, http_method)
            if response is None:
                break

            try:
                envelope = response.json()
            except ValueError:
                log.warning("Malformed SABIO-RK response for page %s: invalid JSON.", page)
                break

            parsed = _parse_page_envelope(envelope, page)
            if parsed is None:
                break

            entries, total_pages = parsed
            if total_pages == 0:
                break

            fetched_entries += len(entries)
            rows.extend(_flatten_kineticlaw_entries(entries))

            if max_pages is not None and page >= max_pages:
                break
            if page >= total_pages:
                break
            page += 1

        log.debug(
            "Fetched %s SABIO-RK kinetic-law entries and flattened %s rows.",
            fetched_entries,
            len(rows),
        )
        return rows

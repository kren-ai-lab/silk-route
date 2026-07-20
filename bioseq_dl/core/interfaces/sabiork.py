"""SABIO-RK kinetics database API interface."""

from __future__ import annotations

import contextlib
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ClassVar

import niquests
from niquests import Request

from bioseq_dl.constants.databases import SABIORK
from bioseq_dl.core.interfaces.base import BaseAPIInterface
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

if TYPE_CHECKING:
    from niquests.models import Response

log = get_logger("bioseq_dl.interfaces.sabiork")

KINETICLAWS_ENDPOINT = "kinlaw-entry/json"
MAX_PAGE_SIZE = 1000
DEFAULT_PAGE_SIZE = 1000
SPECIES_KEY_PARTS = 3
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


def _mapping(value: Any) -> dict[str, Any]:
    """Return value as a plain mapping, or an empty dict."""
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    """Return value as a list, or an empty list."""
    return value if isinstance(value, list) else []


def _nested_mapping(data: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    """Safely descend through nested mappings."""
    current: Any = data
    for key in keys:
        current = _mapping(current).get(key)
    return _mapping(current)


def _nested_value(data: Mapping[str, Any], *keys: str) -> Any:
    """Safely read a nested value from mappings."""
    current: Any = data
    for key in keys:
        current = _mapping(current).get(key)
    return current


def _normalized_value(parameter: Mapping[str, Any], normalized_key: str, fallback_key: str) -> Any:
    """Prefer normalized SABIO-RK parameter values, preserving zero."""
    value = parameter.get(normalized_key)
    return parameter.get(fallback_key) if value is None else value


def _normalized_unit(parameter: Mapping[str, Any]) -> Any:
    """Prefer the normalized unit name, preserving empty strings if supplied."""
    unit = _mapping(parameter.get("unit"))
    value = unit.get("n_name")
    return unit.get("name") if value is None else value


def _associated_species(parameter: Mapping[str, Any]) -> Any:
    """Extract the species label from SABIO-RK species keys when possible."""
    species_key = _nested_value(parameter, "species", "species_key")
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
    for link in _list(_nested_value(entry, "external_links", "kinlaw_entry")):
        link_map = _mapping(link)
        if link_map.get("key") != "UniProtKB_AC":
            continue
        for field in ("value", "id", "identifier", "accession"):
            if field in link_map:
                _append_unique(accessions, link_map[field])
                break

    if not accessions:
        for protein in _list(_nested_value(entry, "enzyme_description", "proteins")):
            _append_unique(accessions, _mapping(protein).get("uniprot_id"))

    if len(accessions) == 1:
        return accessions[0]
    return ";".join(accessions)


def _flatten_kineticlaw_entry(entry: Any) -> list[dict[str, Any]]:
    """Flatten one SABIO-RK kinetic-law entry into compatible tabular rows."""
    if not isinstance(entry, Mapping):
        log.debug("Skipping malformed SABIO-RK entry: expected mapping, got %s", type(entry).__name__)
        return []

    entry_map = _mapping(entry)
    parameters = _list(_nested_value(entry_map, "kineticlaw", "parameter"))
    if not parameters:
        log.debug("Skipping SABIO-RK entry without kinetic parameters: %s", entry_map.get("id"))
        return []

    rows = []
    base_values = {
        "EntryID": entry_map.get("id"),
        "Organism": _nested_value(entry_map, "general", "organism", "name"),
        "UniprotID": _extract_uniprot_accessions(entry_map),
        "ECNumber": _nested_value(entry_map, "enzyme_description", "ec_number"),
        "Reaction": _nested_value(entry_map, "reaction", "equation"),
        "Temperature": _nested_value(
            entry_map, "experimental_conditions", "envvar_temperature", "start_value"
        ),
        "pH": _nested_value(entry_map, "experimental_conditions", "envvar_ph", "start_value"),
        "Tissue": _nested_value(entry_map, "general", "tissue", "name"),
    }

    for parameter in parameters:
        if not isinstance(parameter, Mapping):
            log.debug(
                "Skipping malformed SABIO-RK parameter for entry %s: expected mapping, got %s",
                entry_map.get("id"),
                type(parameter).__name__,
            )
            continue
        parameter_map = _mapping(parameter)
        row = {
            "EntryID": base_values["EntryID"],
            "Organism": base_values["Organism"],
            "UniprotID": base_values["UniprotID"],
            "ECNumber": base_values["ECNumber"],
            "parameter.name": parameter_map.get("name"),
            "parameter.type": _nested_value(parameter_map, "parameter_type", "name"),
            "parameter.associatedSpecies": _associated_species(parameter_map),
            "parameter.startValue": _normalized_value(parameter_map, "n_start_value", "start_value"),
            "parameter.endValue": _normalized_value(parameter_map, "n_end_value", "end_value"),
            "parameter.standardDeviation": _normalized_value(
                parameter_map, "n_standard_deviation", "standard_deviation"
            ),
            "parameter.unit": _normalized_unit(parameter_map),
            "Reaction": base_values["Reaction"],
            "Temperature": base_values["Temperature"],
            "pH": base_values["pH"],
            "Tissue": base_values["Tissue"],
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


def _validate_page_size(value: Any) -> int:
    """Validate the internal SABIO-RK page size option."""
    if isinstance(value, bool):
        msg = "page_size must be an integer between 1 and 1000."
        raise TypeError(msg)
    try:
        page_size = int(value)
    except (TypeError, ValueError) as exc:
        msg = "page_size must be an integer between 1 and 1000."
        raise ValueError(msg) from exc
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        msg = "page_size must be an integer between 1 and 1000."
        raise ValueError(msg)
    return page_size


def _validate_max_pages(value: Any) -> int | None:
    """Validate the optional local smoke-test page cap."""
    if value is None:
        return None
    if isinstance(value, bool):
        msg = "max_pages must be a positive integer."
        raise TypeError(msg)
    try:
        max_pages = int(value)
    except (TypeError, ValueError) as exc:
        msg = "max_pages must be a positive integer."
        raise ValueError(msg) from exc
    if max_pages < 1:
        msg = "max_pages must be a positive integer."
        raise ValueError(msg)
    return max_pages


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
        log.warning("Malformed SABIO-RK response for page %s: invalid total_pages.", page)
        return None
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
                if response.status_code == HTTPStatus.TOO_MANY_REQUESTS and attempt < self.total_retries:
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

"""Neutral metadata serialization for visual query builders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from bioseq_dl.core.workflow.query_interpreter import (
    split_quoted_csv_values,
    strip_surrounding_quotes,
)
from bioseq_dl.gui.query_builders.chebi import (
    ChEBIQueryBuilderRow,
    build_chebi_interpreted_query,
    normalize_chebi_field,
    normalize_chebi_resource,
    validate_chebi_builder_row,
)
from bioseq_dl.gui.query_builders.chembl import (
    CHEMBL_IC50_BUILDER_KEY,
    ChEMBLFilterQueryBuilderRow,
    build_chembl_ic50_interpreted_query,
    normalize_chembl_field,
    normalize_chembl_filter_type,
    normalize_chembl_ic50_condition,
    normalize_chembl_resource,
    restore_chembl_ic50_metadata_row,
    serialize_chembl_ic50_metadata_row,
    validate_chembl_builder_rows,
    validate_chembl_ic50_builder_row,
)
from bioseq_dl.gui.query_builders.pubchem import (
    PubChemQueryBuilderRow,
    build_pubchem_interpreted_query,
    normalize_pubchem_builder_threshold_state,
    normalize_pubchem_field,
    normalize_pubchem_resource,
    validate_pubchem_builder_row,
)
from bioseq_dl.gui.query_builders.registry import (
    get_query_builder_spec,
    is_query_builder_compatible,
)
from bioseq_dl.gui.query_builders.uniprot import (
    UniProtQueryBuilderRow,
    normalize_query_builder_connector,
    normalize_query_builder_field,
    normalize_query_builder_match_mode,
    validate_uniprot_query_builder_rows,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

QUERY_BUILDER_SCHEMA_VERSION = "query-builder-v1"
REQUIRED_QUERY_BUILDER_METADATA_FIELDS = (
    "schema_version",
    "source",
    "builder_key",
    "builder_type",
    "rows",
)
UNIPROT_METADATA_ROW_FIELDS = {"connector", "field", "match_mode", "values"}
CHEMBL_METADATA_ROW_FIELDS = {"field", "operator", "value"}
CHEMBL_IC50_RANGE_METADATA_ROW_FIELDS = {"condition", "minimum", "maximum", "unit"}
CHEMBL_IC50_VALUE_METADATA_ROW_FIELDS = {"condition", "value", "unit"}
HISTORICAL_CHEMBL_IC50_BUILDER_KEY = "chembl_ic50_activity"
HISTORICAL_CHEMBL_IC50_METADATA_ROW_FIELDS = {
    "comparison_mode",
    "lower_value",
    "upper_value",
    "value",
    "standard_units",
}
HISTORICAL_CHEMBL_IC50_CONDITIONS = {
    "range": "range",
    "lt": "less_than",
    "lte": "less_than_or_equal",
    "gt": "greater_than",
    "gte": "greater_than_or_equal",
    "exact": "exact",
}
PUBCHEM_METADATA_ROW_FIELDS = {"field", "value"}
PUBCHEM_THRESHOLD_METADATA_ROW_FIELDS = {"field", "value", "threshold"}
CHEBI_METADATA_ROW_FIELDS = {"field", "value"}


class QueryBuilderMetadataMismatchError(ValueError):
    """Raised when builder metadata does not regenerate the saved query value."""


@dataclass(frozen=True)
class QueryBuilderRestoration:
    """Validated query-builder state reconstructed from neutral metadata."""

    builder_key: str
    form_rows: tuple[dict[str, object], ...]


def normalize_query_value_for_comparison(value: object) -> str:
    """Normalize insignificant whitespace outside quoted query values."""
    normalized: list[str] = []
    quote: str | None = None
    pending_space = False
    for character in str(value or "").strip():
        if quote is not None:
            normalized.append(character)
            if character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            if pending_space and normalized:
                normalized.append(" ")
            pending_space = False
            quote = character
            normalized.append(character)
            continue
        if character.isspace():
            pending_space = True
            continue
        if pending_space and normalized:
            normalized.append(" ")
        pending_space = False
        normalized.append(character)
    return "".join(normalized)


def format_restored_csv_value(value: str) -> str:
    """Quote one restored builder value when it contains a comma."""
    cleaned = str(value).strip()
    if "," in cleaned:
        return f'"{cleaned}"'
    return cleaned


def require_single_metadata_row(rows: object) -> dict[str, object]:
    """Return a single metadata row from query.builder.rows."""
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        msg = "query.builder.rows must contain exactly one mapping."
        raise ValueError(msg)
    return rows[0]


def restore_uniprot_query_builder_rows(rows: object) -> tuple[UniProtQueryBuilderRow, ...]:
    """Restore validated UniProt rows from neutral metadata."""
    if not isinstance(rows, list) or not rows:
        msg = "query.builder.rows must be a non-empty list."
        raise ValueError(msg)
    restored_rows = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != UNIPROT_METADATA_ROW_FIELDS:
            msg = f"query.builder.rows[{index}] has an invalid UniProt row shape."
            raise ValueError(msg)
        connector = row["connector"]
        field = row["field"]
        match_mode = row["match_mode"]
        values = row["values"]
        if connector is not None and not isinstance(connector, str):
            msg = f"query.builder.rows[{index}].connector must be a string or null."
            raise TypeError(msg)
        if not isinstance(field, str) or not isinstance(match_mode, str):
            msg = f"query.builder.rows[{index}] field and match_mode must be strings."
            raise TypeError(msg)
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) or not value.strip() for value in values)
        ):
            msg = f"query.builder.rows[{index}].values must be a non-empty string list."
            raise ValueError(msg)
        restored_rows.append(
            UniProtQueryBuilderRow(
                connector=connector,
                field=field,
                match_mode=match_mode,
                values=",".join(format_restored_csv_value(value) for value in values),
            )
        )
    validate_uniprot_query_builder_rows(restored_rows)
    return tuple(restored_rows)


def restore_chembl_query_builder_rows(
    builder_key: str,
    rows: object,
) -> tuple[ChEMBLFilterQueryBuilderRow, ...]:
    """Restore validated ChEMBL rows from neutral metadata."""
    if not isinstance(rows, list) or not rows:
        msg = "query.builder.rows must be a non-empty list."
        raise ValueError(msg)
    resource = builder_key.removeprefix("chembl_")
    restored_rows = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != CHEMBL_METADATA_ROW_FIELDS:
            msg = f"query.builder.rows[{index}] has an invalid ChEMBL row shape."
            raise ValueError(msg)
        if any(not isinstance(row[field], str) for field in CHEMBL_METADATA_ROW_FIELDS):
            msg = f"query.builder.rows[{index}] values must be strings."
            raise TypeError(msg)
        restored_rows.append(
            ChEMBLFilterQueryBuilderRow(
                resource=resource,
                field=row["field"],
                filter_type=row["operator"],
                value=row["value"],
            )
        )
    validate_chembl_builder_rows(restored_rows)
    return tuple(restored_rows)


def restore_chembl_ic50_query_builder_row(rows: object) -> tuple[object, dict[str, object]]:
    """Restore one validated ChEMBL IC50 row and its form state."""
    row = require_single_metadata_row(rows)
    condition = normalize_chembl_ic50_condition(row.get("condition"))
    allowed_fields = (
        CHEMBL_IC50_RANGE_METADATA_ROW_FIELDS
        if condition == "range"
        else CHEMBL_IC50_VALUE_METADATA_ROW_FIELDS
    )
    if set(row) != allowed_fields:
        msg = "query.builder.rows[0] has an invalid ChEMBL IC50 row shape."
        raise ValueError(msg)
    restored_row = restore_chembl_ic50_metadata_row(row)
    metadata_row = serialize_chembl_ic50_metadata_row(restored_row)
    form_row = {
        "condition": metadata_row["condition"],
        "minimum": metadata_row.get("minimum"),
        "maximum": metadata_row.get("maximum"),
        "value": metadata_row.get("value"),
        "unit": metadata_row["unit"],
    }
    return restored_row, form_row


def is_historical_chembl_ic50_metadata(metadata: Mapping[str, object]) -> bool:
    """Return whether metadata has the exact historical ChEMBL IC50 shape."""
    if (
        metadata.get("schema_version") != QUERY_BUILDER_SCHEMA_VERSION
        or metadata.get("source") != "chembl"
        or metadata.get("builder_key") != HISTORICAL_CHEMBL_IC50_BUILDER_KEY
        or metadata.get("builder_type") != "ic50_activity"
    ):
        return False
    rows = metadata.get("rows")
    return (
        isinstance(rows, list)
        and len(rows) == 1
        and isinstance(rows[0], dict)
        and set(rows[0]) == HISTORICAL_CHEMBL_IC50_METADATA_ROW_FIELDS
    )


def migrate_historical_chembl_ic50_metadata(
    metadata: Mapping[str, object],
) -> dict[str, object] | None:
    """Convert exact historical ChEMBL IC50 metadata to canonical metadata."""
    if not is_historical_chembl_ic50_metadata(metadata):
        return None
    row = require_single_metadata_row(metadata["rows"])
    condition = HISTORICAL_CHEMBL_IC50_CONDITIONS.get(str(row["comparison_mode"]).strip())
    if condition is None:
        msg = "query.builder.rows[0] has an unsupported historical ChEMBL IC50 comparison mode."
        raise ValueError(msg)

    migrated_row: dict[str, object] = {
        "condition": condition,
        "unit": row["standard_units"],
    }
    if condition == "range":
        migrated_row["minimum"] = row["lower_value"]
        migrated_row["maximum"] = row["upper_value"]
    else:
        migrated_row["value"] = row["value"]

    restored_row = restore_chembl_ic50_metadata_row(migrated_row)
    return build_common_query_builder_metadata(
        CHEMBL_IC50_BUILDER_KEY,
        [serialize_chembl_ic50_metadata_row(restored_row)],
    )


def restore_pubchem_query_builder_row(
    builder_key: str,
    rows: object,
) -> PubChemQueryBuilderRow:
    """Restore a validated PubChem row from neutral metadata."""
    row = require_single_metadata_row(rows)
    field = row.get("field")
    allowed_fields = (
        PUBCHEM_THRESHOLD_METADATA_ROW_FIELDS
        if field == "similarity_2d_cid" and "threshold" in row
        else PUBCHEM_METADATA_ROW_FIELDS
    )
    if set(row) != allowed_fields:
        msg = "query.builder.rows[0] has an invalid PubChem row shape."
        raise ValueError(msg)
    if not isinstance(row["field"], str) or not isinstance(row["value"], str):
        msg = "query.builder.rows[0] field and value must be strings."
        raise TypeError(msg)
    resource = builder_key.removeprefix("pubchem_")
    restored_row = PubChemQueryBuilderRow(
        resource=resource,
        field=row["field"],
        value=row["value"],
        threshold=normalize_pubchem_builder_threshold_state(row["field"], row.get("threshold")),
    )
    validate_pubchem_builder_row(restored_row)
    return restored_row


def restore_chebi_query_builder_row(builder_key: str, rows: object) -> ChEBIQueryBuilderRow:
    """Restore a validated ChEBI row from neutral metadata."""
    row = require_single_metadata_row(rows)
    if set(row) != CHEBI_METADATA_ROW_FIELDS:
        msg = "query.builder.rows[0] has an invalid ChEBI row shape."
        raise ValueError(msg)
    if not isinstance(row["field"], str) or not isinstance(row["value"], str):
        msg = "query.builder.rows[0] field and value must be strings."
        raise TypeError(msg)
    resource = builder_key.removeprefix("chebi_")
    restored_row = ChEBIQueryBuilderRow(resource=resource, field=row["field"], value=row["value"])
    validate_chebi_builder_row(restored_row)
    return restored_row


def validate_query_builder_metadata(metadata: Mapping[str, object]) -> None:
    """Validate the common shape of neutral query-builder metadata."""
    for field_name in REQUIRED_QUERY_BUILDER_METADATA_FIELDS[:-1]:
        value = metadata.get(field_name)
        if not isinstance(value, str) or not value.strip():
            msg = f"query.builder.{field_name} must be a non-empty string."
            raise ValueError(msg)
    if metadata["schema_version"] != QUERY_BUILDER_SCHEMA_VERSION:
        msg = f"query.builder.schema_version must be '{QUERY_BUILDER_SCHEMA_VERSION}'."
        raise ValueError(msg)

    rows = metadata.get("rows")
    if not isinstance(rows, list) or not rows:
        msg = "query.builder.rows must be a non-empty list."
        raise ValueError(msg)
    if any(not isinstance(row, dict) for row in rows):
        msg = "query.builder.rows entries must be mappings."
        raise TypeError(msg)


def restore_query_builder_metadata(
    metadata: object,
    query_value: object,
    modality: str,
    interaction_type: str | None,
) -> QueryBuilderRestoration:
    """Validate and restore query-builder metadata compatible with a dataset."""
    if not isinstance(metadata, dict):
        msg = "query.builder must be a mapping."
        raise TypeError(msg)
    validate_query_builder_metadata(metadata)
    migrated_metadata = migrate_historical_chembl_ic50_metadata(metadata)
    if migrated_metadata is not None:
        metadata = migrated_metadata
    builder_key = metadata["builder_key"]
    if not isinstance(builder_key, str):
        msg = "query.builder.builder_key must be a non-empty string."
        raise TypeError(msg)
    spec = get_query_builder_spec(builder_key)
    if metadata["source"] != spec.database:
        msg = "query.builder.source does not match its registered builder."
        raise ValueError(msg)
    if metadata["builder_type"] != spec.builder_type:
        msg = "query.builder.builder_type does not match its registered builder."
        raise ValueError(msg)
    if not is_query_builder_compatible(spec, modality, interaction_type):
        msg = "query.builder is not compatible with the loaded dataset settings."
        raise ValueError(msg)

    if builder_key == "uniprot":
        rows = restore_uniprot_query_builder_rows(metadata["rows"])
        regenerated_query = spec.build_interpreted_query(rows)
        form_rows = tuple(
            {
                "connector": row.connector,
                "field": row.field,
                "values": row.values,
                "match_mode": row.match_mode,
            }
            for row in rows
        )
    elif builder_key == CHEMBL_IC50_BUILDER_KEY:
        row, form_row = restore_chembl_ic50_query_builder_row(metadata["rows"])
        regenerated_query = build_chembl_ic50_interpreted_query(row)
        form_rows = (form_row,)
    elif spec.database == "chembl":
        rows = restore_chembl_query_builder_rows(builder_key, metadata["rows"])
        regenerated_query = spec.build_interpreted_query(rows)
        form_rows = tuple(
            {"field": row.field, "filter_type": row.filter_type, "value": row.value} for row in rows
        )
    elif spec.database == "pubchem":
        row = restore_pubchem_query_builder_row(builder_key, metadata["rows"])
        regenerated_query = build_pubchem_interpreted_query(row)
        form_rows = (
            {
                "field": row.field,
                "value": row.value,
                "threshold": normalize_pubchem_builder_threshold_state(row.field, row.threshold),
            },
        )
    elif spec.database == "chebi":
        row = restore_chebi_query_builder_row(builder_key, metadata["rows"])
        regenerated_query = build_chebi_interpreted_query(row)
        form_rows = ({"field": row.field, "value": row.value},)
    else:
        msg = f"query.builder source '{spec.database}' cannot be restored."
        raise ValueError(msg)

    if normalize_query_value_for_comparison(regenerated_query) != normalize_query_value_for_comparison(
        query_value
    ):
        msg = "query.builder metadata does not regenerate query.value."
        raise QueryBuilderMetadataMismatchError(msg)
    return QueryBuilderRestoration(builder_key, form_rows)


def build_common_query_builder_metadata(builder_key: str, rows: list[dict[str, object]]) -> dict[str, object]:
    """Build common neutral metadata fields for one visual builder."""
    spec = get_query_builder_spec(builder_key)
    metadata: dict[str, object] = {
        "schema_version": QUERY_BUILDER_SCHEMA_VERSION,
        "source": spec.database,
        "builder_key": spec.key,
        "builder_type": spec.builder_type,
        "rows": rows,
    }
    validate_query_builder_metadata(metadata)
    return metadata


def build_uniprot_query_builder_metadata(
    rows: Sequence[UniProtQueryBuilderRow],
) -> dict[str, object]:
    """Build neutral metadata for validated UniProt visual builder rows."""
    validate_uniprot_query_builder_rows(rows)
    serialized_rows = [
        {
            "connector": normalize_query_builder_connector(row.connector),
            "field": normalize_query_builder_field(row.field),
            "match_mode": normalize_query_builder_match_mode(row.match_mode),
            "values": [strip_surrounding_quotes(value) for value in split_quoted_csv_values(row.values)],
        }
        for row in rows
    ]
    return build_common_query_builder_metadata("uniprot", serialized_rows)


def build_chembl_query_builder_metadata(
    builder_key: str,
    rows: Sequence[ChEMBLFilterQueryBuilderRow],
) -> dict[str, object]:
    """Build neutral metadata for validated ChEMBL visual builder rows."""
    validate_chembl_builder_rows(rows)
    spec = get_query_builder_spec(builder_key)
    if spec.database != "chembl":
        msg = f"Query builder '{builder_key}' is not a ChEMBL builder."
        raise ValueError(msg)
    expected_resource = builder_key.removeprefix("chembl_")
    if any(normalize_chembl_resource(row.resource) != expected_resource for row in rows):
        msg = f"Query builder '{builder_key}' does not match its ChEMBL row resource."
        raise ValueError(msg)

    serialized_rows = [
        {
            "field": normalize_chembl_field(row.field),
            "operator": normalize_chembl_filter_type(row.filter_type),
            "value": str(row.value).strip(),
        }
        for row in rows
    ]
    return build_common_query_builder_metadata(builder_key, serialized_rows)


def build_chembl_ic50_query_builder_metadata(row: object) -> dict[str, object]:
    """Build neutral metadata for a validated ChEMBL IC50 visual builder row."""
    restored_row = restore_chembl_ic50_metadata_row(serialize_chembl_ic50_metadata_row(row))
    validate_chembl_ic50_builder_row(restored_row)
    return build_common_query_builder_metadata(
        CHEMBL_IC50_BUILDER_KEY,
        [serialize_chembl_ic50_metadata_row(restored_row)],
    )


def _validated_source_builder_row(
    builder_key: str,
    row: object,
    *,
    database: str,
    database_label: str,
    validate: Callable[[object], None],
    normalize_resource: Callable[[str], str],
    normalize_field: Callable[[str], str],
) -> dict[str, object]:
    """Validate a source builder row and return its serialized ``{field, value}`` mapping."""
    validate(row)
    spec = get_query_builder_spec(builder_key)
    if spec.database != database:
        msg = f"Query builder '{builder_key}' is not a {database_label} builder."
        raise ValueError(msg)
    expected_resource = builder_key.removeprefix(f"{database}_")
    if normalize_resource(row.resource) != expected_resource:
        msg = f"Query builder '{builder_key}' does not match its {database_label} row resource."
        raise ValueError(msg)
    return {
        "field": normalize_field(row.field),
        "value": strip_surrounding_quotes(str(row.value)).strip(),
    }


def build_pubchem_query_builder_metadata(
    builder_key: str,
    row: PubChemQueryBuilderRow,
) -> dict[str, object]:
    """Build neutral metadata for a validated PubChem visual builder row."""
    serialized_row = _validated_source_builder_row(
        builder_key,
        row,
        database="pubchem",
        database_label="PubChem",
        validate=validate_pubchem_builder_row,
        normalize_resource=normalize_pubchem_resource,
        normalize_field=normalize_pubchem_field,
    )
    if serialized_row["field"] == "similarity_2d_cid":
        serialized_row["threshold"] = int(str(row.threshold).strip())
    return build_common_query_builder_metadata(builder_key, [serialized_row])


def build_chebi_query_builder_metadata(
    builder_key: str,
    row: ChEBIQueryBuilderRow,
) -> dict[str, object]:
    """Build neutral metadata for a validated ChEBI visual builder row."""
    serialized_row = _validated_source_builder_row(
        builder_key,
        row,
        database="chebi",
        database_label="ChEBI",
        validate=validate_chebi_builder_row,
        normalize_resource=normalize_chebi_resource,
        normalize_field=normalize_chebi_field,
    )
    return build_common_query_builder_metadata(builder_key, [serialized_row])

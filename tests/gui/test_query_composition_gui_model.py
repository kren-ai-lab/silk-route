"""Tests for the pure GUI query-composition model."""

from __future__ import annotations

from pathlib import Path

import pytest

from bioseq_dl.gui.yaml_builder import (
    QUERY_COMPOSITION_BUILDER_RESTORE_NOTE,
    QUERY_COMPOSITION_PARSE_ERROR_NOTE,
    QUERY_COMPOSITION_VALUE_PARSED_NOTE,
    build_query_composition_metadata,
    build_query_composition_value,
    build_workflow_descriptor,
    load_workflow_yaml_to_form_values,
    render_workflow_yaml,
)


def manual_composition_entry(
    label: str,
    value: str,
    description: str = "",
) -> dict[str, object]:
    """Return the expected local form shape for one manual entry."""
    return {
        "label": label,
        "value": value,
        "description": description,
        "query_input_mode": "Manual query",
        "query_builder_key": "uniprot",
        "uniprot_builder_rows": [],
        "chembl_builder_rows": [],
    }


def advanced_uniprot_entry(label: str, keyword: str) -> dict[str, object]:
    """Return one entry-local UniProt builder form state."""
    return {
        "label": label,
        "value": "",
        "description": f"{keyword} protein query.",
        "query_input_mode": "Advanced builder",
        "query_builder_key": "uniprot",
        "uniprot_builder_rows": [
            {
                "connector": None,
                "field": "keywords",
                "match_mode": "any",
                "values": keyword,
            }
        ],
        "chembl_builder_rows": [],
    }


def composition_form_values() -> dict[str, object]:
    """Return a minimal form containing two labeled queries."""
    return {
        "dataset.name": "protein_composition",
        "dataset.modality": "protein",
        "dataset.mode": "query_composition",
        "query.composition.entries": [
            {
                "label": "antiviral",
                "value": "keywords:antiviral protein",
                "description": "Antiviral protein keyword query.",
            },
            {
                "label": "dna_repair",
                "value": "go:dna repair",
                "description": "DNA repair Gene Ontology query.",
            },
        ],
        "execution.enrich": False,
        "execution.max_workers": 5,
        "execution.total_retries": 3,
        "execution.chembl_pages_to_fetch": 1,
        "execution.debug": False,
        "export.format": "csv",
        "export.include_metadata": True,
        "export.include_summary": True,
    }


def test_query_composition_descriptor_contains_executable_value_and_metadata() -> None:
    descriptor = build_workflow_descriptor(composition_form_values())

    assert descriptor["query"]["value"] == (
        "keywords:antiviral protein=antiviral,go:dna repair=dna_repair"
    )
    assert descriptor["query"]["composition"] == [
        {
            "label": "antiviral",
            "value": "keywords:antiviral protein",
            "description": "Antiviral protein keyword query.",
        },
        {
            "label": "dna_repair",
            "value": "go:dna repair",
            "description": "DNA repair Gene Ontology query.",
        },
    ]
    assert "builder" not in descriptor["query"]


def test_empty_description_is_omitted_from_composition_metadata() -> None:
    metadata = build_query_composition_metadata(
        [{"label": "reviewed", "value": "reviewed:true", "description": "  "}]
    )

    assert metadata == [{"label": "reviewed", "value": "reviewed:true"}]


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        ([], "Add at least one labeled query"),
        ([{"label": "", "value": "reviewed:true"}], "needs a label"),
        ([{"label": "reviewed", "value": ""}], "needs a query value"),
        (
            [
                {"label": "same", "value": "reviewed:true"},
                {"label": "same", "value": "organism_id:9606"},
            ],
            "Labels must be unique",
        ),
        (
            [{"label": "reviewed", "value": "reviewed:true,organism_id:9606"}],
            "cannot contain commas",
        ),
        (
            [{"label": "egfr=bad", "value": "reviewed:true"}],
            "Labels cannot contain equals signs",
        ),
        (
            [{"label": "egfr,bad", "value": "reviewed:true"}],
            "Labels cannot contain commas",
        ),
    ],
)
def test_invalid_query_composition_entries_fail_clearly(
    entries: list[dict[str, object]],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_query_composition_value(entries)


def test_existing_query_composition_example_restores_entries() -> None:
    example_path = Path("examples/workflows/protein_query_composition_labels.yml")

    form_values, warnings = load_workflow_yaml_to_form_values(
        example_path.read_text(encoding="utf-8")
    )

    assert warnings == []
    assert form_values["dataset.mode"] == "Query Composition"
    assert form_values["query.composition.entries"] == [
        manual_composition_entry(
            "antiviral",
            "keywords:antiviral protein",
            "Antiviral protein keyword query.",
        ),
        manual_composition_entry(
            "dna_repair",
            "go:dna repair",
            "DNA repair Gene Ontology query.",
        ),
    ]


def test_query_composition_allows_equals_sign_in_query_value() -> None:
    form_values = composition_form_values()
    form_values["dataset.modality"] = "compound"
    form_values["query.composition.entries"] = [
        {
            "label": "egfr",
            "value": "chembl.target:gene_symbol__iexact=EGFR",
            "description": "EGFR target query.",
        }
    ]

    descriptor = build_workflow_descriptor(form_values)
    loaded_form_values, warnings = load_workflow_yaml_to_form_values(
        render_workflow_yaml(descriptor)
    )

    assert descriptor["query"]["value"] == (
        "chembl.target:gene_symbol__iexact=EGFR=egfr"
    )
    assert descriptor["query"]["composition"] == [
        {
            "label": "egfr",
            "value": "chembl.target:gene_symbol__iexact=EGFR",
            "description": "EGFR target query.",
        }
    ]
    assert warnings == []
    assert loaded_form_values["query.composition.entries"] == [
        manual_composition_entry(
            "egfr",
            "chembl.target:gene_symbol__iexact=EGFR",
            "EGFR target query.",
        )
    ]


def test_query_value_without_composition_metadata_is_parsed() -> None:
    descriptor = build_workflow_descriptor(composition_form_values())
    del descriptor["query"]["composition"]

    form_values, warnings = load_workflow_yaml_to_form_values(
        render_workflow_yaml(descriptor)
    )

    assert QUERY_COMPOSITION_VALUE_PARSED_NOTE in warnings
    assert form_values["query.composition.entries"] == [
        manual_composition_entry("antiviral", "keywords:antiviral protein"),
        manual_composition_entry("dna_repair", "go:dna repair"),
    ]


def test_unparseable_query_composition_value_loads_safe_fallback() -> None:
    descriptor = build_workflow_descriptor(composition_form_values())
    descriptor["query"]["value"] = "reviewed:true"
    del descriptor["query"]["composition"]

    form_values, warnings = load_workflow_yaml_to_form_values(
        render_workflow_yaml(descriptor)
    )

    assert QUERY_COMPOSITION_PARSE_ERROR_NOTE in warnings
    assert form_values["query.composition.entries"] == [
        manual_composition_entry("", "reviewed:true")
    ]


def test_advanced_uniprot_entry_generates_local_builder_metadata() -> None:
    form_values = composition_form_values()
    form_values["query.composition.entries"] = [
        advanced_uniprot_entry("antimicrobial", "Antimicrobial")
    ]

    descriptor = build_workflow_descriptor(form_values)

    assert descriptor["query"]["value"] == "keyword:Antimicrobial=antimicrobial"
    item = descriptor["query"]["composition"][0]
    assert item["label"] == "antimicrobial"
    assert item["value"] == "keyword:Antimicrobial"
    assert item["builder"] == {
        "schema_version": "query-builder-v1",
        "source": "uniprot",
        "builder_key": "uniprot",
        "builder_type": "field_boolean",
        "rows": [
            {
                "connector": None,
                "field": "keywords",
                "match_mode": "any",
                "values": ["Antimicrobial"],
            }
        ],
    }
    assert "builder" not in descriptor["query"]


def test_two_advanced_entries_keep_independent_builder_metadata() -> None:
    form_values = composition_form_values()
    form_values["query.composition.entries"] = [
        advanced_uniprot_entry("antimicrobial", "Antimicrobial"),
        advanced_uniprot_entry("antiviral", "Antiviral"),
    ]

    descriptor = build_workflow_descriptor(form_values)

    assert descriptor["query"]["value"] == (
        "keyword:Antimicrobial=antimicrobial,keyword:Antiviral=antiviral"
    )
    composition = descriptor["query"]["composition"]
    assert composition[0]["builder"]["rows"][0]["values"] == ["Antimicrobial"]
    assert composition[1]["builder"]["rows"][0]["values"] == ["Antiviral"]


def test_mixed_manual_and_advanced_entries_serialize_independently() -> None:
    form_values = composition_form_values()
    form_values["query.composition.entries"] = [
        {
            "label": "reviewed",
            "value": "reviewed:true",
            "description": "Reviewed proteins.",
        },
        advanced_uniprot_entry("antiviral", "Antiviral"),
    ]

    descriptor = build_workflow_descriptor(form_values)

    composition = descriptor["query"]["composition"]
    assert "builder" not in composition[0]
    assert composition[1]["builder"]["builder_key"] == "uniprot"
    assert descriptor["query"]["value"] == (
        "reviewed:true=reviewed,keyword:Antiviral=antiviral"
    )


def test_entry_builder_metadata_round_trip_restores_local_state() -> None:
    form_values = composition_form_values()
    form_values["query.composition.entries"] = [
        advanced_uniprot_entry("antimicrobial", "Antimicrobial")
    ]
    descriptor = build_workflow_descriptor(form_values)

    loaded, warnings = load_workflow_yaml_to_form_values(
        render_workflow_yaml(descriptor)
    )

    assert warnings == []
    entry = loaded["query.composition.entries"][0]
    assert entry["query_input_mode"] == "Advanced builder"
    assert entry["query_builder_key"] == "uniprot"
    assert entry["value"] == "keyword:Antimicrobial"
    assert entry["uniprot_builder_rows"] == [
        {
            "connector": None,
            "field": "keywords",
            "match_mode": "any",
            "values": "Antimicrobial",
        }
    ]
    assert build_workflow_descriptor(loaded) == descriptor


def test_invalid_entry_builder_metadata_falls_back_to_manual_with_note() -> None:
    form_values = composition_form_values()
    form_values["query.composition.entries"] = [
        advanced_uniprot_entry("antimicrobial", "Antimicrobial")
    ]
    descriptor = build_workflow_descriptor(form_values)
    descriptor["query"]["composition"][0]["builder"]["schema_version"] = (
        "query-builder-v2"
    )

    loaded, warnings = load_workflow_yaml_to_form_values(
        render_workflow_yaml(descriptor)
    )

    expected_note = QUERY_COMPOSITION_BUILDER_RESTORE_NOTE.format(
        label="antimicrobial"
    )
    assert expected_note in warnings
    entry = loaded["query.composition.entries"][0]
    assert entry["query_input_mode"] == "Manual query"
    assert entry["label"] == "antimicrobial"
    assert entry["value"] == "keyword:Antimicrobial"
    assert entry["description"] == "Antimicrobial protein query."
    assert "builder" not in entry


def test_chembl_entry_builder_metadata_round_trip_restores_local_state() -> None:
    form_values = composition_form_values()
    form_values["dataset.modality"] = "interaction"
    form_values["dataset.interaction_type"] = "protein-ligand"
    form_values["query.composition.entries"] = [
        {
            "label": "egfr",
            "value": "",
            "description": "EGFR target query.",
            "query_input_mode": "Advanced builder",
            "query_builder_key": "chembl_target",
            "uniprot_builder_rows": [],
            "chembl_builder_rows": [
                {
                    "field": "gene_symbol",
                    "filter_type": "iexact",
                    "value": "EGFR",
                }
            ],
        }
    ]

    descriptor = build_workflow_descriptor(form_values)
    loaded, warnings = load_workflow_yaml_to_form_values(
        render_workflow_yaml(descriptor)
    )

    assert descriptor["query"]["value"] == (
        "chembl.target:gene_symbol__iexact=EGFR=egfr"
    )
    assert "builder" not in descriptor["query"]
    assert descriptor["query"]["composition"][0]["builder"]["builder_key"] == (
        "chembl_target"
    )
    assert warnings == []
    entry = loaded["query.composition.entries"][0]
    assert entry["query_input_mode"] == "Advanced builder"
    assert entry["query_builder_key"] == "chembl_target"
    assert entry["chembl_builder_rows"] == [
        {"field": "gene_symbol", "filter_type": "iexact", "value": "EGFR"}
    ]


def test_query_first_generation_remains_unchanged() -> None:
    form_values = composition_form_values() | {
        "dataset.mode": "query_first",
        "query.value": "reviewed:true",
        "query.input_mode": "manual",
    }

    descriptor = build_workflow_descriptor(form_values)

    assert descriptor["query"]["value"] == "reviewed:true"
    assert "composition" not in descriptor["query"]

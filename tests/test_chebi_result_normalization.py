"""Tests for ChEBI workflow result normalization."""

from __future__ import annotations

from bioseq_dl.core.workflow.chebi_execution import normalize_chebi_records


def test_chebi_normalization_produces_stable_compound_fields() -> None:
    request_plan = {
        "source": "chebi",
        "resource": "entity",
        "query_model": "advanced_search",
        "parameters": {"chebi_id": "CHEBI:15377"},
    }
    payload = {
        "id": 15377,
        "chebi_accession": "CHEBI:15377",
        "name": "water",
        "definition": "An oxygen hydride.",
        "chemical_data": {
            "formula": "H2O",
            "charge": 0,
            "mass": "18.015",
            "monoisotopic_mass": "18.01056",
        },
        "default_structure": {
            "smiles": "[H]O[H]",
            "standard_inchi": "InChI=1S/H2O/h1H2",
            "standard_inchi_key": "XLYOFNOQVPJJNP-UHFFFAOYSA-N",
        },
        "database_accessions": {"CAS": [{"accession_number": "7732-18-5"}]},
    }

    result = normalize_chebi_records(payload, request_plan)

    assert result.loc[0, "source"] == "chebi"
    assert result.loc[0, "compound_id"] == "CHEBI:15377"
    assert result.loc[0, "chebi_id"] == "CHEBI:15377"
    assert result.loc[0, "formula"] == "H2O"
    assert result.loc[0, "charge"] == 0
    assert result.loc[0, "smiles"] == "[H]O[H]"
    assert result.loc[0, "query_resource"] == "entity"


def test_chebi_normalization_handles_search_hits_and_missing_fields() -> None:
    request_plan = {
        "source": "chebi",
        "resource": "entity",
        "query_model": "advanced_search",
        "parameters": {"name_contains": "caffeine"},
    }
    payload = [{"_source": {"chebi_accession": "CHEBI:27732", "name": "caffeine"}}]

    result = normalize_chebi_records(payload, request_plan)

    assert result.loc[0, "compound_id"] == "CHEBI:27732"
    assert result.loc[0, "name"] == "caffeine"
    assert result.loc[0, "definition"] is None

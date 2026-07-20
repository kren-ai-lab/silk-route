"""Offline tests for the UniProt / ChEMBL query interpreters.

The interpreters are pure string->string transforms (alias expansion, ignored
field stripping, multimode ``_any/_all/_not`` expansion and per-field value
resolution), so these run with no network and no mocks.
"""

from __future__ import annotations

import pytest

from bioseq_dl.core.workflow.query_interpreter import (
    build_default_chembl_interpreter,
    build_default_uniprot_interpreter,
)


@pytest.fixture
def uniprot():
    return build_default_uniprot_interpreter()


@pytest.fixture
def chembl():
    return build_default_chembl_interpreter()


# --- UniProt interpret -----------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        # single-word friendly value -> native id (map resolvers)
        ("organism:human", "organism_id:9606"),
        ("ec:transferase", "ec:2"),
        # numeric range -> UniProt [low TO high]
        ("length:100-200", "length:[100 TO 200]"),
        # already-native ids pass through untouched
        ("go:0006281", "go:0006281"),
        ("keywords:KW-0067", "keyword:KW-0067"),
        # prefix aliases
        ("db:pdb", "database:pdb"),
        ("xref:pdb", "database:pdb"),
        ("org:human", "organism_id:9606"),
        # native fields with no field config pass through
        ("reviewed:true", "reviewed:true"),
        ("reviewed:true AND organism:human", "reviewed:true AND organism_id:9606"),
        # ignored fields (chembl-side macros) are stripped, booleans cleaned up
        ("ic50:<1000 AND reviewed:true", "reviewed:true"),
        ("ic50:<1000 OR activity:high AND target:x", ""),
    ],
)
def test_uniprot_interpret(uniprot, query, expected):
    assert uniprot.interpret(query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("keywords_any:KW-0067,KW-0479", "(keyword:KW-0067 OR keyword:KW-0479)"),
        ("keywords_all:KW-0067,KW-0479", "(keyword:KW-0067 AND keyword:KW-0479)"),
        ("keywords_not:KW-0067,KW-0479", "NOT (keyword:KW-0067 AND keyword:KW-0479)"),
        # no suffix defaults to _all
        ("keywords:KW-0067,KW-0479", "(keyword:KW-0067 AND keyword:KW-0479)"),
        # single value: no surrounding parentheses
        ("keywords_any:KW-0067", "keyword:KW-0067"),
    ],
)
def test_uniprot_multimode_expansion(uniprot, query, expected):
    assert uniprot.interpret(query) == expected


# --- UniProt extract_databases ---------------------------------------------


def test_extract_databases_lists_requested_dbs(uniprot):
    assert uniprot.extract_databases("databases:pdb,alphafold") == ["pdb", "alphafold"]


def test_extract_databases_temperature_implies_brenda(uniprot):
    assert uniprot.extract_databases("temperature:30-40") == [
        "brenda_getTemperatureOptimum",
        "brenda_getTemperatureStability",
        "brenda_getTemperatureRange",
    ]


def test_extract_databases_none_when_no_special_fields(uniprot):
    assert uniprot.extract_databases("reviewed:true") == []


# --- ChEMBL interpret ------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("ic50:100-200", "standard_type=IC50 AND standard_value>100 AND standard_value<200"),
        ("ic50:<1000", "standard_type=IC50 AND standard_value<1000"),
        ("ic50:>=50", "standard_type=IC50 AND standard_value>=50"),
        ("ic50:50", "standard_type=IC50 AND standard_value=50"),
        # allowed non-ic50 fields pass through
        ("target:Proteases", "target:Proteases"),
        # ignore_all_fields strips unlisted fields but keeps allowed ones
        ("foo:bar AND ic50:<50", "standard_type=IC50 AND standard_value<50"),
    ],
)
def test_chembl_interpret(chembl, query, expected):
    assert chembl.interpret(query) == expected


def test_chembl_mode_suffix_clause_is_kept(chembl):
    # A _any/_all/_not suffix on an allowed field must not be swallowed and dropped.
    result = chembl.interpret("ic50_any:100,1000")
    assert "standard_value=100" in result
    assert "standard_value=1000" in result


@pytest.mark.parametrize("value", ["inf", "nan"])
def test_chembl_rejects_non_finite_values(chembl, value):
    # Non-finite numbers must not become a standard_value clause.
    assert f"standard_value={value}" not in chembl.interpret(f"ic50:{value}")

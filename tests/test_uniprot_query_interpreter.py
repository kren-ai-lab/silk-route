"""Tests for UniProt friendly query interpretation."""

from __future__ import annotations

from bioseq_dl.core.workflow.query_interpreter import (
    build_default_uniprot_interpreter,
    split_quoted_csv_values,
)


def test_uniprot_interpreter_resolves_quoted_organism_value():
    interpreter = build_default_uniprot_interpreter()

    assert interpreter.interpret('organism_any:"Homo sapiens"') == "organism_id:9606"


def test_uniprot_interpreter_resolves_quoted_keyword_values():
    interpreter = build_default_uniprot_interpreter()

    assert (
        interpreter.interpret('keywords_any:"ATP binding","Metal-binding"')
        == "(keyword:KW-0067 OR keyword:KW-0479)"
    )


def test_uniprot_interpreter_resolves_quoted_go_values():
    interpreter = build_default_uniprot_interpreter()

    assert (
        interpreter.interpret('go_any:"DNA repair","protein folding"')
        == "(go:0006281 OR go:0006457)"
    )


def test_uniprot_interpreter_keeps_temperature_ranges_working():
    interpreter = build_default_uniprot_interpreter()

    assert (
        interpreter.interpret("temperature_any:20-30,50-60")
        == "(cc_bpcp_temp_dependence:20-30 OR cc_bpcp_temp_dependence:50-60)"
    )


def test_uniprot_interpreter_handles_quoted_values_with_connectors():
    interpreter = build_default_uniprot_interpreter()

    assert (
        interpreter.interpret('organism_any:"Homo sapiens" AND temperature_any:20-30,50-60')
        == "organism_id:9606 AND (cc_bpcp_temp_dependence:20-30 OR cc_bpcp_temp_dependence:50-60)"
    )


def test_uniprot_interpreter_handles_mixed_quoted_values_with_or_connector():
    interpreter = build_default_uniprot_interpreter()

    assert (
        interpreter.interpret('keywords_any:"ATP binding","Metal-binding" OR go_any:"DNA repair"')
        == "(keyword:KW-0067 OR keyword:KW-0479) OR go:0006281"
    )


def test_uniprot_interpreter_resolves_taxonomy_alias_names():
    interpreter = build_default_uniprot_interpreter()

    assert interpreter.interpret("taxon_any:human") == "taxonomy_id:9606"
    assert interpreter.interpret('taxon_any:"Homo sapiens"') == "taxonomy_id:9606"
    assert interpreter.interpret("taxid_any:human") == "taxonomy_id:9606"
    assert interpreter.interpret("taxa_any:human") == "taxonomy_id:9606"


def test_uniprot_interpreter_compacts_parentheses_without_removing_boolean_spaces():
    interpreter = build_default_uniprot_interpreter()

    assert (
        interpreter.interpret('keywords_any:"ATP binding","Metal-binding" AND go_any:"DNA repair"')
        == "(keyword:KW-0067 OR keyword:KW-0479) AND go:0006281"
    )


def test_uniprot_interpreter_resolves_databases_field():
    interpreter = build_default_uniprot_interpreter()

    assert interpreter.interpret("databases_any:alphafold,pdb") == "(database:alphafolddb OR database:pdb)"


def test_split_quoted_csv_values_does_not_split_inside_quotes():
    assert split_quoted_csv_values('"DNA, repair","protein folding",20-30') == [
        '"DNA, repair"',
        '"protein folding"',
        "20-30",
    ]

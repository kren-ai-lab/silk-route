"""Unit tests for the UniProt field extractors.

These pure functions transform UniProt JSON sub-structures. Where possible we
drive them with the real UniProt fixture so they track the live response shape.
"""

from __future__ import annotations

from bioseq_dl.core.utils.uniprot_auxiliary_methods import (
    extract_active_sites,
    extract_database_terms,
    extract_diseases,
    extract_domains,
    extract_ec_numbers,
    extract_gene_names,
    extract_interactions,
    extract_keywords,
    extract_ph,
    extract_references,
    extract_temperature,
    extract_variants,
)
from tests._helpers import load_fixture


def _uniprot_entry() -> dict:
    return load_fixture("uniprot", "idmapping_results")["results"][0]["to"]


def test_extract_ec_numbers_from_real_entry():
    entry = _uniprot_entry()
    ec_data = entry["proteinDescription"]["recommendedName"]["ecNumbers"]
    assert extract_ec_numbers(ec_data) == ["2.6.1.1", "2.6.1.7"]


def test_extract_ec_numbers_non_list_returns_empty():
    assert extract_ec_numbers(None) == []  # ty: ignore[invalid-argument-type]  # robustness test


def test_extract_gene_names_from_real_entry():
    entry = _uniprot_entry()
    assert extract_gene_names(entry["genes"]) == ["GOT2"]


def test_extract_gene_names_non_list_returns_empty():
    assert extract_gene_names("nope") == []  # ty: ignore[invalid-argument-type]  # robustness test


def test_extract_database_terms_from_reaction_comments():
    # The reaction branch requires every entry to carry a "reaction" key, so feed
    # the CATALYTIC ACTIVITY comments (which hold the Rhea/ChEBI cross-refs).
    entry = _uniprot_entry()
    reaction_comments = [c for c in entry["comments"] if "reaction" in c]
    rhea_ids = extract_database_terms(reaction_comments, "Rhea")
    assert "RHEA:21824" in rhea_ids
    assert "RHEA:65560" in rhea_ids


def test_extract_database_terms_plain_xrefs():
    xrefs = [
        {"database": "KEGG", "id": "hsa:2806"},
        {"database": "PDB", "id": "1AB1"},
        {"database": "KEGG", "id": "hsa:2807"},
    ]
    assert extract_database_terms(xrefs, "KEGG") == ["hsa:2806", "hsa:2807"]


def test_extract_keywords():
    kws = [{"name": "Transferase"}, {"name": "Mitochondrion"}]
    assert extract_keywords(kws) == ["Transferase", "Mitochondrion"]


def test_extract_references():
    refs = [
        {
            "citation": {
                "title": "A paper",
                "authors": ["Doe J."],
                "journal": "J. Test",
                "publicationDate": "2020",
                "citationCrossReferences": [{"database": "PubMed", "id": "123"}],
            }
        }
    ]
    out = extract_references(refs)
    assert out == [
        {
            "title": "A paper",
            "authors": ["Doe J."],
            "journal": "J. Test",
            "pub_date": "2020",
            "pmid": "123",
        }
    ]


def test_extract_diseases():
    comments = [
        {
            "commentType": "DISEASE",
            "disease": {
                "diseaseId": "Cancer",
                "acronym": "CA",
                "diseaseAccession": "DI-001",
                "description": "desc",
            },
            "note": {"texts": [{"value": "a note"}]},
        },
        {"commentType": "FUNCTION"},  # ignored
    ]
    out = extract_diseases(comments)
    assert len(out) == 1
    assert out[0]["disease_id"] == "Cancer"
    assert out[0]["note"] == "a note"


def test_extract_active_sites_filters_by_type():
    features = [
        {
            "type": "Active site",
            "description": "Proton acceptor",
            "location": {"start": {"value": 100}, "end": {"value": 100}},
        },
        {"type": "Chain", "location": {"start": {"value": 1}, "end": {"value": 400}}},  # ignored
    ]
    out = extract_active_sites(features)
    assert out == [{"type": "Active site", "description": "Proton acceptor", "location": 100}]


def test_extract_domains_range_location():
    features = [
        {
            "type": "Domain",
            "description": "Kinase",
            "location": {"start": {"value": 10}, "end": {"value": 50}},
        }
    ]
    out = extract_domains(features)
    assert out == [{"type": "Domain", "description": "Kinase", "location": "10-50"}]


def test_extract_variants():
    features = [
        {
            "type": "Natural variant",
            "featureId": "VAR_001",
            "location": {"start": {"value": 72}, "end": {"value": 72}},
            "alternativeSequence": {"originalSequence": "R", "alternativeSequences": ["P"]},
            "description": "in dbSNP",
        }
    ]
    out = extract_variants(features)
    assert out[0]["id"] == "VAR_001"
    assert out[0]["location"] == 72
    assert out[0]["originalSequence"] == "R"


def test_extract_interactions():
    comments = [
        {
            "commentType": "INTERACTION",
            "interactions": [
                {
                    "interactantOne": {"uniProtKBAccession": "P1", "geneName": "A"},
                    "interactantTwo": {"uniProtKBAccession": "P2", "geneName": "B"},
                    "numberOfExperiments": 3,
                    "organismDiffer": False,
                }
            ],
        }
    ]
    out = extract_interactions(comments)
    assert out[0]["accesion_a"] == "P1"
    assert out[0]["accesion_b"] == "P2"
    assert out[0]["numberOfExperiments"] == 3


def test_extract_temperature_and_ph():
    comments = [
        {
            "commentType": "BIOPHYSICOCHEMICAL PROPERTIES",
            "temperatureDependence": {"texts": [{"value": "Optimum 37C"}]},
            "phDependence": {"texts": [{"value": "Optimum pH 7"}]},
        }
    ]
    assert extract_temperature(comments) == ["Optimum 37C"]
    assert extract_ph(comments) == ["Optimum pH 7"]

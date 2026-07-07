"""Offline tests for MainWorkflow orchestration.

Mode/modality routing and the query_composition aggregation are exercised with
stubbed modality handlers (no network). One end-to-end protein run drives the
real pipeline against a mocked UniProt stream endpoint.
"""

from __future__ import annotations

import polars as pl
import pytest
from niquests_mock import startswith

from bioseq_dl.core.interfaces.uniprot import API_URL, UniprotInterface
from bioseq_dl.core.workflow.main_workflow import MainWorkflow
from tests._helpers import load_fixture


@pytest.fixture
def workflow():
    return MainWorkflow()


# --- run() mode routing ----------------------------------------------------


def test_run_routes_to_query_first(workflow, monkeypatch):
    monkeypatch.setattr(workflow, "query_first", lambda **kw: ("QF", kw))
    out, kw = workflow.run(modality="protein", mode="query_first", query="x")
    assert out == "QF"
    assert kw["modality"] == "protein"


def test_run_routes_to_query_composition(workflow, monkeypatch):
    monkeypatch.setattr(workflow, "query_composition", lambda **kw: ("QC", kw))
    out, _ = workflow.run(modality="protein", mode="query_composition", queries_with_labels=[])
    assert out == "QC"


@pytest.mark.parametrize(
    ("modality", "mode", "match"),
    [
        ("", "query_first", "modality"),
        ("protein", "", "mode"),
        ("protein", "bogus", "Unknown workflow mode"),
    ],
)
def test_run_invalid_args_raise(workflow, modality, mode, match):
    with pytest.raises(ValueError, match=match):
        workflow.run(modality=modality, mode=mode)


def test_query_first_unknown_modality_raises(workflow):
    with pytest.raises(ValueError, match="Unknown modality"):
        workflow.query_first(modality="genome", query="x")


# --- query_composition aggregation -----------------------------------------


def test_query_composition_labels_and_merges(workflow, monkeypatch):
    def fake_run_protein(query=None, **kwargs):
        return {"uniprot": pl.DataFrame({"acc": [f"P{query}"]})}, {"modality": "protein"}

    monkeypatch.setattr(workflow, "run_protein", fake_run_protein)

    data, metadata = workflow.query_composition(
        modality="protein", queries_with_labels=[("1", "la"), ("2", "lb")]
    )

    # Both runs concatenated under uniprot, each row tagged with its label.
    assert data["uniprot"].to_dicts() == [
        {"acc": "P1", "_label": "la"},
        {"acc": "P2", "_label": "lb"},
    ]
    assert [p["label"] for p in metadata["parts"]] == ["la", "lb"]


def test_query_composition_empty_parts_returns_empty(workflow, monkeypatch):
    monkeypatch.setattr(workflow, "run_protein", lambda **kw: ({}, {}))

    data, metadata = workflow.query_composition(modality="protein", queries_with_labels=[("q", "l")])

    assert data == {}
    assert [p["label"] for p in metadata["parts"]] == ["l"]


def test_query_composition_unknown_modality_raises(workflow):
    with pytest.raises(ValueError, match="Unknown modality"):
        workflow.query_composition(modality="genome", queries_with_labels=[("q", "l")])


# --- _step_chembl_to_uniprot_query -----------------------------------------


def test_chembl_to_uniprot_builds_xref_query(workflow):
    context = {
        "searches": {"uniprot": {"query": None}},
        "data": {"chembl": pl.DataFrame({"target_chembl_id": ["CHEMBL1", "CHEMBL2"]})},
    }
    workflow._step_chembl_to_uniprot_query(context)
    assert context["searches"]["uniprot"]["query"] == "(xref:chembl-CHEMBL1 OR xref:chembl-CHEMBL2)"


def test_chembl_to_uniprot_chunks_large_id_lists(workflow):
    ids = [f"CHEMBL{i}" for i in range(150)]  # > CHEMBL_ID_CHUNK_SIZE (100)
    context = {
        "searches": {"uniprot": {"query": None}},
        "data": {"chembl": pl.DataFrame({"target_chembl_id": ids})},
    }
    workflow._step_chembl_to_uniprot_query(context)
    query = context["searches"]["uniprot"]["query"]
    assert isinstance(query, list)
    assert len(query) == 2  # 100 + 50


def test_chembl_to_uniprot_no_ids_leaves_query_untouched(workflow):
    context = {"searches": {"uniprot": {"query": None}}, "data": {"chembl": pl.DataFrame()}}
    workflow._step_chembl_to_uniprot_query(context)
    assert context["searches"]["uniprot"]["query"] is None


# --- end-to-end protein run (mocked UniProt stream) ------------------------


def test_run_protein_fetches_parses_and_stamps_time(niquests_mock):
    results = load_fixture("uniprot", "idmapping_results")
    niquests_mock.get(url=startswith(f"{API_URL}/uniprotkb/stream")).respond(
        status_code=200, json=results, headers={"Content-Length": "123"}
    )

    workflow = MainWorkflow(uniprot_interface=UniprotInterface())
    data, metadata = workflow.run_protein(query="kinase", enrich=False)

    # UniProt response parsed to a DataFrame and carried under data["uniprot"].
    assert isinstance(data["uniprot"], pl.DataFrame)
    assert len(data["uniprot"]) == len(results["results"])
    # Provenance/timing stamped, fetch metadata recorded.
    assert "time_taken_seconds" in metadata
    assert "fetch" in metadata["uniprot"]


def test_run_protein_empty_query_skips_fetch(niquests_mock):
    workflow = MainWorkflow(uniprot_interface=UniprotInterface())
    data, _ = workflow.run_protein(query="", enrich=False)

    # Empty interpreted query short-circuits: no network call is made.
    assert len(niquests_mock.calls) == 0
    # Parsed output degrades to an empty DataFrame rather than raising.
    assert isinstance(data["uniprot"], pl.DataFrame)
    assert data["uniprot"].is_empty()

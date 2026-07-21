"""Offline tests for MainWorkflow.run_compound source routing.

PubChem/ChEBI prefixes dispatch to their own backends (not ChEMBL); cross-modality
ChEMBL resources are rejected. Fetch steps stubbed; no network.
"""

from __future__ import annotations

import pytest

from bioseq_dl.core.workflow.main_workflow import MainWorkflow


@pytest.fixture
def workflow():
    return MainWorkflow()


@pytest.fixture
def record_steps(workflow, monkeypatch):
    """Stub the three compound fetch steps, recording which one fired."""
    called: list[str] = []

    def make(name):
        def _step(context, *args, **kwargs):
            called.append(name)
            context.setdefault("data", {})[name] = "fetched"
            return context

        return _step

    monkeypatch.setattr(workflow, "_step_fetch_pubchem", make("pubchem"))
    monkeypatch.setattr(workflow, "_step_fetch_chebi", make("chebi"))
    monkeypatch.setattr(workflow, "_step_fetch_chembl", make("chembl"))
    return called


def test_pubchem_prefixed_query_routes_to_pubchem(workflow, record_steps):
    data, meta = workflow.run_compound("pubchem.compound:name=aspirin")
    assert record_steps == ["pubchem"]
    assert meta["modality"] == "compound"
    assert "pubchem" in data


def test_chebi_prefixed_query_routes_to_chebi(workflow, record_steps):
    data, _meta = workflow.run_compound("chebi.entity:name=water")
    assert record_steps == ["chebi"]
    assert "chebi" in data


def test_bare_query_routes_to_chembl(workflow, record_steps):
    workflow.run_compound("IC50 aspirin")
    assert record_steps == ["chembl"]


def test_chembl_molecule_resource_allowed(workflow, record_steps):
    workflow.run_compound("chembl.molecule:max_phase=4")
    assert record_steps == ["chembl"]


def test_cross_modality_chembl_resource_rejected(workflow, record_steps):
    # target resource = interaction modality, not compound.
    with pytest.raises(ValueError, match="not valid for compound"):
        workflow.run_compound("chembl.target:foo")
    assert record_steps == []

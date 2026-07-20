"""Offline tests for the structure-download control validation guard."""

from __future__ import annotations

import pytest

from bioseq_dl.core.workflow.schema import validate_structure_download_controls


@pytest.mark.parametrize("key", ["download_alphafold_structures", "download_pdb_structures"])
class TestValidateStructureDownloadControls:
    def test_inactive_download_is_always_ok(self, key):
        # Inactive flag -> no-op.
        validate_structure_download_controls({"modality": "compound"}, {key: False})

    def test_protein_enrich_true_is_ok(self, key):
        validate_structure_download_controls(
            {"modality": "protein", "interaction_type": None},
            {key: True, "enrich": True},
        )

    def test_non_protein_modality_rejected(self, key):
        with pytest.raises(ValueError, match="only for protein workflows"):
            validate_structure_download_controls({"modality": "compound"}, {key: True, "enrich": True})

    def test_interaction_type_present_rejected(self, key):
        with pytest.raises(ValueError, match="no interaction_type"):
            validate_structure_download_controls(
                {"modality": "protein", "interaction_type": "protein-ligand"},
                {key: True, "enrich": True},
            )

    def test_requires_enrich_true(self, key):
        with pytest.raises(ValueError, match=r"require execution\.enrich"):
            validate_structure_download_controls(
                {"modality": "protein", "interaction_type": None},
                {key: True, "enrich": False},
            )

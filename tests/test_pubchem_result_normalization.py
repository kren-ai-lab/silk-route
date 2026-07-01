"""Tests for PubChem workflow result normalization."""

from __future__ import annotations

from bioseq_dl.core.workflow.pubchem_execution import normalize_pubchem_records


def test_pubchem_normalization_produces_stable_compound_fields() -> None:
    request_plan = {
        "source": "pubchem",
        "resource": "compound",
        "query_model": "compound_lookup",
        "parameters": {"cid": "2244"},
    }
    payload = {
        "PropertyTable": {
            "Properties": [
                {
                    "CID": 2244,
                    "MolecularFormula": "C9H8O4",
                    "MolecularWeight": "180.16",
                    "CanonicalSMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "ConnectivitySMILES": "legacy-canonical-smiles",
                    "IsomericSMILES": "CC(=O)Oc1ccccc1C(=O)O",
                    "SMILES": "legacy-isomeric-smiles",
                    "InChI": "InChI=1S/C9H8O4",
                    "InChIKey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
                    "IUPACName": "2-acetyloxybenzoic acid",
                }
            ]
        }
    }

    result = normalize_pubchem_records(payload, request_plan)

    assert result.loc[0, "source"] == "pubchem"
    assert result.loc[0, "compound_id"] == "PUBCHEM:2244"
    assert result.loc[0, "pubchem_cid"] == 2244
    assert result.loc[0, "name"] == "2-acetyloxybenzoic acid"
    assert result.loc[0, "canonical_smiles"] == "CC(=O)OC1=CC=CC=C1C(=O)O"
    assert result.loc[0, "isomeric_smiles"] == "CC(=O)Oc1ccccc1C(=O)O"
    assert result.loc[0, "query_resource"] == "compound"
    assert result.loc[0, "query_model"] == "compound_lookup"


def test_pubchem_normalization_handles_missing_optional_fields() -> None:
    request_plan = {
        "source": "pubchem",
        "resource": "structure",
        "query_model": "structure_search",
        "parameters": {"smiles_substructure": "c1ccccc1"},
    }

    result = normalize_pubchem_records([{"CID": 241}], request_plan)

    assert result.loc[0, "compound_id"] == "PUBCHEM:241"
    assert result.loc[0, "name"] is None
    assert result.loc[0, "query_resource"] == "structure"

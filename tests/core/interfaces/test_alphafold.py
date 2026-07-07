"""Offline tests for the AlphaFold interface."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest
import responses

from bioseq_dl.core.interfaces.alphafold import AlphafoldInterface
from bioseq_dl.core.interfaces.base import BaseAPIInterface
from tests._helpers import load_fixture

PREDICTION_URL = "https://alphafold.ebi.ac.uk/api/prediction/P12345"
PDB_URL = "https://alphafold.ebi.ac.uk/files/AF-P12345-F1-model_v4.pdb"


def fake_base_fetch_single(
    _interface: BaseAPIInterface,
    _query: object,
    _parse: bool = False,
    *_args: object,
    **_kwargs: object,
) -> tuple[pd.DataFrame, dict]:
    """Return one parsed prediction DataFrame for structure propagation tests."""
    return pd.DataFrame([{"entryId": "AF-P12345-F1", "pdbUrl": PDB_URL}]), {}


@pytest.fixture
def interface(tmp_path):
    # The ctor requires an init.yml (with download_folder) in config_dir.
    (tmp_path / "init.yml").write_text(f"download_folder: {tmp_path}\n")
    # structures=None: avoid the extra structure-file downloads in fetch_single/fetch_batch.
    return AlphafoldInterface(
        structures=None,
        cache_dir=str(tmp_path),
        config_dir=str(tmp_path),
        min_wait=0,
        max_wait=0,
        use_config=False,
    )


@pytest.fixture
def structure_interface(tmp_path):
    """Return an AlphaFold interface configured to download PDB structures."""
    return AlphafoldInterface(
        structures=["pdb"],
        cache_dir=str(tmp_path / "cache"),
        config_dir=str(tmp_path / "config"),
        output_dir=str(tmp_path / "structures"),
        min_wait=0,
        max_wait=0,
        use_config=False,
    )


def test_fetch_builds_url_and_returns_prediction(interface, mocked_responses):
    body = load_fixture("alphafold", "prediction")
    mocked_responses.add(responses.GET, PREDICTION_URL, json=body, status=200)

    result = interface.fetch("P12345", method="prediction")

    assert result == body
    assert len(mocked_responses.calls) == 1
    assert mocked_responses.calls[0].request.url.startswith(PREDICTION_URL)


def test_direct_alphafold_usage_does_not_download_structures_by_default(interface):
    assert interface.structures is None


def test_parse_extracts_requested_fields(interface):
    body = load_fixture("alphafold", "prediction")
    parsed = interface.parse(body, fields_to_extract=["entryId", "uniprotAccession"])

    assert isinstance(parsed, list)
    assert parsed[0] == {"entryId": "AF-P12345-F1", "uniprotAccession": "P12345"}


def test_fetch_single_round_trips_through_cache(interface, mocked_responses):
    body = load_fixture("alphafold", "prediction")
    mocked_responses.add(responses.GET, PREDICTION_URL, json=body, status=200)

    first, _ = interface.fetch_single("P12345", method="prediction")
    second, _ = interface.fetch_single("P12345", method="prediction")

    assert len(mocked_responses.calls) == 1
    assert first == second


def test_download_structures_writes_pdb_and_preserves_local_path(
    structure_interface,
) -> None:
    response = Mock(content=b"PDB CONTENT")
    structure_interface.session.get = Mock(return_value=response)
    parsed = {"entryId": "AF-P12345-F1", "pdbUrl": PDB_URL}

    result = structure_interface.download_structures(parsed)

    expected_path = Path(structure_interface.output_dir) / "AF-P12345-F1-model_v4.pdb"
    assert expected_path.read_bytes() == b"PDB CONTENT"
    assert result["pdb_file"] == str(expected_path)
    assert "pdbUrl" not in result
    response.raise_for_status.assert_called_once_with()


def test_download_structures_preserves_existing_pdb_path_without_request(
    structure_interface,
) -> None:
    expected_path = Path(structure_interface.output_dir) / "AF-P12345-F1-model_v4.pdb"
    expected_path.write_bytes(b"EXISTING PDB")
    structure_interface.session.get = Mock()

    result = structure_interface.download_structures({"pdbUrl": PDB_URL})

    assert result["pdb_file"] == str(expected_path)
    assert "pdbUrl" not in result
    structure_interface.session.get.assert_not_called()


def test_fetch_single_preserves_pdb_file_in_dataframe(
    structure_interface,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = Mock(content=b"PDB CONTENT")
    structure_interface.session.get = Mock(return_value=response)
    monkeypatch.setattr(BaseAPIInterface, "fetch_single", fake_base_fetch_single)

    result, _metadata = structure_interface.fetch_single("P12345", parse=True)

    assert isinstance(result, pd.DataFrame)
    assert result.loc[0, "pdb_file"].endswith("AF-P12345-F1-model_v4.pdb")
    assert "pdbUrl" not in result.columns

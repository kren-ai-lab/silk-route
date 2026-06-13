"""Offline tests for the AlphaFold interface."""

from __future__ import annotations

import pytest
import responses

from bioseq_dl.core.interfaces.alphafold import AlphafoldInterface
from tests._helpers import load_fixture

PREDICTION_URL = "https://alphafold.ebi.ac.uk/api/prediction/P12345"


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


def test_fetch_builds_url_and_returns_prediction(interface, mocked_responses):
    body = load_fixture("alphafold", "prediction")
    mocked_responses.add(responses.GET, PREDICTION_URL, json=body, status=200)

    result = interface.fetch("P12345", method="prediction")

    assert result == body
    assert len(mocked_responses.calls) == 1
    assert mocked_responses.calls[0].request.url.startswith(PREDICTION_URL)


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

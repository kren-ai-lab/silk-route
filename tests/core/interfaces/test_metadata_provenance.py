"""Provenance fields stamped onto fetch metadata.

Every ``fetch_single`` / ``fetch_batch`` return must carry a ``tool`` block
(library name + version) and an ISO-8601 ``started_at`` timestamp, so a saved
dataset records which version of the library produced it and when.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

import pytest

import bioseq_dl
from bioseq_dl.core.interfaces.base import BaseAPIInterface
from bioseq_dl.core.metadata import FetchMetadata


class FakeInterface(BaseAPIInterface):
    API_NAME = "Fake"
    METHODS: ClassVar[dict[str, Any]] = {
        "get": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {"id": (str, None, True)},
            "group_queries": ["id"],
            "separator": ",",
        }
    }

    def __init__(self, **kwargs):
        super().__init__(min_wait=0, max_wait=0, use_config=False, **kwargs)

    def fetch(self, query, *, method="get", **kwargs):
        raw = query["id"] if isinstance(query, dict) else query
        ids = raw.split(",") if isinstance(raw, str) else list(raw)
        return [{"id": x, "value": f"val{x}"} for x in ids]

    def parse(self, data, fields_to_extract, **kwargs):
        return data


@pytest.fixture
def interface(tmp_path):
    return FakeInterface(cache_dir=str(tmp_path))


def _assert_provenance(metadata: dict) -> None:
    assert metadata["tool"] == {"name": "bioseq_dl", "version": bioseq_dl.__version__}
    # started_at / finished_at are parseable ISO-8601 timestamps (not the empty
    # skeleton value), and the run cannot finish before it started.
    assert metadata["started_at"]
    assert metadata["finished_at"]
    started = datetime.fromisoformat(metadata["started_at"])
    finished = datetime.fromisoformat(metadata["finished_at"])
    assert finished >= started


def test_fetch_single_stamps_provenance(interface):
    _, metadata = interface.fetch_single({"id": ["a", "b"]}, method="get", parse=True)
    _assert_provenance(metadata)


def test_fetch_batch_stamps_provenance(interface):
    _, metadata = interface.fetch_batch([{"id": ["a", "b"]}], method="get", parse=True)
    _assert_provenance(metadata)


def test_fetch_metadata_skeleton_has_provenance_keys():
    skeleton = FetchMetadata().to_dict()
    assert skeleton["tool"] == {"name": "", "version": ""}
    assert skeleton["started_at"] == ""
    assert skeleton["finished_at"] == ""
    assert "execution_time" not in skeleton

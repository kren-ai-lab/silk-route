"""FetchMetadata schema v2: serialization, round-trip, and same-source merge."""

from __future__ import annotations

from bioseq_dl.core.metadata import FailedBlock, FetchMetadata, IdBlock, RequestInfo, ToolInfo


def test_to_dict_shape():
    meta = FetchMetadata(
        tool=ToolInfo(name="bioseq_dl", version="0.1.0"),
        started_at="2026-06-23T10:00:00+00:00",
        finished_at="2026-06-23T10:00:01+00:00",
        request=RequestInfo(api_name="ChEMBL", method="molecule", option=None),
    )
    meta.fetched.add("P1", {"id": "P1"})

    d = meta.to_dict()
    assert d["tool"] == {"name": "bioseq_dl", "version": "0.1.0"}
    assert d["request"] == {"api_name": "ChEMBL", "method": "molecule", "option": None}
    assert d["fetched"] == {"ids": ["P1"], "subqueries": [{"id": "P1"}], "length": 1}
    # Symmetric empty buckets all carry a length; failed also carries reasons.
    assert d["cached"] == {"ids": [], "subqueries": [], "length": 0}
    assert d["failed"] == {"ids": [], "subqueries": [], "reasons": [], "length": 0}


def test_from_dict_round_trips():
    meta = FetchMetadata(request=RequestInfo(api_name="KEGG", method="get", option="aaseq"))
    meta.cached.add("hsa:1", {"entries": ["hsa:1"]})
    meta.failed.add("bad", {"entries": ["bad"]})

    assert FetchMetadata.from_dict(meta.to_dict()).to_dict() == meta.to_dict()


def test_from_dict_tolerates_missing_keys():
    # Empty / partial dicts fall back to defaults (used when merge seeds from {}).
    assert FetchMetadata.from_dict({}).to_dict() == FetchMetadata().to_dict()
    assert FetchMetadata.from_dict(None).to_dict() == FetchMetadata().to_dict()


def test_merge_accumulates_buckets_and_widens_window():
    a = FetchMetadata(
        started_at="2026-06-23T10:00:05+00:00",
        finished_at="2026-06-23T10:00:08+00:00",
        request=RequestInfo(api_name="BioGRID", method="interactions"),
        data_info={"total_entries": 2, "data_type": "DataFrame", "columns": [{"name": "x", "n_missing": 1}]},
    )
    a.fetched.add("g1", {"gene": "g1"})

    b = FetchMetadata(
        started_at="2026-06-23T10:00:00+00:00",  # earlier
        finished_at="2026-06-23T10:00:12+00:00",  # later
        request=RequestInfo(api_name="BioGRID", method="interactions"),
        data_info={"total_entries": 3, "data_type": "DataFrame", "columns": [{"name": "x", "n_missing": 2}]},
    )
    b.fetched.add("g2", {"gene": "g2"})

    merged = a.merge(b).to_dict()

    assert merged["started_at"] == "2026-06-23T10:00:00+00:00"  # min
    assert merged["finished_at"] == "2026-06-23T10:00:12+00:00"  # max
    assert merged["fetched"]["ids"] == ["g1", "g2"]
    assert merged["fetched"]["length"] == 2
    assert merged["data_info"]["total_entries"] == 5  # summed
    assert merged["data_info"]["columns"] == [{"name": "x", "n_missing": 3}]  # n_missing summed by name


def test_merge_seeds_request_and_tool_from_populated_side():
    empty = FetchMetadata()
    populated = FetchMetadata(
        tool=ToolInfo(name="bioseq_dl", version="0.1.0"),
        request=RequestInfo(api_name="ChEMBL", method="molecule"),
    )
    merged = empty.merge(populated)
    assert merged.request.api_name == "ChEMBL"
    assert merged.tool.version == "0.1.0"


def test_merge_does_not_mutate_inputs():
    a = FetchMetadata()
    a.fetched.add("g1", {"gene": "g1"})
    b = FetchMetadata()
    b.fetched.add("g2", {"gene": "g2"})

    a.merge(b)

    assert a.fetched.ids == ["g1"]
    assert b.fetched.ids == ["g2"]


def test_idblock_add_keeps_ids_and_subqueries_parallel():
    block = IdBlock()
    block.add("id1", {"q": 1})
    block.add("id2", {"q": 2})
    assert block.ids == ["id1", "id2"]
    assert block.subqueries == [{"q": 1}, {"q": 2}]


def test_failed_block_tracks_reasons_and_merges():
    a = FailedBlock()
    a.add("x", {"id": "x"}, "request_error")
    b = FailedBlock()
    b.add("y", {"id": "y"}, "empty_result")

    merged = a.merged_with(b)
    assert merged.to_dict() == {
        "ids": ["x", "y"],
        "subqueries": [{"id": "x"}, {"id": "y"}],
        "reasons": ["request_error", "empty_result"],
        "length": 2,
    }
    assert FailedBlock.from_dict(merged.to_dict()).to_dict() == merged.to_dict()

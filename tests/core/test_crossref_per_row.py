"""Per-row enrichment outcomes recorded under metadata ``extra.per_row`` (#7).

The merged aggregate alone hides which input rows came back empty or failed;
``_process_dataframe`` now also attaches a per-row breakdown.
"""

from __future__ import annotations

from typing import cast

import polars as pl

from silkroute.core.crossref_enricher import CrossRefEnricher, EndpointSpec
from silkroute.core.metadata import FetchMetadata


def test_process_dataframe_records_per_row_outcomes(monkeypatch):
    enricher = CrossRefEnricher()

    # Row 0 finds 2 records; row 1 comes back empty with a failed id.
    def fake_search_and_merge(row, instance, spec, params, fmt):
        if row["id"] == "P1":
            meta = FetchMetadata(data_info={"total_entries": 2})
            return [{"x": 1}, {"x": 2}], meta.to_dict()
        meta = FetchMetadata(data_info={"total_entries": 0})
        meta.failed.add("P2", {"id": "P2"}, "empty_result")
        return [], meta.to_dict()

    monkeypatch.setattr(enricher, "_search_and_merge", fake_search_and_merge)

    df = pl.DataFrame({"id": ["P1", "P2"]})
    # spec is unused once _search_and_merge is patched.
    _, metadata = enricher._process_dataframe(
        df, instance=None, spec=cast("EndpointSpec", None), params={}, fmt="json"
    )

    per_row = metadata["extra"]["per_row"]
    assert per_row == [
        {"row": 0, "found": 2, "failed_ids": [], "failed_reasons": []},
        {"row": 1, "found": 0, "failed_ids": ["P2"], "failed_reasons": ["empty_result"]},
    ]

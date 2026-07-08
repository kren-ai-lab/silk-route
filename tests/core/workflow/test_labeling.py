"""Offline tests for query-composition labeling and result merging helpers."""

from __future__ import annotations

import polars as pl

from bioseq_dl.core.workflow.main_workflow import (
    attach_label_to_part,
    merge_enrichment_data,
    merge_pair,
)


def test_attach_label_protein_labels_uniprot_only():
    part = {"uniprot": pl.DataFrame({"a": [1]})}
    labeled = attach_label_to_part(part, "L1", "protein")
    assert set(labeled) == {"uniprot"}
    assert labeled["uniprot"]["_label"].to_list() == ["L1"]


def test_attach_label_compound_labels_chembl_and_uniprot():
    part = {"chembl": pl.DataFrame({"a": [1]}), "uniprot": pl.DataFrame({"b": [2]})}
    labeled = attach_label_to_part(part, "L1", "compound")
    assert set(labeled) == {"chembl", "uniprot"}
    assert labeled["chembl"]["_label"].to_list() == ["L1"]
    assert labeled["uniprot"]["_label"].to_list() == ["L1"]


def test_attach_label_compound_without_uniprot_only_chembl():
    part = {"chembl": pl.DataFrame({"a": [1]})}
    assert set(attach_label_to_part(part, "L1", "compound")) == {"chembl"}


def test_attach_label_compound_missing_chembl_returns_empty():
    # Regression: compound modality is gated on a present chembl part.
    assert attach_label_to_part({"uniprot": pl.DataFrame({"a": [1]})}, "L1", "compound") == {}


def test_attach_label_unknown_modality_or_non_dict_returns_empty():
    assert attach_label_to_part({"uniprot": pl.DataFrame()}, "L1", "bogus") == {}
    assert attach_label_to_part("not-a-dict", "L1", "protein") == {}  # ty: ignore[invalid-argument-type]  # type: ignore[arg-type]


def test_attach_label_existing_label_column_preserved_as_original():
    part = {"uniprot": pl.DataFrame({"a": [1], "_label": ["old"]})}
    labeled = attach_label_to_part(part, "new", "protein")
    assert labeled["uniprot"]["_label"].to_list() == ["new"]
    assert labeled["uniprot"]["_label_original"].to_list() == ["old"]


def test_merge_pair_concats_dataframes():
    merged = merge_pair(pl.DataFrame({"a": [1]}), pl.DataFrame({"a": [2]}))
    assert merged["a"].to_list() == [1, 2]


def test_merge_pair_extends_lists_and_pairs_others():
    assert merge_pair([1], [2]) == [1, 2]
    assert merge_pair({"a": 1}, {"b": 2}) == [{"a": 1}, {"b": 2}]


def test_merge_enrichment_data_merges_by_endpoint_key():
    assert merge_enrichment_data([{"x": [1]}], {"x": [2]}) == [{"x": [1, 2]}]
    assert merge_enrichment_data([{"x": [1]}], {"y": [9]}) == [{"x": [1]}, {"y": [9]}]

"""Offline tests for ChEMBL activity-filter parsing and filter-rule validation.

Pure logic, no network: IC50 query parsing, activity endpoint parameter building,
and the filter-rule validator.
"""

from __future__ import annotations

import pytest

from silkroute.core.interfaces.chembl import ChEMBLInterface


@pytest.fixture
def interface(tmp_path):
    return ChEMBLInterface(
        cache_dir=str(tmp_path), config_dir=str(tmp_path), min_wait=0, max_wait=0, use_config=False
    )


# --- extract_ic50_activity_filter -------------------------------------------


def test_extract_returns_none_for_non_string():
    assert ChEMBLInterface.extract_ic50_activity_filter(123) is None


def test_extract_returns_none_when_no_ic50_signal():
    assert ChEMBLInterface.extract_ic50_activity_filter("standard_type='Ki'") is None


def test_extract_greater_than_sets_exclusive_min():
    f = ChEMBLInterface.extract_ic50_activity_filter("ic50 > 5")
    assert f["standard_value_min"] == 5.0
    assert f["standard_value_min_inclusive"] is False
    assert f["standard_value_max"] is None


def test_extract_gte_sets_inclusive_min():
    f = ChEMBLInterface.extract_ic50_activity_filter("ic50 >= 5")
    assert f["standard_value_min"] == 5.0
    assert f["standard_value_min_inclusive"] is True


def test_extract_lte_sets_inclusive_max():
    f = ChEMBLInterface.extract_ic50_activity_filter("ic50 <= 20")
    assert f["standard_value_max"] == 20.0
    assert f["standard_value_max_inclusive"] is True


def test_extract_equals_sets_exact_value():
    f = ChEMBLInterface.extract_ic50_activity_filter("ic50 = 10")
    assert f["standard_value"] == 10.0


def test_extract_range_sets_min_and_max():
    f = ChEMBLInterface.extract_ic50_activity_filter("ic50: 1-10")
    assert f["standard_value_min"] == 1.0
    assert f["standard_value_max"] == 10.0


def test_extract_recognizes_standard_type_form():
    f = ChEMBLInterface.extract_ic50_activity_filter("standard_type = 'IC50' and standard_value < 50")
    assert f["standard_type"] == "IC50"
    assert f["standard_value_max"] == 50.0


# --- build_activity_filter_params -------------------------------------------


def test_build_params_exact_value_short_circuits():
    params = ChEMBLInterface.build_activity_filter_params(
        {"standard_type": "IC50", "standard_value": 10.0}, limit=100
    )
    assert params == {
        "standard_type": "IC50",
        "format": "json",
        "limit": 100,
        "standard_value": "10",  # integer-valued float formatted without decimals
    }


def test_build_params_exclusive_min_uses_gt():
    params = ChEMBLInterface.build_activity_filter_params(
        {"standard_type": "IC50", "standard_value_min": 5.0, "standard_value_min_inclusive": False},
        limit=None,
    )
    assert params["standard_value__gt"] == "5"
    assert "limit" not in params


def test_build_params_inclusive_max_uses_lte():
    params = ChEMBLInterface.build_activity_filter_params(
        {"standard_type": "IC50", "standard_value_max": 2.5, "standard_value_max_inclusive": True},
        limit=None,
    )
    assert params["standard_value__lte"] == "2.5"


# --- validate_filter_rules --------------------------------------------------


def test_validate_filter_rules_accepts_valid(interface):
    assert interface.validate_filter_rules([{"field": "x", "filter_type": "iexact", "value": "v"}])


def test_validate_filter_rules_rejects_non_list(interface):
    assert interface.validate_filter_rules({"field": "x"}) is False


def test_validate_filter_rules_rejects_missing_key(interface):
    assert interface.validate_filter_rules([{"field": "x", "value": 1}]) is False


def test_validate_filter_rules_rejects_unknown_filter_type(interface):
    assert interface.validate_filter_rules([{"field": "x", "filter_type": "bogus", "value": 1}]) is False


def test_validate_filter_rules_rejects_bad_value_type(interface):
    assert interface.validate_filter_rules([{"field": "x", "filter_type": "iexact", "value": [1]}]) is False

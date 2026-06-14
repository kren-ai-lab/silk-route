"""Tests for nested-value extraction helpers."""

from __future__ import annotations

import pytest

from bioseq_dl.core.utils.base_auxiliary_methods import get_nested


def test_empty_path_returns_whole_object():
    data = {"a": 1}
    assert get_nested(data, "") is data


def test_simple_key():
    assert get_nested({"a": 1, "b": 2}, "a") == 1


def test_missing_key_returns_none():
    assert get_nested({"a": 1}, "missing") is None


def test_nested_dict_path():
    data = {"a": {"b": {"c": 42}}}
    assert get_nested(data, "a.b.c") == 42


def test_list_value_keeps_list_shape_single_element():
    # Bug A: a single-element list must NOT collapse to a scalar.
    data = {"items": [{"name": "x"}]}
    assert get_nested(data, "items.name") == ["x"]


def test_list_value_multiple_elements():
    data = {"items": [{"name": "x"}, {"name": "y"}]}
    assert get_nested(data, "items.name") == ["x", "y"]


def test_custom_separator_used_in_recursion():
    # Bug B: the separator must be honored at every nesting level, not just the first.
    data = {"a": {"b": {"c": 7}}}
    assert get_nested(data, "a/b/c", sep="/") == 7


def test_custom_separator_with_list():
    data = {"a": {"items": [{"v": 1}, {"v": 2}]}}
    assert get_nested(data, "a/items/v", sep="/") == [1, 2]


def test_non_string_path_raises_type_error():
    with pytest.raises(TypeError):
        get_nested({"a": 1}, 123)  # type: ignore[arg-type]


def test_scalar_data_returns_none_for_path():
    assert get_nested("not-a-dict", "a") is None

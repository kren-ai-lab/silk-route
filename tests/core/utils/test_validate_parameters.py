"""Unit tests for parameter validation and schema helpers."""

from __future__ import annotations

import pytest

from bioseq_dl.core.utils.base_auxiliary_methods import (
    camel_to_snake,
    get_feature_keys,
    get_primary_keys,
    validate_parameters,
)

# Schema entries are (type, default, is_primary).
SCHEMA = {
    "id": (str, None, True),
    "limit": (int, 10, False),
    "fmt": (str, "json", False),
}


def test_validate_parameters_applies_defaults():
    out = validate_parameters({"id": "X"}, SCHEMA)
    assert out == {"id": "X", "limit": 10, "fmt": "json"}


def test_validate_parameters_keeps_provided_values():
    out = validate_parameters({"id": "X", "limit": 5}, SCHEMA)
    assert out["limit"] == 5


def test_validate_parameters_rejects_unknown_keys():
    with pytest.raises(ValueError, match="Invalid parameter"):
        validate_parameters({"id": "X", "bogus": 1}, SCHEMA)


def test_validate_parameters_type_mismatch_raises():
    with pytest.raises(TypeError):
        validate_parameters({"id": "X", "limit": "notanint"}, SCHEMA)


def test_validate_parameters_none_schema_raises():
    with pytest.raises(ValueError, match="schema is not defined"):
        validate_parameters({}, None)


def test_validate_parameters_omits_keys_with_none_default():
    # 'id' has default None and is not provided -> excluded entirely.
    out = validate_parameters({}, SCHEMA)
    assert "id" not in out
    assert out == {"limit": 10, "fmt": "json"}


def test_get_primary_keys_sorted_and_deduped():
    schema = {"b": (str, None, True), "a": (str, None, True), "c": (int, 0, False)}
    assert get_primary_keys(schema) == ["a", "b"]


def test_camel_to_snake():
    assert camel_to_snake("camelCase") == "camel_case"
    assert camel_to_snake("HTTPMethod") == "h_t_t_p_method"
    assert camel_to_snake("simple") == "simple"


def test_get_feature_keys_nested_and_lists():
    data = {"name": "x", "nested": {"a": 1}, "tags": ["t1", "t2"]}
    keys = get_feature_keys(data)
    assert keys["name"] == "str"
    assert keys["nested.a"] == "dict(int)"
    assert keys["tags"] == "list(str)"

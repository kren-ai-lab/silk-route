"""Shared utility functions for parameter validation and field extraction."""

from typing import Any

### Useful functions ###


def get_nested(data: dict | list, path: str, sep: str = ".") -> Any:
    """Get a nested value from a dictionary or list given a specific path.

    Args:
        data (dict | list): Dictionary or list to search.
        path (str): Path to the desired value.
        sep (str): Separator used in the path. Default is '.'.

    Returns:
        Any: Value at the specified path, or None if not found.

    Raises:
        TypeError: If ``path`` is not a string.

    """
    if not path:
        return data

    if not isinstance(path, str):
        msg = f"Path must be a string, got {type(path).__name__} instead. Value: {path}"
        raise TypeError(msg)

    if not isinstance(data, dict):
        return None

    parts = path.split(sep, maxsplit=1)
    search_key = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    for key, value in data.items():
        if key == search_key:
            if isinstance(value, dict):
                return get_nested(value, rest, sep)
            if isinstance(value, list):
                return [get_nested(item, rest, sep) for item in value]
            return value

    return None


def validate_parameters(inputs: dict, param_schema: dict) -> dict:
    """Validate the input parameters against the method definition.

    Args:
        inputs (dict): The input parameters to validate.
        param_schema (dict): Schema dict mapping param name to (type, default, is_primary) tuples.

    Returns:
        dict: A dictionary of validated parameters.

    Raises:
        ValueError: If the method is not defined or if there are invalid parameters.
        TypeError: If a parameter is of the wrong type.

    """
    if param_schema is None:
        msg = "Parameter schema is not defined. Please check the method definition."
        raise ValueError(msg)

    valid_keys = set(param_schema.keys())
    provided_keys = set(inputs.keys())

    # Verify invalid keys
    invalid_keys = provided_keys - valid_keys
    if invalid_keys:
        msg = f"Invalid parameter(s): {invalid_keys}. Expected: {list(valid_keys)}"
        raise ValueError(msg)

    validated = {}
    for key, (expected_type, default, _) in param_schema.items():
        if key in inputs:
            value = inputs[key]
            if not isinstance(value, expected_type):
                msg = (
                    f"Parameter '{key}' should be of type {expected_type.__name__}, "
                    f"got {type(inputs[key]).__name__}: {inputs[key]!r}"
                )
                raise TypeError(msg)
            validated[key] = value
        elif default is not None:
            validated[key] = default

    return validated


def get_primary_keys(methods_def: dict) -> list:
    """Extract the sorted, unique primary-key parameter names from a methods definition.

    Args:
        methods_def (dict): Schema dict mapping param name to (type, default, is_primary) tuples.

    Returns:
        list: Sorted, de-duplicated names of parameters flagged as primary.

    """
    primary_keys = []
    for param, (_, _, is_primary) in methods_def.items():
        if is_primary:
            primary_keys.append(param)

    # Remove duplicates
    primary_keys = list(set(primary_keys))
    primary_keys.sort()
    return primary_keys

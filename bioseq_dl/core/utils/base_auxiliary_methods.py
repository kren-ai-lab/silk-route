import re
from typing import Any

### Useful functions ###


def camel_to_snake(name: str) -> str:
    """Convert str from camelCase to snake_case.

    Args:
        name (str): String in camelCase.

    Returns:
        str: String in snake_case.

    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def get_nested(data: dict, path: str, sep: str = ".") -> Any:
    """Get a nested value from a dictionary or list given a specific path.

    Args:
        data (Union[dict, list]): Dictionary or list to search.
        path (str): path to the desired value.
        sep (str): Separator used in the path. Default is '.'.

    Returns:
        Any: Value at the specified path, or None if not found.

    """
    if not path:
        return data

    try:
        search_key = path.split(".", maxsplit=1)[0]
    except AttributeError:
        raise ValueError(f"Path must be a string, got {type(path).__name__} instead. Value: {path}")

    for key, value in data.items():
        if key == search_key:
            if isinstance(value, dict):
                return get_nested(value, ".".join(path.split(".")[1:]))
            if isinstance(value, list):
                lst = [get_nested(item, ".".join(path.split(".")[1:])) for item in value]
                if len(lst) == 1:
                    return lst[0]
                return lst
            return value

    return None


def get_feature_keys(data: dict, sep: str = ".") -> dict:
    """Recursively get all keys in a nested dictionary and get the type of the value.
    Use dot notation for nested keys.

    Args:
        data (dict): The dictionary to extract keys from.
        sep (str): The separator to use for nested keys. Default is '.'.

    Returns:
        list: List of keys with their types.

    """
    keys = {}
    if data is None:
        return keys

    if isinstance(data, list):
        data = data[0]  # Use the first element of the list to determine the type

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                nested_keys = get_feature_keys(value, sep=sep)
                for nested_key, nested_value in nested_keys.items():
                    keys[f"{key}{sep}{nested_key}"] = f"{type(value).__name__}({nested_value})"
            if isinstance(value, list) and value:
                # Use the first element of the list to determine the type
                if isinstance(value[0], dict):
                    nested_keys = get_feature_keys(value[0], sep=sep)
                    for nested_key, nested_value in nested_keys.items():
                        keys[f"{key}{sep}{nested_key}"] = nested_value
                else:
                    keys[key] = f"list({type(value[0]).__name__})"
            else:
                keys[key] = type(value).__name__
    else:
        keys["value"] = type(data).__name__
    return keys


def validate_parameters(inputs: dict, param_schema: dict) -> dict:
    """Validates the input parameters against the method definition.

    Args:
        inputs (dict): The input parameters to validate.
        method (str): The method name to validate against.
        methods_def (dict): The definition of methods and their parameters.

    Returns:
        dict: A dictionary of validated parameters.

    Raises:
        ValueError: If the method is not defined or if there are invalid parameters.
        TypeError: If a parameter is of the wrong type.

    """
    if param_schema is None:
        raise ValueError("Parameter schema is not defined. Please check the method definition.")

    valid_keys = set(param_schema.keys())
    provided_keys = set(inputs.keys())

    # Verify invalid keys
    invalid_keys = provided_keys - valid_keys
    if invalid_keys:
        raise ValueError(f"Invalid parameter(s): {invalid_keys}. Expected: {list(valid_keys)}")

    validated = {}
    for key, (expected_type, default, _) in param_schema.items():
        if key in inputs:
            value = inputs[key]
            if not isinstance(value, expected_type):
                raise TypeError(
                    f"Parameter '{key}' should be of type {expected_type.__name__}, "
                    f"got {type(inputs[key]).__name__}: {inputs[key]!r}"
                )
            validated[key] = value
        elif default is not None:
            validated[key] = default

    return validated


def get_primary_keys(methods_def: dict) -> list:
    """Extract primary keys from the methods definition."""
    primary_keys = []
    for param, (_, _, is_primary) in methods_def.items():
        if is_primary:
            primary_keys.append(param)

    # Remove duplicates
    primary_keys = list(set(primary_keys))
    primary_keys.sort()
    return primary_keys

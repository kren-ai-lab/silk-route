import json
import os
from typing import Any

import yaml


def read_config_file(path: str) -> Any:
    """Load a single JSON/YAML config file into a Python object.

    Returns ``None`` for unsupported extensions. Shared by ``ConfigLoader`` and
    ``BaseAPIInterface._load_all_configs`` so the parse logic lives in one place.
    """
    ext = os.path.splitext(path)[1]
    with open(path) as f:
        if ext == ".json":
            return json.load(f)
        if ext in (".yaml", ".yml"):
            return yaml.safe_load(f)
    return None


class ConfigLoader:
    def __init__(self, config_dir: str | None = None):
        if config_dir is None:
            config_dir = ""
        self.config_dir = os.path.abspath(config_dir)
        self.config = {}

    def load_config(self, filename: str) -> bool:
        config_path = os.path.join(self.config_dir, f"{filename}.yml")
        if not os.path.isfile(config_path):
            raise FileNotFoundError(f"Configuration file {filename}.yml not found at {config_path}")

        self.config = read_config_file(config_path)

        return True

    def get_parameter(self, param_name: str) -> str | None:
        if not self.config:
            raise ValueError("Configuration not loaded. Please load a configuration first.")

        if param_name not in self.config:
            raise KeyError(f"Parameter {param_name} not found in configuration.")

        if self.config[param_name] in ["your_email@example.com", "your_password"]:
            return None

        return self.config.get(param_name, None)

from typing import Optional, Dict, List
import os
import yaml

class ConfigLoader:
    def __init__(
            self, 
            config_dir: Optional[str] = None
        ):
        if config_dir is None:
            config_dir = ""
        self.config_dir = os.path.abspath(config_dir)
        self.config = {}

    def load_config(self, filename: str) -> bool:
        config_path = os.path.join(self.config_dir, f"{filename}.yml")
        if not os.path.isfile(config_path):
            raise FileNotFoundError(f"Configuration file {filename}.yml not found at {config_path}")

        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)

        self.config = config

        return True
    
    def get_parameter(self, param_name: str) -> Optional[str]:
        if not self.config:
            raise ValueError("Configuration not loaded. Please load a configuration first.")
        
        if param_name not in self.config:
            raise KeyError(f"Parameter {param_name} not found in configuration.")
        
        if self.config[param_name] in ["your_email@example.com", "your_password"]:
            return None

        return self.config.get(param_name, None)
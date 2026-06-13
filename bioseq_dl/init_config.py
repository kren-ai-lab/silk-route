import os
import shutil
from importlib import resources
from pathlib import Path

from bioseq_dl.constants.databases import BASE_CONFIG_DIR


def ensure_config_dir_exists(config_dir) -> None:
    """Ensure that the given configuration directory exists.
    If it does not exist, create it.
    """
    if not config_dir.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created configuration directory at {config_dir}")


def list_config_files() -> list[str]:
    """List all configuration files in the package's config directory."""
    files = []
    try:
        with resources.path("bioseq_dl", "config") as config_path:
            for root, dirs, filenames in os.walk(config_path):
                for filename in filenames:
                    file_path = Path(root) / filename
                    # Get the relative path from config_path
                    rel_path = file_path.relative_to(config_path)
                    files.append(str(rel_path))
    except FileNotFoundError:
        print("Configuration directory not found in package resources.")
    return files


def copy_single_file_to_user_config(src_path: Path, dest_path: Path) -> None:
    """Copy a single configuration file from src_path to dest_path.
    If the file already exists at dest_path, it will not be overwritten.
    """
    if not dest_path.exists():
        if not dest_path.parent.exists():
            dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest_path)
        print(f"Copied {src_path.name} to {dest_path}")


def copy_configs_to_user(config_dir: Path) -> None:
    """Copy all default configuration files from the package resources to the user's configuration directory."""
    created = []
    with resources.path("bioseq_dl", "config") as config_path:
        for name in list_config_files():
            src_file = config_path / name
            dest_file = BASE_CONFIG_DIR / name
            before = dest_file.exists()
            copy_single_file_to_user_config(src_file, dest_file)
            if not before and dest_file.exists():
                created.append(name)

    return created


def main_init():
    """Initialize configuration directories and files for bioseq_dl.
    This function creates necessary configuration directories and copies
    default configuration files from the package resources to the user's
    configuration directory.
    """
    # Check if the base config directory exists, if not create it
    if not BASE_CONFIG_DIR.exists():
        BASE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Created base configuration directory at {BASE_CONFIG_DIR}")
    else:
        print(f"Base configuration directory already exists at {BASE_CONFIG_DIR}")

    # Copy default config files from package resources to the config directory
    created_files = copy_configs_to_user(BASE_CONFIG_DIR)

    if not created_files:
        print("No new configuration files were created. All files already exist.")
    print("Initialization complete.")

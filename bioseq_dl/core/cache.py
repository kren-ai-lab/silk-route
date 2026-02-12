"""
Cache registry and clear utility.

This module provides a single, well-documented API to register cache locations
across the project and to clear them in a safe, flexible way. The goal is to
allow any module to register one or more cache providers (static paths, runtime
callables or DBConfig objects) and then let callers clear caches using a single
`clear_cache` function without hardcoding paths in command handlers.

API:
- register_cache(name: str, provider)
- list_caches() -> dict
- clear_cache(names: Optional[List[str]] = None, *, dry_run=False, older_than_days=None, pattern=None, allowed_bases=None)

Provider types supported:
- str or pathlib.Path -> a single path
- callable() -> yields/returns an iterable of path-like objects
- objects with attribute `CACHE_DIR` (e.g. DBConfig instances from dbconfig)

Behavior and safety:
- At import time the module will attempt to auto-register caches found in
  `bioseq_dl.constants.databases` by looking for attributes that have a
  `CACHE_DIR` attribute. This keeps defaults centralized and prevents
  duplication.
- `clear_cache` validates that each resolved path is inside one of the
  `allowed_bases` (by default the module gathers known cache base dirs from the
  registered providers and from constants). Use `dry_run=True` to preview what
  would be removed.
- If removal of a path fails the function logs the error but continues with
  other entries.

Example:
    from bioseq_dl.core.cache import clear_cache, register_cache

    # register dynamic provider (e.g. per-run temporary dir)
    register_cache('my_tmp', lambda: ["/tmp/my-run-cache"])

    # clear everything registered (dry-run first)
    clear_cache(dry_run=True)
    clear_cache()

"""
from __future__ import annotations

import logging
import shutil
import time
import glob
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Union

from bioseq_dl.constants import databases as db_consts

_logger = logging.getLogger(__name__)

CacheProvider = Union[str, Path, Callable[[], Iterable[Union[str, Path]]], object]

_CACHE_REGISTRY: Dict[str, CacheProvider] = {}


def register_cache(name: str, provider: CacheProvider) -> None:
    """
    Register a cache provider under `name`.

    The provider may be:
      - a path string or Path object
      - a callable returning an iterable of paths
      - an object exposing a `CACHE_DIR` attribute (e.g. DBConfig)

    Registering will overwrite any previous provider with the same name.
    """
    _CACHE_REGISTRY[name] = provider


def list_caches() -> Dict[str, CacheProvider]:
    """Return a shallow copy of the cache registry."""
    return dict(_CACHE_REGISTRY)


def _resolver_provider_paths(provider: CacheProvider) -> List[Path]:
    """
    Resolve a provider into a list of Path objects.
    """
    if provider is None:
        return []
    # DBConfig-like object with CACHE_DIR attribute
    if hasattr(provider, "CACHE_DIR"):
        c = getattr(provider, "CACHE_DIR")
        if c:
            return [Path(c)]
        return []
    # callable
    if callable(provider):
        out: List[Path] = []
        try:
            for p in provider():
                if p is None:
                    continue
                out.append(Path(p))
        except TypeError:
            # provider() might return a single path (not iterable)
            try:
                single = provider()
                if single is not None:
                    out.append(Path(single))
            except Exception:
                _logger.exception("Provider callable raised an exception")
        except Exception:
            _logger.exception("Provider callable raised an exception")
        return out
    # string / Path-like
    return [Path(provider)]


def _is_within_allowed_bases(path: Path, allowed_bases: List[Path]) -> bool:
    """Return True if path is inside any of the allowed base directories."""
    try:
        p_res = path.resolve()
    except Exception:
        return False
    for base in allowed_bases:
        try:
            base_res = base.resolve()
            # using relative_to to ensure proper containment check
            p_res.relative_to(base_res)
            return True
        except Exception:
            continue
    return False


def _is_empty_file(file_path: Path) -> bool:
    """
    Check if a file is considered empty.
    Empty means:
    - File size is 0
    - File contains only whitespace
    - File contains only [] or {}
    """
    try:
        # Check file size
        if file_path.stat().st_size == 0:
            return True
        
        # Read file content
        try:
            content = file_path.read_text(encoding='utf-8').strip()
        except (UnicodeDecodeError, Exception):
            # If can't read as text, check by bytes
            content = file_path.read_bytes().strip()
            if not content:
                return True
            return False
        
        # Check if content is empty, [], or {}
        if not content or content == '[]' or content == '{}':
            return True
        
        return False
    except Exception:
        _logger.exception("Error checking if file is empty: %s", file_path)
        return False

def clear_cache(
    selected_names: Optional[List[str]] = None,
    *,
    dry_run: bool = False,
    force: bool = False,
    older_than_days: Optional[int] = None,
    empty: bool = False,
    pattern: Optional[str] = None,
    allowed_bases: Optional[List[Union[str, Path]]] = None,
) -> Dict[str, List[str]]:
    """
    Clear registered cache entries.

    Args:
        selected_names: optional list of registered cache names to clear. If None, all
            registered caches are used.
        dry_run: if True, don't delete anything; only return what would be
            deleted.
        force: currently reserved for interactive confirmation skipping.
        older_than_days: if set, only delete files/directories older than this
            many days.
        empty: if True, only delete entries that are empty files.
        pattern: glob pattern relative to each provider path. If set, the glob
            is applied under the provider path (supports recursive globs).
        allowed_bases: optional list of base directories that are considered
            safe to delete within. If not provided, the function will build a
            sensible default from registry and constants.

    Returns:
        Dict[name, list_of_paths_actually_deleted_or_matched]
    """
    # Build default allowed_bases from constants and registered CACHE_DIRs
    if allowed_bases is None:
        allowed_bases_list: List[Path] = []
        # try to pick BASE_CACHE_DIR from constants if present
        try:
            base_cache = getattr(db_consts, "BASE_CACHE_DIR", None)
            if base_cache:
                allowed_bases_list.append(Path(base_cache))
        except Exception:
            pass
        # also add any explicitly configured CACHE_DIRs in constants module
        for v in vars(db_consts).values():
            if hasattr(v, "CACHE_DIR"):
                cd = getattr(v, "CACHE_DIR")
                if cd:
                    allowed_bases_list.append(Path(cd))
        # and any cache dirs already registered
        for provider in _CACHE_REGISTRY.values():
            try:
                for p in _resolver_provider_paths(provider):
                    if p:
                        allowed_bases_list.append(p)
            except Exception:
                continue
        # deduplicate
        allowed_bases = [p for i, p in enumerate({x.resolve(): None for x in allowed_bases_list}.keys())]
    else:
        allowed_bases = [Path(p) for p in allowed_bases]

    _names_selected = selected_names or list(_CACHE_REGISTRY.keys())
    now = time.time()
    age_cutoff = None
    if older_than_days is not None:
        age_cutoff = now - older_than_days * 86400

    report: Dict[str, List[str]] = {}

    for name in _names_selected:
        provider = _CACHE_REGISTRY.get(name)
        if provider is None:
            _logger.warning("Cache name '%s' not registered; skipping", name)
            continue

        resolved_paths: List[Path] = []
        for p in _resolver_provider_paths(provider):
            if not p:
                continue
            if pattern:
                # apply glob under p
                try:
                    matches = glob.glob(str(p / pattern), recursive=True)
                    resolved_paths.extend([Path(m) for m in matches])
                except Exception:
                    _logger.exception("Error globbing pattern %s under %s", pattern, p)
            else:
                resolved_paths.append(p)

        removed_paths: List[str] = []
        for path in resolved_paths:
            try:
                if not path.exists():
                    continue
                # ensure safety
                if not _is_within_allowed_bases(path, allowed_bases):
                    _logger.warning("Skipping path outside allowed bases: %s", path)
                    continue
                # age filter
                if age_cutoff is not None:
                    mtime = path.stat().st_mtime
                    if mtime > age_cutoff:
                        _logger.debug("Skipping recent path %s", path)
                        continue
                # empty filter
                if empty:
                    if path.is_dir():
                        # collect only empty files within directory
                        empty_files = []
                        for file_path in path.rglob('*'):
                            if file_path.is_file() and _is_empty_file(file_path):
                                empty_files.append(file_path)
                        # if no empty files found, skip this directory
                        if not empty_files:
                            _logger.debug("Skipping directory with no empty files: %s", path)
                            continue
                        # add only the empty files
                        removed_paths.extend([str(f) for f in empty_files])
                        if not dry_run:
                            for f in empty_files:
                                f.unlink()
                        continue
                    else:
                        # check if file is empty
                        if not _is_empty_file(path):
                            _logger.debug("Skipping non-empty file %s", path)
                            continue

                removed_paths.append(str(path))
                if not dry_run:
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
            except Exception:
                _logger.exception("Failed to remove %s", path)
        report[name] = removed_paths

    return report


# Initialize default registrations by scanning constants/databases for DBConfig-like objects
def _init_defaults() -> None:
    for k, v in vars(db_consts).items():
        # skip private names
        if k.startswith("_"):
            continue
        # pick up objects that expose CACHE_DIR
        if hasattr(v, "CACHE_DIR"):
            cd = getattr(v, "CACHE_DIR")
            if cd:
                register_cache(k.lower(), v)


_init_defaults()

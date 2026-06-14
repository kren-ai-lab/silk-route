"""Cache registry and clear utility.

This module provides a single, well-documented API to register cache locations
across the project and to clear them in a safe, flexible way. The goal is to
allow any module to register one or more cache providers (static paths, runtime
callables or DBConfig objects) and then let callers clear caches using a single
`clear_cache` function without hardcoding paths in command handlers.

API:
- register_cache(name: str, provider)
- list_caches() -> dict
- clear_cache(selected_names=None, *, dry_run=False, older_than_days=None, empty=False, pattern=None, allowed_bases=None)

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
from collections.abc import Callable, Iterable
from pathlib import Path

from bioseq_dl.constants import databases as db_consts

_logger = logging.getLogger(__name__)

CacheProvider = str | Path | Callable[[], Iterable[str | Path]] | object

_CACHE_REGISTRY: dict[str, CacheProvider] = {}


def register_cache(name: str, provider: CacheProvider) -> None:
    """Register a cache provider under `name`.

    The provider may be:
      - a path string or Path object
      - a callable returning an iterable of paths
      - an object exposing a `CACHE_DIR` attribute (e.g. DBConfig)

    Registering will overwrite any previous provider with the same name.
    """
    _CACHE_REGISTRY[name] = provider


def list_caches() -> dict[str, CacheProvider]:
    """Return a shallow copy of the cache registry."""
    return dict(_CACHE_REGISTRY)


def _resolver_provider_paths(provider: CacheProvider) -> list[Path]:
    """Resolve a provider into a list of Path objects."""
    if provider is None:
        return []
    # DBConfig-like object with CACHE_DIR attribute
    if hasattr(provider, "CACHE_DIR"):
        c = provider.CACHE_DIR
        if c:
            return [Path(c)]
        return []
    # callable
    if callable(provider):
        out: list[Path] = []
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


def _is_within_allowed_bases(path: Path, allowed_bases: list[Path]) -> bool:
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
        except Exception:  # noqa: S112  # path not under this base; try next
            continue
        else:
            return True
    return False


def _is_empty_file(file_path: Path) -> bool:
    """Return True if the file is empty: zero bytes, only whitespace, or just `[]`/`{}`."""
    try:
        if file_path.stat().st_size == 0:
            return True
        try:
            content: str | bytes = file_path.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError:
            content = file_path.read_bytes().strip()
    except OSError:
        _logger.exception("Error checking if file is empty: %s", file_path)
        return False
    else:
        return content in ("", "[]", "{}", b"")


def _default_allowed_bases() -> list[Path]:
    """Build the safe-to-delete base dirs from constants and registered providers."""
    bases: list[Path] = []
    base_cache = getattr(db_consts, "BASE_CACHE_DIR", None)
    if base_cache:
        bases.append(Path(base_cache))
    for v in vars(db_consts).values():
        cd = getattr(v, "CACHE_DIR", None)
        if cd:
            bases.append(Path(cd))
    for provider in _CACHE_REGISTRY.values():
        bases.extend(_resolver_provider_paths(provider))
    return list(dict.fromkeys(p.resolve() for p in bases))


def _expand_targets(provider: CacheProvider, pattern: str | None) -> list[Path]:
    """Resolve a provider to concrete paths, expanding `pattern` as a glob if given."""
    targets: list[Path] = []
    for p in _resolver_provider_paths(provider):
        if not p:
            continue
        if pattern:
            try:
                targets.extend(p.glob(pattern))
            except Exception:
                _logger.exception("Error globbing pattern %s under %s", pattern, p)
        else:
            targets.append(p)
    return targets


def _delete_target(
    path: Path,
    *,
    dry_run: bool,
    age_cutoff: float | None,
    empty: bool,
    allowed_bases: list[Path],
) -> list[str]:
    """Delete one target subject to safety/age/empty filters; return paths removed."""
    if not path.exists():
        return []
    if not _is_within_allowed_bases(path, allowed_bases):
        _logger.warning("Skipping path outside allowed bases: %s", path)
        return []
    if age_cutoff is not None and path.stat().st_mtime > age_cutoff:
        _logger.debug("Skipping recent path %s", path)
        return []

    if empty:
        if path.is_dir():
            empty_files = [f for f in path.rglob("*") if f.is_file() and _is_empty_file(f)]
            if not dry_run:
                for f in empty_files:
                    f.unlink()
            return [str(f) for f in empty_files]
        if not _is_empty_file(path):
            _logger.debug("Skipping non-empty file %s", path)
            return []

    if not dry_run:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    return [str(path)]


def clear_cache(
    selected_names: list[str] | None = None,
    *,
    dry_run: bool = False,
    older_than_days: int | None = None,
    empty: bool = False,
    pattern: str | None = None,
    allowed_bases: list[str | Path] | None = None,
) -> dict[str, list[str]]:
    """Clear registered cache entries.

    Args:
        selected_names: registered cache names to clear; if None, all are used.
        dry_run: if True, don't delete anything; only report what would be deleted.
        older_than_days: if set, only delete entries older than this many days.
        empty: if True, only delete entries that are empty files.
        pattern: recursive glob applied under each provider path.
        allowed_bases: base directories considered safe to delete within;
            defaults to dirs gathered from the registry and constants.

    Returns:
        Dict mapping each cache name to the paths deleted (or matched, if dry_run).

    """
    bases = _default_allowed_bases() if allowed_bases is None else [Path(p) for p in allowed_bases]
    age_cutoff = time.time() - older_than_days * 86400 if older_than_days is not None else None
    names = selected_names or list(_CACHE_REGISTRY)

    report: dict[str, list[str]] = {}
    for name in names:
        provider = _CACHE_REGISTRY.get(name)
        if provider is None:
            _logger.warning("Cache name '%s' not registered; skipping", name)
            continue

        removed: list[str] = []
        for path in _expand_targets(provider, pattern):
            try:
                removed.extend(
                    _delete_target(
                        path, dry_run=dry_run, age_cutoff=age_cutoff, empty=empty, allowed_bases=bases
                    )
                )
            except Exception:
                _logger.exception("Failed to remove %s", path)
        report[name] = removed

    return report


# Initialize default registrations by scanning constants/databases for DBConfig-like objects
def _init_defaults() -> None:
    for k, v in vars(db_consts).items():
        # skip private names
        if k.startswith("_"):
            continue
        # pick up objects that expose CACHE_DIR
        if hasattr(v, "CACHE_DIR"):
            cd = v.CACHE_DIR
            if cd:
                register_cache(k.lower(), v)


_init_defaults()

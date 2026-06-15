"""Cache registry and clear utility.

This module maps cache names to directories and clears them safely. Each
``DBConfig`` cache directory from ``bioseq_dl.constants.databases`` is registered
automatically at import; callers can register extra paths with ``register_cache``
and clear them with a single ``clear_cache`` call instead of hardcoding paths.

API:
- register_cache(name: str, path: str | Path)
- list_caches() -> dict[str, Path]
- clear_cache(selected_names=None, *, dry_run=False, older_than_days=None, empty=False, pattern=None,
  allowed_bases=None)

Behavior and safety:
- `clear_cache` validates that each resolved path is inside one of the
  `allowed_bases` (by default the registered paths plus the cache dirs from
  constants). Use `dry_run=True` to preview what would be removed.
- If removal of a path fails the function logs the error and continues.

Example:
    from bioseq_dl.core.cache import clear_cache, register_cache

    register_cache("my_tmp", "/tmp/my-run-cache")
    clear_cache(dry_run=True)  # preview
    clear_cache()

"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

from bioseq_dl.constants import databases as db_consts

_logger = logging.getLogger(__name__)

_CACHE_REGISTRY: dict[str, Path] = {}


def register_cache(name: str, path: str | Path) -> None:
    """Register a cache directory under `name`.

    ``path`` is a filesystem path (str or Path). Registering overwrites any
    previous entry with the same name.
    """
    _CACHE_REGISTRY[name] = Path(path)


def list_caches() -> dict[str, Path]:
    """Return a shallow copy of the cache registry."""
    return dict(_CACHE_REGISTRY)


def _is_within_allowed_bases(path: Path, allowed_bases: list[Path]) -> bool:
    """Return True if path is inside any of the allowed base directories."""
    try:
        p_res = path.resolve()
    except OSError:
        return False
    for base in allowed_bases:
        try:
            base_res = base.resolve()
            # relative_to raises ValueError when p_res is not under base_res
            p_res.relative_to(base_res)
        except (OSError, ValueError):  # not under this base (or unresolvable); try next
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
    """Build the safe-to-delete base dirs from constants and the registry."""
    bases: list[Path] = []
    base_cache = getattr(db_consts, "BASE_CACHE_DIR", None)
    if base_cache:
        bases.append(Path(base_cache))
    for v in vars(db_consts).values():
        cd = getattr(v, "CACHE_DIR", None)
        if cd:
            bases.append(Path(cd))
    bases.extend(_CACHE_REGISTRY.values())
    return list(dict.fromkeys(p.resolve() for p in bases))


def _expand_targets(path: Path, pattern: str | None) -> list[Path]:
    """Return the path itself, or its `pattern` glob matches when given."""
    if not pattern:
        return [path]
    try:
        return list(path.glob(pattern))
    except OSError:
        _logger.exception("Error globbing pattern %s under %s", pattern, path)
        return []


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
        cache_path = _CACHE_REGISTRY.get(name)
        if cache_path is None:
            _logger.warning("Cache name '%s' not registered; skipping", name)
            continue

        removed: list[str] = []
        for path in _expand_targets(cache_path, pattern):
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


# Register each DBConfig's cache directory found in constants/databases.
def _init_defaults() -> None:
    for k, v in vars(db_consts).items():
        if k.startswith("_"):
            continue
        cache_dir = getattr(v, "CACHE_DIR", None)
        if cache_dir:
            register_cache(k.lower(), cache_dir)


_init_defaults()

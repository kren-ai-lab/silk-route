"""Cache management CLI commands."""

import logging

import typer

from bioseq_dl.core.cache import clear_cache, list_caches
from bioseq_dl.logging import get_logger
from bioseq_dl.logging.logger import configure_logging

app = typer.Typer(name="cache", help="Cache utility commands for BioSeqDownloader.")


@app.command("list")
def list_registered(
    log_level: str = typer.Option(
        "info", "--log", "-l", help="Logging level (debug, info, warning, error, critical)."
    ),
) -> None:
    """List registered caches."""
    LOG_LEVELS = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    logging_level = LOG_LEVELS.get(log_level.lower(), logging.INFO)
    configure_logging(level=logging_level)

    log = get_logger("bioseq_dl.cli.cache.list")
    regs = list_caches()
    if not regs:
        log.info("No caches registered.")
        raise typer.Exit
    log.info("Registered caches:")
    for k, v in regs.items():
        log.info("  %s -> %s", k, getattr(v, "CACHE_DIR", v))


@app.command("clear")
def clear(
    cache_names: list[str] | None = typer.Option(
        None, "--name", "-n", help="Cache name to clear (repeatable)."
    ),
    clear_all: bool = typer.Option(False, "--all", help="Clear all registered caches."),
    dry_run: bool = typer.Option(True, "--dry-run", help="Don't delete, only show what would be removed."),
    older_than: int | None = typer.Option(
        None, "--older-than", help="Only delete entries older than this many days."
    ),
    pattern: str | None = typer.Option(None, "--pattern", help="Glob pattern relative to each cache path."),
    force: bool = typer.Option(False, "--force", help="Skip any confirmation prompts (non-interactive)."),
    list_registered: bool = typer.Option(False, "--list", help="List registered caches and exit."),
    empty: bool = typer.Option(False, "--empty", help="Clear empty caches only."),
    log_level: str = typer.Option(
        "info", "--log", "-l", help="Logging level (debug, info, warning, error, critical)."
    ),
) -> dict:
    """Clear cached data.

    Use --name to specify one or more registered cache names, or --all to clear everything.
    By default the command runs in --dry-run mode.
    """
    LOG_LEVELS = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    logging_level = LOG_LEVELS.get(log_level.lower(), logging.INFO)
    configure_logging(level=logging_level)

    log = get_logger("bioseq_dl.cli.cache.clear")

    if list_registered:
        regs = list_caches()
        if not regs:
            log.info("No caches registered.")
            raise typer.Exit
        log.info("Registered caches:")
        for k, v in regs.items():
            log.info("  %s -> %s", k, getattr(v, "CACHE_DIR", v))
        raise typer.Exit

    if cache_names and clear_all:
        log.error("Cannot use --name and --all together. Pick one.")
        raise typer.Exit(code=2)

    selected_names = None if clear_all else cache_names

    if not dry_run and not force:
        preview = clear_cache(
            selected_names=selected_names,
            dry_run=True,
            older_than_days=older_than,
            pattern=pattern,
            empty=empty,
        )
        total = sum(len(v) for v in preview.values())
        if total and not typer.confirm(f"Delete {total} path(s)?"):
            raise typer.Abort

    log.info("Clearing caches (dry_run=%s) - selected=%s", dry_run, selected_names or "ALL")

    results = clear_cache(
        selected_names=selected_names,
        dry_run=dry_run,
        older_than_days=older_than,
        pattern=pattern,
        empty=empty,
    )

    # Summarize results
    total = sum(len(v) for v in results.values())
    if dry_run:
        log.info("Dry-run: %d path(s) would be affected.", total)
    else:
        log.info("Removed %d path(s).", total)

    for name, p_list in results.items():
        if not p_list:
            log.debug("%s: nothing to do", name)
            continue
        log.info("%s:", name)
        for p in p_list:
            log.info("  %s", p)

    return results

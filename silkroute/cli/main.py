"""SilkRoute main CLI app."""

import sys
import traceback
from typing import Any

import typer
from polars.exceptions import PolarsError
from typer.core import TyperGroup

from silkroute import __version__
from silkroute._provenance import utc_now
from silkroute.cli._shared import EXIT_INTERNAL, EXIT_RUNTIME
from silkroute.cli.collect_data import fetch_app, search_app
from silkroute.cli.helper_commands import app as cache_app
from silkroute.cli.workflows import workflow_app
from silkroute.core.exceptions import SilkRouteError
from silkroute.logging import setup_logging


class _ExitCodeGroup(TyperGroup):
    """Map errors escaping a command to exit codes: 3 for runtime/data errors, 4 for anything else.

    Usage errors (``typer.BadParameter`` and friends) and ``typer.Exit`` keep their own code (2 for usage).
    """

    def invoke(self, ctx: Any) -> Any:  # typer.Context is not the vendored base type
        try:
            return super().invoke(ctx)
        except (typer.Exit, typer.Abort):
            raise
        except Exception as exc:
            if callable(getattr(exc, "show", None)):  # a (vendored) Click exception: usage error, exit 2
                raise
            if isinstance(exc, SilkRouteError | OSError | PolarsError | UnicodeDecodeError):
                typer.echo(f"Error: {exc}", err=True)
                raise typer.Exit(EXIT_RUNTIME) from exc
            traceback.print_exception(exc, file=sys.stderr)
            raise typer.Exit(EXIT_INTERNAL) from exc


app = typer.Typer(
    cls=_ExitCodeGroup,
    name="silkroute",
    help="Fetch sequences from multiple biological databases",
)
app.add_typer(fetch_app, name="fetch", help="Fetch data using API nomenclature.")
app.add_typer(search_app, name="search", help="Fetch data using general search interfaces.")
app.add_typer(workflow_app, name="workflow", help="Run or validate data-fetching workflows.")
app.add_typer(cache_app, name="cache", help="Cache management commands.")


def _version_callback(value: bool) -> None:
    """Print the package version and exit when ``value`` is true."""
    if value:
        typer.echo(f"silkroute {__version__}")
        raise typer.Exit


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(  # noqa: ARG001  # consumed by eager callback
        False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
    log: str = typer.Option(
        "info", "--log", "-l", help="Logging level: debug, info, warning, error, critical."
    ),
) -> None:
    """SilkRoute CLI entry point."""
    setup_logging(log)
    ctx.meta["started_at"] = utc_now()  # provenance sidecars of fetch/search record when the run began
    if ctx.invoked_subcommand is None:
        typer.echo("Welcome to SilkRoute! Use --help to see available commands.")


if __name__ == "__main__":
    app()

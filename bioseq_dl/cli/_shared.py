"""Shared helpers for CLI commands.

``BaseAPIInterface.fetch_single`` / ``fetch_batch`` return a ``(data, metadata)``
tuple. CLI commands historically did ``result = interface.fetch_single(...)``
followed by ``result.to_csv(...)``, which raised ``AttributeError`` because
``result`` was the tuple, not the data. ``save_or_print`` unpacks the tuple and
either writes the data to ``output`` or prints a short preview.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
import typer

from bioseq_dl.core.export import export_dataframe, normalize_export_format

if TYPE_CHECKING:
    import logging


_OUTPUT_HELP = "Output file to save the results. Prints a preview if omitted."
_OUTPUT_DIR_HELP = "Output directory for results."
_FORMAT_HELP = "Output format: csv, json, xml, parquet. Inferred from extension if omitted."


def fetch_auto(interface: Any, queries: list[Any], method: str, **kwargs: Any) -> Any:
    """Dispatch to ``fetch_batch`` for several queries, else ``fetch_single``.

    ``queries`` is the already-split list of per-item queries; callers own the
    splitting/shaping (comma input, dict wrapping, etc.). This owns only the
    one-vs-many decision that was previously copy-pasted across commands.
    """
    if len(queries) > 1:
        return interface.fetch_batch(queries=queries, method=method, **kwargs)
    return interface.fetch_single(query=queries[0], method=method, **kwargs)


def output_option(help: str = _OUTPUT_HELP) -> Any:  # noqa: A002  # `help` matches typer's kwarg
    """Build the standard ``--output/-o`` file option (None = print preview)."""
    return typer.Option(None, "--output", "-o", help=help)


def output_dir_option(help: str = _OUTPUT_DIR_HELP) -> Any:  # noqa: A002
    """Build the standard ``--output-dir/-o`` directory option (required)."""
    return typer.Option(..., "--output-dir", "-o", help=help)


def format_option(help: str = _FORMAT_HELP) -> Any:  # noqa: A002
    """Build the standard ``--format/-f`` export-format option."""
    return typer.Option(None, "--format", "-f", help=help)


def unwrap(result: Any) -> Any:
    """Return just the data from a ``(data, metadata)`` fetch result.

    ``fetch_single`` / ``fetch_batch`` return a 2-tuple whose second element is a
    metadata dict. Anything that is not such a tuple is returned unchanged.
    """
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):  # noqa: PLR2004  # (data, metadata) pair
        return result[0]
    return result


def save_or_print(
    result: Any,
    output: str | None = None,
    *,
    output_format: str | None = None,
    preview_rows: int = 5,
) -> None:
    """Unpack a fetch result and either save it to ``output`` or print a preview.

    Args:
        result: Raw return value of ``fetch_single`` / ``fetch_batch`` (a
            ``(data, metadata)`` tuple) or already-unwrapped data.
        output: Path to save to. If ``None``, a preview is printed instead.
        output_format: Export format (csv/json/xml/parquet) for DataFrame
            results. If ``None``, inferred from the ``output`` extension,
            defaulting to csv. Ignored for non-DataFrame data.
        preview_rows: Number of rows to show when previewing a DataFrame.

    """
    data = unwrap(result)

    if isinstance(data, pd.DataFrame):
        if output:
            fmt = output_format or (Path(output).suffix.lstrip(".") or "csv")
            try:
                saved = export_dataframe(data, output, output_format=fmt)
            except ValueError as e:
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(code=1) from None
            typer.echo(f"Results saved to {saved}")
        else:
            typer.echo(data.head(preview_rows))
        return

    if output:
        with Path(output).open("w") as fh:
            if isinstance(data, bytes):
                fh.write(data.decode("utf-8"))
            elif isinstance(data, (dict, list)):
                json.dump(data, fh, indent=2, default=str)
            else:
                fh.write(str(data))
        typer.echo(f"Results saved to {output}")
    else:
        typer.echo(data)


def _write_metadata(out_dir: Path, metadata: dict) -> None:
    """Write the run metadata JSON into ``out_dir``."""
    with (out_dir / "metadata.json").open("w") as f:
        json.dump(metadata, f, indent=2, default=str)


def _save_tabular(
    export_data: Any,
    enriched_data: Any,
    metadata: dict,
    out_dir: Path,
    export_format: str,
    logger: logging.Logger,
) -> None:
    """Save DataFrame results (and any enrichment frames) as csv/parquet."""
    if not (isinstance(export_data, pd.DataFrame) and not export_data.empty):
        logger.warning("No results to save in %s format.", export_format.upper())
        return
    tabular_format = normalize_export_format(export_format)
    export_path = out_dir / f"uniprot_results.{tabular_format}"
    export_dataframe(export_data, export_path, output_format=tabular_format)
    if isinstance(enriched_data, dict):
        for key, value in enriched_data.items():
            logger.info("Saving %s results into %s directory", key, out_dir)
            export_dataframe(value, out_dir / f"{key}_results.{tabular_format}", output_format=tabular_format)
    _write_metadata(out_dir, metadata)
    logger.info("Results saved to %s", export_path)


def _save_json(
    export_data: Any, enriched_data: Any, metadata: dict, out_dir: Path, logger: logging.Logger
) -> None:
    """Save dict/list results (and any enrichment) as JSON."""
    if not isinstance(export_data, (dict, list)):
        logger.warning("No results to save in JSON format.")
        return
    with (out_dir / "uniprot_results.json").open("w") as f:
        json.dump(export_data, f, indent=2, default=str)
    if isinstance(enriched_data, dict):
        for key, value in enriched_data.items():
            logger.info("Saving %s results into %s directory", key, out_dir)
            with (out_dir / f"{key}_results.json").open("w") as f:
                json.dump(value, f, indent=2, default=str)
    _write_metadata(out_dir, metadata)
    logger.info("Results saved to %s/uniprot_results.json", out_dir)


def _save_xml(
    export_data: Any, enriched_data: Any, metadata: dict, out_dir: Path, logger: logging.Logger
) -> None:
    """Save ElementTree results (and any enrichment) as XML."""
    if not hasattr(export_data, "getroot"):
        logger.warning("No results to save in XML format.")
        return
    export_data.write(f"{out_dir}/uniprot_results.xml", encoding="utf-8", xml_declaration=True)
    if isinstance(enriched_data, dict):
        for key, value in enriched_data.items():
            logger.info("Saving %s results into %s directory", key, out_dir)
            value.write(f"{out_dir}/{key}_results.xml", encoding="utf-8", xml_declaration=True)
    _write_metadata(out_dir, metadata)
    logger.info("Results saved to %s/uniprot_results.xml", out_dir)


def save_uniprot_results(
    export_data: Any,
    enriched_data: Any,
    metadata: dict,
    output: str,
    export_format: str,
    logger: logging.Logger,
) -> None:
    """Persist UniProt search results and enrichment in the requested format.

    Shared by the uniprot-search CLI commands (ids / query / sequences), which
    previously duplicated this csv/parquet/json/xml export branching.
    """
    out_dir = Path(output)
    if export_format in {"csv", "parquet"}:
        _save_tabular(export_data, enriched_data, metadata, out_dir, export_format, logger)
    elif export_format == "json":
        _save_json(export_data, enriched_data, metadata, out_dir, logger)
    elif export_format == "xml":
        _save_xml(export_data, enriched_data, metadata, out_dir, logger)
    else:
        logger.warning(export_format)
        logger.warning("No UniProt data found for the given search.")

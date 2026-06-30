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
from typing import TYPE_CHECKING, Any, Literal, cast

import polars as pl
import typer

from bioseq_dl.core.export import (
    USER_EXPORT_FORMATS,
    export_dataframe,
    normalize_export_format,
    normalize_parse_format,
    normalize_user_export_format,
)

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

    Args:
        interface (Any): API interface exposing ``fetch_single`` / ``fetch_batch``.
        queries (list[Any]): Already-split list of per-item queries.
        method (str): Fetch method name forwarded to the interface.
        **kwargs (Any): Extra keyword arguments forwarded to the fetch call.

    Returns:
        Any: The interface's fetch result (a ``(data, metadata)`` tuple).

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


def split_result(result: Any) -> tuple[Any, dict | None]:
    """Split a ``(data, metadata)`` fetch result into its two parts.

    ``fetch_single`` / ``fetch_batch`` return a 2-tuple whose second element is a
    metadata dict. Anything that is not such a tuple is treated as already-unwrapped
    data with no metadata (``None``).

    Args:
        result (Any): A ``(data, metadata)`` tuple or already-unwrapped data.

    Returns:
        tuple[Any, dict | None]: The data and its metadata dict (``None`` if absent).

    """
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):  # noqa: PLR2004  # (data, metadata) pair
        return result[0], result[1]
    return result, None


def unwrap(result: Any) -> Any:
    """Return just the data from a ``(data, metadata)`` fetch result."""
    return split_result(result)[0]


def _metadata_enabled() -> bool:
    """Whether to write metadata sidecars, per the ``fetch --no-metadata`` flag.

    Reads the shared click context meta set by the ``fetch`` callback; defaults
    to ``True`` outside a CLI invocation (e.g. when called directly in tests).

    Returns:
        bool: ``True`` if metadata sidecars should be written.

    """
    try:
        # typer vendors click; this is its current location for the active-context lookup.
        from typer._click.globals import get_current_context  # noqa: PLC0415
    except ImportError:  # pragma: no cover - guards against typer internals moving
        return True
    ctx = get_current_context(silent=True)
    if ctx is None:
        return True
    return bool(ctx.meta.get("write_metadata", True))


def _write_metadata_sidecar(output_path: str | Path, metadata: dict) -> None:
    """Write fetch metadata as a sidecar JSON next to ``output_path``.

    ``results.csv`` -> ``results.metadata.json``, keeping the provenance tied to
    the data file it describes (no clobber when several commands share a dir).

    Args:
        output_path (str | Path): Path of the data file the sidecar describes.
        metadata (dict): Provenance metadata to serialize.

    """
    sidecar = Path(output_path).with_suffix(".metadata.json")
    with sidecar.open("w") as fh:
        json.dump(metadata, fh, indent=2, default=str)
    typer.echo(f"Metadata saved to {sidecar}")


def save_or_print(
    result: Any,
    output: str | None = None,
    *,
    output_format: str | None = None,
    preview_rows: int = 5,
    write_metadata: bool | None = None,
) -> None:
    """Unpack a fetch result and either save it to ``output`` or print a preview.

    When ``output`` is given and the result carries metadata, the provenance is
    also written to a ``<output>.metadata.json`` sidecar.

    Args:
        result (Any): Raw return value of ``fetch_single`` / ``fetch_batch`` (a
            ``(data, metadata)`` tuple) or already-unwrapped data.
        output (str | None): Path to save to. If ``None``, a preview is printed instead.
        output_format (str | None): Export format (csv/json/xml/parquet) for DataFrame
            results. If ``None``, inferred from the ``output`` extension,
            defaulting to csv. Ignored for non-DataFrame data.
        preview_rows (int): Number of rows to show when previewing a DataFrame.
        write_metadata (bool | None): Whether to write the metadata sidecar. ``None`` (the
            default) defers to the ``fetch --no-metadata`` CLI flag.

    """
    data, metadata = split_result(result)
    if write_metadata is None:
        write_metadata = _metadata_enabled()

    if isinstance(data, pl.DataFrame):
        if output:
            fmt = output_format or (Path(output).suffix.lstrip(".") or "csv")
            try:
                saved = export_dataframe(data, output, output_format=fmt)
            except ValueError as e:
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(code=1) from None
            typer.echo(f"Results saved to {saved}")
            if metadata and write_metadata:
                _write_metadata_sidecar(saved, metadata)
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
        if metadata and write_metadata:
            _write_metadata_sidecar(output, metadata)
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
    """Save DataFrame results (and any enrichment frames) as csv/parquet.

    Args:
        export_data (Any): Main result; saved only if a non-empty DataFrame.
        enriched_data (Any): Optional dict of named enrichment DataFrames.
        metadata (dict): Run metadata written alongside the results.
        out_dir (Path): Output directory for the result files.
        export_format (str): Requested format (``csv`` or ``parquet``).
        logger (logging.Logger): Logger for progress and warnings.

    """
    if not (isinstance(export_data, pl.DataFrame) and not export_data.is_empty()):
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
    """Save dict/list results (and any enrichment) as JSON.

    Args:
        export_data (Any): Main result; saved only if a dict or list.
        enriched_data (Any): Optional dict of named enrichment results.
        metadata (dict): Run metadata written alongside the results.
        out_dir (Path): Output directory for the result files.
        logger (logging.Logger): Logger for progress and warnings.

    """
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
    """Save ElementTree results (and any enrichment) as XML.

    Args:
        export_data (Any): Main result; saved only if it exposes ``getroot``.
        enriched_data (Any): Optional dict of named enrichment ElementTrees.
        metadata (dict): Run metadata written alongside the results.
        out_dir (Path): Output directory for the result files.
        logger (logging.Logger): Logger for progress and warnings.

    """
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

    Args:
        export_data (Any): Main result to save.
        enriched_data (Any): Optional dict of named enrichment results.
        metadata (dict): Run metadata written alongside the results.
        output (str): Output directory path.
        export_format (str): Requested format (csv, parquet, json, or xml).
        logger (logging.Logger): Logger for progress and warnings.

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


def validate_export_format(export_format: str) -> str:
    """Normalize a user export-format string, or exit(1) with an error message.

    Shared by the uniprot-search CLI commands (ids / query / sequences), which
    previously duplicated this normalize-or-Exit(1) block verbatim.

    Args:
        export_format (str): User-supplied export-format string.

    Returns:
        str: The normalized export format.

    Raises:
        typer.Exit: If the format is not one of the supported export formats.

    """
    normalized = normalize_user_export_format(export_format)
    if normalized is None:
        typer.echo(
            f"Error: Unsupported export format '{export_format}'. "
            f"Supported formats are: {', '.join(USER_EXPORT_FORMATS)}.",
            err=True,
        )
        raise typer.Exit(code=1)
    return normalized


def parse_and_save_uniprot(
    instance: Any,
    response: Any,
    metadata: dict,
    *,
    crossref_fields: str,
    output: str,
    export_format: str,
    logger: logging.Logger,
) -> None:
    """Parse a UniProt response, optionally enrich, and save in the requested format.

    Shared tail of the uniprot-search CLI commands (ids / query / sequences):
    create the output dir, dump the raw response, parse, run cross-reference
    enrichment when ``crossref_fields`` is set, and persist via
    ``save_uniprot_results``.

    Args:
        instance (Any): UniProt interface exposing ``parse``.
        response (Any): Raw UniProt response to parse and save.
        metadata (dict): Run metadata, extended in place with parsing/enrichment info.
        crossref_fields (str): Comma-separated cross-reference fields to enrich, if any.
        output (str): Output directory path.
        export_format (str): Requested export format.
        logger (logging.Logger): Logger for progress messages.

    """
    # Lazy import: pulls the heavy interface/query-builder graph only for the
    # uniprot-search commands, not every CLI module that imports this helper file.
    from bioseq_dl.core.utils.crossref_enrichment import run_crossref_enrichment  # noqa: PLC0415

    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "raw_response.json").open("w") as f:
        json.dump(response, f, indent=2, default=str)

    logger.info("Parsing results...")
    parse_format = normalize_parse_format(export_format) or "dataframe"
    fmt = cast("Literal['json', 'dataframe', 'xml']", parse_format)
    export_data, parsed_metadata = instance.parse(results=response, extract_fields=None, format=fmt)
    metadata["parsing"] = parsed_metadata

    enriched_data = None
    if crossref_fields:
        logger.info("Running cross-reference enrichment...")
        enriched_data, enriched_metadata = run_crossref_enrichment(
            export_data, crossref_fields.split(","), format=fmt
        )
        metadata["enrichment"] = enriched_metadata

    save_uniprot_results(export_data, enriched_data, metadata, output, export_format, logger)

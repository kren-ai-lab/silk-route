import os
import typer
from typing import List, Tuple, Optional
import re
import json
import logging

import pandas as pd

from bioseq_dl.core.workflow.main_workflow import MainWorkflow
from bioseq_dl.core.export import export_dataframe, normalize_export_format
from bioseq_dl.logging import configure_logging

app = typer.Typer(name="workflow", help="Run predefined data collection workflows.")

from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.cli.workflows")


MODALITIES = ['protein', 'compound', 'interaction']
MODES = ['query_first', 'query_composition']
FORMATS = ['dataframe', 'json', 'xml', 'parquet']


def is_valid_export_label(label: object) -> bool:
    """Return whether a result label should be exported as a file."""
    if label is None:
        return False
    normalized = str(label).strip()
    if not normalized:
        return False
    return normalized.lower() not in {"none", "null"}


def is_empty_export_content(content: object) -> bool:
    """Return whether export content is empty."""
    if content is None:
        return True
    if isinstance(content, pd.DataFrame):
        return content.empty
    if isinstance(content, str):
        return content.strip() == ""
    if isinstance(content, bytes):
        return content == b""
    if isinstance(content, (dict, list, tuple, set)):
        return len(content) == 0
    return False


def split_pair(s: str) -> Tuple[str, str]:
    if '=' in s:
        q, label = s.split('=', 1)
    elif '|' in s:
        q, label = s.split('|', 1)
    else:
        raise ValueError(f"Invalid format '{s}'. Use 'query=label' or 'query|label'.")
    return q.strip(), label.strip()

@app.command(name="run")
def run_workflow(
    output: str = typer.Option(
        ..., "-o", "--output", 
        help="Output directory for results"
    ),
    modality: str = typer.Option(
        ..., "--modality", "-m",
        help="Modality of the workflow to run. Supported modalities: 'protein', 'compound', 'interaction'."
    ),
    mode: str = typer.Option(
        ..., "--mode", "-d",
        help="Mode of the workflow to run. Supported modes: 'query_first', 'query_composition'."
    ),
    query: str = typer.Option(
        ..., "--query", "-q",
        help="Query or list of queries to run the workflow on. If query composition mode is selected, a labeled query string should be provided. For example q1=label1,q2=label2"
    ),
    fields: Optional[str] = typer.Option(
        None, "--fields",
        help="Comma-separated UniProt fields to fetch. Default is empty (UniProt API defaults)."
    ),
    export_format: str = typer.Option(
        "dataframe", "--export-format", "-e",
        help="Format to export the results. Options: dataframe, json, xml, parquet. Default is 'dataframe'."
    ),
    enrich: bool = typer.Option(
        True, "--enrich/--no-enrich",
        help="Whether to perform data enrichment. Default is True."
    ),
    max_workers: int = typer.Option(
        5, "--max-workers", "-w",
        help="Maximum number of worker threads to use for API calls. Default is 5."
    ),
    total_retries: int = typer.Option(
        3, "--total-retries", "-r",
        help="Total number of retries for failed API calls. Default is 3."
    ),
    uniprot_timeout: Optional[float] = typer.Option(
        None, "--uniprot-timeout",
        help="Timeout (seconds) for UniProt API requests. Default is 60."
    ),
    debug: bool = typer.Option(
        False, "--debug",
        help="Enable debug logging"
    ),
) -> None:
    """
    Run a specific workflow by name.
    """
    logger = log
    try:
        if debug:
            configure_logging(level=logging.DEBUG)
            logger = get_logger("bioseq_dl.cli.workflows")  # re-fetch so root handlers pick new level
            logger.debug("Debug logging enabled")
    except Exception as e:
        logger.warning(f"Could not configure logging: {e}")

    if modality not in MODALITIES:
        typer.echo(f"Error: Unsupported modality '{modality}'. Supported modalities are: {', '.join(MODALITIES)}")
        raise typer.Exit(code=1)
    
    if mode not in MODES:
        typer.echo(f"Error: Unsupported mode '{mode}'. Supported modes are: {', '.join(MODES)}")
        raise typer.Exit(code=1)
    
    if export_format not in FORMATS:
        typer.echo(f"Error: Unsupported export format '{export_format}'. Supported formats are: {', '.join(FORMATS)}")
        raise typer.Exit(code=1)

    wf = MainWorkflow()
    
    try:
        if mode == "query_first":
            data, meta = wf.run(
                mode=mode,
                modality=modality,
                export_format=export_format,
                query=query,
                fields=fields,
                enrich=enrich,
                max_workers=max_workers,
                total_retries=total_retries,
                uniprot_timeout=uniprot_timeout,
            )
        elif mode == "query_composition":
            if ',' in query:
                queries = [q.strip() for q in query.split(',')]
                queries_with_labels = [split_pair(q) for q in queries]
            else:
                raise ValueError("For non-composition modes, please provide multiple queries as 'query1=label1,query2=label2'.")
                
            data, meta = wf.run(
                mode=mode,
                modality=modality,
                export_format=export_format,
                queries_with_labels=queries_with_labels,
                fields=fields,
                enrich=enrich,
                uniprot_timeout=uniprot_timeout,
            )
        else:
            raise ValueError(f"Unsupported modality '{modality}'.")
    except TimeoutError as e:
        logger.error(str(e))
        raise typer.Exit(code=1)


    os.makedirs(output, exist_ok=True)
    logger.info("Exporting workflow results to %s", output)
    
    # Save results ignoring 'uniprot_enrichment' key
    tabular_format = normalize_export_format(export_format) if export_format in {"dataframe", "parquet"} else None
    if export_format in {"dataframe", "parquet"}:
        for label, df in data.items():
            if label == "uniprot_enrichment":
                continue
            if not is_valid_export_label(label) or is_empty_export_content(df):
                continue
            export_label = str(label).strip()
            export_dataframe(
                df,
                os.path.join(output, f"{export_label}_results.{tabular_format}"),
                output_format=tabular_format,
            )
    elif export_format == "json":
        for label, content in data.items():
            if label == "uniprot_enrichment":
                continue
            if not is_valid_export_label(label) or is_empty_export_content(content):
                continue
            export_label = str(label).strip()
            with open(f"{output}/{export_label}_results.json", "w") as f:
                json.dump(content, f)
    elif export_format == "xml":
        for label, content in data.items():
            if label == "uniprot_enrichment":
                continue
            if not is_valid_export_label(label) or is_empty_export_content(content):
                continue

            export_label = str(label).strip()
            with open(f"{output}/{export_label}_results.xml", "w") as f:
                f.write(content)

    # Save enrichement data if present
    if "uniprot_enrichment" in data:
        for label, df in data["uniprot_enrichment"].items():
            if not is_valid_export_label(label) or is_empty_export_content(df):
                continue
            export_label = str(label).strip()
            if export_format in {"dataframe", "parquet"}:
                export_dataframe(
                    df,
                    os.path.join(output, f"{export_label}.{tabular_format}"),
                    output_format=tabular_format,
                )
            elif export_format == "json":
                with open(f"{output}/{export_label}.json", "w") as f:
                    json.dump(df, f)
            elif export_format == "xml":
                with open(f"{output}/{export_label}.xml", "w") as f:
                    f.write(df)
    
    # Save metadata
    if isinstance(meta, dict):
        try:
            with open(f"{output}/metadata.json", "w") as f:
                json.dump(meta, f, default=lambda o: o.__name__ if hasattr(o, "__name__") else str(o), indent=2)
        except TypeError:
            # Fallback: convert any non-serializable values to strings (use __name__ for types when available)
            simple_meta = {k: (v.__name__ if hasattr(v, "__name__") else str(v)) for k, v in meta.items()}
            with open(f"{output}/metadata.json", "w") as f:
                json.dump(simple_meta, f, indent=2)
    logger.info("Workflow export completed")
    typer.echo(f"Workflow completed. Results saved to '{output}'")

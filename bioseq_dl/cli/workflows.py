import os
import typer
from typing import List, Tuple
import re
import json
import logging

from bioseq_dl.core.workflow.main_workflow import MainWorkflow
from bioseq_dl.logging import configure_logging

app = typer.Typer(name="workflow", help="Run predefined data collection workflows.")

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

    def configure_logging(level: int = logging.INFO, **kwargs: object) -> None:
        logging.basicConfig(level=level, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

log = get_logger("bioseq_dl.cli.workflows")
# -------------------------------------------------


MODALITIES = ['protein', 'compound', 'interaction']
MODES = ['query_first', 'query_composition']
FORMATS = ['dataframe', 'json', 'xml']

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
    export_format: str = typer.Option(
        "dataframe", "--export-format", "-e",
        help="Format to export the results. Default is 'dataframe'."
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
    
    if mode == "query_first":
        data, meta = wf.run(
            mode=mode,
            modality=modality,
            export_format=export_format,
            query=query,
            enrich=enrich,
            max_workers=max_workers,
            total_retries=total_retries
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
            enrich=enrich
        )
    else:
        raise ValueError(f"Unsupported modality '{modality}'.")


    os.makedirs(output, exist_ok=True)
    
    # Save results ignoring 'uniprot_enrichment' key
    if export_format == "dataframe":
        for label, df in data.items():
            if label == "uniprot_enrichment":
                continue
            df.to_csv(f"{output}/{label}_results.csv", index=False)
    elif export_format == "json":
        for label, content in data.items():
            if label == "uniprot_enrichment":
                continue
            with open(f"{output}/{label}_results.json", "w") as f:
                json.dump(content, f)
    elif export_format == "xml":
        for label, content in data.items():
            if label == "uniprot_enrichment":
                continue

            with open(f"{output}/{label}_results.xml", "w") as f:
                f.write(content)

    # Save enrichement data if present
    if "uniprot_enrichment" in data:
        for label, df in data["uniprot_enrichment"].items():
            if export_format == "dataframe":
                df.to_csv(f"{output}/{label}.csv", index=False)
            elif export_format == "json":
                with open(f"{output}/{label}.json", "w") as f:
                    json.dump(df, f)
            elif export_format == "xml":
                with open(f"{output}/{label}.xml", "w") as f:
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
    typer.echo(f"Workflow completed. Results saved to '{output}'")

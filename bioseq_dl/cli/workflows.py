import os
import typer
from pathlib import Path
from typing import Any, List, Tuple, Optional
import re
import json
import logging

import pandas as pd
import yaml

from bioseq_dl.core.workflow.main_workflow import MainWorkflow
from bioseq_dl.core.export import export_dataframe, normalize_export_format
from bioseq_dl.logging import configure_logging

app = typer.Typer(name="workflow", help="Run predefined data collection workflows.")

from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.cli.workflows")


MODALITIES = ['protein', 'compound', 'interaction']
METHODS = ['query_first', 'query_composition']
FORMATS = ['dataframe', 'csv', 'json', 'xml', 'parquet']

WORKFLOW_DEFAULTS = {
    "output": None,
    "query": None,
    "modality": None,
    "method": None,
    "export_format": "dataframe",
    "enrich": True,
    "debug": False,
    "workers": 5,
    "retries": 3,
    "fields": None,
    "crossref_fields": None,
    "interaction_type": None,
    "include_isoform": False,
    "uniprot_timeout": None,
}

WORKFLOW_RECIPE_KEYS = set(WORKFLOW_DEFAULTS)
WORKFLOW_RECIPE_ALIASES = {
    "outdir": "output",
    "output_dir": "output",
    "mode": "modality",
    "export": "export_format",
    "format": "export_format",
    "max_workers": "workers",
    "total_retries": "retries",
}
WORKFLOW_RECIPE_ALLOWED_KEYS = WORKFLOW_RECIPE_KEYS | set(WORKFLOW_RECIPE_ALIASES)
WORKFLOW_RECIPE_DISPLAY_KEYS = WORKFLOW_RECIPE_KEYS
LEGACY_ROUTE_KEY = "dis" + "patch"
LEGACY_METHOD_KEY = LEGACY_ROUTE_KEY + "_mode"
LEGACY_METHOD_ERRORS = {
    LEGACY_METHOD_KEY: f"Unknown workflow YAML key '{LEGACY_METHOD_KEY}'. Use 'method' instead.",
    LEGACY_ROUTE_KEY: f"Unknown workflow YAML key '{LEGACY_ROUTE_KEY}'. Use 'method' instead.",
}
FORBIDDEN_WORKFLOW_RECIPE_KEYS = {
    "api_key",
    "access_key",
    "password",
    "email",
    "token",
    "secret",
    "bioseq_dl_biogrid_api_key",
    "bioseq_dl_brenda_email",
    "bioseq_dl_brenda_password",
    "bioseq_dl_refseq_email",
}


def check_forbidden_workflow_recipe_keys(value: object) -> None:
    """Reject credential-like keys anywhere in a workflow recipe."""
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if str(key).lower() in FORBIDDEN_WORKFLOW_RECIPE_KEYS:
                raise ValueError(
                    "Credentials must be provided through environment variables or .env, not workflow YAML."
                )
            check_forbidden_workflow_recipe_keys(nested_value)
    elif isinstance(value, list):
        for item in value:
            check_forbidden_workflow_recipe_keys(item)


def normalize_workflow_recipe_keys(values: dict) -> dict:
    """Normalize supported workflow recipe aliases to canonical keys."""
    normalized = {}
    for key, value in values.items():
        key_name = str(key)
        if key_name in LEGACY_METHOD_ERRORS:
            raise ValueError(LEGACY_METHOD_ERRORS[key_name])
        canonical_key = WORKFLOW_RECIPE_ALIASES.get(key_name, key_name)
        if canonical_key in normalized:
            raise ValueError(
                f"Workflow recipe defines both '{canonical_key}' and an alias for it. "
                "Use only the canonical key."
            )
        normalized[canonical_key] = value
    return normalized


def load_workflow_recipe(config_path: str | Path) -> dict:
    """Load a workflow recipe from a YAML file."""
    path = Path(config_path)
    if not path.exists():
        raise ValueError(f"Workflow recipe file does not exist: {path}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid workflow YAML in {path}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Could not read workflow recipe {path}: {exc}") from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError("Workflow YAML root must be a mapping.")
    return loaded


def validate_workflow_recipe(recipe: dict) -> dict:
    """Validate and normalize a workflow recipe."""
    if not isinstance(recipe, dict):
        raise ValueError("Workflow recipe must be a mapping.")

    check_forbidden_workflow_recipe_keys(recipe)

    version = recipe.get("version")
    if version is not None and str(version) != "1":
        raise ValueError("Unsupported workflow recipe version. Only version 1 is supported.")

    kind = recipe.get("kind")
    if kind is not None and kind != "workflow":
        raise ValueError("Unsupported workflow recipe kind. Only 'workflow' is supported.")

    if "workflow" in recipe:
        workflow_values = recipe["workflow"]
        if workflow_values is None:
            workflow_values = {}
        if not isinstance(workflow_values, dict):
            raise ValueError("The 'workflow' section must be a mapping.")
        allowed_top_level = {"version", "kind", "workflow"}
        unknown_top_level = set(recipe) - allowed_top_level
        if unknown_top_level:
            allowed = ", ".join(sorted(allowed_top_level))
            unknown = ", ".join(sorted(unknown_top_level))
            raise ValueError(f"Unknown top-level workflow recipe key(s): {unknown}. Allowed keys: {allowed}.")
    else:
        workflow_values = {
            key: value
            for key, value in recipe.items()
            if key not in {"version", "kind"}
        }

    workflow_values = {str(key): value for key, value in workflow_values.items()}
    for key_name, message in LEGACY_METHOD_ERRORS.items():
        if key_name in workflow_values:
            raise ValueError(message)

    unknown_keys = set(workflow_values) - WORKFLOW_RECIPE_ALLOWED_KEYS
    if unknown_keys:
        unknown = ", ".join(sorted(unknown_keys))
        allowed = ", ".join(sorted(WORKFLOW_RECIPE_DISPLAY_KEYS))
        raise ValueError(f"Unknown workflow recipe key(s): {unknown}. Allowed keys: {allowed}.")

    return normalize_workflow_recipe_keys(workflow_values)


def merge_workflow_recipe(cli_values: dict, recipe_values: dict) -> dict:
    """Merge explicit CLI values with YAML recipe values."""
    merged = {**WORKFLOW_DEFAULTS, **recipe_values}
    explicit_cli_values = {key: value for key, value in cli_values.items() if value is not None}
    merged.update(explicit_cli_values)
    return merged


def collect_cli_workflow_values(
    output: Optional[str],
    modality: Optional[str],
    method: Optional[str],
    query: Optional[str],
    fields: Optional[str],
    crossref_fields: Optional[str],
    export_format: Optional[str],
    enrich: Optional[bool],
    max_workers: Optional[int],
    total_retries: Optional[int],
    uniprot_timeout: Optional[float],
    debug: Optional[bool],
    include_isoform: Optional[bool],
    interaction_type: Optional[str],
) -> dict:
    """Return workflow values explicitly provided through CLI options."""
    return {
        "output": output,
        "modality": modality,
        "method": method,
        "query": query,
        "fields": fields,
        "crossref_fields": crossref_fields,
        "export_format": export_format,
        "enrich": enrich,
        "workers": max_workers,
        "retries": total_retries,
        "uniprot_timeout": uniprot_timeout,
        "debug": debug,
        "include_isoform": include_isoform,
        "interaction_type": interaction_type,
    }


def validate_merged_workflow_values(values: dict) -> None:
    """Validate merged workflow CLI and recipe values."""
    missing_keys = [key for key in ("output", "query", "modality", "method") if not values.get(key)]
    if missing_keys:
        missing = ", ".join(missing_keys)
        raise ValueError(f"Missing required workflow value(s): {missing}. Provide them with CLI options or --config.")

    if values["modality"] not in MODALITIES:
        raise ValueError(
            f"Unsupported modality '{values['modality']}'. Supported modalities are: {', '.join(MODALITIES)}"
        )

    if values["method"] not in METHODS:
        raise ValueError(
            f"Unsupported method '{values['method']}'. Supported methods are: {', '.join(METHODS)}"
        )

    if values["export_format"] not in FORMATS:
        raise ValueError(
            f"Unsupported export format '{values['export_format']}'. Supported formats are: {', '.join(FORMATS)}"
        )


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
    config: Optional[Path] = typer.Option(
        None, "--config",
        help="Path to a YAML workflow recipe."
    ),
    output: Optional[str] = typer.Option(
        None, "-o", "--output",
        help="Output directory for results"
    ),
    modality: Optional[str] = typer.Option(
        None, "--modality", "-m",
        help="Modality of the workflow to run. Supported modalities: 'protein', 'compound', 'interaction'."
    ),
    method: Optional[str] = typer.Option(
        None, "--method", "-d",
        help="Workflow method to run. Supported methods: query_first, query_composition."
    ),
    query: Optional[str] = typer.Option(
        None, "--query", "-q",
        help="Query or list of queries to run the workflow on. If query_composition is selected, a labeled query string should be provided. For example q1=label1,q2=label2"
    ),
    fields: Optional[str] = typer.Option(
        None, "--fields",
        help="Comma-separated UniProt fields to fetch. Default is empty (UniProt API defaults)."
    ),
    crossref_fields: Optional[str] = typer.Option(
        None, "--crossref-fields",
        help="Comma-separated cross-reference fields for enrichment."
    ),
    export_format: Optional[str] = typer.Option(
        None, "--export-format", "-e",
        help="Format to export the results. Options: dataframe, csv, json, xml, parquet. Default is 'dataframe'."
    ),
    enrich: Optional[bool] = typer.Option(
        None, "--enrich/--no-enrich",
        help="Whether to perform data enrichment. Default is True."
    ),
    max_workers: Optional[int] = typer.Option(
        None, "--max-workers", "-w",
        help="Maximum number of worker threads to use for API calls. Default is 5."
    ),
    total_retries: Optional[int] = typer.Option(
        None, "--total-retries", "-r",
        help="Total number of retries for failed API calls. Default is 3."
    ),
    uniprot_timeout: Optional[float] = typer.Option(
        None, "--uniprot-timeout",
        help="Timeout (seconds) for UniProt API requests. Default is 60."
    ),
    debug: Optional[bool] = typer.Option(
        None, "--debug/--no-debug",
        help="Enable debug logging"
    ),
    include_isoform: Optional[bool] = typer.Option(
        None, "--include-isoform/--no-include-isoform",
        help="Include isoforms in UniProt results. Default is False."
    ),
    interaction_type: Optional[str] = typer.Option(
        None, "--interaction-type",
        help="Interaction workflow type, when modality is interaction."
    ),
) -> None:
    """
    Run a specific workflow by name.
    """
    logger = log
    try:
        recipe_values = validate_workflow_recipe(load_workflow_recipe(config)) if config else {}
        cli_values = collect_cli_workflow_values(
            output=output,
            modality=modality,
            method=method,
            query=query,
            fields=fields,
            crossref_fields=crossref_fields,
            export_format=export_format,
            enrich=enrich,
            max_workers=max_workers,
            total_retries=total_retries,
            uniprot_timeout=uniprot_timeout,
            debug=debug,
            include_isoform=include_isoform,
            interaction_type=interaction_type,
        )
        workflow_values = merge_workflow_recipe(cli_values, recipe_values)
        validate_merged_workflow_values(workflow_values)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    try:
        if workflow_values["debug"]:
            configure_logging(level=logging.DEBUG)
            logger = get_logger("bioseq_dl.cli.workflows")  # re-fetch so root handlers pick new level
            logger.debug("Debug logging enabled")
    except Exception as e:
        logger.warning(f"Could not configure logging: {e}")

    wf = MainWorkflow()
    
    try:
        if workflow_values["method"] == "query_first":
            data, meta = wf.run(
                method=workflow_values["method"],
                modality=workflow_values["modality"],
                export_format=workflow_values["export_format"],
                query=workflow_values["query"],
                fields=workflow_values["fields"],
                enrich=workflow_values["enrich"],
                max_workers=workflow_values["workers"],
                total_retries=workflow_values["retries"],
                uniprot_timeout=workflow_values["uniprot_timeout"],
                include_isoform=workflow_values["include_isoform"],
                interaction_type=workflow_values["interaction_type"],
                crossref_fields=workflow_values["crossref_fields"],
            )
        elif workflow_values["method"] == "query_composition":
            if ',' in workflow_values["query"]:
                queries = [q.strip() for q in workflow_values["query"].split(',')]
                queries_with_labels = [split_pair(q) for q in queries]
            else:
                raise ValueError("For query_composition, please provide multiple queries as 'query1=label1,query2=label2'.")
                
            data, meta = wf.run(
                method=workflow_values["method"],
                modality=workflow_values["modality"],
                export_format=workflow_values["export_format"],
                queries_with_labels=queries_with_labels,
                fields=workflow_values["fields"],
                enrich=workflow_values["enrich"],
                uniprot_timeout=workflow_values["uniprot_timeout"],
                crossref_fields=workflow_values["crossref_fields"],
            )
        else:
            raise ValueError(f"Unsupported method '{workflow_values['method']}'.")
    except TimeoutError as e:
        logger.error(str(e))
        raise typer.Exit(code=1)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


    output = workflow_values["output"]
    export_format = workflow_values["export_format"]
    os.makedirs(output, exist_ok=True)
    logger.info("Exporting workflow results to %s", output)
    
    # Save results ignoring 'uniprot_enrichment' key
    tabular_format = normalize_export_format(export_format)
    if tabular_format in {"csv", "parquet"}:
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
            if tabular_format in {"csv", "parquet"}:
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

"""UniProt cross-reference CLI commands."""

# bioseq_dl/cli/uniprot_crossref.py
import json
from pathlib import Path

import pandas as pd
import typer

from bioseq_dl.constants.uniprot import XREF_MAPPING
from bioseq_dl.core.crossref_enricher import CrossRefEnricher, EndpointSpec
from bioseq_dl.core.interfacesconfig import load_packaged_config
from bioseq_dl.logging import get_logger

app = typer.Typer(help="Search and download cross-references from UniProt.")

log = get_logger("bioseq_dl.cli.uniprot_crossref")

CROSS_REF_FIELDS = [xref.lower() for xref in XREF_MAPPING]


def save_to_file(
    df: pd.DataFrame, out_dir: str, filename: str, db: str, endpoint: str, option: str | None
) -> None:
    """Run UniProt cross-reference ID mapping."""
    # Make folder with filename
    (Path(out_dir) / filename).mkdir(parents=True, exist_ok=True)
    # Save the DataFrame to a CSV file
    if option is None:
        output_file = Path(out_dir) / filename / f"{db}_{endpoint}_results.csv"
    else:
        output_file = Path(out_dir) / filename / f"{db}_{endpoint}_{option}_results.csv"
    df.to_csv(output_file, index=False)
    log.info(f"Results for {db} with option {option} saved to {output_file}")


@app.command(name="")
def run(
    input_file: str = typer.Option(
        ...,
        "--input",
        "-i",
        help="Input file with UniProt IDs.",
        case_sensitive=True,
    ),
    out_dir: str = typer.Option(
        ...,
        "--out_dir",
        "-o",
        help="Output directory for results.",
        case_sensitive=True,
    ),
    databases: str = typer.Option(
        "all",
        "--databases",
        "-d",
        help="List of databases to query separated by commas, or 'all' to query all databases. Options: "
        + ", ".join(CROSS_REF_FIELDS),
        case_sensitive=False,
    ),
) -> None:
    """Run UniProt cross-reference name mapping."""
    try:
        # Check if input file exists
        if not Path(input_file).exists():
            msg = f"Input file {input_file} does not exist."
            raise FileNotFoundError(msg)

        # Load input file into a DataFrame
        try:
            df = pd.read_csv(input_file)
        except Exception as e:
            msg = f"Error reading input file {input_file}: {e}"
            raise ValueError(msg) from e

        endpoints_config = load_packaged_config("uniprot_crossref", "config_endpoints.yml") or {}

        if databases == "all":
            databases = ",".join(CROSS_REF_FIELDS)

        endpoint_specs = []
        # Generate the endpoint specs based on selected crossref fields
        for xref in databases.split(","):
            if xref in CROSS_REF_FIELDS:
                endpoint_config = endpoints_config.get(xref)
                if not isinstance(endpoint_config, dict):
                    continue

                for ep_name, ep_info in endpoint_config.get("endpoints", {}).items():
                    if ep_info.get("enabled", False):
                        options = ep_info.get("options", [None]) if "options" in ep_info else [None]
                        endpoint_specs.extend(
                            EndpointSpec(
                                database=xref,
                                endpoint=ep_name,
                                option=ep_option,
                                params=ep_info.get("params", {}),
                            )
                            for ep_option in options
                        )

        if not endpoint_specs:
            msg = (
                "No valid endpoint specifications found. Please check your database selections and "
                "configuration."
            )
            raise ValueError(msg)
        log.debug(f"Endpoint specifications: {endpoint_specs}")
        enricher = CrossRefEnricher(endpoint_specs)
        enriched_data, enriched_metadata = enricher.enrich(df)

        if isinstance(enriched_data, pd.DataFrame) and not enriched_data.empty:
            log.info(f"Crossref enrichment resulted in {len(enriched_data)} rows")

        # Create output directory if it doesn't exist
        if not Path(out_dir).exists():
            Path(out_dir).mkdir(parents=True)

        if isinstance(enriched_data, pd.DataFrame) and not enriched_data.empty:
            filename = Path(input_file).stem
            results_path = Path(out_dir) / f"{filename}_results.csv"
            enriched_data.to_csv(results_path, index=False)
            log.info(f"Results saved to {results_path}")
        else:
            log.info("No results to save.")

        metadata_path = Path(out_dir) / "metadata.json"
        with metadata_path.open("w") as f:
            json.dump(enriched_metadata, f, indent=2)
            log.info(f"Metadata saved to {metadata_path}")

    except typer.BadParameter as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from None
    except Exception as e:
        typer.secho(f"Unexpected error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None

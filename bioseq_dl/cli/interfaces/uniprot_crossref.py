# bioseq_dl/cli/uniprot_crossref.py
import os, logging
from typing import List
import pandas as pd
import typer
from bioseq_dl.core.utils.query_builders import QUERY_BUILDERS, INTERFACE_CLASSES
from typer.colors import YELLOW

from bioseq_dl.core.crossref_enricher import CrossRefEnricher, EndpointSpec
from bioseq_dl.core.interfacesconfig import ConfigLoader
from bioseq_dl.constants.databases import BASE_CONFIG_DIR
from bioseq_dl.constants.uniprot import XREF_MAPPING

app = typer.Typer(help="Search and download cross-references from UniProt.")

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

log = get_logger("bioseq_dl.cli.uniprot_crossref")
# -------------------------------------------------

CROSS_REF_FIELDS = [xref.lower() for xref in XREF_MAPPING.keys()]

def save_to_file(df, out_dir, filename, db, endpoint, option):
    # Make folder with filename
    os.makedirs(os.path.join(out_dir, filename), exist_ok=True)
    # Save the DataFrame to a CSV file
    if option is None:
        output_file = os.path.join(out_dir, f"{filename}/{db}_{endpoint}_results.csv")
    else:
        output_file = os.path.join(out_dir, f"{filename}/{db}_{endpoint}_{option}_results.csv")
    df.to_csv(output_file, index=False)
    log.info(f"Results for {db} with option {option} saved to {output_file}")

@app.command(name="")
def run(
    input: str = typer.Option(
        ..., "--input", "-i",
        help="Input file with UniProt IDs.",
        case_sensitive=True,
    ),
    out_dir: str = typer.Option(
        ..., "--out_dir", "-o",
        help="Output directory for results.",
        case_sensitive=True,
    ),
    databases: str = typer.Option(
        "all", "--databases", "-d",
        help="List of databases to query separated by commas, or 'all' to query all databases. Options: " + ", ".join(CROSS_REF_FIELDS),
        case_sensitive=False,
    )
):    
    try:
        # Check if input file exists
        if not os.path.exists(input):
            raise FileNotFoundError(f"Input file {input} does not exist.")

        # Load input file into a DataFrame
        try:
            df = pd.read_csv(input)
        except Exception as e:
            raise ValueError(f"Error reading input file {input}: {e}")
        
        config = ConfigLoader(config_dir=str(BASE_CONFIG_DIR) + "/uniprot_crossref")
        config.load_config("config_endpoints")
    
        if databases == "all":
            databases = ",".join(CROSS_REF_FIELDS)

        endpoint_specs = []
        # Generate the endpoint specs based on selected crossref fields
        for xref in databases.split(","):
            if xref in CROSS_REF_FIELDS:
                endpoint_config = config.get_parameter(xref)
                if not isinstance(endpoint_config, dict):
                    continue

                for ep_name, ep_info in endpoint_config.get("endpoints", {}).items():
                    if ep_info.get("enabled", False):
                        if "options" in ep_info:
                            for ep_option in ep_info.get("options", [None]):
                                endpoint_specs.append(
                                    EndpointSpec(
                                        database=xref,
                                        endpoint=ep_name,
                                        option=ep_option,
                                        params=ep_info.get("params", {}),
                                    )
                                )
                        else:
                            endpoint_specs.append(
                                EndpointSpec(
                                    database=xref,
                                    endpoint=ep_name,
                                    option=None,
                                    params=ep_info.get("params", {}),
                                )
                            )
        
        if not endpoint_specs:
            raise ValueError("No valid endpoint specifications found. Please check your database selections and configuration.")
        log.debug(f"Endpoint specifications: {endpoint_specs}")
        enricher = CrossRefEnricher(endpoint_specs)
        enriched_data, enriched_metadata = enricher.enrich(df)

        if isinstance(enriched_data, pd.DataFrame) and not enriched_data.empty:
            log.info(f"Crossref enrichment resulted in {len(enriched_data)} rows")

        # Create output directory if it doesn't exist
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)


        if isinstance(enriched_data, pd.DataFrame) and not enriched_data.empty:
            filename = os.path.splitext(os.path.basename(input))[0]
            enriched_data.to_csv(os.path.join(out_dir, f"{filename}_results.csv"), index=False)
            log.info(f"Results saved to {os.path.join(out_dir, f'{filename}_results.csv')}")
        else:
            log.info("No results to save.")

        with open(os.path.join(out_dir, "metadata.json"), "w") as f:
            import json
            json.dump(enriched_metadata, f, indent=2)
            log.info(f"Metadata saved to {os.path.join(out_dir, 'metadata.json')}")



    except typer.BadParameter as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    except Exception as e:
        typer.secho(f"Unexpected error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
# bioseq_dl/cli/uniprot_crossref.py
import os
from typing import List
import pandas as pd
import typer
from bioseq_dl.core.utils.query_builders import QUERY_BUILDERS, INTERFACE_CLASSES
from typer.colors import YELLOW

from bioseq_dl.core.crossref_enricher import CrossRefEnricher, EndpointSpec
from bioseq_dl.core.interfacesconfig import ConfigLoader
from bioseq_dl.constants.databases import BASE_CONFIG_DIR

CROSS_REF_FIELDS = [
    "alphafold",
    "biodbnet",
    "biogrid",
    "brenda",
    "chembl",
    "chebi",
    "genontology",
    "interpro",
    "kegg",
    "panther",
    "pathwaycommons",
    "pdb",
    "pubchem",
    "reactome",
    "rhea",
]

app = typer.Typer(help="Search and download cross-references from UniProt.")

def save_to_file(df, out_dir, filename, db, endpoint, option):
    # Make folder with filename
    os.makedirs(os.path.join(out_dir, filename), exist_ok=True)
    # Save the DataFrame to a CSV file
    if option is None:
        output_file = os.path.join(out_dir, f"{filename}/{db}_{endpoint}_results.csv")
    else:
        output_file = os.path.join(out_dir, f"{filename}/{db}_{endpoint}_{option}_results.csv")
    df.to_csv(output_file, index=False)
    print(f"Results for {db} with option {option} saved to {output_file}")

@app.command(name="")
def run(
    input: str = typer.Option(
        "--input", "-i",
        help="Input file with UniProt IDs.",
        case_sensitive=True,
    ),
    out_dir: str = typer.Option(
        "--out_dir", "-o",
        help="Output directory for results.",
        case_sensitive=True,
    ),
    databases: str = typer.Option(
        "all", "--databases", "-d",
        help="List of databases to query separated by commas, or 'all' to query all databases. Options: " + ", ".join(CROSS_REF_FIELDS),
        case_sensitive=False,
    ),
    config_path: str = typer.Option(
        None, "--config", "-c",
        help="Path to the configuration file for endpoints."
    ),
    download_structures: bool = typer.Option(
        False, "--download_structures", "-ds",
        help="Download PDB structures."
    ),
    no_concat: bool = typer.Option(
        False, "--no-concat",
        help="Do not concatenate results into a single DataFrame."
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

        # Create output directory if it doesn't exist
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        
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
        print(f"Endpoint specifications: {endpoint_specs}")
        enricher = CrossRefEnricher(endpoint_specs)
        result = enricher.enrich(df, concat_results=not no_concat)

        if isinstance(result, pd.DataFrame) and not result.empty:
            print(f"Crossref enrichment resulted in {len(result)} rows")
            return result
       
        if no_concat:
            if isinstance(result, dict):
                for name, result_df in result.items():
                    result_df.to_csv(os.path.join(out_dir, f"{name}_results.csv"), index=False)
                    print(f"Results for {name} saved to {os.path.join(out_dir, f'{name}_results.csv')}")
            else:
                print("No results to save.")
        else:
            if isinstance(result, pd.DataFrame) and not result.empty:
                output_file = os.path.join(out_dir, "crossref_results.csv")
                result.to_csv(output_file, index=False)
                print(f"Results saved to {output_file}")
            else:
                print("No results to save.")



    except typer.BadParameter as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    except Exception as e:
        typer.secho(f"Unexpected error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
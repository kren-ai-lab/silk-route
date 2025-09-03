# bioseq_dl/cli/uniprot_crossref.py
import os, yaml
from pathlib import Path
import pandas as pd
import typer
from dotenv import load_dotenv
import importlib.resources as resources
from bioseq_dl.core.utils.query_builders import QUERY_BUILDERS, INTERFACE_CLASSES
from typer.colors import YELLOW


app = typer.Typer(help="Search and download cross-references from UniProt.")

biogrid_api_key = None
brenda_email = None
brenda_password = None

##########################################
# Generic Fetch
##########################################

def search_and_merge(row, instance, database_name, endpoint, params, option=None):
    # Construir clave de búsqueda: {database}_{method}_{option}
    if option:
        key = f"{database_name}_{endpoint}_{option}"
    else:
        key = f"{database_name}_{endpoint}"

    # Buscar builder
    query_builder = QUERY_BUILDERS.get(key)
    if not query_builder:
        raise ValueError(f"No query builder registered for key '{key}'")

    # Construir query
    query_params = query_builder(row, params)

    method_params = {
        "method": endpoint,
        "parse": True,
        "to_dataframe": True

    }
    # Previene el error en genontology al receibir option
    if option:
        method_params["option"] = option

    if isinstance(query_params, dict) \
        or ( isinstance(query_params, list) and len(query_params) == 1):
        # Si es una lista de un solo dict, usar ese dict directamente
        query_params = query_params[0] if isinstance(query_params, list) else query_params
        result = instance.fetch_single(
            query=query_params,
            **method_params
        )
    elif isinstance(query_params, list) and len(query_params) > 1:
        # Si es una lista de varios dicts, usarla como está
        result = instance.fetch_batch(
            queries=query_params,
            **method_params
        )
    else:
        # Si no es una lista, retornar DataFrame vacío
        return pd.DataFrame()

    # Unir con la fila original
    row_expanded = pd.concat([pd.DataFrame([row] * len(result)).reset_index(drop=True),
                            result.reset_index(drop=True)], axis=1)

    return row_expanded


def process_dataframe(df, database_name, endpoint, instance, params, option=None):
    all_results = df.apply(
        lambda row: search_and_merge(
            row,
            instance,
            database_name,
            endpoint,
            params,
            option=option
        ),
        axis=1
    )

    if all_results.empty:
        print(f"No results found for {database_name} with endpoint {endpoint} and option {option}.")
        return pd.DataFrame()

    # Combinar todos los resultados
    return pd.concat(all_results.tolist(), ignore_index=True)

##########################################
# Main Interface for Cross-references
##########################################
def fetch_crossref(
        database_name: str, 
        df: pd.DataFrame, 
        config_data: dict,
        endpoint: str, 
        option: str|None = None,
    ):
    if database_name not in INTERFACE_CLASSES:
        raise ValueError(f"Unsupported database: {database_name}")

    # Crear la instancia correcta
    if database_name == "brenda":
        instance = INTERFACE_CLASSES[database_name](
            email=os.getenv("brenda_email"),
            password=os.getenv("brenda_password")
        )
    else:
        instance = INTERFACE_CLASSES[database_name]()

    # Obtener params
    params = get_params(database_name, config_data, endpoint)
    if option:
        params["option"] = option

    if database_name == "biogrid":
        biogrid_api_key = os.getenv("biogrid_api_key")
        if not biogrid_api_key:
            typer.echo("Warning: BioGRID API key is not set. BioGRID results will be skipped", err=False)
            return pd.DataFrame()
    
        params["accessKey"] = biogrid_api_key
        
    return process_dataframe(df, database_name, endpoint, instance, params, option=option)

##########################################
# Auxiliary functions
##########################################

def is_enabled(api_name, config_data, endpoint_name=None, option=None):
    api_conf = config_data.get(api_name, {})
    if not api_conf.get("enabled", False):
        return False
    if endpoint_name:
        if option:
            return api_conf.get("endpoints", {}).get(endpoint_name, {}).get("options", {}).get(option, {}).get("enabled", False)
        return api_conf.get("endpoints", {}).get(endpoint_name, {}).get("enabled", False)
    return True

def get_params(api_name, config_data, endpoint_name):
    return (
        config_data.get(api_name, {})
        .get("endpoints", {})
        .get(endpoint_name, {})
        .get("params", {})
    )

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
    config_path: str = typer.Option(
        None, "--config", "-c",
        help="Path to the configuration file for endpoints."
    ),
    download_structures: bool = typer.Option(
        False, "--download_structures", "-d",
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
        
        if config_path is None:
            with resources.files("bioseq_dl.config.uniprot_crossref").joinpath("config_endpoints.yml").open("r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
        else:
            with open(config_path, "r", encoding="utf-8") as file:
                config_data = yaml.safe_load(file)

        if not isinstance(config_data, dict) or not config_data:
            raise ValueError(f"Configuration file {config_path or 'default config'} is empty or invalid.")

        typer.echo(f"Using configuration from {config_path if config_path else 'default config'}")

        # Load environment variables
        load_dotenv()
        
        filename, _ = os.path.splitext(os.path.basename(input))
        export_df = pd.DataFrame()
        
        print(config_data["brenda"].keys())

        for db in list(config_data.keys()):
            if not is_enabled(db, config_data):
                continue
            print(f"Processing database: {db}")
            for endpoint in config_data[db].get("endpoints", {}).keys():
                if not is_enabled(db, config_data, endpoint):
                    continue
                print(f"Using endpoint: {endpoint}")

                if "options" in config_data[db].get("endpoints", {}).get(endpoint, {}):
                    for option in config_data[db]["endpoints"][endpoint].get("options", {}).keys():
                        if not is_enabled(db, config_data, endpoint, option):
                            continue
                        print(f"Using option: {option}")
                        # Fetch data from the database with the specified option
                        tmp_df = fetch_crossref(
                            database_name=db,
                            df=df,
                            config_data=config_data,
                            endpoint=endpoint,
                            option=option
                        )
                        if isinstance(tmp_df, pd.DataFrame) and not tmp_df.empty:
                            if not no_concat:
                                export_df = pd.concat([export_df, tmp_df], axis=1)
                            else:
                                save_to_file(tmp_df, out_dir, filename, db, endpoint, option=option)
                        else:
                            print(f"No data fetched for {db} with option {option} or the result is not a DataFrame.")
                else:
                    # Fetch data from the database
                    tmp_df = fetch_crossref(
                        database_name=db,
                        df=df,
                        config_data=config_data,
                        endpoint=endpoint
                    )
                    if not no_concat:
                        export_df = pd.concat([export_df, tmp_df], axis=1)
                    else:
                        save_to_file(tmp_df, out_dir, filename, db, endpoint, option=None)

        if not no_concat:
            # Save the concatenated DataFrame to a CSV file
            output_file = os.path.join(out_dir, f"{filename}_crossref_results.csv")
            export_df.to_csv(output_file, index=False)
            print(f"Concatenated results saved to {output_file}")

    except typer.BadParameter as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    except Exception as e:
        typer.secho(f"Unexpected error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
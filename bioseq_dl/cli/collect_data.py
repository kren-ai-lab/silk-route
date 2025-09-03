import typer, os
from typing import List

import pandas as pd
from bioseq_dl import (
    AlphafoldInterface, 
    BioDBNetInterface, 
    BioGRIDInterface,
    BrendaInterface,
    ChEMBLInterface,
    ChEBIInterface,
    GenOntologyInterface,
    InterproInterface,
    KEGGInterface,
    PathwayCommonsInterface,
    PantherInterface,
    PDBInterface,
    PrideInterface,
    PubChemInterface,
    ReactomeInterface,
    RefSeqInterface,
    RheaInterface,
    StringInterface
)
from bioseq_dl.constants.biodbnet import inputs as biodbnet_inputs, outputs as biodbnet_outputs

app = typer.Typer(help="Collect data from various biological databases.")

@app.command("alphafold")
def run_alphafold(
    id: str = typer.Option(
        ..., "--id", "-id",
        help="UniProt ID of the protein to fetch from AlphaFold."
    ),
    download_structures: bool = typer.Option(
        False,
        "--download-structures", "-ds",
        help="Whether to download the predicted structure files (PDB format)."
    ),
    output: str = typer.Option(
        None, "--output", "-o",
        help="Output file to save the fetched data.",
    )
):
    """Fetch data from AlphaFold database."""
    if download_structures:
        instance = AlphafoldInterface(
            structures=['pdb'],
            output_dir=output
        )
    else:
        instance = AlphafoldInterface()

    if len(id.split(",")) > 1:
        ids: List[str] = id.split(",")
        df = pd.DataFrame(instance.fetch_batch(
            queries=ids,
            method="prediction",
            parse=True,
            to_dataframe=True
        ))
    else:
        df = pd.DataFrame(instance.fetch_single(
            query=id,
            method="prediction",
            parse=True, 
            to_dataframe=True
        ))

    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))

@app.command("biodbnet")
def run_biodbnet(
    method: str = typer.Option(
        "db2db", "--method", "-m",
        help=f"Method to use. Options: {', '.join(BioDBNetInterface.METHODS.keys())}"
    ),
    input: str = typer.Option(
        "genesymbol", "--input", "-i",
        help=f"Type of input identifier. Options: {', '.join(biodbnet_inputs)}"
    ),
    value: str = typer.Option(
        ..., "--value", "-v",
        help="Identifier value(s), comma-separated for multiple values."
    ),
    outputs: str = typer.Option(
        "affyid,genesymbol,go-biologicalprocess", "--outputs", "-o",
        help=f"Type of output identifier(s). Options: {', '.join(biodbnet_outputs)}"
    ),
    pathways: str = typer.Option(
        None, "--pathways", "-p",
        help="Filter results by specific pathway(s), comma-separated."
    ),
    taxon_id: int = typer.Option(
        None, "--taxon_id", "-t",
        help="NCBI Taxonomy ID to filter results by organism."
    ),
    output: str = typer.Option(
        None, "--output", "-out",
        help="Output file to save the fetched data.",
    )

):
    """Fetch interaction data from BioGRID database."""
    instance = BioDBNetInterface()

    df = pd.DataFrame(instance.fetch_single(

        query={
            "input": input,
            "inputValues": value.split(","),
            "outputs": outputs,
            "pathways": pathways,
            "taxonId": taxon_id
        },
        method=method,
        parse=True,
        to_dataframe=True
    )).dropna(axis=1, how='all')

    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))

@app.command("biogrid")
def run_biogrid(
    method: str = typer.Option(
        "interactions", "--method", "-m",
        help=f"Method to use. Options: {', '.join(BioGRIDInterface.METHODS.keys())}"
    ),
    gene_list: str = typer.Option(
        None, "--gene-list", "-gl",
        help="Comma-separated list of gene symbols to fetch interactions for."
    ),
    taxon_id: str = typer.Option(
        None, "--taxon_id", "-t",
        help="NCBI Taxonomy ID to filter results by organism."
    ),
    access_key: str = typer.Option(
        None, "--access_key", "-ak",
        help="BioGRID API key to make authenticated requests"
    ),
    output: str = typer.Option(
        None, "--output", "-out",
        help="Output file to save the fetched data.",
    )
):
    """Fetch interaction data from BioGRID database."""
    if access_key is None:
        access_key = os.getenv("biogrid_api_key", None)
        if access_key is None:
            raise ValueError("An access key is required. Provide it via --access_key or set the biogrid_api_key environment variable.")

    instance = BioGRIDInterface()

    query = {
        "accessKey": access_key
    }

    if gene_list:
        query["geneList"] = gene_list.split(",")
    if taxon_id:
        query["taxId"] = taxon_id

    df = pd.DataFrame(instance.fetch_single(
        query=query,
        method=method,
        parse=True,
        to_dataframe=True
    ))

    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))


brenda_app = typer.Typer(help="Fetch data from BRENDA database.")
app.add_typer(brenda_app, name="brenda")
@brenda_app.command("KmValues")
def run_km_values(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access (if required)."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme to fetch Km values for."),
    km_value: str = typer.Option(None, "--km_value", "-km", help="Specific Km value to filter results."),
    km_value_max: str = typer.Option(None, "--km_value_max", "-kmmax", help="Maximum Km value to filter results."),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism name to filter results."),
    output: str = typer.Option(None, "--output", "-o", help="Output file to save the fetched data.",)
):
    """Fetch Km values from BRENDA database."""
    if email is None or password is None:
        email = os.getenv("brenda_email", None)
        password = os.getenv("brenda_password", None)
        if email is None or password is None:
            raise ValueError("Email and password are required. Provide them via --email and --password or set the brenda_email and brenda_password environment variables.")
    
    instance = BrendaInterface(email=email, password=password)

    query = {}

    if ec_number: query["ecNumber"] = ec_number
    if organism: query["organism"] = organism
    if km_value: query["kmValue"] = km_value
    if km_value_max: query["kmValueMaximum"] = km_value_max

    df = pd.DataFrame(instance.fetch_single(
        query=query,
        method="getKmValue",
        parse=True,
        to_dataframe=True
    ))

    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))

@brenda_app.command("Ic50Values")
def run_ic50_values(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    ic50_value: str = typer.Option(None, "--ic50_value", "--ic50", help="IC50 value filter."),
    ic50_value_max: str = typer.Option(None, "--ic50_value_max", "--ic50max", help="Maximum IC50 value filter."),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch IC50 values from BRENDA."""
    if email is None or password is None:
        email = os.getenv("brenda_email", None)
        password = os.getenv("brenda_password", None)
        if email is None or password is None:
            raise ValueError("Email and password are required. Provide them via --email and --password or set the brenda_email and brenda_password environment variables.")
    
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number: query["ecNumber"] = ec_number
    if ic50_value: query["ic50Value"] = ic50_value
    if ic50_value_max: query["ic50ValueMaximum"] = ic50_value_max
    if organism: query["organism"] = organism

    df = pd.DataFrame(instance.fetch_single(query=query, method="getIc50Value", parse=True, to_dataframe=True))
    if output: df.to_csv(output, index=False)
    else: print(df.head(5))


# ========= getKcatKmValue → KcatKmValues =========
@brenda_app.command("KcatKmValues")
def run_kcat_km_values(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    kcat_km_value: str = typer.Option(None, "--kcat_km_value", "--kcatkm", help="kcat/Km value filter."),
    kcat_km_value_max: str = typer.Option(None, "--kcat_km_value_max", "--kcatkmmax", help="Maximum kcat/Km value."),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch kcat/Km values from BRENDA."""
    if email is None or password is None:
        email = os.getenv("brenda_email", None)
        password = os.getenv("brenda_password", None)
        if email is None or password is None:
            raise ValueError("Email and password are required. Provide them via --email and --password or set the brenda_email and brenda_password environment variables.")
    
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number: query["ecNumber"] = ec_number
    if kcat_km_value: query["kcatKmValue"] = kcat_km_value
    if kcat_km_value_max: query["kcatKmValueMaximum"] = kcat_km_value_max
    if organism: query["organism"] = organism

    df = pd.DataFrame(instance.fetch_single(query=query, method="getKcatKmValue", parse=True, to_dataframe=True))
    if output: df.to_csv(output, index=False)
    else: print(df.head(5))


# ========= getKiValue → KiValues =========
@brenda_app.command("KiValues")
def run_ki_values(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    ki_value: str = typer.Option(None, "--ki_value", "--ki", help="Ki value filter."),
    ki_value_max: str = typer.Option(None, "--ki_value_max", "--kimax", help="Maximum Ki value filter."),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch Ki values from BRENDA."""
    if email is None or password is None:
        email = os.getenv("brenda_email", None)
        password = os.getenv("brenda_password", None)
        if email is None or password is None:
            raise ValueError("Email and password are required. Provide them via --email and --password or set the brenda_email and brenda_password environment variables.")
    
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number: query["ecNumber"] = ec_number
    if ki_value: query["kiValue"] = ki_value
    if ki_value_max: query["kiValueMaximum"] = ki_value_max
    if organism: query["organism"] = organism

    df = pd.DataFrame(instance.fetch_single(query=query, method="getKiValue", parse=True, to_dataframe=True))
    if output: df.to_csv(output, index=False)
    else: print(df.head(5))


@brenda_app.command("PhRange")
def run_ph_range(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    ph_range: str = typer.Option(None, "--ph_range", "--phr", help="pH range minimum filter."),
    ph_range_max: str = typer.Option(None, "--ph_range_max", "--phrmax", help="pH range maximum filter."),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch pH range data from BRENDA."""
    if email is None or password is None:
        email = os.getenv("brenda_email", None)
        password = os.getenv("brenda_password", None)
        if email is None or password is None:
            raise ValueError("Email and password are required. Provide them via --email and --password or set the brenda_email and brenda_password environment variables.")
    
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number: query["ecNumber"] = ec_number
    if ph_range: query["phRange"] = ph_range
    if ph_range_max: query["phRangeMaximum"] = ph_range_max
    if organism: query["organism"] = organism

    df = pd.DataFrame(instance.fetch_single(query=query, method="getPhRange", parse=True, to_dataframe=True))
    if output: df.to_csv(output, index=False)
    else: print(df.head(5))


# ========= getPhOptimum → PhOptimum =========
@brenda_app.command("PhOptimum")
def run_ph_optimum(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    ph_optimum: str = typer.Option(None, "--ph_optimum", "--pho", help="pH optimum minimum filter."),
    ph_optimum_max: str = typer.Option(None, "--ph_optimum_max", "--phomax", help="pH optimum maximum filter."),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch pH optimum data from BRENDA."""
    if email is None or password is None:
        email = os.getenv("brenda_email", None)
        password = os.getenv("brenda_password", None)
        if email is None or password is None:
            raise ValueError("Email and password are required. Provide them via --email and --password or set the brenda_email and brenda_password environment variables.")
    
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number: query["ecNumber"] = ec_number
    if ph_optimum: query["phOptimum"] = ph_optimum
    if ph_optimum_max: query["phOptimumMaximum"] = ph_optimum_max
    if organism: query["organism"] = organism

    df = pd.DataFrame(instance.fetch_single(query=query, method="getPhOptimum", parse=True, to_dataframe=True))
    if output: df.to_csv(output, index=False)
    else: print(df.head(5))


@brenda_app.command("PhStability")
def run_ph_stability(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    ph_stability: str = typer.Option(None, "--ph_stability", "--phs", help="pH stability minimum filter."),
    ph_stability_max: str = typer.Option(None, "--ph_stability_max", "--phsmax", help="pH stability maximum filter."),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch pH stability data from BRENDA."""
    if email is None or password is None:
        email = os.getenv("brenda_email", None)
        password = os.getenv("brenda_password", None)
        if email is None or password is None:
            raise ValueError("Email and password are required. Provide them via --email and --password or set the brenda_email and brenda_password environment variables.")
    
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number: query["ecNumber"] = ec_number
    if ph_stability: query["phStability"] = ph_stability
    if ph_stability_max: query["phStabilityMaximum"] = ph_stability_max
    if organism: query["organism"] = organism

    df = pd.DataFrame(instance.fetch_single(query=query, method="getPhStability", parse=True, to_dataframe=True))
    if output: df.to_csv(output, index=False)
    else: print(df.head(5))

@brenda_app.command("Cofactor")
def run_cofactor(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch cofactor data from BRENDA."""
    if email is None or password is None:
        email = os.getenv("brenda_email", None)
        password = os.getenv("brenda_password", None)
        if email is None or password is None:
            raise ValueError("Email and password are required. Provide them via --email and --password or set the brenda_email and brenda_password environment variables.")
    
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number: query["ecNumber"] = ec_number
    if organism: query["organism"] = organism

    df = pd.DataFrame(instance.fetch_single(query=query, method="getCofactor", parse=True, to_dataframe=True))
    if output: df.to_csv(output, index=False)
    else: print(df.head(5))

@brenda_app.command("TemperatureOptimum")
def run_temperature_optimum(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    temperature_optimum: str = typer.Option(None, "--temperature_optimum", "--topt", help="Temperature optimum min."),
    temperature_optimum_max: str = typer.Option(None, "--temperature_optimum_max", "--toptmax", help="Temperature optimum max."),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch temperature optimum data from BRENDA."""
    if email is None or password is None:
        email = os.getenv("brenda_email", None)
        password = os.getenv("brenda_password", None)
        if email is None or password is None:
            raise ValueError("Email and password are required. Provide them via --email and --password or set the brenda_email and brenda_password environment variables.")
    
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number: query["ecNumber"] = ec_number
    if temperature_optimum: query["temperatureOptimum"] = temperature_optimum
    if temperature_optimum_max: query["temperatureOptimumMaximum"] = temperature_optimum_max
    if organism: query["organism"] = organism

    df = pd.DataFrame(instance.fetch_single(query=query, method="getTemperatureOptimum", parse=True, to_dataframe=True))
    if output: df.to_csv(output, index=False)
    else: print(df.head(5))

@brenda_app.command("TemperatureStability")
def run_temperature_stability(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    temperature_stability: str = typer.Option(None, "--temperature_stability", "--tstab", help="Temperature stability min."),
    temperature_stability_max: str = typer.Option(None, "--temperature_stability_max", "--tstabmax", help="Temperature stability max."),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch temperature stability data from BRENDA."""
    if email is None or password is None:
        email = os.getenv("brenda_email", None)
        password = os.getenv("brenda_password", None)
        if email is None or password is None:
            raise ValueError("Email and password are required. Provide them via --email and --password or set the brenda_email and brenda_password environment variables.")
    
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number: query["ecNumber"] = ec_number
    if temperature_stability: query["temperatureStability"] = temperature_stability
    if temperature_stability_max: query["temperatureStabilityMaximum"] = temperature_stability_max
    if organism: query["organism"] = organism

    df = pd.DataFrame(instance.fetch_single(query=query, method="getTemperatureStability", parse=True, to_dataframe=True))
    if output: df.to_csv(output, index=False)
    else: print(df.head(5))

@brenda_app.command("TemperatureRange")
def run_temperature_range(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    temperature_range: str = typer.Option(None, "--temperature_range", "--trng", help="Temperature range min."),
    temperature_range_max: str = typer.Option(None, "--temperature_range_max", "--trngmax", help="Temperature range max."),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch temperature range data from BRENDA."""
    if email is None or password is None:
        email = os.getenv("brenda_email", None)
        password = os.getenv("brenda_password", None)
        if email is None or password is None:
            raise ValueError("Email and password are required. Provide them via --email and --password or set the brenda_email and brenda_password environment variables.")
    
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number: query["ecNumber"] = ec_number
    if temperature_range: query["temperatureRange"] = temperature_range
    if temperature_range_max: query["temperatureRangeMaximum"] = temperature_range_max
    if organism: query["organism"] = organism

    df = pd.DataFrame(instance.fetch_single(query=query, method="getTemperatureRange", parse=True, to_dataframe=True))
    if output: df.to_csv(output, index=False)
    else: print(df.head(5))
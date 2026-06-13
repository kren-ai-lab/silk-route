import pandas as pd
import typer

from bioseq_dl import BrendaInterface

app = typer.Typer(help="Fetch data from BRENDA database.")


@app.command("KmValues")
def run_km_values(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access (if required)."),
    ec_number: str = typer.Option(
        ..., "--ec_number", "-ec", help="EC number of the enzyme to fetch Km values for."
    ),
    km_value: str = typer.Option(None, "--km_value", "-km", help="Specific Km value to filter results."),
    km_value_max: str = typer.Option(
        None, "--km_value_max", "-kmmax", help="Maximum Km value to filter results."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism name to filter results."),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file to save the fetched data.",
    ),
):
    """Fetch Km values from BRENDA database."""
    instance = BrendaInterface(email=email, password=password)

    query = {}

    if ec_number:
        query["ecNumber"] = ec_number
    if organism:
        query["organism"] = organism
    if km_value:
        query["kmValue"] = km_value
    if km_value_max:
        query["kmValueMaximum"] = km_value_max

    df = pd.DataFrame(instance.fetch_single(query=query, method="getKmValue", parse=True, format="dataframe"))

    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))


@app.command("Ic50Values")
def run_ic50_values(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    ic50_value: str = typer.Option(None, "--ic50_value", "--ic50", help="IC50 value filter."),
    ic50_value_max: str = typer.Option(
        None, "--ic50_value_max", "--ic50max", help="Maximum IC50 value filter."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch IC50 values from BRENDA."""
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number:
        query["ecNumber"] = ec_number
    if ic50_value:
        query["ic50Value"] = ic50_value
    if ic50_value_max:
        query["ic50ValueMaximum"] = ic50_value_max
    if organism:
        query["organism"] = organism

    df = pd.DataFrame(
        instance.fetch_single(query=query, method="getIc50Value", parse=True, format="dataframe")
    )
    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))


# ========= getKcatKmValue → KcatKmValues =========
@app.command("KcatKmValues")
def run_kcat_km_values(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    kcat_km_value: str = typer.Option(None, "--kcat_km_value", "--kcatkm", help="kcat/Km value filter."),
    kcat_km_value_max: str = typer.Option(
        None, "--kcat_km_value_max", "--kcatkmmax", help="Maximum kcat/Km value."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch kcat/Km values from BRENDA."""
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number:
        query["ecNumber"] = ec_number
    if kcat_km_value:
        query["kcatKmValue"] = kcat_km_value
    if kcat_km_value_max:
        query["kcatKmValueMaximum"] = kcat_km_value_max
    if organism:
        query["organism"] = organism

    df = pd.DataFrame(
        instance.fetch_single(query=query, method="getKcatKmValue", parse=True, format="dataframe")
    )
    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))


# ========= getKiValue → KiValues =========
@app.command("KiValues")
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
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number:
        query["ecNumber"] = ec_number
    if ki_value:
        query["kiValue"] = ki_value
    if ki_value_max:
        query["kiValueMaximum"] = ki_value_max
    if organism:
        query["organism"] = organism

    df = pd.DataFrame(instance.fetch_single(query=query, method="getKiValue", parse=True, format="dataframe"))
    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))


@app.command("PhRange")
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
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number:
        query["ecNumber"] = ec_number
    if ph_range:
        query["phRange"] = ph_range
    if ph_range_max:
        query["phRangeMaximum"] = ph_range_max
    if organism:
        query["organism"] = organism

    df = pd.DataFrame(instance.fetch_single(query=query, method="getPhRange", parse=True, format="dataframe"))
    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))


# ========= getPhOptimum → PhOptimum =========
@app.command("PhOptimum")
def run_ph_optimum(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    ph_optimum: str = typer.Option(None, "--ph_optimum", "--pho", help="pH optimum minimum filter."),
    ph_optimum_max: str = typer.Option(
        None, "--ph_optimum_max", "--phomax", help="pH optimum maximum filter."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch pH optimum data from BRENDA."""
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number:
        query["ecNumber"] = ec_number
    if ph_optimum:
        query["phOptimum"] = ph_optimum
    if ph_optimum_max:
        query["phOptimumMaximum"] = ph_optimum_max
    if organism:
        query["organism"] = organism

    df = pd.DataFrame(
        instance.fetch_single(query=query, method="getPhOptimum", parse=True, format="dataframe")
    )
    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))


@app.command("PhStability")
def run_ph_stability(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    ph_stability: str = typer.Option(None, "--ph_stability", "--phs", help="pH stability minimum filter."),
    ph_stability_max: str = typer.Option(
        None, "--ph_stability_max", "--phsmax", help="pH stability maximum filter."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch pH stability data from BRENDA."""
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number:
        query["ecNumber"] = ec_number
    if ph_stability:
        query["phStability"] = ph_stability
    if ph_stability_max:
        query["phStabilityMaximum"] = ph_stability_max
    if organism:
        query["organism"] = organism

    df = pd.DataFrame(
        instance.fetch_single(query=query, method="getPhStability", parse=True, format="dataframe")
    )
    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))


@app.command("Cofactor")
def run_cofactor(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch cofactor data from BRENDA."""
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number:
        query["ecNumber"] = ec_number
    if organism:
        query["organism"] = organism

    df = pd.DataFrame(
        instance.fetch_single(query=query, method="getCofactor", parse=True, format="dataframe")
    )
    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))


@app.command("TemperatureOptimum")
def run_temperature_optimum(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    temperature_optimum: str = typer.Option(
        None, "--temperature_optimum", "--topt", help="Temperature optimum min."
    ),
    temperature_optimum_max: str = typer.Option(
        None, "--temperature_optimum_max", "--toptmax", help="Temperature optimum max."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch temperature optimum data from BRENDA."""
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number:
        query["ecNumber"] = ec_number
    if temperature_optimum:
        query["temperatureOptimum"] = temperature_optimum
    if temperature_optimum_max:
        query["temperatureOptimumMaximum"] = temperature_optimum_max
    if organism:
        query["organism"] = organism

    df = pd.DataFrame(
        instance.fetch_single(query=query, method="getTemperatureOptimum", parse=True, format="dataframe")
    )
    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))


@app.command("TemperatureStability")
def run_temperature_stability(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    temperature_stability: str = typer.Option(
        None, "--temperature_stability", "--tstab", help="Temperature stability min."
    ),
    temperature_stability_max: str = typer.Option(
        None, "--temperature_stability_max", "--tstabmax", help="Temperature stability max."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch temperature stability data from BRENDA."""
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number:
        query["ecNumber"] = ec_number
    if temperature_stability:
        query["temperatureStability"] = temperature_stability
    if temperature_stability_max:
        query["temperatureStabilityMaximum"] = temperature_stability_max
    if organism:
        query["organism"] = organism

    df = pd.DataFrame(
        instance.fetch_single(query=query, method="getTemperatureStability", parse=True, format="dataframe")
    )
    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))


@app.command("TemperatureRange")
def run_temperature_range(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec_number", "-ec", help="EC number of the enzyme."),
    temperature_range: str = typer.Option(
        None, "--temperature_range", "--trng", help="Temperature range min."
    ),
    temperature_range_max: str = typer.Option(
        None, "--temperature_range_max", "--trngmax", help="Temperature range max."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = typer.Option(None, "--output", "-o", help="CSV file to save results."),
):
    """Fetch temperature range data from BRENDA."""
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number:
        query["ecNumber"] = ec_number
    if temperature_range:
        query["temperatureRange"] = temperature_range
    if temperature_range_max:
        query["temperatureRangeMaximum"] = temperature_range_max
    if organism:
        query["organism"] = organism

    df = pd.DataFrame(
        instance.fetch_single(query=query, method="getTemperatureRange", parse=True, format="dataframe")
    )
    if output:
        df.to_csv(output, index=False)
    else:
        print(df.head(5))

"""BRENDA CLI commands."""

import typer

from bioseq_dl import BrendaInterface
from bioseq_dl.cli._shared import format_option, output_option, save_or_print

app = typer.Typer(help="Fetch data from BRENDA database.")


@app.command("km-values")
def run_km_values(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access (if required)."),
    ec_number: str = typer.Option(
        ..., "--ec-number", "-ec", help="EC number of the enzyme to fetch Km values for."
    ),
    km_value: str = typer.Option(None, "--km-value", "-km", help="Specific Km value to filter results."),
    km_value_max: str = typer.Option(
        None, "--km-value-max", "-kmmax", help="Maximum Km value to filter results."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism name to filter results."),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
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

    df = instance.fetch_single(query=query, method="getKmValue", parse=True, format="dataframe")

    save_or_print(df, output, output_format=output_format)


@app.command("ic50-values")
def run_ic50_values(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec-number", "-ec", help="EC number of the enzyme."),
    ic50_value: str = typer.Option(None, "--ic50-value", "--ic50", help="IC50 value filter."),
    ic50_value_max: str = typer.Option(
        None, "--ic50-value-max", "--ic50max", help="Maximum IC50 value filter."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
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

    df = instance.fetch_single(query=query, method="getIc50Value", parse=True, format="dataframe")
    save_or_print(df, output, output_format=output_format)


# ========= getKcatKmValue → KcatKmValues =========
@app.command("kcat-km-values")
def run_kcat_km_values(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec-number", "-ec", help="EC number of the enzyme."),
    kcat_km_value: str = typer.Option(None, "--kcat-km-value", "--kcatkm", help="kcat/Km value filter."),
    kcat_km_value_max: str = typer.Option(
        None, "--kcat-km-value-max", "--kcatkmmax", help="Maximum kcat/Km value."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
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

    df = instance.fetch_single(query=query, method="getKcatKmValue", parse=True, format="dataframe")
    save_or_print(df, output, output_format=output_format)


# ========= getKiValue → KiValues =========
@app.command("ki-values")
def run_ki_values(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec-number", "-ec", help="EC number of the enzyme."),
    ki_value: str = typer.Option(None, "--ki-value", "--ki", help="Ki value filter."),
    ki_value_max: str = typer.Option(None, "--ki-value-max", "--kimax", help="Maximum Ki value filter."),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
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

    df = instance.fetch_single(query=query, method="getKiValue", parse=True, format="dataframe")
    save_or_print(df, output, output_format=output_format)


@app.command("ph-range")
def run_ph_range(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec-number", "-ec", help="EC number of the enzyme."),
    ph_range: str = typer.Option(None, "--ph-range", "--phr", help="pH range minimum filter."),
    ph_range_max: str = typer.Option(None, "--ph-range-max", "--phrmax", help="pH range maximum filter."),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
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

    df = instance.fetch_single(query=query, method="getPhRange", parse=True, format="dataframe")
    save_or_print(df, output, output_format=output_format)


# ========= getPhOptimum → PhOptimum =========
@app.command("ph-optimum")
def run_ph_optimum(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec-number", "-ec", help="EC number of the enzyme."),
    ph_optimum: str = typer.Option(None, "--ph-optimum", "--pho", help="pH optimum minimum filter."),
    ph_optimum_max: str = typer.Option(
        None, "--ph-optimum-max", "--phomax", help="pH optimum maximum filter."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
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

    df = instance.fetch_single(query=query, method="getPhOptimum", parse=True, format="dataframe")
    save_or_print(df, output, output_format=output_format)


@app.command("ph-stability")
def run_ph_stability(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec-number", "-ec", help="EC number of the enzyme."),
    ph_stability: str = typer.Option(None, "--ph-stability", "--phs", help="pH stability minimum filter."),
    ph_stability_max: str = typer.Option(
        None, "--ph-stability-max", "--phsmax", help="pH stability maximum filter."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
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

    df = instance.fetch_single(query=query, method="getPhStability", parse=True, format="dataframe")
    save_or_print(df, output, output_format=output_format)


@app.command("cofactor")
def run_cofactor(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec-number", "-ec", help="EC number of the enzyme."),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch cofactor data from BRENDA."""
    instance = BrendaInterface(email=email, password=password)

    query = {}
    if ec_number:
        query["ecNumber"] = ec_number
    if organism:
        query["organism"] = organism

    df = instance.fetch_single(query=query, method="getCofactor", parse=True, format="dataframe")
    save_or_print(df, output, output_format=output_format)


@app.command("temperature-optimum")
def run_temperature_optimum(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec-number", "-ec", help="EC number of the enzyme."),
    temperature_optimum: str = typer.Option(
        None, "--temperature-optimum", "--topt", help="Temperature optimum min."
    ),
    temperature_optimum_max: str = typer.Option(
        None, "--temperature-optimum-max", "--toptmax", help="Temperature optimum max."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
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

    df = instance.fetch_single(query=query, method="getTemperatureOptimum", parse=True, format="dataframe")
    save_or_print(df, output, output_format=output_format)


@app.command("temperature-stability")
def run_temperature_stability(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec-number", "-ec", help="EC number of the enzyme."),
    temperature_stability: str = typer.Option(
        None, "--temperature-stability", "--tstab", help="Temperature stability min."
    ),
    temperature_stability_max: str = typer.Option(
        None, "--temperature-stability-max", "--tstabmax", help="Temperature stability max."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
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

    df = instance.fetch_single(query=query, method="getTemperatureStability", parse=True, format="dataframe")
    save_or_print(df, output, output_format=output_format)


@app.command("temperature-range")
def run_temperature_range(
    email: str = typer.Option(None, "--email", "-e", help="Email address required by BRENDA for access."),
    password: str = typer.Option(None, "--password", "-p", help="Password for BRENDA access."),
    ec_number: str = typer.Option(..., "--ec-number", "-ec", help="EC number of the enzyme."),
    temperature_range: str = typer.Option(
        None, "--temperature-range", "--trng", help="Temperature range min."
    ),
    temperature_range_max: str = typer.Option(
        None, "--temperature-range-max", "--trngmax", help="Temperature range max."
    ),
    organism: str = typer.Option(None, "--organism", "-org", help="Organism filter."),
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
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

    df = instance.fetch_single(query=query, method="getTemperatureRange", parse=True, format="dataframe")
    save_or_print(df, output, output_format=output_format)

"""BRENDA CLI commands."""

from typing import Any

import typer

from silkroute import BrendaInterface
from silkroute.cli._shared import format_option, output_option, save_or_print

app = typer.Typer(help="Fetch data from BRENDA database.")


# Shared option/argument defaults, reused across the BRENDA commands.
_EMAIL_OPTION: Any = typer.Option(
    None,
    "--email",
    "-e",
    envvar="SILKROUTE_BRENDA_EMAIL",
    help="BRENDA account email (or set SILKROUTE_BRENDA_EMAIL).",
)
_PASSWORD_OPTION: Any = typer.Option(
    None,
    "--password",
    envvar="SILKROUTE_BRENDA_PASSWORD",
    help="BRENDA password. Prefer the SILKROUTE_BRENDA_PASSWORD env var over passing it on the command line.",
)
_EC_ARGUMENT: Any = typer.Argument(..., help="EC number of the enzyme.")
_ORGANISM_OPTION: Any = typer.Option(None, "--organism", "-org", help="Organism name to filter results.")


def _run_brenda(
    method: str,
    *,
    email: str | None,
    password: str | None,
    ec_number: str,
    organism: str | None,
    output: str | None,
    output_format: str | None,
    filters: dict[str, str | None],
) -> None:
    """Build the BRENDA query, fetch, and save/print.

    ``filters`` maps BRENDA API field names to optional values; ``None`` values
    are dropped. ``ecNumber`` and ``organism`` are added automatically.
    """
    instance = BrendaInterface(email=email, password=password)

    query: dict[str, str] = {"ecNumber": ec_number}
    if organism:
        query["organism"] = organism
    query.update({key: value for key, value in filters.items() if value is not None})

    df = instance.fetch_single(query=query, method=method, parse=True, format="dataframe")
    save_or_print(df, output, output_format=output_format)


@app.command("km-values")
def run_km_values(
    ec_number: str = _EC_ARGUMENT,
    email: str = _EMAIL_OPTION,
    password: str = _PASSWORD_OPTION,
    km_value: str = typer.Option(None, "--km-value", "-km", help="Specific Km value to filter results."),
    km_value_max: str = typer.Option(
        None, "--km-value-max", "-kmmax", help="Maximum Km value to filter results."
    ),
    organism: str = _ORGANISM_OPTION,
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch Km values from BRENDA database."""
    _run_brenda(
        "getKmValue",
        email=email,
        password=password,
        ec_number=ec_number,
        organism=organism,
        output=output,
        output_format=output_format,
        filters={"kmValue": km_value, "kmValueMaximum": km_value_max},
    )


@app.command("ic50-values")
def run_ic50_values(
    ec_number: str = _EC_ARGUMENT,
    email: str = _EMAIL_OPTION,
    password: str = _PASSWORD_OPTION,
    ic50_value: str = typer.Option(None, "--ic50-value", "--ic50", help="IC50 value filter."),
    ic50_value_max: str = typer.Option(
        None, "--ic50-value-max", "--ic50max", help="Maximum IC50 value filter."
    ),
    organism: str = _ORGANISM_OPTION,
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch IC50 values from BRENDA."""
    _run_brenda(
        "getIc50Value",
        email=email,
        password=password,
        ec_number=ec_number,
        organism=organism,
        output=output,
        output_format=output_format,
        filters={"ic50Value": ic50_value, "ic50ValueMaximum": ic50_value_max},
    )


@app.command("kcat-km-values")
def run_kcat_km_values(
    ec_number: str = _EC_ARGUMENT,
    email: str = _EMAIL_OPTION,
    password: str = _PASSWORD_OPTION,
    kcat_km_value: str = typer.Option(None, "--kcat-km-value", "--kcatkm", help="kcat/Km value filter."),
    kcat_km_value_max: str = typer.Option(
        None, "--kcat-km-value-max", "--kcatkmmax", help="Maximum kcat/Km value."
    ),
    organism: str = _ORGANISM_OPTION,
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch kcat/Km values from BRENDA."""
    _run_brenda(
        "getKcatKmValue",
        email=email,
        password=password,
        ec_number=ec_number,
        organism=organism,
        output=output,
        output_format=output_format,
        filters={"kcatKmValue": kcat_km_value, "kcatKmValueMaximum": kcat_km_value_max},
    )


@app.command("ki-values")
def run_ki_values(
    ec_number: str = _EC_ARGUMENT,
    email: str = _EMAIL_OPTION,
    password: str = _PASSWORD_OPTION,
    ki_value: str = typer.Option(None, "--ki-value", "--ki", help="Ki value filter."),
    ki_value_max: str = typer.Option(None, "--ki-value-max", "--kimax", help="Maximum Ki value filter."),
    organism: str = _ORGANISM_OPTION,
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch Ki values from BRENDA."""
    _run_brenda(
        "getKiValue",
        email=email,
        password=password,
        ec_number=ec_number,
        organism=organism,
        output=output,
        output_format=output_format,
        filters={"kiValue": ki_value, "kiValueMaximum": ki_value_max},
    )


@app.command("ph-range")
def run_ph_range(
    ec_number: str = _EC_ARGUMENT,
    email: str = _EMAIL_OPTION,
    password: str = _PASSWORD_OPTION,
    ph_range: str = typer.Option(None, "--ph-range", "--phr", help="pH range minimum filter."),
    ph_range_max: str = typer.Option(None, "--ph-range-max", "--phrmax", help="pH range maximum filter."),
    organism: str = _ORGANISM_OPTION,
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch pH range data from BRENDA."""
    _run_brenda(
        "getPhRange",
        email=email,
        password=password,
        ec_number=ec_number,
        organism=organism,
        output=output,
        output_format=output_format,
        filters={"phRange": ph_range, "phRangeMaximum": ph_range_max},
    )


@app.command("ph-optimum")
def run_ph_optimum(
    ec_number: str = _EC_ARGUMENT,
    email: str = _EMAIL_OPTION,
    password: str = _PASSWORD_OPTION,
    ph_optimum: str = typer.Option(None, "--ph-optimum", "--pho", help="pH optimum minimum filter."),
    ph_optimum_max: str = typer.Option(
        None, "--ph-optimum-max", "--phomax", help="pH optimum maximum filter."
    ),
    organism: str = _ORGANISM_OPTION,
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch pH optimum data from BRENDA."""
    _run_brenda(
        "getPhOptimum",
        email=email,
        password=password,
        ec_number=ec_number,
        organism=organism,
        output=output,
        output_format=output_format,
        filters={"phOptimum": ph_optimum, "phOptimumMaximum": ph_optimum_max},
    )


@app.command("ph-stability")
def run_ph_stability(
    ec_number: str = _EC_ARGUMENT,
    email: str = _EMAIL_OPTION,
    password: str = _PASSWORD_OPTION,
    ph_stability: str = typer.Option(None, "--ph-stability", "--phs", help="pH stability minimum filter."),
    ph_stability_max: str = typer.Option(
        None, "--ph-stability-max", "--phsmax", help="pH stability maximum filter."
    ),
    organism: str = _ORGANISM_OPTION,
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch pH stability data from BRENDA."""
    _run_brenda(
        "getPhStability",
        email=email,
        password=password,
        ec_number=ec_number,
        organism=organism,
        output=output,
        output_format=output_format,
        filters={"phStability": ph_stability, "phStabilityMaximum": ph_stability_max},
    )


@app.command("cofactor")
def run_cofactor(
    ec_number: str = _EC_ARGUMENT,
    email: str = _EMAIL_OPTION,
    password: str = _PASSWORD_OPTION,
    organism: str = _ORGANISM_OPTION,
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch cofactor data from BRENDA."""
    _run_brenda(
        "getCofactor",
        email=email,
        password=password,
        ec_number=ec_number,
        organism=organism,
        output=output,
        output_format=output_format,
        filters={},
    )


@app.command("temperature-optimum")
def run_temperature_optimum(
    ec_number: str = _EC_ARGUMENT,
    email: str = _EMAIL_OPTION,
    password: str = _PASSWORD_OPTION,
    temperature_optimum: str = typer.Option(
        None, "--temperature-optimum", "--topt", help="Temperature optimum min."
    ),
    temperature_optimum_max: str = typer.Option(
        None, "--temperature-optimum-max", "--toptmax", help="Temperature optimum max."
    ),
    organism: str = _ORGANISM_OPTION,
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch temperature optimum data from BRENDA."""
    _run_brenda(
        "getTemperatureOptimum",
        email=email,
        password=password,
        ec_number=ec_number,
        organism=organism,
        output=output,
        output_format=output_format,
        filters={
            "temperatureOptimum": temperature_optimum,
            "temperatureOptimumMaximum": temperature_optimum_max,
        },
    )


@app.command("temperature-stability")
def run_temperature_stability(
    ec_number: str = _EC_ARGUMENT,
    email: str = _EMAIL_OPTION,
    password: str = _PASSWORD_OPTION,
    temperature_stability: str = typer.Option(
        None, "--temperature-stability", "--tstab", help="Temperature stability min."
    ),
    temperature_stability_max: str = typer.Option(
        None, "--temperature-stability-max", "--tstabmax", help="Temperature stability max."
    ),
    organism: str = _ORGANISM_OPTION,
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch temperature stability data from BRENDA."""
    _run_brenda(
        "getTemperatureStability",
        email=email,
        password=password,
        ec_number=ec_number,
        organism=organism,
        output=output,
        output_format=output_format,
        filters={
            "temperatureStability": temperature_stability,
            "temperatureStabilityMaximum": temperature_stability_max,
        },
    )


@app.command("temperature-range")
def run_temperature_range(
    ec_number: str = _EC_ARGUMENT,
    email: str = _EMAIL_OPTION,
    password: str = _PASSWORD_OPTION,
    temperature_range: str = typer.Option(
        None, "--temperature-range", "--trng", help="Temperature range min."
    ),
    temperature_range_max: str = typer.Option(
        None, "--temperature-range-max", "--trngmax", help="Temperature range max."
    ),
    organism: str = _ORGANISM_OPTION,
    output: str = output_option(),
    output_format: str = format_option(),
) -> None:
    """Fetch temperature range data from BRENDA."""
    _run_brenda(
        "getTemperatureRange",
        email=email,
        password=password,
        ec_number=ec_number,
        organism=organism,
        output=output,
        output_format=output_format,
        filters={"temperatureRange": temperature_range, "temperatureRangeMaximum": temperature_range_max},
    )

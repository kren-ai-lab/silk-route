"""PRIDE CLI commands."""

import typer

from bioseq_dl import PrideInterface
from bioseq_dl.cli._shared import format_option, output_option, save_or_print

app = typer.Typer(help="Collect data from PRIDE database.")


@app.command("search_projects")
def run_search_projects(
    keyword: str = typer.Argument(..., help="Keyword to search for."),
    filter_value: str | None = typer.Option(None, "--filter", help="Filter for the search."),
    page: int = typer.Option(0, "--page", help="Page number for pagination."),
    dateGap: str | None = typer.Option(None, "--dateGap", help="Date gap filter."),
    sortDirection: str = typer.Option("DESC", "--sortDirection", help="Sort direction (ASC or DESC)."),
    sortFields: str = typer.Option("submissionDate", "--sortFields", help="Field to sort by."),
    output: str | None = output_option(),
    output_format: str = format_option(),
) -> None:
    """Search for projects in the PRIDE database."""
    interface = PrideInterface()
    query = {
        "keyword": keyword,
        "filter": filter_value,
        "page": page,
        "dateGap": dateGap,
        "sortDirection": sortDirection,
        "sortFields": sortFields,
    }
    results = interface.fetch_single(
        method="search", option="projects", query=query, parse=True, format="dataframe"
    )

    save_or_print(results, output, output_format=output_format)


@app.command("projects")
def run_projects(
    projectAccession: str = typer.Argument(..., help="Project accession ID."),
    output: str | None = output_option(),
    output_format: str = format_option(),
) -> None:
    """Get details of a specific project by its accession ID."""
    interface = PrideInterface()
    query = {"projectAccession": projectAccession}
    results = interface.fetch_single(
        method="projects", option="default", query=query, parse=True, format="dataframe"
    )

    save_or_print(results, output, output_format=output_format)


@app.command("similar_projects")
def run_similar_projects(
    accession: str = typer.Argument(..., help="Project accession ID to find similar projects."),
    page: int = typer.Option(0, "--page", help="Page number for pagination."),
    pageSize: int = typer.Option(10, "--pageSize", help="Number of results per page."),
    output: str | None = output_option(),
    output_format: str = format_option(),
) -> None:
    """Get similar projects to a given project accession ID."""
    interface = PrideInterface()
    query = {"accession": accession, "page": page, "pageSize": pageSize}
    results = interface.fetch_single(
        method="projects", option="similarProjects", query=query, parse=True, format="dataframe"
    )

    save_or_print(results, output, output_format=output_format)

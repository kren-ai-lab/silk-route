import pandas as pd 
import typer
from bioseq_dl import UniprotInterface
from bioseq_dl.constants.uniprot import VALID_FIELDS, XREF_MAPPING

app = typer.Typer(name="uniprot-search-query", help="Search and download sequences from UniProt using queries.")    

@app.command()
def run(
    output: str = typer.Option(
        ..., "-o", "--output", 
        help="Output file path"
    ),
    query: str = typer.Option(
        ..., "-q", "--query", 
        help="Query to search for"
    ),
    fields: str = typer.Option(
        ",".join(VALID_FIELDS), "-f", "--fields", 
        help="Fields to include in the output"
    ),
    crossref_fields: str = typer.Option(
        ",".join([xref[1] for xref in XREF_MAPPING.values()]), "-xr", "--crossref_fields", 
        help="Cross reference fields to include in the output"
    ),
    sort: str = typer.Option(
        "accession asc", "-s", "--sort", 
        help="Sort order for the results"
    ),
    format: str = typer.Option(
        "json", "-fmt", "--format", 
        help="Format of the output"
    ),
    include_isoform: bool = typer.Option(
        False, "--include_isoform", 
        help="Include isoforms in the results"
    ),
    download: bool = typer.Option(
        False, "--download", 
        help="Download the results"
    )):
    instance = UniprotInterface()
    print(f"Downloading data using\nquery {query}\nfields {fields}\ncrossref_fields {crossref_fields}\nformat {format}\nsort {sort}\ninclude_isoform {include_isoform}\ndownload {download}")
    xref_mapping = {v[1]: v[0] for k, v in XREF_MAPPING.items() if v[0] is not None}
    xref = ",".join([xref_mapping[c] for c in crossref_fields.split(",") if c in xref_mapping])

    response = instance.submit_stream(
        query=query,
        fields=fields + "," + xref,
        sort=sort,
        include_isoform=include_isoform,
        download=download,
        format=format
    )
    with open("response.json", "w") as f:
        f.write(response.text)

    print("Parsing results...")
    export_df = instance.parse_stream_response(
        query=query,
        response=response,
        extract_fields=None
    )

    export_df.to_csv(output, index=False)

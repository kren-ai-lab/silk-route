import pandas as pd 
import typer
from bioseq_dl import UniprotInterface

app = typer.Typer(name="uniprot-search-query", help="Search and download sequences from UniProt using queries.")    

FIELDS = [
    "accession",
    "protein_name",
    "gene_primary",
    "organism_name",
    "lineage",
    "ec",
    "sequence"
]

CROSS_REF_FIELDS = {
    "alphafold": "xref_alphafolddb",
    "biogrid": "xref_biogrid",
    "brenda": "xref_brenda",
    "go": "go_id",
    "chembl": "xref_chembl",
    "interpro": "xref_interpro",
    "kegg": "xref_kegg",
    "panther": "xref_panther",
    "pathwaycommons": "xref_pathwaycommons",
    "pdb": "xref_pdb",
    "pfam": "xref_pfam",
    "pride": "xref_pride",
    "refseq": "xref_refseq",
    "reactome": "xref_reactome",
    "string": "xref_string",
    "rhea": "rhea",
}

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
        ",".join(FIELDS), "-f", "--fields", 
        help="Fields to include in the output"
    ),
    crossref_fields: str = typer.Option(
        ",".join(CROSS_REF_FIELDS.keys()), "-xr", "--crossref_fields", 
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
    xref = ",".join([CROSS_REF_FIELDS[c] for c in crossref_fields.split(",") if c in CROSS_REF_FIELDS])

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

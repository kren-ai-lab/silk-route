import gradio as gr
import pandas as pd
from bioseq_dl import UniprotInterface

###############################
# UniProt Search UI
###############################

FIELDS = [
    "accession",
    "protein_name",
    "gene_primary",
    "organism_name",
    "lineage",
    "ec",
    "sequence"
]

CROSS_REF_FIELDS = [
    "xref_pfam",
    "xref_kegg",
    "xref_alphafolddb",
    "xref_chembl",
    "xref_refseq",
    "xref_brenda",
    "xref_reactome",
    "xref_pdb",
    "xref_interpro",
    "xref_panther",
    "xref_pathwaycommons",
    "xref_pride",
    "xref_string",
    "rhea",
    "go_id"
]

def run_uniprot_query(query, fields, crossref_fields, sort, fmt, include_isoform, download):
    logs = []
    logs.append(f"Starting query: {query}")
    
    fields = fields or []
    crossref_fields = crossref_fields or []
    logs.append(f"Using fields: {fields}")
    logs.append(f"Using crossref fields: {crossref_fields}")
    logs.append(f"Sort: {sort}, Format: {fmt}, Include Isoform: {include_isoform}, Download: {download}")

    instance = UniprotInterface()

    try:
        logs.append("Submitting stream request to UniProt...")
        response = instance.submit_stream(
            query=query,
            fields=",".join(fields + crossref_fields),
            sort=sort,
            include_isoform=include_isoform,
            download=download,
            format=fmt
        )
        logs.append(f"Response received (status code {response.status_code})")

        logs.append("Parsing response...")
        df = instance.parse_stream_response(query=query, response=response, extract_fields=None)

    except Exception as e:
        logs.append(f"Error: {e}")
        df = pd.DataFrame()  # retorna un df vacío en caso de error

    return df, "\n".join(logs)


def build_ui():
    with gr.Tab("UniProt Search"):
        query_input = gr.Textbox(label="Query", placeholder="Make a UniProt query")

        fields_select = gr.CheckboxGroup(
            choices=FIELDS,
            value=FIELDS,
            label="Fields"
        )
        crossref_select = gr.CheckboxGroup(
            choices=CROSS_REF_FIELDS,
            value=CROSS_REF_FIELDS,
            label="Cross-reference Fields"
        )

        sort_input = gr.Textbox(label="Sort", value="accession asc")
        fmt_dropdown = gr.Dropdown(choices=["json"], value="json", label="Format")
        include_isoform_chk = gr.Checkbox(label="Include Isoforms", value=False)
        download_chk = gr.Checkbox(label="Download Raw", value=False)

        search_btn = gr.Button("Search")
        results_out = gr.Dataframe(label="Results", interactive=False, wrap=True)
        logs_out = gr.Textbox(label="Logs", interactive=False)
        

        search_btn.click(
            fn=run_uniprot_query,
            inputs=[query_input, fields_select, crossref_select, sort_input, fmt_dropdown, include_isoform_chk, download_chk],
            outputs=[results_out, logs_out]
        )


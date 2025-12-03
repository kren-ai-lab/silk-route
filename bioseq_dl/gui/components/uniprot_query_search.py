import logging, os
import tempfile
import gradio as gr
import pandas as pd
from bioseq_dl import UniprotInterface

from bioseq_dl.core.crossref_enricher import CrossRefEnricher, EndpointSpec
from bioseq_dl.core.interfacesconfig import ConfigLoader
from bioseq_dl.constants.databases import BASE_CONFIG_DIR
from bioseq_dl.constants.uniprot import VALID_FIELDS, XREF_MAPPING, VALID_CROSS_REF_FIELDS
from .utils import run_crossref_enrichment

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

log = get_logger("bioseq_dl.gui.components.uniprot_query_search")
# -------------------------------------------------

###############################
# UniProt Search UI
###############################

def run_uniprot_query(query, fields, crossref_fields, sort, fmt, include_isoform, download):
    gui_logs = []
    log.info(f"Starting query: {query}")
    
    fields = fields or []
    xref_fields = [XREF_MAPPING[c][0] for c in (crossref_fields or []) if c in XREF_MAPPING and XREF_MAPPING[c][0]]
    log.debug(f"Using fields: {fields}")
    log.debug(f"Using crossref fields: {xref_fields}")
    log.debug(f"Sort: {sort}, Format: {fmt}, Include Isoform: {include_isoform}, Download: {download}")

    instance = UniprotInterface()

    try:
        log.info("Submitting stream request to UniProt...")
        response = instance.submit_stream(
            query=query,
            fields=",".join(fields + xref_fields),
            sort=sort,
            include_isoform=include_isoform,
            download=download,
            format=fmt
        )
        log.info(f"Response received (status code {response.status_code})")

        log.info("Parsing response...")
        df = instance.parse_results(results=response, extract_fields=None)

    except Exception as e:
        gui_logs.append(f"Error during UniProt query, see logs for details.")
        log.error(f"Error: {e}")
        df = pd.DataFrame()  # retorna un df vacío en caso de error
    
    if crossref_fields:
        gui_logs.append(f"Running cross-reference enrichment for fields: {', '.join(crossref_fields)}")
        df = run_crossref_enrichment(df, crossref_fields)
    
    gui_logs.append(f"Query completed with {len(df)} results.")

    log.info("Cleaning and formatting results...")
    xref_columns = [XREF_MAPPING[c][1] for c in (crossref_fields or []) if c in XREF_MAPPING and XREF_MAPPING[c][1]]
    xref_columns = [VALID_CROSS_REF_FIELDS[c] for c in VALID_CROSS_REF_FIELDS.keys() if c not in xref_columns]
    df = df.drop(columns=xref_columns, errors='ignore')

    return df, "\n".join(gui_logs)

def generate_file(df):
    tmp_path = os.path.join(tempfile.gettempdir(), "search_results.csv")
    df.to_csv(tmp_path, index=False)
    return tmp_path

def build_ui():
    with gr.Row():
        query_input = gr.Textbox(label="Query", placeholder="Make a UniProt query")
    with gr.Row():
        fields_select = gr.CheckboxGroup(
            choices=VALID_FIELDS,
            value=VALID_FIELDS[0],
            label="Fields"
        )
    with gr.Row():
        crossref_select = gr.CheckboxGroup(
            choices=list(XREF_MAPPING.keys()),
            value=list(XREF_MAPPING.keys())[0],
            label="Cross-reference Fields"
        )

    with gr.Row():
        sort_input = gr.Textbox(label="Sort", value="accession asc")
        fmt_dropdown = gr.Dropdown(choices=["json"], value="json", label="Format")
    with gr.Row():
        include_isoform_chk = gr.Checkbox(label="Include Isoforms", value=False)
        download_chk = gr.Checkbox(label="Download Raw", value=False)
    with gr.Row():
        search_btn = gr.Button("Search")
    with gr.Row():
        with gr.Column(scale=2):
            results_out = gr.Dataframe(label="Results", interactive=False, visible=False, wrap=False, show_search='filter', max_height=320)
        with gr.Column(scale=1):
            file_out = gr.File(label="Download Results", interactive=False, visible=False)
    with gr.Row():
        logs_out = gr.Textbox(label="Logs", interactive=False, visible=False)

    search_btn.click(
        fn=run_uniprot_query,
        inputs=[query_input, fields_select, crossref_select, sort_input, fmt_dropdown, include_isoform_chk, download_chk],
        outputs=[results_out, logs_out]
    ).then(
        fn=lambda: [gr.update(visible=True), gr.update(visible=True), gr.update(visible=True)],
        outputs=[results_out, logs_out, file_out]
    ).then(
        fn=generate_file,
        inputs=[results_out],
        outputs=[file_out]
    )


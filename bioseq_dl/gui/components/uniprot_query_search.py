import gradio as gr
import pandas as pd
from bioseq_dl import UniprotInterface

from bioseq_dl.core.crossref_enricher import CrossRefEnricher, EndpointSpec
from bioseq_dl.core.interfacesconfig import ConfigLoader
from bioseq_dl.constants.databases import BASE_CONFIG_DIR
from bioseq_dl.constants.uniprot import VALID_FIELDS, XREF_MAPPING
###############################
# UniProt Search UI
###############################



def run_crossref_enrichment(df, crossref_fields):
    if df.empty:
        return df
    print(f"Running crossref enrichment for fields: {crossref_fields}")
    config = ConfigLoader(config_dir=str(BASE_CONFIG_DIR) + "/uniprot_crossref")
    config.load_config("config_endpoints")

    endpoint_specs = []
    # Generate the endpoint specs based on selected crossref fields
    for key, (uniprot_field, db_name) in XREF_MAPPING.items():
        if db_name and key in crossref_fields:
            print(f"Processing crossref field: {key} -> db: {db_name}, uniprot_field: {uniprot_field}")
            endpoint_config = config.get_parameter(db_name)
            if not isinstance(endpoint_config, dict):
                continue
            #if not endpoint_config.get("enabled", False):
            #    continue

            for ep_name, ep_info in endpoint_config.get("endpoints", {}).items():
                if ep_info.get("enabled", False):
                    if "options" in ep_info:
                        for ep_option in ep_info.get("options", [None]):
                            endpoint_specs.append(
                                EndpointSpec(
                                    database=db_name,
                                    endpoint=ep_name,
                                    option=ep_option,
                                    params=ep_info.get("params", {}),
                                )
                            )
                    else:
                        endpoint_specs.append(
                            EndpointSpec(
                                database=db_name,
                                endpoint=ep_name,
                                option=None,
                                params=ep_info.get("params", {}),
                            )
                        )

    print(endpoint_specs)
    enricher = CrossRefEnricher(endpoint_specs)
    crossref_df = enricher.enrich(df, concat_results=True)
    if isinstance(crossref_df, pd.DataFrame) and not crossref_df.empty:
        print(f"Crossref enrichment resulted in {len(crossref_df)} rows")
        return crossref_df
    print("Crossref enrichment returned empty DataFrame or result is not a DataFrame")
    return df

def run_uniprot_query(query, fields, crossref_fields, sort, fmt, include_isoform, download):
    logs = []
    logs.append(f"Starting query: {query}")
    
    fields = fields or []
    xref_fields = [XREF_MAPPING[c][0] for c in (crossref_fields or []) if c in XREF_MAPPING and XREF_MAPPING[c][0]]
    logs.append(f"Using fields: {fields}")
    logs.append(f"Using crossref fields: {xref_fields}")
    logs.append(f"Sort: {sort}, Format: {fmt}, Include Isoform: {include_isoform}, Download: {download}")

    instance = UniprotInterface()

    try:
        logs.append("Submitting stream request to UniProt...")
        response = instance.submit_stream(
            query=query,
            fields=",".join(fields + xref_fields),
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
    
    if crossref_fields:
        df = run_crossref_enrichment(df, crossref_fields)

    return df, "\n".join(logs)


def build_ui():

    with gr.Blocks():
        query_input = gr.Textbox(label="Query", placeholder="Make a UniProt query")

        fields_select = gr.CheckboxGroup(
            choices=VALID_FIELDS,
            value=VALID_FIELDS,
            label="Fields"
        )
        crossref_select = gr.CheckboxGroup(
            choices=list(XREF_MAPPING.keys()),
            value=list(XREF_MAPPING.keys()),
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


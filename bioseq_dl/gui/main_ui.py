import gradio as gr
import pandas as pd
from typing import List, Tuple
from bioseq_dl.gui.components.uniprot_query_search import build_ui as build_uniprot_search_ui
from bioseq_dl.gui.components.uniprot_blast_search import build_ui as build_uniprot_blast_search_ui
from bioseq_dl.gui.components.databases import build_api_ui
from bioseq_dl.gui.interfaces import (
    ALPHAFOLD,
    BIODBNET,
    BIOGRID,
    BRENDA,
    CHEMBL,
    CHEBI,
    GENONTOLOGY,
    INTERPRO,
    KEGG,
    PATHWAYCOMMONS,
    PANTHER,
    PDB,
    PRIDE,
    PUBCHEM,
    REACTOME,
    REFSEQ,
    RHEA,
    STRINGDB
)
from bioseq_dl.gui.theme import SylphyTheme

# For each database interface there is a dictionary entry with:
# - class: the interface class
# - label: the display name
# - init: a dictionary of initialization parameters
# - methods: a dictionary of methods with their input templates

# Methods can have:
# - input_type: 'atomic' (single string) or 'composite' (multiple fields)
# - inputs: a list of input field definitions
# - multisearch: (optional) if True, allows multiple queries separated by commas
# - options: (optional) for methods with multiple options, each option has its own input template

REGISTRY = {
    "AlphaFold": ALPHAFOLD,
    "BioDBNet": BIODBNET,
    "BioGRID": BIOGRID,
    "Brenda": BRENDA,
    "ChEMBL": CHEMBL,
    "ChEBI": CHEBI,
    "GenOntology": GENONTOLOGY,
    "Interpro": INTERPRO,
    "KEGG": KEGG,
    "PathwayCommons": PATHWAYCOMMONS,
    "Panther": PANTHER,
    "ProteinDataBank": PDB,
    "Pride": PRIDE,
    "PubChem": PUBCHEM,
    "Reactome": REACTOME,
    "RefSeq": REFSEQ,
    "Rhea": RHEA,
    "StringDB": STRINGDB
}

# For every code in the component module, there should be a subtab in the main UI

# -------------------------
# Visibility helpers
# -------------------------

def api_panel_and_button_updates(selected_name: str, all_names: List[str]) -> Tuple[List[dict], List[dict]]:
    """
    Given a selected API name and a list of all API names, returns (group_updates, button_updates) so the selected API is visible and its button is primary.
    """
    group_updates  = [gr.update(visible=(n == selected_name)) for n in all_names]
    button_updates = [gr.update(variant=("primary" if n == selected_name else "secondary")) for n in all_names]
    return group_updates, button_updates

def on_api_button_click(target_name: str, all_names: List[str]) -> List[dict]:
    """
    Flattened updates for convenience: first panel updates, then button updates.
    """
    groups, buttons = api_panel_and_button_updates(target_name, all_names)
    return groups + buttons

def section_updates_and_buttons(section: str) -> Tuple[dict, dict, dict, dict]:
    """
    Returns (apis_container_u, uniprot_container_u, apis_btn_u, uniprot_btn_u).
    Highlights the active section button.
    """
    is_apis = (section == "APIs")
    return (
        gr.update(visible=is_apis),
        gr.update(visible=not is_apis),
        gr.update(variant=("primary" if is_apis else "secondary")),
        gr.update(variant=("primary" if not is_apis else "secondary")),
    )

def uniprot_panels_and_buttons(choice: str) -> Tuple[dict, dict, dict, dict]:
    """
    Returns (search_group_u, blast_group_u, search_btn_u, blast_btn_u).
    Highlights the active UniProt tool button.
    """
    is_search = (choice == "UniProt Search")
    return (
        gr.update(visible=is_search),
        gr.update(visible=not is_search),
        gr.update(variant=("primary" if is_search else "secondary")),
        gr.update(variant=("primary" if not is_search else "secondary")),
    )

def toggle_sidebar(current_visible: bool) -> dict:
    """Toggle sidebar visibility."""
    return gr.update(visible=not current_visible)

def section_updates_buttons_and_sidebar_groups(section: str) -> Tuple[dict, dict, dict, dict, dict, dict]:
    """
    Returns updates for:
      1) apis_container (right side content)
      2) uniprot_container (right side content)
      3) btn_section_apis (variant)
      4) btn_section_uniprot (variant)
      5) apis_btns_group (left sidebar group with API buttons) -> visible
      6) uniprot_btns_group (left sidebar group with UniProt buttons) -> visible
    """
    is_apis = (section == "APIs")
    apis_container_u    = gr.update(visible=is_apis)
    uniprot_container_u = gr.update(visible=not is_apis)
    apis_btn_u          = gr.update(variant=("primary" if is_apis else "secondary"))
    uniprot_btn_u       = gr.update(variant=("primary" if not is_apis else "secondary"))
    apis_btns_group_u   = gr.update(visible=is_apis)
    uniprot_btns_group_u= gr.update(visible=not is_apis)
    return (apis_container_u, uniprot_container_u,
            apis_btn_u, uniprot_btn_u,
            apis_btns_group_u, uniprot_btns_group_u)

# ----------------- main UI -----------------
CUSTOM_CSS = """
/* Visual "card" */
.card {
  border: 1px solid rgba(148,163,184,0.35);
  border-radius: 14px;
  padding: 14px;
  background: rgba(30,41,59,0.25);
  margin-bottom: 14px;
}
/* Make headings inside cards breathe */
.card h3, .card h4 {
  margin-top: 6px !important;
  margin-bottom: 10px !important;
}
/* Optional divider */
.divider {
  height: 1px;
  background: rgba(148,163,184,0.35);
  margin: 12px 0;
}
"""

def on_select_tool(tool_choice):
    # toggle visibility of tool containers
    show_uniprot = tool_choice == "UniProt"
    return (
        gr.update(visible=show_uniprot),
        gr.update(visible=show_uniprot),
    )

def build_ui():
    api_names = list(REGISTRY.keys())
    default_api = api_names[0] if api_names else None

    with gr.Blocks(theme=SylphyTheme, css=CUSTOM_CSS) as demo:
        with gr.Row():
            # --- LEFTBAR ---
            with gr.Column(scale=0, min_width=160, visible=True) as leftbar:
                gr.Markdown("## BioSeq-DL Explorer")
                # Section buttons
                btn_section_apis    = gr.Button("APIs",   variant="primary")
                btn_section_uniprot = gr.Button("UniProt", variant="secondary")

                # Group API buttons
                with gr.Column(visible=True) as apis_btns_group:
                    #gr.Markdown("**APIs**")
                    gr.Markdown(
                        "<div style='text-align:center'>"
                        f"<h2>APIs</h2>"
                        "</div>"
                    )
                    api_buttons = []
                    api_name_states = []
                    for name in api_names:
                        btn = gr.Button(name, variant=("primary" if name == default_api else "secondary"))
                        api_buttons.append(btn)
                        api_name_states.append(gr.State(name))

                # Group UniProt buttons
                with gr.Column(visible=False) as uniprot_btns_group:
                    gr.Markdown("**UniProt**")
                    btn_uniprot_search = gr.Button("UniProt Search", variant="primary")
                    btn_uniprot_blast  = gr.Button("UniProt BLAST",  variant="secondary")

                api_order_state = gr.State(api_names)

            # --- RIGHT CONTENT ---
            with gr.Column():
                with gr.Row():
                    with gr.Column(scale=0, min_width=160):
                        btn_toggle_sidebar = gr.Button("☰", scale=0)

                with gr.Row():
                    with gr.Column(visible=True) as apis_container:
                        api_groups = []
                        for name, info in REGISTRY.items():
                            with gr.Column(visible=(name == default_api)) as g:
                                build_api_ui(name, info)
                            api_groups.append(g)

                    # --- UniProt container ---
                    with gr.Column(visible=False) as uniprot_container:
                        # UniProt Search subsection
                        with gr.Column(visible=True) as uniprot_search_group:
                            build_uniprot_search_ui()
                        # UniProt BLAST subsection
                        with gr.Column(visible=False) as uniprot_blast_group:
                            build_uniprot_blast_search_ui()

        # ---- wiring ----

        # Section: Controls the visibility of the sidebar button groups
        btn_section_apis.click(
            fn=section_updates_buttons_and_sidebar_groups,
            inputs=gr.State("APIs"),
            outputs=[
                apis_container, uniprot_container,
                btn_section_apis, btn_section_uniprot,
                apis_btns_group, uniprot_btns_group
            ]
        )
        btn_section_uniprot.click(
            fn=section_updates_buttons_and_sidebar_groups,
            inputs=gr.State("UniProt"),
            outputs=[
                apis_container, uniprot_container,
                btn_section_apis, btn_section_uniprot,
                apis_btns_group, uniprot_btns_group
            ]
        )

        # APIs: panel visibility + active button highlight (unchanged)
        for btn, name_state in zip(api_buttons, api_name_states):
            btn.click(
                fn=on_api_button_click,
                inputs=[name_state, api_order_state],
                outputs=(api_groups + api_buttons)
            )

        # UniProt: subpanel visibility + active button highlight (unchanged)
        btn_uniprot_search.click(
            fn=uniprot_panels_and_buttons,
            inputs=gr.State("UniProt Search"),
            outputs=[uniprot_search_group, uniprot_blast_group, btn_uniprot_search, btn_uniprot_blast]
        )
        btn_uniprot_blast.click(
            fn=uniprot_panels_and_buttons,
            inputs=gr.State("UniProt BLAST"),
            outputs=[uniprot_search_group, uniprot_blast_group, btn_uniprot_search, btn_uniprot_blast]
        )

        # Toggle sidebar (optional, unchanged)
        sidebar_visible = gr.State(True)
        btn_toggle_sidebar.click(
            fn=toggle_sidebar,
            inputs=sidebar_visible,
            outputs=leftbar
        ).then(
            fn=lambda v: not v,
            inputs=sidebar_visible,
            outputs=sidebar_visible
        )

    return demo
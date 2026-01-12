import os, logging
import tempfile
import pandas as pd
import gradio as gr
from bioseq_dl.core.utils.blast_search import DATABASES as BLAST_DATABASES
from bioseq_dl.constants.uniprot import VALID_FIELDS, XREF_MAPPING, VALID_CROSS_REF_FIELDS
from bioseq_dl.core.utils.blast_search import (
    download_uniprot_database,
    check_blast,
    make_blast_database,
    run_blast,
    parse_blast_results
)
from bioseq_dl import UniprotInterface
from .utils import run_crossref_enrichment, load_dataframe

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

log = get_logger("bioseq_dl.gui.components.uniprot_blast_search")
# -------------------------------------------------

def run_blast_from_file(file, seq_column, database, evalue, blast_type, min_identity, min_coverage, fields, crossref_fields):
    gui_logs = []
    df, _ = load_dataframe(file)
    if df is None or df.empty:
        gui_logs.append("Could not load DataFrame or it is empty.")
        return pd.DataFrame(), "\n".join(gui_logs)
    if not database:
        gui_logs.append("No database selected.")
        return pd.DataFrame(), "\n".join(gui_logs)

    if seq_column not in df.columns:
        gui_logs.append(f"Column '{seq_column}' not found in DataFrame.")
        return pd.DataFrame(), "\n".join(gui_logs)

    sequences = df[seq_column].dropna().tolist()
    log.info(f"BLAST with {len(sequences)} sequences")
    log.debug(f"Database: {database}, E-value: {evalue}, Type: {blast_type}, Min Identity: {min_identity}")

    download_uniprot_database(database, "fasta")
    log.info(f"Database {database} downloaded.")

    blastp_path = check_blast()
    log.info(f"Using blastp at: {blastp_path}")

    make_blast_database(database, extension="fasta")
    log.info(f"BLAST database {database} created.")

    run_blast(sequences, database, blast_type=blast_type, evalue=evalue)

    results = parse_blast_results("tmp/blast_results.txt")

    if not results:
        log.warning("No BLAST results found.")
        gui_logs.append("No BLAST results found.")
        return pd.DataFrame(), "\n".join(gui_logs)


    df_blast = pd.DataFrame(results)

    df_blast = df_blast.rename(columns={"query": "id", "subject": "subject_id"})
    df_blast = df_blast.drop(columns=["id"])
    df_blast = df_blast.rename(columns={seq_column: "sequence"})
    df_blast["accession"] = df_blast["subject_id"].apply(lambda x: x.split("|")[1])
    df_blast = df_blast.drop(columns=["subject_id","alignment_length", "evalue", "bit_score"])
    log.info("BLAST completed successfully.")

    df_blast["identity"] = df_blast["identity"].astype(float)
    df_blast = df_blast[df_blast['identity'] >= min_identity]

    df_blast["coverage"] = df_blast["coverage"].astype(float)
    df_blast = df_blast[df_blast['coverage'] >= min_coverage]
    
    instance = UniprotInterface()
    results, _ = instance.download_batch(
        df_blast,
        "accession", 
        False, 
        'UniProtKB_AC-ID', 
        'UniProtKB', 
        5000
    )

    with open("test" + ".json", 'w') as f:
        for result in results:
            f.write(str(result) + '\n')

    # Probably this can be optimized
    xref = [XREF_MAPPING[c][1] for c in crossref_fields if c in XREF_MAPPING if XREF_MAPPING[c][1]]
    xref = [VALID_CROSS_REF_FIELDS[x] for x in xref if x in VALID_CROSS_REF_FIELDS]
    export_df, _ = instance.parse(results, fields + xref, format="dataframe")

    if crossref_fields:
        gui_logs.append(f"Running cross-reference enrichment for fields: {', '.join(crossref_fields)}")
        export_df = run_crossref_enrichment(export_df, crossref_fields)

    gui_logs.append(f"BLAST completed with {len(export_df)} results after filtering by {min_identity}% identity.")
    return export_df, "\n".join(gui_logs), export_df

def generate_file(df):
    tmp_path = os.path.join(tempfile.gettempdir(), "search_results.csv")
    df.to_csv(tmp_path, index=False)
    return tmp_path

def build_ui():
    with gr.Row():
        file_input = gr.File(label="Upload DataFrame (CSV/Excel)", file_types=[".csv", ".xlsx"])
    with gr.Row():
        seq_column_dropdown = gr.Dropdown(label="Sequence Column", choices=[], interactive=True)

        def update_columns(file):
            df, cols = load_dataframe(file)
            if df is None or not cols:
                return gr.Dropdown(choices=[], value=None)
            return gr.Dropdown(choices=cols, value=cols[0])
        file_input.change(update_columns, inputs=file_input, outputs=seq_column_dropdown)
    
        db_dropdown = gr.Dropdown(
            label="Database",
            choices=list(BLAST_DATABASES.keys())
        )
    with gr.Row():
        evalue_input = gr.Number(label="E-value", value=0.001)
        blast_type_dropdown = gr.Dropdown(
            label="BLAST Type",
            choices=["blastp", "blastn", "blastx"],
            value="blastp"
        )
        min_identity_input = gr.Number(label="Minimum Identity (%)", value=90.0)
        coverage_input = gr.Number(label="Minimum Coverage (%)", value=0.0)
    with gr.Row():
        fields_select = gr.CheckboxGroup(
            choices=VALID_FIELDS,
            value=[VALID_FIELDS[0]],
            label="Fields"
        )
    with gr.Row():
        crossref_select = gr.CheckboxGroup(
            choices=list(XREF_MAPPING.keys()),
            value=[list(XREF_MAPPING.keys())[0]],
            label="Cross-reference Fields"
        )
    with gr.Row():
        run_btn = gr.Button("Run BLAST")
    with gr.Row():
        with gr.Column(scale=2):
            results_out = gr.Dataframe(label="BLAST Results", interactive=False, visible=False, wrap=False, show_search='filter')
        with gr.Column(scale=1):
            file_out = gr.File(label="Download Results", visible=False)
    with gr.Row():
        logs_out = gr.Textbox(label="Logs", interactive=False, visible=False)

    run_btn.click(
        fn=run_blast_from_file,
        inputs=[file_input, seq_column_dropdown, db_dropdown, evalue_input, blast_type_dropdown, min_identity_input, coverage_input, fields_select, crossref_select],
        outputs=[results_out, logs_out]
    ).then(
        fn=lambda: [gr.update(visible=True), gr.update(visible=True), gr.update(visible=True)],
        outputs=[results_out, logs_out, file_out]
    ).then(
        fn=generate_file,
        inputs=[results_out],
        outputs=[file_out]
    )
import os
import tempfile
import pandas as pd
import gradio as gr
from bioseq_dl.cli.blast_alignment import databases as BLAST_DATABASES
from bioseq_dl.cli.blast_alignment import (
    download_uniprot_database,
    check_blast,
    make_blast_database,
    run_blast,
    parse_blast_results
)
from bioseq_dl import UniprotInterface


def load_dataframe(file):
    """Carga un archivo CSV o Excel en un DataFrame."""
    if file is None:
        return None, []
    try:
        if file.name.endswith(".csv"):
            df = pd.read_csv(file.name)
        elif file.name.endswith(".xlsx"):
            df = pd.read_excel(file.name)
        else:
            return None, []
        return df, list(df.columns)
    except Exception as e:
        return None, [f"Error: {e}"]

def run_blast_from_file(file, seq_column, database, evalue, blast_type, min_identity):
    logs = []
    df, _ = load_dataframe(file)
    if df is None or df.empty:
        logs.append("Could not load DataFrame or it is empty.")
        return pd.DataFrame(), "\n".join(logs)

    if seq_column not in df.columns:
        logs.append(f"Column '{seq_column}' not found in DataFrame.")
        return pd.DataFrame(), "\n".join(logs)

    sequences = df[seq_column].dropna().tolist()
    logs.append(f"BLAST with {len(sequences)} sequences")
    logs.append(f"Database: {database}, E-value: {evalue}, Type: {blast_type}, Min Identity: {min_identity}")

    download_uniprot_database(database, "fasta")
    logs.append(f"Database {database} downloaded.")

    blastp_path = check_blast()
    logs.append(f"Using blastp at: {blastp_path}")

    make_blast_database(database, extension="fasta")
    logs.append(f"BLAST database {database} created.")

    run_blast(sequences, database, blast_type=blast_type, evalue=evalue)

    results = parse_blast_results("tmp/blast_results.txt")

    if not results:
        logs.append("No BLAST results found.")
        return pd.DataFrame(), "\n".join(logs)


    df_blast = pd.DataFrame(results)

    df_blast = df_blast.rename(columns={"query": "id", "subject": "subject_id"})
    df_blast = df_blast.drop(columns=["id"])
    df_blast = df_blast.rename(columns={seq_column: "sequence"})
    df_blast["accession"] = df_blast["subject_id"].apply(lambda x: x.split("|")[1])
    df_blast = df_blast.drop(columns=["subject_id","alignment_length", "evalue", "bit_score"])
    logs.append("BLAST completed successfully.")

    df_blast["identity"] = df_blast["identity"].astype(float)
    df_blast = df_blast[df_blast['identity'] >= min_identity]
    
    instance = UniprotInterface()
    results = instance.download_batch(
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
    export_df = instance.parse_results(results, None)

    return export_df, "\n".join(logs)

def save_results(df):
    if df is None or df.empty:
        return None
    tmp_path = os.path.join(tempfile.gettempdir(), "blast_results.csv")
    df.to_csv(tmp_path, index=False)
    return tmp_path

def build_ui():
     with gr.Blocks():
        file_input = gr.File(label="Upload DataFrame (CSV/Excel)", file_types=[".csv", ".xlsx"])

        seq_column_dropdown = gr.Dropdown(label="Sequence Column", choices=[], interactive=True)

        def update_columns(file):
            df, cols = load_dataframe(file)
            if df is None or not cols:
                return gr.Dropdown(choices=[], value=None)
            return gr.Dropdown(choices=cols, value=cols[0])

        file_input.change(update_columns, inputs=file_input, outputs=seq_column_dropdown)

        db_dropdown = gr.Dropdown(
            label="Database",
            choices=list(BLAST_DATABASES.keys()),
            value="uniprot"
        )
        evalue_input = gr.Number(label="E-value", value=0.001)
        blast_type_dropdown = gr.Dropdown(
            label="BLAST Type",
            choices=["blastp", "blastn", "blastx"],
            value="blastp"
        )
        min_identity_input = gr.Number(label="Minimum Identity (%)", value=90.0)

        run_btn = gr.Button("Run BLAST")
        save_btn = gr.Button("Save Results", interactive=False)
        file_out = gr.File(label="Download Results", visible=False)
        results_out = gr.Dataframe(label="BLAST Results", interactive=False)
        logs_out = gr.Textbox(label="Logs", interactive=False)

        

        run_btn.click(
            fn=run_blast_from_file,
            inputs=[file_input, seq_column_dropdown, db_dropdown, evalue_input, blast_type_dropdown, min_identity_input],
            outputs=[results_out, logs_out]
        ).then(
            lambda: gr.update(interactive=True),
            None,
            save_btn
        )

        # Guardar resultados en CSV
        save_btn.click(
            fn=save_results,
            inputs=results_out,
            outputs=file_out
        ).then(
            lambda: gr.update(visible=True),
            None,
            file_out
        )
import typer
from bioseq_dl.gui.main_ui import build_ui

app = typer.Typer(name="gui", help="Launch GUI interface for BioSeqDownloader")


@app.command("run")
def run(
    host: str = "127.0.0.1",
    # TODO Cambiar a 7860
    port: int = 7560,
    share: bool = False
):
    """
    Launch the Gradio GUI.
    """
    demo = build_ui()
    demo.launch(server_name=host, server_port=port, share=share)


if __name__ == "__main__":
    app()
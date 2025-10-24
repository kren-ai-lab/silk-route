import typer
import logging
from bioseq_dl.gui.main_ui import build_ui
from bioseq_dl.logging.logger import configure_logging

app = typer.Typer(name="gui", help="Launch GUI interface for BioSeqDownloader")

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)
# -------------------------------------------------

LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

@app.command("run")
def run(
    host: str = typer.Option(
    "127.0.0.1", help="Host to run the server on."
    ),
    port: int = typer.Option(
        7860, help="Port to run the server on."
    ),
    share: bool = typer.Option(
        False, help="Whether to share the interface publicly."
    ),
    log_level: str = typer.Option(
        "info", "--log", "-l", help="Logging level (debug, info, warning, error, critical)."
    )
):
    """
    Launch the Gradio GUI.
    """
    logging_level = LOG_LEVELS.get(log_level.lower(), logging.INFO)
    configure_logging(level=logging_level)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    log = get_logger("bioseq_dl.interfaces.gui")
    log.info(f"Starting GUI on {host}:{port} with log_level={log_level}")

    demo = build_ui()
    demo.launch(server_name=host, server_port=port, share=share)


if __name__ == "__main__":
    app()
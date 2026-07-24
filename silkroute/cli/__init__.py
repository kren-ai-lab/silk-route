"""CLI entry points for SilkRoute."""

import typer

app = typer.Typer(name="silkroute", add_completion=False, help="Description")

if __name__ == "__main__":
    app()

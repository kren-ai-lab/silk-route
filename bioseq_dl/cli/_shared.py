"""Shared helpers for CLI commands.

``BaseAPIInterface.fetch_single`` / ``fetch_batch`` return a ``(data, metadata)``
tuple. CLI commands historically did ``result = interface.fetch_single(...)``
followed by ``result.to_csv(...)``, which raised ``AttributeError`` because
``result`` was the tuple, not the data. ``save_or_print`` unpacks the tuple and
either writes the data to ``output`` or prints a short preview.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import typer


def unwrap(result: Any) -> Any:
    """Return just the data from a ``(data, metadata)`` fetch result.

    ``fetch_single`` / ``fetch_batch`` return a 2-tuple whose second element is a
    metadata dict. Anything that is not such a tuple is returned unchanged.
    """
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
        return result[0]
    return result


def save_or_print(result: Any, output: str | None = None, *, preview_rows: int = 5) -> None:
    """Unpack a fetch result and either save it to ``output`` or print a preview.

    Args:
        result: Raw return value of ``fetch_single`` / ``fetch_batch`` (a
            ``(data, metadata)`` tuple) or already-unwrapped data.
        output: Path to save to. If ``None``, a preview is printed instead.
        preview_rows: Number of rows to show when previewing a DataFrame.

    """
    data = unwrap(result)

    if isinstance(data, pd.DataFrame):
        if output:
            data.to_csv(output, index=False)
            typer.echo(f"Results saved to {output}")
        else:
            typer.echo(data.head(preview_rows))
        return

    if output:
        with open(output, "w") as fh:
            if isinstance(data, bytes):
                fh.write(data.decode("utf-8"))
            elif isinstance(data, (dict, list)):
                json.dump(data, fh, indent=2, default=str)
            else:
                fh.write(str(data))
        typer.echo(f"Results saved to {output}")
    else:
        typer.echo(data)

"""Typed model for the fetch metadata produced by ``BaseAPIInterface``.

``fetch_single`` / ``fetch_batch`` build a :class:`FetchMetadata` internally and
return ``meta.to_dict()`` so downstream consumers (CLI sidecars, crossref
enrichment, workflows) keep receiving a plain JSON-ready dict. Centralizing the
schema here means the field set is declared once instead of being scattered as
string keys across the fetch return paths.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _empty_tool() -> dict[str, str]:
    return {"name": "", "version": ""}


@dataclass
class FetchMetadata:
    """Provenance and result-shape metadata for a single fetch call.

    Field order matches the serialized JSON layout. ``started_at`` / ``finished_at``
    are ISO-8601 UTC timestamps; ``tool`` is the ``{name, version}`` provenance
    block; ``data_info`` is the per-result schema block built by
    ``BaseAPIInterface._build_data_info``.
    """

    tool: dict[str, str] = field(default_factory=_empty_tool)
    started_at: str = ""
    cached_ids: list[Any] = field(default_factory=list)
    cached_subqueries: list[Any] = field(default_factory=list)
    fetched_ids: list[Any] = field(default_factory=list)
    fetched_subqueries: list[Any] = field(default_factory=list)
    failed_ids: list[Any] = field(default_factory=list)
    fetched_length: int = 0
    data_info: dict[str, Any] = field(default_factory=dict)
    finished_at: str = ""
    api_name: str = ""
    method: str = ""
    option: Any = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain, JSON-ready dict (deep-copied nested values)."""
        return asdict(self)

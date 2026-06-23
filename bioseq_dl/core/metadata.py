"""Typed model for the fetch metadata produced by ``BaseAPIInterface``.

``fetch_single`` / ``fetch_batch`` build a :class:`FetchMetadata` internally and
return ``meta.to_dict()`` so downstream consumers (CLI sidecars, crossref
enrichment, workflows) keep receiving a plain JSON-ready dict. Centralizing the
schema here means the field set is declared once instead of being scattered as
string keys across the fetch return paths.

Serialized shape::

    {
      "tool":       {"name": "bioseq_dl", "version": "0.1.0"},
      "started_at": "<iso>", "finished_at": "<iso>",
      "request":    {"api_name": "ChEMBL", "method": "molecule", "option": null},
      "cached":     {"ids": [...], "subqueries": [...], "length": N},
      "fetched":    {"ids": [...], "subqueries": [...], "length": N},
      "failed":     {"ids": [...], "subqueries": [...], "length": N},
      "data_info":  {...}
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolInfo:
    """Library provenance: which build produced the dataset."""

    name: str = ""
    version: str = ""

    def to_dict(self) -> dict[str, str]:
        """Serialize to ``{name, version}``."""
        return {"name": self.name, "version": self.version}

    @classmethod
    def from_dict(cls, data: dict | None) -> ToolInfo:
        """Reconstruct from a serialized ``{name, version}`` dict."""
        data = data or {}
        return cls(name=data.get("name", ""), version=data.get("version", ""))


@dataclass
class RequestInfo:
    """What was requested: database, endpoint, and the method variant/profile."""

    api_name: str = ""
    method: str = ""
    option: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to ``{api_name, method, option}``."""
        return {"api_name": self.api_name, "method": self.method, "option": self.option}

    @classmethod
    def from_dict(cls, data: dict | None) -> RequestInfo:
        """Reconstruct from a serialized ``{api_name, method, option}`` dict."""
        data = data or {}
        return cls(
            api_name=data.get("api_name", ""),
            method=data.get("method", ""),
            option=data.get("option"),
        )


@dataclass
class IdBlock:
    """A bucket of subqueries that shared a fate (cached / fetched / failed).

    ``ids`` and ``subqueries`` are parallel: ``ids[i]`` is the identifier of
    ``subqueries[i]``. ``length`` (serialized only) is the bucket size.
    """

    ids: list[Any] = field(default_factory=list)
    subqueries: list[Any] = field(default_factory=list)

    def add(self, identifier: Any, subquery: Any) -> None:
        """Append one (identifier, subquery) pair to the bucket."""
        self.ids.append(identifier)
        self.subqueries.append(subquery)

    def merged_with(self, other: IdBlock) -> IdBlock:
        """Return a new bucket concatenating this one with ``other``."""
        return IdBlock(ids=self.ids + other.ids, subqueries=self.subqueries + other.subqueries)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to ``{ids, subqueries, length}`` (``length`` = bucket size)."""
        return {"ids": self.ids, "subqueries": self.subqueries, "length": len(self.ids)}

    @classmethod
    def from_dict(cls, data: dict | None) -> IdBlock:
        """Reconstruct from a serialized ``{ids, subqueries}`` dict (``length`` ignored)."""
        data = data or {}
        return cls(ids=list(data.get("ids", [])), subqueries=list(data.get("subqueries", [])))


def _widest(a: str, b: str, *, keep_min: bool) -> str:
    """Min/max of two ISO-8601 timestamps, ignoring empty strings."""
    if not a:
        return b
    if not b:
        return a
    return min(a, b) if keep_min else max(a, b)


def _merge_columns(cols_a: list[dict], cols_b: list[dict]) -> list[dict]:
    """Merge per-column ``data_info`` entries, summing ``n_missing`` by column name."""
    merged = [dict(c) for c in cols_a]
    by_name = {c.get("name"): c for c in merged}
    for cb in cols_b:
        name = cb.get("name")
        if name in by_name:
            by_name[name]["n_missing"] = by_name[name].get("n_missing", 0) + cb.get("n_missing", 0)
        else:
            merged.append(dict(cb))
    return merged


def _merge_data_info(a: dict, b: dict) -> dict:
    """Merge two ``data_info`` blocks (sum ``total_entries`` and per-column ``n_missing``)."""
    if not a:
        return dict(b or {})
    if not b:
        return dict(a)
    return {
        "total_entries": a.get("total_entries", 0) + b.get("total_entries", 0),
        "data_type": a.get("data_type") or b.get("data_type"),
        "columns": _merge_columns(a.get("columns", []), b.get("columns", [])),
    }


@dataclass
class FetchMetadata:
    """Provenance and result-shape metadata for a single fetch call."""

    tool: ToolInfo = field(default_factory=ToolInfo)
    started_at: str = ""
    finished_at: str = ""
    request: RequestInfo = field(default_factory=RequestInfo)
    cached: IdBlock = field(default_factory=IdBlock)
    fetched: IdBlock = field(default_factory=IdBlock)
    failed: IdBlock = field(default_factory=IdBlock)
    data_info: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain, JSON-ready dict."""
        return {
            "tool": self.tool.to_dict(),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "request": self.request.to_dict(),
            "cached": self.cached.to_dict(),
            "fetched": self.fetched.to_dict(),
            "failed": self.failed.to_dict(),
            "data_info": self.data_info,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> FetchMetadata:
        """Reconstruct from a serialized dict (round-trips ``to_dict``)."""
        data = data or {}
        return cls(
            tool=ToolInfo.from_dict(data.get("tool")),
            started_at=data.get("started_at", ""),
            finished_at=data.get("finished_at", ""),
            request=RequestInfo.from_dict(data.get("request")),
            cached=IdBlock.from_dict(data.get("cached")),
            fetched=IdBlock.from_dict(data.get("fetched")),
            failed=IdBlock.from_dict(data.get("failed")),
            data_info=dict(data.get("data_info") or {}),
        )

    def merge(self, other: FetchMetadata) -> FetchMetadata:
        """Accumulate a same-source ``other`` into a new instance.

        Buckets concatenate, ``data_info`` counts sum, and the time window widens
        (earliest ``started_at`` → latest ``finished_at``). ``tool`` / ``request``
        come from whichever side is populated (they are expected to match across
        same-source fetches).
        """
        return FetchMetadata(
            tool=self.tool if self.tool != ToolInfo() else other.tool,
            started_at=_widest(self.started_at, other.started_at, keep_min=True),
            finished_at=_widest(self.finished_at, other.finished_at, keep_min=False),
            request=self.request if self.request != RequestInfo() else other.request,
            cached=self.cached.merged_with(other.cached),
            fetched=self.fetched.merged_with(other.fetched),
            failed=self.failed.merged_with(other.failed),
            data_info=_merge_data_info(self.data_info, other.data_info),
        )

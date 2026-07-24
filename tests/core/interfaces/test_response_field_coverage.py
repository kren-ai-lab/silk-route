"""Structural drift detector: do API responses still carry the fields we consume?

The library extracts fields from API responses via per-database ``fields.yml``
maps (dot-path → output name) and, for UniProt, the in-code ``field_map_base``.
These maps are the exact contract between the integration and each upstream API.

This test resolves every consumed source-path against the frozen fixture
(``tests/fixtures/<api>/<case>.json``) and compares the set of paths that
*currently resolve* against a committed baseline
(``tests/fixtures/_field_coverage_baseline.json``).

Why a baseline instead of "every consumed field must resolve":
    Field maps are often supersets — the union of every field an endpoint can
    return across record types/options. Any single captured response exercises
    only a subset (e.g. PathwayCommons ``fetch`` declares 34 fields; one entity
    returns 3). Requiring all of them would always fail. Instead we snapshot
    what resolves today and fail only when that set SHRINKS — i.e. a field the
    API used to return for this fixture disappeared (rename/removal/restructure).
    That is the real drift signal, with no false positives from optional fields.

When an API legitimately changes and you re-capture a fixture, regenerate the
baseline:

    REGEN_FIELD_BASELINE=1 uv run pytest tests/core/interfaces/test_response_field_coverage.py

and review the diff before committing.

The coverage gap (consumed fields NOT exercised by any fixture) is the backlog
for enriching fixtures, not an error. ``test_coverage_report`` prints it but is
skipped by default; opt in with ``SHOW_FIELD_COVERAGE=1`` to see the summary.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from silkroute.core.interfacesconfig import load_packaged_config
from tests._helpers import load_fixture

BASELINE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "_field_coverage_baseline.json"

_MISSING = object()


def _resolve(data: Any, path: str, sep: str = ".") -> Any:
    """Resolve a dot-path, returning ``_MISSING`` for an ABSENT key.

    Mirrors ``get_nested`` traversal (dict descent, list fan-out) but
    distinguishes a missing key from a present-but-``None`` value — which
    ``get_nested`` cannot. Over a list, a path resolves if it resolves in any
    item (a field absent from some records but present in others still counts
    as carried by the API).
    """
    if not path:
        return data
    if isinstance(data, list):
        return True if any(_resolve(i, path, sep) is not _MISSING for i in data) else _MISSING
    if not isinstance(data, dict):
        return _MISSING
    head, _, rest = path.partition(sep)
    if head not in data:
        return _MISSING
    return _resolve(data[head], rest, sep) if rest else data[head]


def _present(data: Any, path: str) -> bool:
    return _resolve(data, path) is not _MISSING


def _values(d: dict) -> list:
    return list(d.values())


# Each spec ties a fixture to the field map the integration applies to it.
#   key      : stable id (also the baseline key)
#   api/case : locate tests/fixtures/<api>/<case>.json
#   config   : silkroute/config/<config>/fields.yml subdir (may differ from api:
#              genontology->go, stringdb->string)
#   option   : top-level key in fields.yml, or a tuple for nested option dicts
#              (pride/pubchem). None => UniProt's in-code field_map_base.
#   records  : fixture -> the record (or list of records) the field map targets;
#              encodes each interface's envelope unwrapping (paginated lists,
#              dict-of-records, JSON-LD @graph, nested search results, ...).
_Spec = dict[str, Any]

SPECS: list[_Spec] = [
    {
        "key": "alphafold/prediction",
        "api": "alphafold",
        "case": "prediction",
        "config": "alphafold",
        "option": "prediction",
        "records": lambda f: f,
    },
    {
        "key": "biodbnet/getpathways",
        "api": "biodbnet",
        "case": "getpathways",
        "config": "biodbnet",
        "option": "getpathways",
        "records": lambda f: f,
    },
    {
        "key": "biogrid/interactions",
        "api": "biogrid",
        "case": "interactions",
        "config": "biogrid",
        "option": "interactions",
        "records": _values,
    },
    {
        "key": "brenda/getKmValue",
        "api": "brenda",
        "case": "getKmValue",
        "config": "brenda",
        "option": "getKmValue",
        "records": lambda f: f,
    },
    {
        "key": "chebi/compound",
        "api": "chebi",
        "case": "compound",
        "config": "chebi",
        "option": "compound",
        "records": lambda f: f,
    },
    {
        "key": "chembl/activity",
        "api": "chembl",
        "case": "activity",
        "config": "chembl",
        "option": "activity",
        "records": lambda f: f["activities"],
    },
    {
        "key": "genontology/term",
        "api": "genontology",
        "case": "term",
        "config": "go",
        "option": "ontology-term",
        "records": lambda f: f,
    },
    {
        "key": "interpro/entry",
        "api": "interpro",
        "case": "entry",
        "config": "interpro",
        "option": "entry",
        "records": lambda f: f,
    },
    {
        "key": "panther/geneinfo",
        "api": "panther",
        "case": "geneinfo",
        "config": "panther",
        "option": "geneinfo",
        "records": lambda f: f["search"]["mapped_genes"]["gene"],
    },
    {
        "key": "pathwaycommons/fetch",
        "api": "pathwaycommons",
        "case": "fetch",
        "config": "pathwaycommons",
        "option": "fetch",
        "records": lambda f: f["@graph"],
    },
    {
        "key": "pdb/entry",
        "api": "pdb",
        "case": "entry",
        "config": "pdb",
        "option": "entry",
        "records": lambda f: f,
    },
    {
        "key": "pride/project",
        "api": "pride",
        "case": "project",
        "config": "pride",
        "option": ("projects", "default"),
        "records": lambda f: f,
    },
    {
        "key": "pubchem/pug_view_compound",
        "api": "pubchem",
        "case": "pug_view_compound",
        "config": "pubchem",
        "option": ("pug_view/compound", "default"),
        "records": lambda f: f,
    },
    {
        "key": "reactome/discover",
        "api": "reactome",
        "case": "discover",
        "config": "reactome",
        "option": "data/discover",
        "records": lambda f: f,
    },
    {
        "key": "refseq/protein",
        "api": "refseq",
        "case": "protein",
        "config": "refseq",
        "option": "protein",
        "records": lambda f: f,
    },
    {
        "key": "stringdb/get_string_ids",
        "api": "stringdb",
        "case": "get_string_ids",
        "config": "string",
        "option": "get_string_ids",
        "records": lambda f: f,
    },
    # UniProt: no fields.yml; the contract is the in-code field_map_base, and the
    # idmapping envelope nests each entry under ``to``.
    {
        "key": "uniprot/idmapping_results",
        "api": "uniprot",
        "case": "idmapping_results",
        "config": None,
        "option": None,
        "records": lambda f: [r["to"] for r in f["results"]],
    },
]

# Text-format / empty-config fixtures intentionally excluded from path resolution:
#   kegg, sabiork  -> responses are flat text parsed by the interface, not JSON
#                     whose keys match fields.yml source paths.
#   rhea, sabiork  -> fields.yml is empty (no field contract to check).
# Their structure is covered by the interfaces' own parse tests.
EXCLUDED = {"kegg", "sabiork", "rhea"}


def _field_map(spec: _Spec) -> dict[str, str]:
    """Return {output_name: source_path} for a spec."""
    option = spec["option"]
    if option is None:  # UniProt field_map_base: {out: (path, extractor)}
        from silkroute.core.interfaces.uniprot import UniprotInterface

        iface = UniprotInterface(use_config=False)
        return {out: spec_path for out, (spec_path, _fn) in iface.field_map_base.items()}

    cfg = load_packaged_config(spec["config"], "fields.yml")
    node: Any = cfg
    keys = option if isinstance(option, tuple) else (option,)
    for k in keys:
        node = node[k]
    return node


def _resolved_paths(spec: _Spec) -> list[str]:
    """Output names whose source path resolves in this fixture (sorted)."""
    fixture = load_fixture(spec["api"], spec["case"])
    records = spec["records"](fixture)
    fmap = _field_map(spec)
    return sorted(out for out, src in fmap.items() if _present(records, src))


def _build_baseline() -> dict[str, list[str]]:
    return {spec["key"]: _resolved_paths(spec) for spec in SPECS}


# --- regeneration shim: run once with REGEN_FIELD_BASELINE=1 to refresh ------
if os.environ.get("REGEN_FIELD_BASELINE"):
    BASELINE_PATH.write_text(json.dumps(_build_baseline(), indent=2, sort_keys=True) + "\n")


def _load_baseline() -> dict[str, list[str]]:
    if not BASELINE_PATH.exists():
        pytest.skip(f"baseline missing; run REGEN_FIELD_BASELINE=1 to create {BASELINE_PATH.name}")
    return json.loads(BASELINE_PATH.read_text())


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s["key"])
def test_no_consumed_field_dropped(spec: _Spec) -> None:
    """Every field that resolved at baseline must still resolve.

    A failure means the frozen API response no longer carries a field the
    integration extracts — an upstream rename/removal/restructure (drift), or a
    fixture re-captured against a changed API. Investigate before regenerating.
    """
    baseline = _load_baseline()
    assert spec["key"] in baseline, (
        f"{spec['key']} not in baseline; run REGEN_FIELD_BASELINE=1 and review the diff"
    )
    expected = set(baseline[spec["key"]])
    current = set(_resolved_paths(spec))
    dropped = sorted(expected - current)
    assert not dropped, (
        f"{spec['key']}: consumed fields no longer present in the API response (possible drift): {dropped}"
    )


def test_coverage_report(capsys: pytest.CaptureFixture[str]) -> None:
    """Opt-in report: consumed fields NOT exercised by any fixture.

    This is the fixture-enrichment backlog — fields the integration reads but
    that no captured response demonstrates, so drift in them would go unnoticed.
    It never fails; it is pure diagnostics, so it stays quiet on normal runs and
    only prints when explicitly requested:

        SHOW_FIELD_COVERAGE=1 uv run pytest tests/core/interfaces/test_response_field_coverage.py
    """
    if not os.environ.get("SHOW_FIELD_COVERAGE"):
        pytest.skip("set SHOW_FIELD_COVERAGE=1 to print the consumed-field coverage report")
    lines = ["", "Consumed-field coverage (exercised / declared):"]
    for spec in SPECS:
        fmap = _field_map(spec)
        resolved = set(_resolved_paths(spec))
        gap = sorted(set(fmap) - resolved)
        lines.append(f"  {spec['key']:<34} {len(resolved):>3}/{len(fmap):<3}")
        if gap:
            lines.append(f"      not exercised: {gap}")
    with capsys.disabled():
        print("\n".join(lines))  # noqa: T201 -- intentional human-facing test report

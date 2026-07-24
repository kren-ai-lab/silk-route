"""Env-gated capture script: (re)generate ``tests/fixtures/<api>/<case>.json``.

This script is **never** run by the test suite or CI. It exists so the frozen
fixtures replayed by the offline tests can be regenerated from the real APIs.

Usage::

    SILKROUTE_CAPTURE=1 uv run python -m tests._capture.capture
    SILKROUTE_CAPTURE=1 uv run python -m tests._capture.capture rhea chebi

Optional positional args restrict capture to the named APIs.

Captures drive the **real interface** so the request (URL, params, method, body)
is exactly what production builds, and record the **raw HTTP body** the interface
receives -- i.e. exactly what the offline tests register with ``responses``.
Text APIs (kegg, sabiork) are stored as a JSON string.

Credentialed / non-HTTP APIs (biogrid, brenda, refseq) are only captured when
the relevant env vars are set; otherwise they are skipped with a log line.
UniProt has no credentials but runs a multi-step id-mapping flow.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from tests._helpers import FIXTURES_DIR

TIMEOUT = 30


def _save(api: str, case: str, payload: object) -> None:
    out = FIXTURES_DIR / api / f"{case}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        json.dump(payload, f, indent=2)
    print(f"wrote {out.relative_to(FIXTURES_DIR.parent.parent)}")  # noqa: T201


def _capture_raw(api, case, interface, *, as_text=False, **fetch_kwargs):
    """Drive ``interface.fetch`` and save the raw body of its first HTTP response."""
    captured: dict = {}
    original_send = interface.session.send

    def spy(request, **kwargs):
        response = original_send(request, **kwargs)
        if "body" not in captured:
            captured["body"] = response.text if as_text else response.json()
        return response

    interface.session.send = spy
    interface.fetch(**fetch_kwargs)
    interface.session.send = original_send

    if "body" not in captured:
        msg = f"no response captured for {api}/{case}"
        raise RuntimeError(msg)
    _save(api, case, captured["body"])


def _tmp_kwargs() -> dict:
    return {
        "cache_dir": tempfile.mkdtemp(prefix="silkroute-capture-"),
        "config_dir": tempfile.mkdtemp(prefix="silkroute-capture-cfg-"),
        "min_wait": 0,
        "max_wait": 0,
        "use_config": False,
    }


# --- Plain HTTP APIs (no credentials) -------------------------------------


def capture_rhea() -> None:
    from silkroute.core.interfaces.rhea import RheaInterface

    _capture_raw(
        "rhea", "reaction", RheaInterface(**_tmp_kwargs()), query="RHEA:10000", method="rhea", limit=1
    )


def capture_chebi() -> None:
    from silkroute.core.interfaces.chebi import ChEBIInterface

    _capture_raw("chebi", "compound", ChEBIInterface(**_tmp_kwargs()), query="15377", method="compound")


def capture_alphafold() -> None:
    from silkroute.core.interfaces.alphafold import AlphafoldInterface

    cfg = tempfile.mkdtemp(prefix="silkroute-capture-cfg-")
    with (Path(cfg) / "init.yml").open("w") as f:
        f.write(f"download_folder: {cfg}\n")
    iface = AlphafoldInterface(
        structures=None,
        cache_dir=tempfile.mkdtemp(prefix="silkroute-capture-"),
        config_dir=cfg,
        min_wait=0,
        max_wait=0,
        use_config=False,
    )
    _capture_raw("alphafold", "prediction", iface, query="P12345", method="prediction")


def capture_genontology() -> None:
    from silkroute.core.interfaces.genontology import GenOntologyInterface

    _capture_raw(
        "genontology",
        "term",
        GenOntologyInterface(**_tmp_kwargs()),
        query="GO:0008150",
        method="ontology-term",
    )


def capture_pride() -> None:
    from silkroute.core.interfaces.pride import PrideInterface

    _capture_raw("pride", "project", PrideInterface(**_tmp_kwargs()), query="PXD000001", method="projects")


def capture_pdb() -> None:
    from silkroute.core.interfaces.proteindatabank import PDBInterface

    iface = PDBInterface(download_structures=False, **_tmp_kwargs())
    _capture_raw("pdb", "entry", iface, query="4HHB", method="entry")


def capture_stringdb() -> None:
    from silkroute.core.interfaces.stringdb import StringInterface

    _capture_raw(
        "stringdb",
        "get_string_ids",
        StringInterface(**_tmp_kwargs()),
        query={"identifiers": "TP53", "species": 9606},
        method="get_string_ids",
    )


def capture_interpro() -> None:
    from silkroute.core.interfaces.interpro import InterproInterface

    _capture_raw(
        "interpro",
        "entry",
        InterproInterface(**_tmp_kwargs()),
        query={"db": "InterPro", "id": "IPR000001"},
        method="entry",
    )


def capture_reactome() -> None:
    from silkroute.core.interfaces.reactome import ReactomeInterface

    _capture_raw(
        "reactome",
        "discover",
        ReactomeInterface(**_tmp_kwargs()),
        query="R-HSA-109581",
        method="data-discover",
    )


def capture_chembl() -> None:
    from silkroute.core.interfaces.chembl import ChEMBLInterface

    _capture_raw(
        "chembl",
        "activity",
        ChEMBLInterface(**_tmp_kwargs()),
        query={"target_chembl_id": "CHEMBL279"},
        method="activity",
        limit=1,
    )


def capture_pubchem() -> None:
    from silkroute.core.interfaces.pubchem import PubChemInterface

    _capture_raw(
        "pubchem",
        "pug_view_compound",
        PubChemInterface(**_tmp_kwargs()),
        query={"cid": "444444"},
        method="pug_view/compound",
        option="default",
    )


def capture_kegg() -> None:
    from silkroute.core.interfaces.kegg import KEGGInterface

    _capture_raw(
        "kegg",
        "get",
        KEGGInterface(**_tmp_kwargs()),
        as_text=True,
        query={"entries": "hsa:10458"},
        method="get",
    )


def capture_panther() -> None:
    from silkroute.core.interfaces.panther import PantherInterface

    _capture_raw(
        "panther",
        "geneinfo",
        PantherInterface(**_tmp_kwargs()),
        query={"geneInputList": "TP53", "organism": "9606"},
        method="geneinfo",
    )


def capture_pathwaycommons() -> None:
    from silkroute.core.interfaces.pathwaycommons import PathwayCommonsInterface

    _capture_raw(
        "pathwaycommons",
        "fetch",
        PathwayCommonsInterface(**_tmp_kwargs()),
        query={"uri": ["uniprot:P04637"]},
        method="fetch",
    )


def capture_biodbnet() -> None:
    from silkroute.core.interfaces.biodbnet import BioDBNetInterface

    _capture_raw(
        "biodbnet",
        "getpathways",
        BioDBNetInterface(**_tmp_kwargs()),
        query={"pathways": "1", "taxonId": "511145"},
        method="getpathways",
    )


def capture_sabiork() -> None:
    from silkroute.core.interfaces.sabiork import SabiorkInterface

    _capture_raw(
        "sabiork",
        "kineticlaws",
        SabiorkInterface(**_tmp_kwargs()),
        as_text=True,
        query={"UniProtKB_AC": "P00330"},
        method="kineticlaws",
    )


# --- Credentialed / non-HTTP APIs ------------------------------------------


def capture_biogrid() -> None:
    key = os.getenv("SILKROUTE_BIOGRID_API_KEY")
    if not key:
        print("skip biogrid: no SILKROUTE_BIOGRID_API_KEY")  # noqa: T201
        return
    from silkroute.core.interfaces.biogrid import BioGRIDInterface

    iface = BioGRIDInterface(api_key=key, **_tmp_kwargs())
    _capture_raw(
        "biogrid",
        "interactions",
        iface,
        query={"geneList": "TP53", "taxId": "9606", "max": 1},
        method="interactions",
    )


def capture_uniprot() -> None:
    from silkroute.core.interfaces.uniprot import UniprotInterface

    iface = UniprotInterface()
    job = iface.submit_id_mapping("UniProtKB_AC-ID", "UniProtKB", ["P12345"])
    if iface.check_id_mapping_results_ready(job):
        link = iface.get_id_mapping_results_link(job)
        _save("uniprot", "idmapping_results", iface.get_id_mapping_results_search(link))


def capture_refseq() -> None:
    email = os.getenv("SILKROUTE_REFSEQ_EMAIL")
    if not email:
        print("skip refseq: no SILKROUTE_REFSEQ_EMAIL")  # noqa: T201
        return
    from silkroute.core.interfaces.refseq import RefSeqInterface

    iface = RefSeqInterface(email=email, **_tmp_kwargs())
    data = iface.fetch("NP_000537", method="protein")
    _save("refseq", "protein", json.loads(json.dumps(data, default=str)))


def capture_brenda() -> None:
    email = os.getenv("SILKROUTE_BRENDA_EMAIL")
    password = os.getenv("SILKROUTE_BRENDA_PASSWORD")
    if not (email and password):
        print("skip brenda: no SILKROUTE_BRENDA_EMAIL / SILKROUTE_BRENDA_PASSWORD")  # noqa: T201
        return
    from silkroute.core.interfaces.brenda import BrendaInterface

    # BrendaInterface hardcodes min_wait/max_wait, so don't pass them via _tmp_kwargs.
    iface = BrendaInterface(
        email=email,
        password=password,
        cache_dir=tempfile.mkdtemp(prefix="silkroute-capture-"),
        config_dir=tempfile.mkdtemp(prefix="silkroute-capture-cfg-"),
        use_config=False,
    )
    data = iface.fetch({"ecNumber": "1.1.1.1", "organism": "Homo sapiens"}, method="getKmValue")
    if not data:
        raise RuntimeError("brenda returned no data (check credentials)")
    _save("brenda", "getKmValue", data)


CAPTURES = {
    "rhea": capture_rhea,
    "chebi": capture_chebi,
    "alphafold": capture_alphafold,
    "genontology": capture_genontology,
    "pride": capture_pride,
    "pdb": capture_pdb,
    "stringdb": capture_stringdb,
    "interpro": capture_interpro,
    "reactome": capture_reactome,
    "chembl": capture_chembl,
    "pubchem": capture_pubchem,
    "kegg": capture_kegg,
    "panther": capture_panther,
    "pathwaycommons": capture_pathwaycommons,
    "biodbnet": capture_biodbnet,
    "sabiork": capture_sabiork,
    "biogrid": capture_biogrid,
    "uniprot": capture_uniprot,
    "refseq": capture_refseq,
    "brenda": capture_brenda,
}


def main(argv: list[str]) -> int:
    if os.getenv("SILKROUTE_CAPTURE") != "1":
        print("Refusing to run: set SILKROUTE_CAPTURE=1 to capture fixtures from the network.")  # noqa: T201
        return 1

    # Load credentials from .env (SILKROUTE_BIOGRID_API_KEY, SILKROUTE_REFSEQ_EMAIL, ...)
    # so the credentialed captures can find them.
    from silkroute.core.credentials import load_environment_files

    load_environment_files()

    selected = argv or list(CAPTURES)
    unknown = [name for name in selected if name not in CAPTURES]
    if unknown:
        print(f"Unknown APIs: {', '.join(unknown)}. Available: {', '.join(CAPTURES)}")  # noqa: T201
        return 2

    failed = []
    for name in selected:
        try:
            CAPTURES[name]()
        except Exception as e:  # keep going across APIs  # noqa: BLE001  # defensive catch-all
            print(f"error capturing {name}: {e}")  # noqa: T201
            failed.append(name)

    if failed:
        print(f"FAILED: {', '.join(failed)}")  # noqa: T201
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

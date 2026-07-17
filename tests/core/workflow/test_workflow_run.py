"""Offline tests for MainWorkflow orchestration.

Mode/modality routing and the query_composition aggregation are exercised with
stubbed modality handlers (no network). One end-to-end protein run drives the
real pipeline against a mocked UniProt stream endpoint.
"""

from __future__ import annotations

import polars as pl
import pytest
from niquests_mock import startswith

from bioseq_dl.core.interfaces.uniprot import API_URL, UniprotInterface
from bioseq_dl.core.workflow import main_workflow as workflow_module
from bioseq_dl.core.workflow.main_workflow import MainWorkflow
from tests._helpers import load_fixture


@pytest.fixture
def workflow():
    return MainWorkflow()


class RecordingUniprot:
    """UniProt fake that records fetch/parse formats without network access."""

    def __init__(self, parsed_frame=None):
        self.submit_calls = []
        self.parse_calls = []
        self.parsed_frame = (
            parsed_frame
            if parsed_frame is not None
            else pl.DataFrame(
                {
                    "accession": ["P12345"],
                    "gene_primary": [["TP53"]],
                    "organism_id": ["9606"],
                    "biogrid_ids": ["108356"],
                    "string_ids": ["9606.ENSP00000269305"],
                }
            )
        )

    def submit_stream(self, **kwargs):
        self.submit_calls.append(kwargs)
        return {"results": [{"primaryAccession": "P12345"}]}, {"extra": {"total_results": 1}}

    def parse(self, results, extract_fields=None, **kwargs):
        output_format = kwargs.get("format", "json")
        self.parse_calls.append(
            {"results": results, "extract_fields": extract_fields, "format": output_format}
        )
        return (
            self.parsed_frame,
            {"format": output_format},
        )


class RecordingPpiCrossRefEnricher:
    """CrossRef fake that records PPI enrichment formats without API calls."""

    instances = []

    def __init__(self, endpoint_specs=None, max_workers=4, total_retries=3):
        self.endpoint_specs = list(endpoint_specs or [])
        self.max_workers = max_workers
        self.total_retries = total_retries
        self.enrich_calls = []
        self.instances.append(self)

    def enrich(self, data, **kwargs):
        output_format = kwargs.get("format", "dataframe")
        self.enrich_calls.append({"data": data, "format": output_format})
        results = {
            spec.key: pl.DataFrame({"source_accession": ["P12345"], "source_endpoint": [spec.endpoint]})
            for spec in self.endpoint_specs
        }
        return (
            results,
            {spec.key: {"format": output_format} for spec in self.endpoint_specs},
        )


class RecordingPpiWorkflow(MainWorkflow):
    """Workflow subclass that records the PPI context export format."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ppi_context_export_formats = []

    def _step_fetch_additional_ppi_interaction_sources(self, context, **kwargs):
        self.ppi_context_export_formats.append(context["searches"]["uniprot"].get("export_format"))
        super()._step_fetch_additional_ppi_interaction_sources(context, **kwargs)


# --- run() mode routing ----------------------------------------------------


def test_run_routes_to_query_first(workflow, monkeypatch):
    monkeypatch.setattr(workflow, "query_first", lambda **kw: ("QF", kw))
    out, kw = workflow.run(modality="protein", mode="query_first", query="x")
    assert out == "QF"
    assert kw["modality"] == "protein"


def test_run_routes_to_query_composition(workflow, monkeypatch):
    monkeypatch.setattr(workflow, "query_composition", lambda **kw: ("QC", kw))
    out, _ = workflow.run(modality="protein", mode="query_composition", queries_with_labels=[])
    assert out == "QC"


@pytest.mark.parametrize(
    ("modality", "mode", "match"),
    [
        ("", "query_first", "modality"),
        ("protein", "", "mode"),
        ("protein", "bogus", "Unknown workflow mode"),
    ],
)
def test_run_invalid_args_raise(workflow, modality, mode, match):
    with pytest.raises(ValueError, match=match):
        workflow.run(modality=modality, mode=mode)


def test_query_first_unknown_modality_raises(workflow):
    with pytest.raises(ValueError, match="Unknown modality"):
        workflow.query_first(modality="genome", query="x")


def test_ppi_csv_export_keeps_upstream_parse_formats_dataframe(monkeypatch, niquests_mock):
    RecordingPpiCrossRefEnricher.instances = []
    monkeypatch.setattr(workflow_module, "CrossRefEnricher", RecordingPpiCrossRefEnricher)
    uniprot = RecordingUniprot()
    workflow = RecordingPpiWorkflow(uniprot_interface=uniprot)

    data, metadata = workflow.query_first(
        modality="interaction",
        interaction_type="protein-protein",
        query="reviewed:true",
        export_format="csv",
    )

    assert workflow.ppi_context_export_formats == ["csv"]
    assert uniprot.submit_calls
    assert all("format" not in call for call in uniprot.submit_calls)
    assert [call["format"] for call in uniprot.parse_calls] == ["dataframe"]
    assert RecordingPpiCrossRefEnricher.instances
    ppi_enricher = RecordingPpiCrossRefEnricher.instances[-1]
    assert [call["format"] for call in ppi_enricher.enrich_calls] == ["dataframe"]
    assert all(call["format"] != "csv" for call in uniprot.parse_calls)
    assert all(call["format"] != "csv" for call in ppi_enricher.enrich_calls)
    assert isinstance(data["uniprot"], pl.DataFrame)
    assert set(data["uniprot_enrichment"]) == {
        "biogrid_interactions",
        "string_interaction_partners",
    }
    assert metadata["mode"] == "query_first"
    assert len(niquests_mock.calls) == 0


def split_fields(value):
    return [field.strip() for field in value.split(",") if field.strip()]


def test_ppi_default_fields_include_required_interaction_inputs(monkeypatch, niquests_mock):
    RecordingPpiCrossRefEnricher.instances = []
    monkeypatch.setattr(workflow_module, "CrossRefEnricher", RecordingPpiCrossRefEnricher)
    uniprot = RecordingUniprot()
    workflow = MainWorkflow(uniprot_interface=uniprot)

    workflow.query_first(
        modality="interaction",
        interaction_type="protein-protein",
        query="reviewed:true",
        fields=None,
        enrich=False,
    )

    requested_fields = split_fields(uniprot.submit_calls[0]["fields"])
    assert requested_fields == [
        "accession",
        "protein_name",
        "organism_name",
        "organism_id",
        "sequence",
        "length",
        "gene_primary",
        "xref_string",
    ]
    assert len(requested_fields) == len(set(requested_fields))
    assert RecordingPpiCrossRefEnricher.instances
    assert len(niquests_mock.calls) == 0


def test_ppi_user_fields_are_preserved_and_deduplicated(monkeypatch, niquests_mock):
    RecordingPpiCrossRefEnricher.instances = []
    monkeypatch.setattr(workflow_module, "CrossRefEnricher", RecordingPpiCrossRefEnricher)
    uniprot = RecordingUniprot()
    workflow = MainWorkflow(uniprot_interface=uniprot)

    workflow.query_first(
        modality="interaction",
        interaction_type="protein-protein",
        query="reviewed:true",
        fields="accession, custom_field, accession, organism_id",
        enrich=False,
    )

    requested_fields = split_fields(uniprot.submit_calls[0]["fields"])
    assert requested_fields == ["accession", "custom_field", "organism_id", "gene_primary", "xref_string"]
    assert len(requested_fields) == len(set(requested_fields))
    assert len(niquests_mock.calls) == 0


def test_ppi_endpoint_specs_use_gene_organism_and_id_fallbacks(monkeypatch):
    RecordingPpiCrossRefEnricher.instances = []
    monkeypatch.setattr(workflow_module, "CrossRefEnricher", RecordingPpiCrossRefEnricher)
    workflow = MainWorkflow(uniprot_interface=RecordingUniprot())
    context = {
        "searches": {"uniprot": {"export_format": "csv"}},
        "data": {
            "uniprot": pl.DataFrame(
                {"accession": ["P12345"], "gene_primary": [["TP53"]], "organism_id": ["9606"]}
            )
        },
        "metadata": {},
    }

    workflow._step_fetch_additional_ppi_interaction_sources(context)

    instance = RecordingPpiCrossRefEnricher.instances[-1]
    assert [(spec.database, spec.endpoint) for spec in instance.endpoint_specs] == [
        ("biogrid", "interactions"),
        ("string", "interaction_partners"),
    ]
    assert set(context["data"]["uniprot_enrichment"]) == {
        "biogrid_interactions",
        "string_interaction_partners",
    }


@pytest.mark.parametrize(
    ("frame", "expected_specs"),
    [
        (
            pl.DataFrame({"accession": ["P12345"], "string_ids": ["9606.ENSP00000269305"]}),
            [("string", "interaction_partners")],
        ),
        (
            pl.DataFrame({"accession": ["P12345"], "biogrid_ids": ["108356"]}),
            [("biogrid", "interactions")],
        ),
        (
            pl.DataFrame({"accession": ["P12345"], "gene_primary": [["TP53"]], "organism_id": ["9606"]}),
            [("biogrid", "interactions"), ("string", "interaction_partners")],
        ),
    ],
)
def test_ppi_source_eligibility_matches_registered_query_builders(
    monkeypatch,
    frame,
    expected_specs,
):
    RecordingPpiCrossRefEnricher.instances = []
    monkeypatch.setattr(workflow_module, "CrossRefEnricher", RecordingPpiCrossRefEnricher)
    workflow = MainWorkflow(uniprot_interface=RecordingUniprot())
    context = {
        "searches": {"uniprot": {"export_format": "csv"}},
        "data": {"uniprot": frame},
        "metadata": {},
    }

    workflow._step_fetch_additional_ppi_interaction_sources(context)

    instance = RecordingPpiCrossRefEnricher.instances[-1]
    assert [(spec.database, spec.endpoint) for spec in instance.endpoint_specs] == expected_specs
    assert [call["format"] for call in instance.enrich_calls] == ["dataframe"]


def test_ppi_without_usable_columns_records_skip_reason(monkeypatch, caplog):
    RecordingPpiCrossRefEnricher.instances = []
    monkeypatch.setattr(workflow_module, "CrossRefEnricher", RecordingPpiCrossRefEnricher)
    workflow = MainWorkflow(uniprot_interface=RecordingUniprot())
    initial_instance_count = len(RecordingPpiCrossRefEnricher.instances)
    context = {
        "searches": {"uniprot": {"export_format": "csv"}},
        "data": {"uniprot": pl.DataFrame({"accession": ["P12345"]})},
        "metadata": {},
    }

    with caplog.at_level("WARNING"):
        workflow._step_fetch_additional_ppi_interaction_sources(context)

    assert len(RecordingPpiCrossRefEnricher.instances) == initial_instance_count
    assert "ppi_sources" in context["metadata"]["uniprot_enrichment"]
    assert "No usable UniProt columns for PPI source fetch" in caplog.text


def test_ppi_query_composition_forwards_fields(monkeypatch, niquests_mock):
    RecordingPpiCrossRefEnricher.instances = []
    monkeypatch.setattr(workflow_module, "CrossRefEnricher", RecordingPpiCrossRefEnricher)
    uniprot = RecordingUniprot()
    workflow = MainWorkflow(uniprot_interface=uniprot)

    workflow.query_composition(
        modality="interaction",
        interaction_type="protein-protein",
        queries_with_labels=[("reviewed:true", "reviewed")],
        fields="accession",
        enrich=False,
    )

    assert split_fields(uniprot.submit_calls[0]["fields"]) == [
        "accession",
        "gene_primary",
        "organism_id",
        "xref_string",
    ]
    assert len(niquests_mock.calls) == 0


# --- query_composition aggregation -----------------------------------------


def test_query_composition_labels_and_merges(workflow, monkeypatch):
    def fake_run_protein(query=None, **kwargs):
        return {"uniprot": pl.DataFrame({"acc": [f"P{query}"]})}, {"modality": "protein"}

    monkeypatch.setattr(workflow, "run_protein", fake_run_protein)

    data, metadata = workflow.query_composition(
        modality="protein", queries_with_labels=[("1", "la"), ("2", "lb")]
    )

    # Both runs concatenated under uniprot, each row tagged with its label.
    assert data["uniprot"].to_dicts() == [
        {"acc": "P1", "_label": "la"},
        {"acc": "P2", "_label": "lb"},
    ]
    assert [p["label"] for p in metadata["parts"]] == ["la", "lb"]


def test_query_composition_empty_parts_returns_empty(workflow, monkeypatch):
    monkeypatch.setattr(workflow, "run_protein", lambda **kw: ({}, {}))

    data, metadata = workflow.query_composition(modality="protein", queries_with_labels=[("q", "l")])

    assert data == {}
    assert [p["label"] for p in metadata["parts"]] == ["l"]


def test_query_composition_unknown_modality_raises(workflow):
    with pytest.raises(ValueError, match="Unknown modality"):
        workflow.query_composition(modality="genome", queries_with_labels=[("q", "l")])


# --- _step_chembl_to_uniprot_query -----------------------------------------


def test_chembl_to_uniprot_builds_xref_query(workflow):
    context = {
        "searches": {"uniprot": {"query": None}},
        "data": {"chembl": pl.DataFrame({"target_chembl_id": ["CHEMBL1", "CHEMBL2"]})},
    }
    workflow._step_chembl_to_uniprot_query(context)
    assert context["searches"]["uniprot"]["query"] == "(xref:chembl-CHEMBL1 OR xref:chembl-CHEMBL2)"


def test_chembl_to_uniprot_chunks_large_id_lists(workflow):
    ids = [f"CHEMBL{i}" for i in range(150)]  # > CHEMBL_ID_CHUNK_SIZE (100)
    context = {
        "searches": {"uniprot": {"query": None}},
        "data": {"chembl": pl.DataFrame({"target_chembl_id": ids})},
    }
    workflow._step_chembl_to_uniprot_query(context)
    query = context["searches"]["uniprot"]["query"]
    assert isinstance(query, list)
    assert len(query) == 2  # 100 + 50


def test_chembl_to_uniprot_no_ids_leaves_query_untouched(workflow):
    context = {"searches": {"uniprot": {"query": None}}, "data": {"chembl": pl.DataFrame()}}
    workflow._step_chembl_to_uniprot_query(context)
    assert context["searches"]["uniprot"]["query"] is None


# --- end-to-end protein run (mocked UniProt stream) ------------------------


def test_run_protein_fetches_parses_and_stamps_time(niquests_mock):
    results = load_fixture("uniprot", "idmapping_results")
    niquests_mock.get(url=startswith(f"{API_URL}/uniprotkb/stream")).respond(
        status_code=200, json=results, headers={"Content-Length": "123"}
    )

    workflow = MainWorkflow(uniprot_interface=UniprotInterface())
    data, metadata = workflow.run_protein(query="kinase", enrich=False)

    # UniProt response parsed to a DataFrame and carried under data["uniprot"].
    assert isinstance(data["uniprot"], pl.DataFrame)
    assert len(data["uniprot"]) == len(results["results"])
    # Provenance/timing stamped, fetch metadata recorded.
    assert "time_taken_seconds" in metadata
    assert "fetch" in metadata["uniprot"]


def test_run_protein_empty_query_skips_fetch(niquests_mock):
    workflow = MainWorkflow(uniprot_interface=UniprotInterface())
    data, _ = workflow.run_protein(query="", enrich=False)

    # Empty interpreted query short-circuits: no network call is made.
    assert len(niquests_mock.calls) == 0
    # Parsed output degrades to an empty DataFrame rather than raising.
    assert isinstance(data["uniprot"], pl.DataFrame)
    assert data["uniprot"].is_empty()

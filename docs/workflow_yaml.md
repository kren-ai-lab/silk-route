# Workflow YAML Descriptors

BioSeqDownloader workflow YAML files are structured dataset descriptors for reproducible data acquisition runs. They configure the current workflow CLI, describe the dataset objective, preserve query and execution context, and generate metadata plus a compact run summary.

They are not a generic workflow engine, a multi-step pipeline language, or a plugin system. The current implementation maps a specific set of descriptor fields to `bioseq-dl workflow run` and preserves the rest as descriptive metadata.

Workflow descriptors must declare the frozen schema version:

```yaml
schema_version: "workflow-v1"
```

No other schema version is accepted.

The old top-level key `version` is forbidden. Use only
`schema_version: "workflow-v1"` for the workflow YAML schema marker.

## Execution Model

The workflow execution strategy is configured with:

```yaml
dataset:
  mode: query_first
```

Valid `dataset.mode` values are:

- `query_first`
- `query_composition`

`query_first` describes one query. `query_composition` describes multiple
labeled queries; each query is retrieved separately and assigned its label.

The CLI equivalent is `--mode` (or `-d`) with the same values.

## CLI Override Priority

When a YAML descriptor and CLI options are both provided, values are resolved in this order:

1. Explicit CLI arguments.
2. YAML descriptor values.
3. Existing workflow defaults.

Examples:

```bash
bioseq-dl workflow run --config examples/workflows/protein_query_first_minimal.yml
bioseq-dl workflow run --config examples/workflows/protein_query_first_minimal.yml -o result_override
bioseq-dl workflow run --config examples/workflows/protein_query_first_minimal.yml -e csv
```

The organized workflow-v1 examples live under `examples/workflows/`.
There are no legacy workflow YAML examples outside that directory.
Use `examples/workflows/full_options_reference.yml` as the tutorial/reference
descriptor for the full schema surface. It is documentation-oriented and is not
intended to be executed as a complete workflow.

The runnable examples under `examples/workflows/` intentionally keep preserved-only
metadata fields out unless the example is specifically demonstrating metadata
preservation. This keeps executable descriptors aligned with behavior implemented
by the current workflow runner.

Example descriptors:

| File | Purpose | Schema-valid | Intended-to-run | Requires-internet | Notes |
| --- | --- | --- | --- | --- | --- |
| `examples/workflows/full_options_reference.yml` | Tutorial/reference descriptor | Yes | No | No | Documents the schema surface and current limitations. |
| `examples/workflows/protein_query_first_minimal.yml` | Minimal protein `query_first` workflow | Yes | Yes | Yes | Small UniProt example. |
| `examples/workflows/protein_query_first_with_fields.yml` | Protein query with UniProt request fields | Yes | Yes | Yes | `query.fields` is passed to UniProt and is not an output-column filter. |
| `examples/workflows/protein_query_first_with_gui_metadata.yml` | Protein query with preserved GUI metadata | Yes | Yes | Yes | Demonstrates `query.builder`; `query.value` remains executable. |
| `examples/workflows/protein_query_composition_labels.yml` | Labeled protein query-composition workflow | Yes | Yes | Yes | Demonstrates preserved `query.composition`; labels still execute from `query.value`. |
| `examples/workflows/compound_chembl_ic50_ranges.yml` | Small ChEMBL IC50 range workflow | Yes | Yes | Yes | Uses `execution.chembl_pages_to_fetch: 1`. |
| `examples/workflows/compound_pubchem_name.yml` | PubChem compound name lookup | Yes | Yes | Yes | Exports normalized PubChem properties. |
| `examples/workflows/compound_pubchem_substructure.yml` | PubChem SMILES substructure search | Yes | Yes | Yes | Uses a conservative first-pass result cap. |
| `examples/workflows/compound_chebi_name.yml` | ChEBI entity name search | Yes | Yes | Yes | Exports normalized ChEBI entity records. |
| `examples/workflows/interaction_ppi_uniprot.yml` | Protein-protein interaction workflow descriptor | Yes | Yes | Yes | Keeps interaction settings limited to currently validated fields. |
| `examples/workflows/interaction_pli_chembl.yml` | Protein-ligand interaction workflow descriptor | Yes | Yes | Yes | Uses a small ChEMBL query and page cap. |
| `examples/workflows/invalid/missing_schema_version.yml` | Invalid missing-schema example | No | No | No | Expected to fail because `schema_version` is required. |
| `examples/workflows/invalid/unsupported_schema_version.yml` | Invalid unsupported-schema example | No | No | No | Expected to fail because only `"workflow-v1"` is accepted. |
| `examples/workflows/invalid/forbidden_version_key.yml` | Invalid old-version-key example | No | No | No | Expected to fail because top-level `version` is forbidden. |
| `examples/workflows/invalid/unknown_top_level_section.yml` | Invalid unknown-section example | No | No | No | Expected to fail because `resoures` is not a supported section. |
| `examples/workflows/invalid/invalid_query_composition.yml` | Invalid composition metadata example | No | No | No | Expected to fail because each composition item needs `label` and `value`. |

Educational notebooks live under `examples/notebooks/`. The validation and
metadata walkthrough notebooks are designed to work offline when the local
package dependencies are installed. Notebooks that run workflow descriptors
clearly mark live API cells and handle network/API failures gracefully.

## Top-Level Sections

Required top-level sections:

| Section | Type | Role |
| --- | --- | --- |
| `schema_version` | string | Required schema marker. Must be exactly `"workflow-v1"`. |
| `dataset` | mapping | Dataset identity plus executable `modality` and `mode`. |
| `query` | mapping | Executable query string plus query metadata and fetch options. |
| `execution` | mapping | Executable workflow controls such as enrichment, retries, and logging. |
| `export` | mapping | Output directory, format, metadata, and summary controls. |

Optional core sections:

| Section | Type | Role |
| --- | --- | --- |
| `resources` | mapping | Descriptive list of intended primary and integration resources. |
| `harmonization` | mapping | Export/reporting aids and descriptive harmonization metadata. |
| `reporting` | mapping | Descriptor-provided report fields plus generated runtime metrics. |

Allowed descriptive extension sections:

- `interaction_retrieval`
- `activity_retrieval`
- `chemical_metadata_integration`
- `protein_target_integration`
- `temperature_enrichment`
- `cross_source_integration`

These extension sections are preserved in metadata and run summary output. API retrieval for them is handled only by workflow logic that explicitly supports it.

Unknown top-level sections are rejected. For example, `resoures` fails because the accepted section is `resources`.

The canonical top-level order is:

1. `schema_version`
2. `dataset`
3. `query`
4. `resources`
5. `execution`
6. `harmonization`
7. `export`
8. `reporting`
9. Optional descriptive extension sections

## Field Reference

Field roles:

- **Executable**: changes the workflow run.
- **Descriptive**: accepted and preserved for metadata or reporting context.
- **Generated**: filled or overwritten by BioSeqDownloader during reporting.

Current executable fields are the fields that should be used to control
workflow behavior today:

| Field | Current behavior |
| --- | --- |
| `schema_version` | Required schema marker. Must be exactly `"workflow-v1"`. |
| `dataset.modality` | Selects the workflow modality: `protein`, `compound`, or `interaction`. |
| `dataset.mode` | Selects `query_first` or `query_composition`. |
| `dataset.interaction_type` | Required for interaction workflows and validated as `protein-protein` or `protein-ligand`. |
| `query.value` | The executable query string. |
| `query.fields` | User-selected UniProt request/result fields. |
| `query.crossref_fields` | Enrichment source selections used by supported enrichment paths when enrichment is enabled. |
| `query.include_isoform` | Passed to UniProt requests. |
| `execution.enrich` | Enables supported enrichment behavior. |
| `execution.max_workers` | Controls worker count for supported workflow/enrichment paths. |
| `execution.total_retries` | Controls retry settings for supported interfaces. |
| `execution.chembl_pages_to_fetch` | Caps ChEMBL page retrieval. |
| `execution.uniprot_timeout` | Controls UniProt request timeout when provided. |
| `execution.debug` | Enables debug logging. |
| `harmonization.id_column` | Adds deterministic IDs to exported tabular outputs when absent. |
| `export.output_dir` | Selects the output directory. |
| `export.format` | Selects `csv`, `json`, `xml`, or `parquet`. |
| `export.include_metadata` | Controls metadata manifest writing. |
| `export.include_summary` | Controls run summary writing. |
| `export.manifest_file` | Selects the metadata manifest filename. |
| `export.summary_file` | Selects the run summary filename. |

Workflow modality controls routing. Protein workflows are UniProt-oriented and
reject ChEMBL-prefixed queries such as `chembl.target:` or `chembl.activity:`
instead of passing them into the UniProt query interpreter. They also reject
chemical-source query-builder prefixes such as `pubchem.compound:` and
`chebi.entity:` before UniProt routing. Compound workflows are
compound/chemical-oriented: compatible `chembl.molecule:` and
`chembl.activity:` queries run through ChEMBL and keep ChEMBL outputs rather
than automatically constructing UniProt target queries. PubChem compound and
structure prefixes execute through PubChem. ChEBI entity ID and name/text
queries execute through ChEBI; the remaining ChEBI plans fail clearly before
network access. Protein-ligand workflows accept
ChEMBL query prefixes and reject PubChem or ChEBI prefixes before ChEMBL
routing. Protein-ligand
relationship construction belongs to `dataset.modality: interaction` with
`dataset.interaction_type: protein-ligand`, where ChEMBL target/activity data
can be mapped to UniProt target details. Protein-protein interaction workflows
remain UniProt-oriented and reject ChEMBL, PubChem, and ChEBI source-prefixed
queries.

Preserved metadata fields are accepted by the schema and carried into metadata
or summaries, but they must not be described as execution controls:

| Field or section | Current behavior |
| --- | --- |
| `dataset.name` | Dataset identity and default output-directory source when `export.output_dir` is absent. |
| `dataset.description` | Preserved descriptive text. |
| `dataset.primary_data_source` | Preserved descriptive text; routing comes from modality, mode, and query interpretation. |
| `query.description` | Preserved descriptive text. |
| `query.filtering_strategy` | Preserved descriptive text; executable filtering belongs in `query.value`. |
| `query.builder` | Preserved neutral visual-editor metadata only. |
| `query.composition` | Preserved neutral visual-editor metadata only. If `query.composition` is present, it must match the executable `query.value`. |
| `harmonization.sequence_column` | Used only for generated unique-sequence reporting when matching tabular output exists. |
| `reporting` custom fields | Preserved YAML-safe descriptive values unless overwritten by generated reporting. |

Future features are listed in [Future Workflow YAML Features](#future-workflow-yaml-features).

The lightweight schema definition and workflow-v1 validator used by GUI or YAML
generator tools are available through:

```python
from bioseq_dl.workflow_schema_definition import (
    get_workflow_v1_schema_definition,
    validate_workflow_v1_descriptor,
)
```

The validator checks descriptor structure and field types without importing the
workflow CLI, API interfaces, pandas, network clients, export helpers, or
NiceGUI.

Developer note: the shared UniProt friendly-query field catalog lives in
`bioseq_dl.core.workflow.query_field_catalog` and is the source of truth for
both the current UniProt query interpreter and GUI query-builder code.
Friendly query syntax supports quoted values with spaces, such as
`organism_any:"Homo sapiens"` and `go_any:"DNA repair","protein folding"`.
GUI builder rows compile to a final interpreted query and store that executable
string in `query.value`. The pure builder utilities prepare query text only;
live validation and data retrieval happen in the workflow run.

The optional NiceGUI interface prepares `workflow-v1` YAML descriptors only. It
does not execute workflows, call external APIs, or download biological data.
The GUI keeps credentials out of YAML and treats live API access as part of the
later workflow run. For `query_first`, Manual query writes typed text directly
to `query.value`, while Advanced builder lets users choose a database-specific
builder. The interpreted query preview is the value written to `query.value`.
The friendly query preview is display-only. Advanced mode also writes neutral
`query.builder` metadata so visual editors can restore its source-specific rows
later; Manual query mode omits it. For UniProt-style protein queries, the GUI
includes a Review status selector that maps to `reviewed:true` or
`reviewed:false` inside `query.value`. The workflow-v1 schema does not add a
separate reviewed key; users can also write the reviewed filter manually in
YAML.

For `query_composition`, the GUI includes a labeled query editor. Each entry has
a label, optional description, and either a manual query value or a compatible
UniProt or ChEMBL advanced builder. The GUI joins entries as comma-separated
`query=label` pairs in `query.value` and writes matching `query.composition`
metadata, including independent builder metadata for advanced entries:

```yaml
query:
  value: "keywords:antiviral protein=antiviral,go:dna repair=dna_repair"
  composition:
    - label: antiviral
      value: "keywords:antiviral protein"
      description: Antiviral protein keyword query.
    - label: dna_repair
      value: "go:dna repair"
      description: DNA repair Gene Ontology query.
```
Install it with the optional GUI extra and run:

```bash
pip install -e ".[gui]"
bioseq-dl-gui
```

It can also be run as a module:

```bash
python -m bioseq_dl.gui.nicegui_app
```

The GUI writes `schema_version: "workflow-v1"` automatically. `query.value` is
the only executable query field. Advanced `query_first` mode emits optional
top-level `query.builder` metadata. Advanced labeled entries emit independent
builder metadata inside `query.composition[]`; manual modes omit it. Workflows
ignore visual builder metadata during execution. Generated YAML can be copied
from the preview or saved as a `.yml` file through the browser.

The GUI can load an existing `workflow-v1` YAML file and populate supported form
fields. Loading validates the descriptor, fills the editable Dataset, Query,
Execution, Harmonization, and Export controls, and regenerates the YAML preview
from those editable fields. YAML generated from Advanced builder mode may
include `query.builder` metadata. If that metadata is valid, compatible with the
loaded dataset settings, and regenerates the same `query.value`, the GUI restores
the selected advanced builder and its rows. If `query.builder` is missing,
invalid, incompatible, or no longer matches `query.value`, the GUI loads the
saved query text in Manual query mode. For `query_composition`, valid metadata
restores the labeled rows; when metadata is absent, the GUI reconstructs rows
from valid `query.value` pairs. Workflow execution continues to use only
`query.value`. Metadata such as `resources` or `reporting` may also validate as
workflow-v1 descriptor metadata and is shown as read-only.

GUI controls use human-friendly labels while generated YAML keeps exact
`workflow-v1` values. `Query First` writes `query_first`, `Query Composition`
writes `query_composition`, and modality labels write `protein`, `compound`, or
`interaction`. `No interaction` omits `dataset.interaction_type` for protein and
compound datasets; it is invalid when the selected modality is `Interaction`.

`UniProt return fields` is a selectable list of normal UniProt request/result
fields. Selected values are stored as field IDs in `query.fields`; an advanced
manual input remains available for custom UniProt field IDs. New GUI workflows
preselect `accession`, `protein_name`, `organism_name`, `organism_id`,
`sequence`, and `length`. If `query.fields` is missing or empty in a workflow
YAML, BioSeqDownloader uses those same default UniProt return fields internally.
Technical `xref_*` fields are usually derived internally from selected
enrichment sources rather than shown as normal return-field choices, and they
are not part of the normal default return fields. Enrichment is disabled by default;
its source selector and advanced cross-reference input appear only after
`Enable enrichment` is selected. Selected GUI sources are written as lowercase
keys in `query.crossref_fields`. Multiple sources are available, but actual
enrichment depends on usable cross-reference data and enabled packaged
endpoints. PubChem and ChEBI remain query sources/builders; their enrichment
availability follows the same endpoint constraints. The builder prepares query
text only; network access happens later when the CLI runs the workflow.

`ChEMBL workflow pages to fetch` is located under collapsed source-specific
execution options. It controls ChEMBL pagination and is not a general
enrichment setting. The default output-directory mode writes
`results/{dataset.name}`. The custom mode accepts only relative paths,
normalizes backslashes to forward slashes, and rejects absolute paths or `..`
traversal. This path is used later when the workflow runs.

Advanced UniProt builder rows use two separate controls for query logic.
Connector combines the current row with the previous row; use `AND` when both
conditions should be required and `OR` when either condition can match. Match
mode combines comma-separated values inside a single row: `Any` means at least
one value can match, `All` means every value must match, and `Not` excludes the
values. Values with spaces can be quoted, such as `"Homo sapiens"` or
`"DNA repair"`. The friendly query preview is an intermediate display only; the
interpreted `query.value` preview is the value that generated YAML stores under
`query.value`.

Advanced ChEMBL builders use resource-specific filters rather than UniProt-style
connectors and match modes. ChEMBL target, assay, cell line, and molecule
builders emit filter-list query strings; the ChEMBL activity builder emits flat
parameter query strings. ChEMBL rows are combined with `AND`; use the `in`
filter type for multiple allowed values in a single field. The ChEMBL builder
prepares the ChEMBL query text only; ChEMBL validation happens later when the
workflow runs. `query.fields` and `query.crossref_fields` remain separate from
all query-builder fields.

Advanced PubChem builders are available for compound datasets. The compound
builder prepares lookup strings for CID, name/synonym, InChI, and InChIKey. The
structure builder prepares SMILES identity, SMILES substructure, and 2-D
similarity query strings with an integer threshold. PubChem is modeled here as
a compound resolver and structure-search source, not as a replacement for
ChEMBL activity, assay, target, or protein-ligand workflows.
The catalog/GUI field `similarity_2d` accepts a reference CID; the pure builder
maps it explicitly to `similarity_2d_cid` and adds the selected `threshold` to
the executable query.

Advanced ChEBI builders are also available for compound datasets. The entity
builder prepares ChEBI ID, name/text, formula, mass range, charge range,
database cross-reference, and curation-star query strings. The ontology builder
prepares relation-plus-term strings, and the structure builder prepares
connectivity, substructure, or similarity strings. ChEBI is modeled here as a
chemical entity, ontology, and structure source.
ChEBI catalog/GUI fields use descriptive names. In particular,
`ontology_relation` and `ontology_term` map explicitly to the executable
`relation` and `term` parameters.

PubChem and ChEBI builders prepare `query.value` strings and pure request plans.
Generated YAML contains neither credentials nor builder metadata. The GUI
prepares YAML; workflow execution and PubChem/ChEBI API calls stay in the CLI.
PubChem and ChEBI builders are available for `modality: compound`; protein and
interaction workflows reject PubChem/ChEBI prefixes before source execution.
ChEMBL remains the supported source for protein-ligand activity and target
workflows.

Executable now:

- `pubchem.compound:cid=...`
- `pubchem.compound:name=...`
- `pubchem.compound:inchi=...`
- `pubchem.compound:inchikey=...`
- `pubchem.structure:smiles_identity=...`
- `pubchem.structure:smiles_substructure=...`
- `pubchem.structure:similarity_2d_cid=... AND threshold=...`
- `chebi.entity:chebi_id=...`
- `chebi.entity:name=...`
- `chebi.entity:name_contains=...`

Prepared but not executable yet:

- ChEBI formula/range/cross-reference queries;
- ChEBI ontology queries;
- ChEBI structure queries.

CSV runs write `pubchem_results.csv` or `chebi_results.csv`. When enabled,
`metadata.json` and `run_summary.yml` include the query source, resource, model,
request plan, record count, and output-file information.

Example PubChem compound descriptor:

```yaml
schema_version: "workflow-v1"
dataset:
  name: pubchem_compound_example
  modality: compound
  mode: query_first
query:
  value: pubchem.compound:name="glucose"
execution:
  max_workers: 2
  total_retries: 1
  debug: false
export:
  output_dir: results/pubchem_glucose
  format: csv
  include_metadata: true
  include_summary: true
```

Example PubChem structure descriptor:

```yaml
schema_version: "workflow-v1"
dataset:
  name: pubchem_structure_example
  modality: compound
  mode: query_first
query:
  value: pubchem.structure:smiles_substructure="c1ccccc1"
execution:
  max_workers: 2
  total_retries: 1
  debug: false
export:
  output_dir: results/pubchem_substructure
  format: csv
  include_metadata: true
  include_summary: true
```

Example ChEBI entity descriptor:

```yaml
schema_version: "workflow-v1"
dataset:
  name: chebi_entity_example
  modality: compound
  mode: query_first
query:
  value: chebi.entity:name_contains="caffeine"
execution:
  max_workers: 2
  total_retries: 1
  debug: false
export:
  output_dir: results/chebi_caffeine
  format: csv
  include_metadata: true
  include_summary: true
```

Prepared ChEBI ontology descriptor (not executable yet):

```yaml
schema_version: "workflow-v1"
dataset:
  name: chebi_ontology_example
  modality: compound
  mode: query_first
query:
  value: chebi.ontology:relation=has_role AND term=metabolite
```

Advanced query builders are filtered by the selected dataset modality and
interaction type. Protein datasets currently expose the UniProt builder.
Compound datasets expose compatible ChEMBL molecule and activity builders plus
PubChem compound/structure and ChEBI entity/ontology/structure builders.
Protein-ligand interaction datasets expose compatible ChEMBL target, assay, and
activity builders. Protein-protein interaction datasets expose the UniProt
builder. If Interaction is selected without an interaction type, no advanced
builder is shown and Manual query mode remains available. These filters guide
the GUI choices; the workflow runner still validates compatibility when the
descriptor is executed from the CLI.

ChEMBL queries generated by the GUI should be paired with a compatible modality.
Use compound workflows for compound/activity-oriented ChEMBL outputs. Use
protein-ligand interaction workflows when the goal is to connect ChEMBL target
or activity records back to UniProt target details. PubChem and ChEBI generated
queries should be paired with compound descriptors. ChEMBL, PubChem, and ChEBI
source-prefixed queries are rejected when paired with incompatible protein or
protein-protein workflows.

Developer query-builder architecture note: query builders are database- and
resource-specific. The extension point is
`bioseq_dl.gui.query_builders.registry`, which registers lightweight builder
specifications without importing NiceGUI or API interfaces. UniProt uses a
field/boolean/match-mode builder that compiles to a final UniProt-compatible
`query.value`. ChEMBL does not share that model: target, assay, cell line, and
molecule builders use ChEMBL filter-list rows, while ChEMBL activity uses flat
parameter rows. ChEMBL substructure and similarity are special structure-query
patterns documented as future builder resources and are not implemented in the
GUI. PubChem and ChEBI use source-specific catalogs and parser semantics rather
than the ChEMBL filter model. `examples/API_usage_demo.ipynb` was used as local
usage context for the supported ChEMBL query patterns. Builders and parsers
produce YAML-ready query text and local request plans. The compound workflow
turns supported plans into source-specific interface calls and normalized
records. UniProt and ChEMBL builders can also store neutral row metadata for
GUI reconstruction. PubChem and ChEBI currently store only final interpreted
query text. The GUI never performs API calls, and `query.value` remains the
only executable query.

The `Harmonization` section describes expected output columns and related
reporting behavior. `ID column`, `Label column`, `Sequence column`, and `Unique
sequence strategy` are optional text inputs. `Metadata fields` accepts a
comma-separated list and writes it as a YAML list. `sequence_column` is useful
only when generated tabular output contains that column, and
`unique_sequence_strategy` is currently descriptive. These controls describe
expected output structure. Data cleaning, merging, renaming, filtering, and
deduplication are handled by the workflow logic that supports those operations.

### Manual GUI smoke test

1. Install GUI dependencies with `pip install -e ".[gui]"`.
2. Start the GUI with `bioseq-dl-gui`.
3. Fill `Dataset name`.
4. Fill `Executable query value` in Manual query mode, or define one Advanced UniProt builder condition.
5. Click `Generate YAML`.
6. Confirm the YAML contains `schema_version: workflow-v1`.
7. Click `Validate YAML`.
8. Confirm validation succeeds.
9. Click `Save YAML`.
10. Confirm a `.yml` file is downloaded.
11. Confirm the GUI did not execute a workflow or call external APIs.

### Manual GUI load smoke test

1. Install GUI dependencies with `pip install -e ".[gui]"`.
2. Start the GUI with `bioseq-dl-gui`.
3. Open `Load existing workflow YAML`.
4. Upload a valid `.yml` or `.yaml` workflow-v1 descriptor.
5. Confirm supported form fields are populated.
6. Confirm compatible `query.builder` metadata restores Advanced builder rows.
7. Confirm YAML without matching builder metadata opens in Manual query mode with a load note.
8. Click `Generate YAML`.
9. Confirm the preview still contains `schema_version: workflow-v1`.
10. Confirm no workflow output files or API activity were produced by the GUI.

### `dataset`

| Field | Type | Required | Default | Role | Internal mapping | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| `name` | string | Required only when `export.output_dir` is absent | none | Descriptive and defaulting | Used to derive `output` as `results/{dataset.name}` when `export.output_dir` is not set | Retrieval is controlled by modality, mode, and query. |
| `description` | string or null | Optional | `null` | Descriptive | Preserved in descriptor metadata and summary | Used as dataset context. |
| `modality` | string | Required | none | Executable | Normalized to `workflow_values["modality"]` and passed to `MainWorkflow.run(modality=...)` | Must be `protein`, `compound`, or `interaction`. |
| `mode` | string | Required | none | Executable | Normalized to `workflow_values["mode"]` and passed to `MainWorkflow.run(mode=...)` | Must be `query_first` or `query_composition`. |
| `primary_data_source` | string or null | Optional | `null` | Descriptive | Preserved in metadata and summary | Does not route the workflow. |
| `interaction_type` | string or null | Optional | `null` | Executable for interaction workflows | Passed as `interaction_type` | Required by the interaction modality handler; expected values are handled by the workflow code, currently `protein-protein` or `protein-ligand`. |

### `query`

| Field | Type | Required | Default | Role | Internal mapping | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| `value` | non-empty string | Required | none | Executable | Normalized to `workflow_values["query"]` | For `query_first`, this is the query string. For `query_composition`, use comma-separated labeled pairs such as `temperature:99=temp_99,temperature:98=temp_98`. |
| `builder` | mapping | Optional | omitted | Neutral visual-editor metadata | Preserved in descriptor metadata and summary | Advanced builders emit `query-builder-v1` metadata with `source`, `builder_key`, `builder_type`, and source-specific `rows`. |
| `composition` | list of mappings | Optional | omitted | Neutral visual-editor metadata | Preserved in descriptor metadata and summary | `query.value` remains executable. Each item requires non-empty `label` and `value`, with optional `description` and per-entry `builder` mapping. |
| `description` | string or null | Optional | `null` | Descriptive | Preserved in metadata and summary | Used as descriptor context. |
| `filtering_strategy` | string or null | Optional | `null` | Descriptive | Preserved in metadata and summary | Filtering must be encoded in `query.value`; `query.filters` is not supported. |
| `fields` | null, string, or list of strings | Optional | `null` | Executable | Normalized to `workflow_values["fields"]`; missing or empty values use the default UniProt return fields before the UniProt fetch | It controls normal requested UniProt fields. Defaults are `accession`, `protein_name`, `organism_name`, `organism_id`, `sequence`, and `length`. Parser columns still come from the workflow parser's field map. BioSeqDownloader may add technical `xref_*` request fields internally when enrichment needs cross-reference identifiers. |
| `crossref_fields` | null, string, or list of strings | Optional | `null` | Executable when enrichment is enabled | Normalized to `workflow_values["crossref_fields"]` and passed to the enrichment path | Stores enrichment source selections separately from `query.fields`; unavailable or unsupported cross-reference fields may produce no enrichment output. |
| `include_isoform` | boolean | Optional | `false` | Executable | Normalized to `workflow_values["include_isoform"]` and passed to UniProt fetches | Applies to UniProt requests. |

`query.value` is the only executable query field. `query.builder` and
`query.composition` are preserved neutral visual-editor metadata used to
reconstruct the corresponding GUI controls; execution continues to use
`query.value`.

When `dataset.mode` is `query_composition` and `query.composition` is present,
the preserved composition metadata must match the executable comma-separated
`query.value` pairs. For example,
`query.value: "gene:TP53=tp53,gene:BRCA1=brca1"` must be described by
composition items containing the exact `(value, label)` pairs
`("gene:TP53", "tp53")` and `("gene:BRCA1", "brca1")`.
When composition metadata is omitted, the GUI can reconstruct editor rows from
valid `query.value` pairs. Because commas separate entries and the current
format has no escaping mechanism, this GUI version rejects commas inside an
individual composition query value.

### `resources`

| Field | Type | Required | Default | Role | Internal mapping | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| `primary` | list of strings | Optional | omitted | Descriptive | Preserved in metadata and summary | Current routing comes from `dataset.modality`, `dataset.mode`, and query interpretation. |
| `integration` | list of strings | Optional | omitted | Descriptive | Preserved in metadata and summary | Use query cross-reference fields and `execution.enrich` for supported enrichment behavior. |

### `execution`

| Field | Type | Required | Default | Role | Internal mapping | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| `enrich` | boolean | Optional | `false` | Executable | Normalized to `workflow_values["enrich"]` | Enables supported cross-reference enrichment when usable cross-reference fields exist. |
| `max_workers` | integer | Optional | `5` | Executable | Normalized to `workflow_values["workers"]` and passed to workflow/enrichment calls | Mainly affects enrichment and extra API calls that use worker pools. |
| `total_retries` | integer | Optional | `3` | Executable | Normalized to `workflow_values["retries"]`; used to initialize `UniprotInterface(total_retries=...)` and passed to workflow/enrichment calls | Retry behavior depends on the called interface. |
| `chembl_pages_to_fetch` | integer | Optional | `-1` | Executable for ChEMBL workflow fetches | Passed to ChEMBL workflow acquisition as `pages_to_fetch` | `-1` fetches all available ChEMBL pages. Positive values cap the number of pages. `0` and values below `-1` are rejected. |
| `merge_results` | boolean | Optional | `false` | Descriptive metadata | Normalized to `workflow_values["merge_results"]` and written to metadata/summary | Query-composition combines results independently of this descriptive flag. |
| `uniprot_timeout` | number or null | Optional | `null` | Executable | Normalized to `workflow_values["uniprot_timeout"]` and passed to UniProt fetches | `null` uses the interface default timeout. |
| `debug` | boolean | Optional | `false` | Executable | Normalized to `workflow_values["debug"]` | Enables debug logging when true. |

For ChEMBL workflows, `chembl_pages_to_fetch: -1` is the default and means fetch all available pages until ChEMBL stops returning `page_meta.next`. Positive integers cap the number of pages. `limit` is records per page, not total records and not a page count. Large ChEMBL queries can take longer when all pages are fetched; use a positive page cap for quick validation runs.

For IC50 activity queries, the ChEMBL workflow constrains `standard_type` to `IC50` and applies numeric `standard_value` filters for exact values or requested ranges. IC50 macros default to `standard_units=nM`; an explicit unit may be added, for example `ic50:0-10 AND standard_units:uM` or `ic50:0-10 AND standard_units:nM=very_high_potency` in query composition. The numeric range is interpreted in the selected ChEMBL `standard_units`; no unit conversion is applied.

The GUI exposes this syntax through the compound-only **ChEMBL IC50 activity builder** in Query First and Query Composition. The builder accepts ranges, comparisons, and exact values; `standard_units` is optional.

```yaml
dataset:
  name: chembl_ic50_activity_composition
  description: Compound bioactivity dataset grouped by IC50 potency ranges using ChEMBL activity records.
  modality: compound
  mode: query_composition
  primary_data_source: chembl

query:
  value: "ic50:0-10 AND standard_units:nM=very_high_potency,ic50:10-100 AND standard_units:nM=high_potency,ic50:100-1000 AND standard_units:nM=moderate_potency"
  description: Retrieve ChEMBL IC50 activity records grouped into labeled potency ranges.
```

### `harmonization`

Harmonization fields describe expected tabular columns and reporting-related
behavior. Except for the documented deterministic ID and sequence reporting
uses, they are preserved as descriptor metadata while exported data stays unchanged.
The NiceGUI `Metadata fields` control accepts comma-separated values and emits
`metadata_fields` as a YAML list.

| Field | Type | Required | Default | Role | Internal mapping | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| `id_column` | string or null | Optional | `null` | Executable for tabular exports | Normalized to `workflow_values["id_column"]` and used by export helpers | Adds deterministic IDs to exported tabular results when the column is absent. In-memory data stays unchanged. |
| `label_column` | string or null | Optional | `null` | Descriptive | Preserved in metadata and summary | Query-composition currently writes labels to `_label`; exported column names stay unchanged. |
| `sequence_column` | string or null | Optional | `null` | Generated reporting aid | Used to calculate `reporting.unique_sequences` when tabular outputs contain the named column | Exported columns stay unchanged. |
| `unique_sequence_strategy` | string or null | Optional | `null` | Descriptive | Preserved in metadata and summary | Deduplication is handled elsewhere for now. |
| `metadata_fields` | list of strings | Optional | omitted | Descriptive | Preserved in metadata and summary | Exported columns stay unchanged. |

### `export`

| Field | Type | Required | Default | Role | Internal mapping | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| `output_dir` | string or null | Optional if `dataset.name` is present | `results/{dataset.name}` | Executable | Normalized to `workflow_values["output"]` | Required by merged workflow values after defaults are applied. |
| `format` | string | Optional | `csv` | Executable | Normalized to `workflow_values["export_format"]` | Supported values are `csv`, `json`, `xml`, and `parquet`. |
| `include_metadata` | boolean | Optional | `true` | Executable | Normalized to `workflow_values["include_metadata"]` | Controls whether the manifest JSON is written. |
| `include_summary` | boolean | Optional | `true` | Executable | Normalized to `workflow_values["include_summary"]` | Controls whether the run summary YAML is written. |
| `manifest_file` | string or null | Optional | `metadata.json` | Executable | Normalized to `workflow_values["manifest_file"]` | The file content is JSON regardless of extension. |
| `summary_file` | string or null | Optional | `run_summary.yml` | Executable | Normalized to `workflow_values["summary_file"]` | The file content is YAML regardless of extension. |
| `result_files` | any YAML value | Optional | omitted | Descriptive | Preserved in the export descriptor | Output filenames are derived from result labels such as `uniprot_results`. |

`dataframe` is not a public export format. Use `csv`, `json`, `xml`, or `parquet` in YAML and CLI export options.

### `reporting`

`reporting` is a free-form mapping with YAML-safe values: null, strings, numbers, booleans, dates, lists, and dictionaries with string keys.

| Field | Type | Required | Default | Role | Internal mapping | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| `workflow_execution_time_seconds` | number or null | Optional | generated | Generated | Overwritten with measured duration | Descriptor value is replaced after execution. |
| `retrieved_records` | integer or null | Optional | generated when rows are known | Generated | Set from exported primary result row counts | Only available for tabular primary outputs that report rows. |
| `unique_sequences` | integer or null | Optional | generated when possible | Generated | Set from unique values in `harmonization.sequence_column` | Only available when a sequence column is configured and present in tabular primary outputs. |
| `notes` | string or null | Optional | `null` | Descriptive | Preserved unless overwritten by user/metadata processing | Does not affect execution. |
| other fields | YAML-safe values | Optional | omitted | Descriptive | Preserved in metadata and summary | Unsupported value types are rejected. |

## Forbidden Fields

These YAML fields are not supported:

| Forbidden field | Reason | Alternative |
| --- | --- | --- |
| `version` | Old root key | Use `schema_version: "workflow-v1"`. |
| `kind` | Old root key | Use the structured sections. |
| `workflow` | Old root key | Use the structured sections. |
| `dispatch_mode` | Removed workflow mode key | Use `dataset.mode` in YAML or `--mode` in the CLI. |
| `dispatch` | Removed workflow mode key | Use `dataset.mode` in YAML or `--mode` in the CLI. |
| `method` | Removed workflow mode key | Use `dataset.mode` in YAML or `--mode` in the CLI. |
| `query.type` | Query types are not implemented in YAML | Use `query.value`. |
| `query.filters` | Structured query filters are not implemented | Put executable filtering in `query.value` and descriptive notes in `query.filtering_strategy`. |

Credential-like keys are rejected anywhere in the YAML descriptor. Do not put credentials in YAML.

Forbidden credential examples:

- `api_key`
- `access_key`
- `password`
- `email`
- `token`
- `secret`
- `BIOSEQ_DL_BIOGRID_API_KEY`
- `BIOSEQ_DL_BRENDA_EMAIL`
- `BIOSEQ_DL_BRENDA_PASSWORD`
- `BIOSEQ_DL_REFSEQ_EMAIL`

Credentials must be provided through environment variables or `.env` files, not workflow YAML.

## Outputs

Workflow runs can produce:

- Data result files, such as `uniprot_results.csv`, `chembl_results.csv`,
  `pubchem_results.csv`, or `chebi_results.csv`.
- Enrichment files, named from enrichment result labels when enrichment data exists.
- A metadata manifest, default `metadata.json`, when `export.include_metadata` is true.
- A compact run summary, default `run_summary.yml`, when `export.include_summary` is true.

The metadata manifest includes:

- a tool identity block with the tool name, distribution name, import package name, and version;
- raw workflow metadata returned by the workflow implementation;
- the original descriptor;
- the normalized descriptor after CLI overrides and defaults;
- normalized executable workflow values;
- execution status and timing;
- output file metadata;
- reporting metrics.

Executable PubChem and ChEBI compound runs also record the query source prefix,
query resource, query model, request plan, and normalized record count in the
workflow metadata. The run summary copies the source and request plan into its
query section.

The run summary includes:

- the same tool identity block;
- dataset and query information;
- execution status, timing, enrichment, retry, and worker settings;
- export settings;
- output filenames and tabular row/column counts when available;
- reporting metrics;
- optional resources, harmonization, and descriptive extension sections.

Execution status values are:

- `success`: no metadata errors were detected.
- `completed_with_errors`: result outputs exist, but metadata contains errors.
- `failed`: execution failed, or metadata contains an error and no primary result output exists.

Primary UniProt request failures raise an error and the CLI exits non-zero. When an output directory is known, failure metadata and/or a failure summary are written according to `include_metadata` and `include_summary`.

If `harmonization.id_column` is set, exported tabular outputs for CSV, Parquet, and JSON receive a deterministic ID column when that column is not already present. Empty outputs and labels such as `none` or `null` are not exported as result files.

## Example: Minimal Protein Query Workflow

```yaml
schema_version: "workflow-v1"

dataset:
  name: antimicrobial_reviewed_proteins
  description: Reviewed UniProt protein records retrieved with an antimicrobial query.
  modality: protein
  mode: query_first
  primary_data_source: uniprot

query:
  value: "antimicrobial AND reviewed:true"
  description: Retrieve reviewed UniProt protein entries matching an antimicrobial query.
  filtering_strategy: >
    Filtering is encoded in the UniProt-compatible query string.

execution:
  enrich: false
  max_workers: 5
  total_retries: 3
  debug: true

harmonization:
  id_column: "_id"

export:
  output_dir: "results/protein_antimicrobial_reviewed"
  format: csv
  include_metadata: true
  include_summary: true
  manifest_file: "metadata.json"
  summary_file: "run_summary.yml"
```

## Example: Disease-Oriented UniProt Query

```yaml
schema_version: "workflow-v1"

dataset:
  name: uniprot_breast_cancer_proteins
  description: Reviewed UniProt protein records associated with breast cancer disease annotations.
  modality: protein
  mode: query_first
  primary_data_source: uniprot

query:
  value: "cc_disease:breast cancer AND reviewed:true"
  description: Retrieve reviewed UniProt entries associated with breast cancer.
  filtering_strategy: >
    Disease filtering is encoded directly in the UniProt-compatible query string
    using the cc_disease field.

execution:
  enrich: false
  max_workers: 5
  total_retries: 3

harmonization:
  id_column: "_id"

export:
  output_dir: "results/uniprot_breast_cancer_proteins"
  format: parquet
  include_metadata: true
  include_summary: true
  manifest_file: "metadata.json"
  summary_file: "run_summary.yml"
```

## Future Workflow YAML Features

These features are not part of the current executable workflow behavior.
They are documented as possible future extensions and must not be used as active fields in executable examples until implementation and tests exist.

Do not reintroduce these fields into runnable examples as though they control
execution. If a future implementation makes one of these fields executable,
update the implementation, tests, examples, and this documentation together.

| Future feature | Fields or sections | Purpose | Current status |
| --- | --- | --- | --- |
| Resource-driven routing | `resources.primary`, `resources.integration` | Allow YAML descriptors to explicitly select primary and secondary databases for execution. | Not an execution driver in the current workflow. Routing comes from `dataset.modality`, `dataset.mode`, and the current workflow implementation. |
| Interaction retrieval configuration | `interaction_retrieval` | Allow explicit configuration of PPI or PLI retrieval sources and strategies. | Do not include it in executable YAML unless implementation and tests exist for that behavior. |
| Activity retrieval configuration | `activity_retrieval` | Allow explicit activity type, units, thresholds, and range strategies for ChEMBL-like workflows. | Use only the currently supported executable query syntax in `query.value`. |
| Chemical metadata integration | `chemical_metadata_integration` | Allow explicit enrichment of compound metadata from chemical sources. | Future feature unless the workflow code supports it directly and tests cover it. |
| Protein target integration | `protein_target_integration` | Allow explicit target metadata enrichment from protein sources. | Future feature unless the workflow code supports it directly and tests cover it. |
| Temperature enrichment | `temperature_enrichment` | Allow explicit temperature metadata retrieval or enrichment. | Future feature unless the workflow code supports it directly and tests cover it. |
| Cross-source integration | `cross_source_integration` | Allow explicit integration rules across multiple databases. | Future feature unless the workflow code supports it directly and tests cover it. |
| Runtime reporting fields in YAML | `reporting.workflow_execution_time_seconds`, `reporting.retrieved_records`, `reporting.unique_sequences` | Represent measured outputs from workflow execution. | Generated outputs, not user-authored input fields. They should appear in metadata or summaries generated after execution, not in executable YAML examples. |
| Planned export filename control | `export.result_files` | Allow user-defined output filenames. | Future feature unless current code supports it directly. Output filenames currently derive from result labels. |

## Validation Notes

The schema above is based on the current implementation in:

- `bioseq_dl/cli/workflows.py`
- `bioseq_dl/core/workflow/main_workflow.py`
- `bioseq_dl/core/export.py`

Important current limitations:

- `resources.integration` is descriptive only.
- `execution.merge_results` is metadata only.
- Domain-specific extension sections are descriptive only.
- Compound workflows execute ChEMBL and PubChem queries plus ChEBI entity ID/name searches.
  ChEBI advanced filters, ontology searches, and structure searches remain pending.
- `harmonization.metadata_fields`, `label_column`, and `unique_sequence_strategy` describe expected structure; output filtering, renaming, merging, and deduplication come from supported workflow logic.
- `query.fields` is sent to UniProt as the fetch `fields` parameter, but parsing currently uses the workflow parser's field map rather than this value as an output-column filter.
- Output filenames are derived from result labels, not `export.result_files`.

Keep preserved-only and future-facing fields out of runnable examples unless an
example is specifically demonstrating metadata preservation. This includes
descriptive `resources` entries, domain-specific extension sections,
descriptor-provided `reporting` placeholders, `execution.merge_results`,
and `export.result_files`. Descriptive harmonization fields may be included when
they accurately document expected output columns or reporting intent.

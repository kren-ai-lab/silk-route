# Workflow YAML Descriptors

BioSeqDownloader workflow YAML files are structured dataset descriptors for reproducible data acquisition runs. They configure the current workflow CLI, describe the dataset objective, preserve query and execution context, and generate metadata plus a compact run summary.

They are not a generic workflow engine, a multi-step pipeline language, or a plugin system. The current implementation maps a specific set of descriptor fields to `bioseq-dl workflow run` and preserves the rest as descriptive metadata.

## Execution Model

The workflow execution strategy is configured with:

```yaml
dataset:
  mode: query_first
```

Valid `dataset.mode` values are:

- `query_first`
- `query_composition`

## CLI Override Priority

When a YAML descriptor and CLI options are both provided, values are resolved in this order:

1. Explicit CLI arguments.
2. YAML descriptor values.
3. Existing workflow defaults.

Examples:

```bash
bioseq-dl workflow run --config examples/protein-dataset-construction.yml
bioseq-dl workflow run --config examples/protein-dataset-construction.yml -o result_override
bioseq-dl workflow run --config examples/protein-dataset-construction.yml -e csv
```

Validated example descriptors are:

- `examples/protein-dataset-construction.yml`
- `examples/interaction-aware-dataset-construction.yml`
- `examples/compound-dataset-construction.yml`

## Top-Level Sections

Required top-level sections:

| Section | Type | Role |
| --- | --- | --- |
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

These extension sections are preserved in metadata and run summary output. They do not currently activate extra APIs or retrieval steps.

Unknown top-level sections are rejected. For example, `resoures` fails because the accepted section is `resources`.

## Field Reference

Field roles:

- **Executable**: changes the workflow run.
- **Descriptive**: accepted and preserved, but does not currently change execution.
- **Generated**: filled or overwritten by BioSeqDownloader during reporting.

### `dataset`

| Field | Type | Required | Default | Role | Internal mapping | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| `name` | string | Required only when `export.output_dir` is absent | none | Descriptive and defaulting | Used to derive `output` as `results/{dataset.name}` when `export.output_dir` is not set | Does not otherwise affect retrieval. |
| `description` | string or null | Optional | `null` | Descriptive | Preserved in descriptor metadata and summary | Does not affect execution. |
| `modality` | string | Required | none | Executable | Normalized to `workflow_values["modality"]` and passed to `MainWorkflow.run(modality=...)` | Must be `protein`, `compound`, or `interaction`. |
| `mode` | string | Required | none | Executable | Normalized to `workflow_values["mode"]` and passed to `MainWorkflow.run(mode=...)` | Must be `query_first` or `query_composition`. |
| `primary_data_source` | string or null | Optional | `null` | Descriptive | Preserved in metadata and summary | Does not route the workflow. |
| `interaction_type` | string or null | Optional | `null` | Executable for interaction workflows | Passed as `interaction_type` | Required by the interaction modality handler; expected values are handled by the workflow code, currently `protein-protein` or `protein-ligand`. |

### `query`

| Field | Type | Required | Default | Role | Internal mapping | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| `value` | non-empty string | Required | none | Executable | Normalized to `workflow_values["query"]` | For `query_first`, this is the query string. For `query_composition`, use comma-separated labeled pairs such as `temperature:99=temp_99,temperature:98=temp_98`. |
| `description` | string or null | Optional | `null` | Descriptive | Preserved in metadata and summary | Does not affect query execution. |
| `filtering_strategy` | string or null | Optional | `null` | Descriptive | Preserved in metadata and summary | Filtering must be encoded in `query.value`; `query.filters` is not supported. |
| `fields` | null, string, or list of strings | Optional | `null` | Executable | Normalized to `workflow_values["fields"]` and passed to the UniProt fetch as the API `fields` parameter | It controls requested UniProt fields. It is not currently used as a parser column filter. |
| `crossref_fields` | null, string, or list of strings | Optional | `null` | Executable when enrichment is enabled | Normalized to `workflow_values["crossref_fields"]` and passed to the enrichment path | Used with `execution.enrich`; unavailable or unsupported cross-reference fields may produce no enrichment output. |
| `include_isoform` | boolean | Optional | `false` | Executable | Normalized to `workflow_values["include_isoform"]` and passed to UniProt fetches | Applies to UniProt requests. |

### `resources`

| Field | Type | Required | Default | Role | Internal mapping | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| `primary` | list of strings | Optional | omitted | Descriptive | Preserved in metadata and summary | Does not choose the API. Current routing comes from `dataset.modality`, `dataset.mode`, and query interpretation. |
| `integration` | list of strings | Optional | omitted | Descriptive | Preserved in metadata and summary | Does not automatically activate integration APIs. Use query cross-reference fields and `execution.enrich` for supported enrichment behavior. |

### `execution`

| Field | Type | Required | Default | Role | Internal mapping | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| `enrich` | boolean | Optional | `true` | Executable | Normalized to `workflow_values["enrich"]` | Enables supported cross-reference enrichment when usable cross-reference fields exist. |
| `max_workers` | integer | Optional | `5` | Executable | Normalized to `workflow_values["workers"]` and passed to workflow/enrichment calls | Mainly affects enrichment and extra API calls that use worker pools. |
| `total_retries` | integer | Optional | `3` | Executable | Normalized to `workflow_values["retries"]`; used to initialize `UniprotInterface(total_retries=...)` and passed to workflow/enrichment calls | Retry behavior depends on the called interface. |
| `chembl_pages_to_fetch` | integer | Optional | `-1` | Executable for ChEMBL workflow fetches | Passed to ChEMBL workflow acquisition as `pages_to_fetch` | `-1` fetches all available ChEMBL pages. Positive values cap the number of pages. `0` and values below `-1` are rejected. |
| `merge_results` | boolean | Optional | `false` | Descriptive metadata | Normalized to `workflow_values["merge_results"]` and written to metadata/summary | Does not currently trigger automatic result merging. Query-composition combines results independently of this flag. |
| `uniprot_timeout` | number or null | Optional | `null` | Executable | Normalized to `workflow_values["uniprot_timeout"]` and passed to UniProt fetches | `null` uses the interface default timeout. |
| `debug` | boolean | Optional | `false` | Executable | Normalized to `workflow_values["debug"]` | Enables debug logging when true. |

For ChEMBL workflows, `chembl_pages_to_fetch: -1` is the default and means fetch all available pages until ChEMBL stops returning `page_meta.next`. `limit` is records per page, not total records and not a page count.

### `harmonization`

| Field | Type | Required | Default | Role | Internal mapping | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| `id_column` | string or null | Optional | `null` | Executable for tabular exports | Normalized to `workflow_values["id_column"]` and used by export helpers | Adds deterministic IDs to exported DataFrame results when the column is absent. It does not mutate in-memory data. |
| `label_column` | string or null | Optional | `null` | Descriptive | Preserved in metadata and summary | Query-composition currently writes labels to `_label`; this field does not rename that column. |
| `sequence_column` | string or null | Optional | `null` | Generated reporting aid | Used to calculate `reporting.unique_sequences` when tabular outputs contain the named column | Does not alter exported columns. |
| `unique_sequence_strategy` | string or null | Optional | `null` | Descriptive | Preserved in metadata and summary | Does not currently change deduplication or export behavior. |
| `metadata_fields` | list of strings | Optional | omitted | Descriptive | Preserved in metadata and summary | Does not currently filter output columns. |

### `export`

| Field | Type | Required | Default | Role | Internal mapping | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| `output_dir` | string or null | Optional if `dataset.name` is present | `results/{dataset.name}` | Executable | Normalized to `workflow_values["output"]` | Required by merged workflow values after defaults are applied. |
| `format` | string | Optional | `csv` | Executable | Normalized to `workflow_values["export_format"]` | Supported values are `csv`, `json`, `xml`, and `parquet`. BioSeqDownloader may use pandas DataFrames internally, but `dataframe` is not a valid file export format. |
| `include_metadata` | boolean | Optional | `true` | Executable | Normalized to `workflow_values["include_metadata"]` | Controls whether the manifest JSON is written. |
| `include_summary` | boolean | Optional | `true` | Executable | Normalized to `workflow_values["include_summary"]` | Controls whether the run summary YAML is written. |
| `manifest_file` | string or null | Optional | `metadata.json` | Executable | Normalized to `workflow_values["manifest_file"]` | The file content is JSON regardless of extension. |
| `summary_file` | string or null | Optional | `run_summary.yml` | Executable | Normalized to `workflow_values["summary_file"]` | The file content is YAML regardless of extension. |
| `result_files` | any YAML value | Optional | omitted | Descriptive | Preserved in the export descriptor | Does not currently control result filenames. Output filenames are derived from result labels such as `uniprot_results`. |

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
| `version` | Old root key | Use the structured `dataset`, `query`, `execution`, and `export` sections. |
| `kind` | Old root key | Use the structured sections. |
| `workflow` | Old root key | Use the structured sections. |
| `method` | Old workflow mode name | Use `dataset.mode`. |
| `dispatch` | Old workflow mode name | Use `dataset.mode`. |
| `dispatch_mode` | Old workflow mode name | Use `dataset.mode`. |
| `query.type` | Query types are not implemented in YAML | Use `query.value`. |
| `query.filters` | Structured query filters are not implemented | Put executable filtering in `query.value` and descriptive notes in `query.filtering_strategy`. |
| `export.format: dataframe` | `dataframe` is an internal Python object type, not a file export format | Use `export.format: csv`. |

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

- Data result files, such as `uniprot_results.csv`, `uniprot_results.parquet`, or `chembl_results.csv`.
- Enrichment files, named from enrichment result labels when enrichment data exists.
- A metadata manifest, default `metadata.json`, when `export.include_metadata` is true.
- A compact run summary, default `run_summary.yml`, when `export.include_summary` is true.

The metadata manifest includes:

- raw workflow metadata returned by the workflow implementation;
- the original descriptor;
- the normalized descriptor after CLI overrides and defaults;
- normalized executable workflow values;
- execution status and timing;
- output file metadata;
- reporting metrics.

The run summary includes:

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

If `harmonization.id_column` is set, exported DataFrame outputs for CSV, Parquet, and JSON receive a deterministic ID column when that column is not already present. Empty outputs and labels such as `none` or `null` are not exported as result files.

## Example: Minimal Protein Query Workflow

```yaml
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

resources:
  primary:
    - uniprot
  integration: []

execution:
  enrich: false
  max_workers: 5
  total_retries: 3
  merge_results: false
  debug: true

harmonization:
  id_column: "_id"
  label_column: null
  sequence_column: "sequence"
  metadata_fields:
    - accession
    - protein_name
    - organism_name
    - sequence

export:
  output_dir: "results/protein_antimicrobial_reviewed"
  format: csv
  include_metadata: true
  include_summary: true
  manifest_file: "metadata.json"
  summary_file: "run_summary.yml"

reporting:
  workflow_execution_time_seconds: null
  retrieved_records: null
  unique_sequences: null
  notes: >
    Values are filled after execution from exported result files and metadata.
```

## Example: Disease-Oriented UniProt Query

```yaml
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

resources:
  primary:
    - uniprot
  integration: []

execution:
  enrich: false
  max_workers: 5
  total_retries: 3
  merge_results: false

harmonization:
  id_column: "_id"
  label_column: null
  sequence_column: "sequence"
  metadata_fields:
    - accession
    - protein_name
    - gene_primary
    - organism_name
    - sequence
    - diseases

export:
  output_dir: "results/uniprot_breast_cancer_proteins"
  format: parquet
  include_metadata: true
  include_summary: true
  manifest_file: "metadata.json"
  summary_file: "run_summary.yml"

reporting:
  workflow_execution_time_seconds: null
  retrieved_records: null
  unique_sequences: null
  notes: >
    Disease annotations are parsed from structured UniProt DISEASE comments
    when the response includes disease objects.
```

## Validation Notes

The schema above is based on the current implementation in:

- `bioseq_dl/cli/workflows.py`
- `bioseq_dl/core/workflow/main_workflow.py`
- `bioseq_dl/core/export.py`

Important current limitations:

- `resources.integration` is descriptive only.
- `execution.merge_results` is metadata only.
- Domain-specific extension sections are descriptive only.
- `harmonization.metadata_fields`, `label_column`, and `unique_sequence_strategy` do not filter, rename, merge, or deduplicate output.
- `query.fields` is sent to UniProt as the fetch `fields` parameter, but parsing currently uses the workflow parser's field map rather than this value as an output-column filter.
- `export.result_files` does not control output filenames.

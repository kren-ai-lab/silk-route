# TODO

## Base interface (`core/interfaces/base.py`)
- [ ] Make `parse` return a consistent structure across interfaces (DataFrame
  conversion currently branches on list-vs-dict to guess the shape).
- [ ] Add an option to skip caching empty results.
- [ ] `fetch_batch`: merge the inner per-subquery metadata from delegated
  `fetch_single` calls instead of recording batch-granularity only.

## UniProt (`core/interfaces/uniprot.py`)
- [ ] Make `from_db`/`to_db` optional and only valid when `auto_db=False`.
- [ ] Improve the `submit_stream` docstring for `include_isoform` / `download`.
- [ ] Drop `bytes`/`str` from `parse`'s return type once the ElementTree path is assured.
- [ ] Optionally include `intActId` (a/b) in interaction extraction
  (`extract_interactions`); currently omitted.

## KEGG (`core/interfaces/kegg.py`)
- [ ] Fix cache dedup: a multi-entry query caches a combined response, but
  fetching a single entry then writes a separate cache file instead of reusing it.
- [ ] Decide multiple-entries-per-request vs one-at-a-time.
- [ ] Add more methods (DDI, Link).
- [ ] Verify json-vs-text handling for functions other than `get`.

## BioGRID (`core/interfaces/biogrid.py`)
- [ ] Add more fields/methods from the BioGRID docs.
- [ ] Fix `format=tab2` (non-JSON) requests — only JSON works today (low priority).
  Repro:
  ```python
  query = {
      "accessKey": biogrid_api_key,
      "geneList": ["1148170", "1148186", "112090"],
      "searchBiogridIds": True,
      "format": "tab2",
  }
  ```
  fails with `Extra data: line 1 column 8 (char 7)` for URL
  `.../interactions?accessKey={KEY}&geneList=1148170|1148186|112090&searchBiogridIds=True&format=tab2`
  (the response decoder assumes JSON).

## Reactome (`core/interfaces/reactome.py`)
- [ ] Review methods beyond `data-discover`.

## InterPro (`core/interfaces/interpro.py`)
- [ ] Add modifier definitions.
- [ ] Update `METHODS` for `fetch()` (uses a unique query type).

## Workflow (`core/workflow/main_workflow.py`)
- [ ] Document the `pages_to_fetch=-1` and `limit=100` defaults at their call site.
- [ ] Normalize the metadata returned by `query_first`/`query_composition`
  (still a flexible dict mixing counters, nested parts, and enrichment).
- [ ] Reintroduce declarative pipelines / custom step overrides
  (`self.pipelines`, `self.step_overrides`), currently disabled.

## CrossRef enrichment (`core/crossref_enricher.py`)
- [ ] Verify the DataFrame concat path in `_process_dataframe`.
- [ ] Verify the XML export/merge path in `_process_dataframe`.

## Chemical search (`cli/interfaces/chemical_search_query.py`)
- [ ] Preserve provenance from both PubChem stages (`pug/compound` then
  `pug_view/compound`); `dict.update` currently keeps only the last.

## Metadata provenance
- [ ] Add `source_url` / `api_version` to fetch metadata.

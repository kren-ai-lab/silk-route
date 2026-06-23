"""UniProt API interface."""

import json
import re
import time
import xml.etree.ElementTree as ET
import zlib
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import parse_qs, urlencode, urlparse

import niquests
import pandas as pd

from bioseq_dl.constants.databases import DATABASES, UNIPROT
from bioseq_dl.core.exceptions import RequestError
from bioseq_dl.core.interfaces.base import BaseAPIInterface
from bioseq_dl.core.metadata import FetchMetadata, RequestInfo, current_tool
from bioseq_dl.core.utils.uniprot_auxiliary_methods import (
    extract_active_sites,
    extract_database_terms,
    extract_diseases,
    extract_domains,
    extract_ec_numbers,
    extract_gene_names,
    extract_interactions,
    extract_keywords,
    extract_ph,
    extract_references,
    extract_simple,
    extract_temperature,
    extract_variants,
)
from bioseq_dl.core.utils.xmlhandler import dict_to_elementtree
from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.interfaces.uniprot")

API_URL = "https://rest.uniprot.org"
POLLING_INTERVAL = 3


class UniprotInterface(BaseAPIInterface):
    """UniProt universal protein knowledge base API interface."""

    API_NAME = "UniProt"
    DB_CONFIG = UNIPROT

    def __init__(
        self,
        total_retries: int = 5,
        timeout: float = 60,
        cache_dir: str | None = None,
        config_dir: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the UniProt interface.

        UniProt uses a bespoke id-mapping / stream flow rather than the generic
        ``fetch`` machinery, but inherits ``BaseAPIInterface`` for shared session,
        cache, and directory handling. ``use_config`` defaults to ``False`` since
        UniProt ships no per-database YAML config.
        """
        kwargs.setdefault("use_config", False)
        super().__init__(cache_dir=cache_dir, config_dir=config_dir, total_retries=total_retries, **kwargs)
        self.timeout = timeout
        self.db_config: dict[str, dict[str, Any]] = {
            "uniprot": {
                "patterns": [
                    r"^[A-N,R-Z][0-9][A-Z][A-Z, 0-9][A-Z, 0-9][0-9]$",
                    r"^[A-N,R-Z][0-9][A-Z][A-Z, 0-9][A-Z, 0-9][0-9][A-Z][A-Z, 0-9][A-Z, 0-9][0-9]$",
                    r"^[OPQ][0-9][A-Z0-9][A-Z0-9][A-Z0-9][0-9]$",
                ],
                "from_db": "UniProtKB_AC-ID",
                "to_db": "UniProtKB",
            },
            "pdb": {"patterns": [r"^[0-9][A-Z0-9]{3}$"], "from_db": "PDB", "to_db": "UniProtKB"},
        }

        # Base field map for parsing UniProt results
        # To add more possible fields, just add them to this map.
        # Remember to add the extractor function if needed.
        # The extractor function should take the data and return the desired value.
        # See utils.py for available extractor functions.
        self.field_map_base: dict[str, tuple[str, Callable[..., Any]]] = {
            "accession": ("primaryAccession", extract_simple),
            "protein_name": ("proteinDescription.recommendedName.fullName.value", extract_simple),
            "ec": ("proteinDescription.recommendedName.ecNumbers", extract_ec_numbers),
            "organism": ("organism.scientificName", extract_simple),
            "gene_primary": ("genes", extract_gene_names),
            "organism_id": ("organism.taxonId", extract_simple),
            "lineage": ("organism.lineage", extract_simple),
            "sequence": ("sequence.value", extract_simple),
            "length": ("sequence.length", extract_simple),
            "alphafold_ids": ("uniProtKBCrossReferences", extract_database_terms),
            "biogrid_ids": ("uniProtKBCrossReferences", extract_database_terms),
            "brenda_ids": ("uniProtKBCrossReferences", extract_database_terms),
            "chebi_ids": ("comments", extract_database_terms),
            "chembl_ids": ("uniProtKBCrossReferences", extract_database_terms),
            "go_terms": ("uniProtKBCrossReferences", extract_database_terms),
            "interpro_ids": ("uniProtKBCrossReferences", extract_database_terms),
            "kegg_ids": ("uniProtKBCrossReferences", extract_database_terms),
            "panther_ids": ("uniProtKBCrossReferences", extract_database_terms),
            "pathwaycommons_ids": ("uniProtKBCrossReferences", extract_database_terms),
            "pdb_ids": ("uniProtKBCrossReferences", extract_database_terms),
            "pfam_ids": ("uniProtKBCrossReferences", extract_database_terms),
            "pride_ids": ("uniProtKBCrossReferences", extract_database_terms),
            "reactome_ids": ("uniProtKBCrossReferences", extract_database_terms),
            "refseq_ids": ("uniProtKBCrossReferences", extract_database_terms),
            "rhea_ids": ("comments", extract_database_terms),
            "sabiork_ids": ("uniProtKBCrossReferences", extract_database_terms),
            "string_ids": ("uniProtKBCrossReferences", extract_database_terms),
            "references": ("references", extract_references),
            "diseases": ("comments", extract_diseases),
            "active_sites": ("features", extract_active_sites),
            "temperature": ("comments", extract_temperature),
            "ph": ("comments", extract_ph),
            "domains": ("features", extract_domains),
            "variants": ("features", extract_variants),
            "interactions": ("comments", extract_interactions),
            "keyword": ("keywords", extract_keywords),
        }

    def check_response(self, response: niquests.Response) -> None:
        """Check for HTTP errors in a UniProt response and re-raise if present."""
        try:
            response.raise_for_status()
        except niquests.HTTPError:
            log.exception("HTTP error occurred: %s - %s", response.status_code, response.text)
            log.exception("Response JSON: %s", response.json())
            raise

    def submit_id_mapping(self, from_db: str, to_db: str, ids: list) -> str:
        """Submit an ID mapping job and return the job ID."""
        request = niquests.post(
            f"{API_URL}/idmapping/run",
            data={"from": from_db, "to": to_db, "ids": ",".join(ids)},
            timeout=self.timeout,
        )
        self.check_response(request)
        return request.json()["jobId"]

    def print_progress_batches(self, batch_index: int, size: int, total: int) -> None:
        """Log batch download progress."""
        n_fetched = min((batch_index + 1) * size, total)
        log.info("Fetched: %s / %s", n_fetched, total)

    def combine_batches(self, all_results: Any, batch_results: Any, file_format: str) -> Any:
        """Combine incremental batch results into a single accumulated result."""
        if file_format == "json":
            for key in ("results", "failedIds"):
                if batch_results.get(key):
                    all_results[key] += batch_results[key]
        elif file_format == "tsv":
            return all_results + batch_results[1:]
        else:
            return all_results + batch_results
        return all_results

    def decode_results(self, response: niquests.Response, file_format: str, compressed: bool) -> Any:
        """Decode a UniProt API response into JSON, XML, or plain text."""
        content = response.content or b""
        raw = zlib.decompress(content, 16 + zlib.MAX_WBITS) if compressed else content

        # xlsx is binary: never UTF-8-decode it.
        if file_format == "xlsx":
            return [raw]

        # Decode text only now (xlsx already returned), keeping the original
        # source per branch: response.json()/response.text for uncompressed.
        text = raw.decode("utf-8") if compressed else (response.text or "")
        if file_format == "json":
            return json.loads(text) if compressed else response.json()
        if file_format == "tsv":
            return [line for line in text.split("\n") if line]
        if file_format == "xml":
            return [text]
        return text

    def get_xml_namespace(self, element: ET.Element) -> str:
        """Extract the XML namespace from an element tag."""
        m = re.match(r"\{(.*)\}", element.tag)
        return m.groups()[0] if m else ""

    def merge_xml_results(self, xml_results: list) -> bytes:
        """Merge a list of XML byte strings into one root element."""
        merged_root = ET.fromstring(xml_results[0])  # noqa: S314  # trusted UniProt API response
        for result in xml_results[1:]:
            root = ET.fromstring(result)  # noqa: S314  # trusted UniProt API response
            for child in root.findall("{http://uniprot.org/uniprot}entry"):
                merged_root.insert(-1, child)
        ET.register_namespace("", self.get_xml_namespace(merged_root[0]))
        return ET.tostring(merged_root, encoding="utf-8", xml_declaration=True)

    def get_id_mapping_results_search(self, url: str) -> Any:
        """Fetch ID mapping search results for a given URL."""
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        file_format = query["format"][0] if "format" in query else "json"
        if "size" in query:
            size = int(query["size"][0])
        else:
            size = 500
            query["size"] = [str(size)]
        compressed = query["compressed"][0].lower() == "true" if "compressed" in query else False
        parsed = parsed._replace(query=urlencode(query, doseq=True))
        url = parsed.geturl()
        request = self.session.get(url, timeout=self.timeout)
        self.check_response(request)
        results = self.decode_results(request, file_format, compressed)
        total = int(request.headers["x-total-results"])
        self.print_progress_batches(0, size, total)
        for i, batch in enumerate(self.get_batch(request, file_format, compressed), 1):
            results = self.combine_batches(results, batch, file_format)
            self.print_progress_batches(i, size, total)
        if file_format == "xml":
            return self.merge_xml_results(results)
        return results

    def get_id_mapping_results_link(self, job_id: str) -> str:
        """Return the redirect URL for a completed ID mapping job."""
        url = f"{API_URL}/idmapping/details/{job_id}"
        request = self.session.get(url, timeout=self.timeout)
        self.check_response(request)
        return request.json()["redirectURL"]

    def get_next_link(self, headers: Mapping[str, str]) -> str | None:
        """Extract the 'next' link from pagination headers."""
        re_next_link = re.compile(r'<(.+)>; rel="next"')
        if "Link" in headers:
            match = re_next_link.match(headers["Link"])
            if match:
                return match.group(1)
        return None

    def get_batch(
        self, batch_response: niquests.Response, file_format: str, compressed: bool
    ) -> Iterator[Any]:
        """Yield decoded result batches following pagination links."""
        batch_url = self.get_next_link(batch_response.headers)
        while batch_url:
            batch_response = self.session.get(batch_url, timeout=self.timeout)
            batch_response.raise_for_status()
            yield self.decode_results(batch_response, file_format, compressed)
            batch_url = self.get_next_link(batch_response.headers)

    def check_id_mapping_results_ready(self, job_id: str) -> bool:
        """Poll until an ID mapping job is complete, then return True."""
        while True:
            log.debug("Checking status for job ID: %s", job_id)
            request = self.session.get(f"{API_URL}/idmapping/status/{job_id}", timeout=self.timeout)
            self.check_response(request)
            j = request.json()
            if "jobStatus" in j:
                if j["jobStatus"] == "RUNNING":
                    log.info("Job is still running. Retrying in %ss", POLLING_INTERVAL)
                    time.sleep(POLLING_INTERVAL)
                else:
                    log.exception("Job failed with status: %s", j["jobStatus"])
                    status = j["jobStatus"]
                    raise RequestError(status)
            else:
                return bool(j["results"] or j["failedIds"])

    def identify_id_type(self, id_str: str) -> str:
        """Identifica el tipo de ID basado en patrones regex."""
        if not isinstance(id_str, str):
            return ""

        for db_type, config in self.db_config.items():
            for pattern in config["patterns"]:
                if re.fullmatch(pattern, id_str):
                    return db_type
        return ""

    def group_ids_by_type(self, ids: list[str]) -> dict[str, list[str]]:
        """Agrupa IDs por su tipo detectado."""
        grouped = {db_type: [] for db_type in self.db_config}
        grouped["unknown"] = []

        for id_str in ids:
            if not isinstance(id_str, str):
                continue

            id_type = self.identify_id_type(id_str)
            if id_type in grouped:
                grouped[id_type].append(id_str)
            else:
                grouped["unknown"].append(id_str)
        return grouped

    def download_batch(
        self,
        dataset: pd.DataFrame,
        column_ids: str,
        auto_db: bool = False,
        from_db: str = "UniProtKB_AC-ID",
        to_db: str = "UniProtKB",
        batch_size: int = 5000,
    ) -> tuple[list[dict], dict]:
        """Download data from UniProt in batches based on a DataFrame of IDs.

        Args:
            dataset (pd.DataFrame): DataFrame containing the IDs.
            column_ids (str): Column name in the DataFrame with the IDs.
            auto_db (bool): Whether to automatically detect the database type.
            from_db (str): Database to convert from (used if auto_db is False).
            to_db (str): Database to convert to (used if auto_db is False).
            batch_size (int): Number of IDs to process in each batch.

        """
        ids = dataset[column_ids].dropna().unique().tolist()

        results: list[dict] = []

        if auto_db:
            # Automatically detect and group IDs, then process EVERY group and
            # accumulate both results and metadata (earlier groups were previously
            # overwritten, silently dropping their data for mixed-ID inputs).
            id_groups = self.group_ids_by_type(ids)
            log.debug(
                "Auto db has identified the following ID groups: %s",
                {k: len(v) for k, v in id_groups.items()},
            )
            meta = FetchMetadata()
            groups: list[dict[str, Any]] = []
            for db_type, id_list in id_groups.items():
                if not id_list or db_type == "unknown":
                    continue

                config = self.db_config[db_type]
                group_results, group_metadata = self.process_id_batch(
                    ids=id_list,
                    from_db=config["from_db"],
                    to_db=config["to_db"],
                    batch_size=batch_size,
                    db_type=db_type,
                )
                results.extend(group_results)
                group_meta = FetchMetadata.from_dict(group_metadata)
                meta = meta.merge(group_meta)
                groups.append(
                    {
                        "db_type": db_type,
                        "from_db": config["from_db"],
                        "to_db": config["to_db"],
                        "num_batches": group_meta.extra.get("num_batches", 0),
                        "failed_ids_count": group_meta.extra.get("failed_ids_count", 0),
                    }
                )
            # Per-group flat fields (from_db/to_db/db_type) are ambiguous across
            # groups; expose the per-group breakdown instead.
            meta.extra = {"batch_size": batch_size, "groups": groups}
        else:
            # Manually use the provided from_db/to_db parameters.
            group_results, group_metadata = self.process_id_batch(
                ids=ids, from_db=from_db, to_db=to_db, batch_size=batch_size, db_type="manual"
            )
            results = group_results
            meta = FetchMetadata.from_dict(group_metadata)

        # Augment with the input-query provenance specific to the batch download.
        meta.extra.update(
            {
                "query_values": dataset[column_ids].tolist(),
                "total_rows": len(dataset),
                "columns": dataset.columns.tolist(),
                "id_column": column_ids,
                "auto_db": auto_db,
            }
        )

        return results, meta.to_dict()

    def process_id_batch(
        self, ids: list[str], from_db: str, to_db: str, batch_size: int, db_type: str
    ) -> tuple[list[dict], dict]:
        """Procesa un lote de IDs de un tipo específico."""
        downloader = UniprotInterface()
        time_started = time.time()
        job_id = None
        results = []
        total = len(ids)
        log.info("Processing %s %s IDs in batches of %s", total, db_type, batch_size)

        for batch_index, start in enumerate(range(0, total, batch_size)):
            batch = ids[start : start + batch_size]
            job_id = downloader.submit_id_mapping(from_db, to_db, batch)

            if downloader.check_id_mapping_results_ready(job_id):
                link = downloader.get_id_mapping_results_link(job_id)
                search = downloader.get_id_mapping_results_search(link)

                # Add information about the source to the results
                if isinstance(search, dict):
                    for result in search.get("results", []):
                        result["source_db"] = db_type
                    results.append(search)

            self.print_progress_batches(batch_index, batch_size, total)

        time_finished = time.time()
        failed_ids = [fid for res in results for fid in res.get("failedIds", [])]
        mapped_records = [record for res in results for record in res.get("results", [])]
        meta = FetchMetadata(
            tool=current_tool(),
            started_at=datetime.fromtimestamp(time_started, tz=UTC).isoformat(),
            finished_at=datetime.fromtimestamp(time_finished, tz=UTC).isoformat(),
            request=RequestInfo(api_name=self.API_NAME, method="idmapping", option=None),
            data_info=self._build_data_info(mapped_records),
            extra={
                "batch_size": batch_size,
                "num_batches": (len(ids) + batch_size - 1) // batch_size,
                "from_db": from_db,
                "to_db": to_db,
                "db_type": db_type,
                "failed_ids_count": len(failed_ids),
            },
        )
        for fid in failed_ids:
            meta.failed.add(fid, {"id": fid}, "unmapped")

        return results, meta.to_dict()

    def submit_stream(
        self,
        query: str,
        fields: str,
        sort: str,
        include_isoform: bool | None = False,
        download: bool | None = False,
        method: str = "uniprotkb",
        timeout: float | None = None,
    ) -> tuple[dict, dict]:
        """Submit a query to the Uniprot stream API.

        Args:
            query (str): The query string.
            fields (str): The fields to include in the response.
            sort (str): The sorting order.
            include_isoform (bool, optional): Whether to include isoforms. Defaults to False.
            download (bool, optional): Whether to download the results. Defaults to False.
            method (str): UniProt endpoint to query (default: "uniprotkb").
            timeout (float, optional): Request timeout in seconds. Defaults to the interface timeout.

        Returns:
            niquests.Response: The response object.

        """
        parameters = {
            "query": query,
            "fields": fields,
            "sort": sort,
            "includeIsoform": str(include_isoform),
            "download": str(download),
            "format": "json",
        }
        metadata: dict[str, Any] = {}
        response = None

        headers = {"Accept": "application/json"}

        effective_timeout = self.timeout if timeout is None else timeout
        endpoint_path = f"/{method}/stream"

        for attempt in range(self.total_retries):
            try:
                time_started = time.time()
                started_at = datetime.fromtimestamp(time_started, tz=UTC).isoformat()
                log.info("UniProt stream request started (path=%s)", endpoint_path)
                log.debug(
                    "UniProt stream request details: query=%s fields=%s sort=%s include_isoform=%s "
                    "timeout=%s "
                    "started_at=%s",
                    query,
                    fields,
                    sort,
                    include_isoform,
                    effective_timeout,
                    started_at,
                )
                response = niquests.get(
                    f"{API_URL}/{method}/stream",
                    params=parameters,
                    headers=headers,
                    timeout=effective_timeout,
                )
                response.raise_for_status()
                time_finished = time.time()
                finished_at = datetime.fromtimestamp(time_finished, tz=UTC).isoformat()
                elapsed_seconds = time_finished - time_started
                size_header = response.headers.get("Content-Length")
                response_size_bytes = (
                    int(size_header)
                    if size_header and size_header.isdigit()
                    else len(response.content or b"")
                )
                payload = response.json()
                results_count = 0
                if isinstance(payload, dict):
                    results_count = len(payload.get("results", []))
                elif isinstance(payload, list):
                    results_count = len(payload)
                log.info(
                    "UniProt stream response received (status=%s elapsed=%.2fs)",
                    response.status_code,
                    elapsed_seconds,
                )
                log.debug(
                    "UniProt stream response details: finished_at=%s size_bytes=%s results=%s",
                    finished_at,
                    response_size_bytes,
                    results_count,
                )
                meta = FetchMetadata(
                    tool=current_tool(),
                    started_at=started_at,
                    finished_at=finished_at,
                    request=RequestInfo(api_name=self.API_NAME, method=method, option=None),
                    data_info=self._build_data_info(
                        payload.get("results", []) if isinstance(payload, dict) else payload
                    ),
                    extra={
                        "api_url": API_URL,
                        "status_code": response.status_code,
                        "response_size_bytes": response_size_bytes,
                        "total_results": results_count,
                        "attempts": attempt + 1,
                        "query": query,
                        "fields": fields,
                        "sort": sort,
                        "include_isoform": include_isoform,
                        "download": download,
                        "timeout_seconds": effective_timeout,
                    },
                )
                if isinstance(payload, dict):
                    for failed_id in payload.get("failedIds", []):
                        meta.failed.add(failed_id, query, "unmapped")
                metadata = meta.to_dict()
            except niquests.exceptions.Timeout as e:
                if attempt < self.total_retries - 1:
                    log.warning(
                        "UniProt stream request timed out after %ss on attempt %s/%s. Retrying...",
                        effective_timeout,
                        attempt + 1,
                        self.total_retries,
                    )
                    time.sleep(POLLING_INTERVAL)
                else:
                    message = (
                        f"UniProt request timed out after {effective_timeout}s. "
                        "The query may be too broad or the UniProt API may be slow. "
                        "Try narrowing the query, using --no-enrich, or increasing --uniprot-timeout."
                    )
                    log.exception(message)
                    raise TimeoutError(message) from e
            except niquests.exceptions.RequestException as e:
                if attempt < self.total_retries - 1:
                    log.info("Attempt %s failed: %s. Retrying...", attempt + 1, e)
                    time.sleep(POLLING_INTERVAL)
                else:
                    message = f"UniProt request failed after all retry attempts: {e}"
                    log.exception(message)
                    raise RuntimeError(message) from e
            else:
                return payload, metadata
        return {}, {}

    def adapt_field_map(
        self, field_map: dict[str, tuple[str, Callable[..., Any]]], use_prefix: bool = False
    ) -> dict[str, tuple[str, Callable[..., Any]]]:
        """Adapt the field map to include a prefix if needed."""
        if not use_prefix:
            return field_map

        adapted_map = {}
        for key, (path, extractor) in field_map.items():
            new_path = f"to.{path}" if not path.startswith("to.") else path
            adapted_map[key] = (new_path, extractor)
        return adapted_map

    def _parse_result(self, result: dict, extract_fields: list[str] | None) -> dict:
        """Parse a single UniProt result into a flat ``{field: value}`` dict.

        Fields that can't be extracted are kept as ``None`` so the aggregate
        field-coverage stats in :meth:`parse` can tell present from missing.
        """
        parsed = {}

        # Change field_map if 'from' and 'to' keys are present
        if "from" in result and "to" in result:
            field_map = self.adapt_field_map(self.field_map_base, use_prefix=True)
        else:
            field_map = self.field_map_base

        log.debug("Parsing result with field map: %s", field_map.keys())
        for field, (path, extractor) in field_map.items():
            try:
                # Navigate through the path (e.g. 'to.proteinDescription...')
                data = result
                for raw_key in path.split("."):
                    key = int(raw_key) if raw_key.isdigit() else raw_key
                    data = data.get(key, {})

                # Extract the value using the specific function
                if field in DATABASES:
                    parsed[field] = extractor(data, DATABASES[field]) if data else None
                else:
                    parsed[field] = extractor(data) if data else None
            except (KeyError, AttributeError, IndexError):
                parsed[field] = None

        # Apply filtering
        if extract_fields is not None:
            parsed = {k: v for k, v in parsed.items() if k in extract_fields}

        return parsed

    @staticmethod
    def _aggregate_parse_metadata(
        parsed: list[dict], failed_records: int, extract_fields: list[str] | None
    ) -> dict:
        """Aggregate per-record parse results into dataset-level metadata.

        Replaces the old behavior of returning only the first record's metadata.
        ``field_coverage`` maps each requested field to how many records actually
        carried a non-null value — surfacing sparse fields across the whole result.
        """
        records = [p for p in parsed if p.get("status") != "failed"]
        if extract_fields is not None:
            requested = list(extract_fields)
        else:
            # No explicit selection: use the union of fields seen across records.
            requested = list({field for record in records for field in record})
        return {
            "requested_fields": requested,
            "records": len(records),
            "failed_records": failed_records,
            "field_coverage": {
                field: sum(1 for record in records if record.get(field) is not None) for field in requested
            },
        }

    def parse(  # ty: ignore[invalid-method-override]  # type: ignore[bad-override]
        self,
        results: dict | list[dict],
        extract_fields: list[str] | None,
        format: Literal["json", "dataframe", "xml"] = "json",  # noqa: A002
    ) -> tuple[(pd.DataFrame | list[dict] | bytes | str | ET.ElementTree), dict | list[dict]]:
        """Parse UniProt JSON results into a DataFrame.

        Args:
            results (Dict): The JSON results from UniProt.
            extract_fields (Optional[List[str]]): List of fields to extract.
            format (Literal["json", "dataframe", "xml"]): The output format.

        """
        parsed: list = []
        failed_records = 0

        def _accumulate(res: dict) -> None:
            """Collect parsed results + failed-id placeholders from one results dict."""
            nonlocal failed_records
            parsed.extend(self._parse_result(result, extract_fields) for result in res.get("results", []))
            for failed_id in res.get("failedIds", []):
                parsed.append({"uniprot_id": failed_id, "status": "failed"})
                failed_records += 1

        if isinstance(results, dict):
            _accumulate(results)
        elif isinstance(results, list):
            for res in results:
                if isinstance(res, dict):
                    _accumulate(res)
                else:
                    log.warning("Tried to parse non-dict result: %s, skipping.", type(res))

        meta_out = self._aggregate_parse_metadata(parsed, failed_records, extract_fields)
        if format == "dataframe":
            return pd.DataFrame(parsed).dropna(axis=1, how="all"), meta_out
        if format == "xml":
            return dict_to_elementtree(parsed, root_tag="results"), meta_out
        return parsed, meta_out

    def fetch(self, query: str | dict | list, *, method: str = "uniprotkb", **kwargs: Any) -> Any:
        """UniProt does not use the generic fetch machinery.

        Data is retrieved through the dedicated flows instead:
        ``submit_stream`` (query search) and ``download_batch`` /
        ``submit_id_mapping`` (id mapping). ``parse`` then shapes the results.
        """
        msg = (
            "UniprotInterface does not implement generic fetch(); use submit_stream() "
            "for query search or download_batch()/submit_id_mapping() for id mapping."
        )
        raise NotImplementedError(msg)

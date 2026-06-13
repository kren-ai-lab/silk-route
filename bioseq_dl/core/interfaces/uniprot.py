import json
import re
import time
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime
from typing import Literal
from urllib.parse import parse_qs, urlencode, urlparse
from xml.etree import ElementTree

import pandas as pd
import requests
from tqdm import tqdm

from bioseq_dl.constants.databases import DATABASES, UNIPROT
from bioseq_dl.core.interfaces.base import BaseAPIInterface
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
    API_NAME = "UniProt"
    DB_CONFIG = UNIPROT

    def __init__(
        self,
        total_retries: int = 5,
        timeout: float = 60,
        cache_dir: str | None = None,
        config_dir: str | None = None,
        **kwargs,
    ):
        """Initialize the UniProt interface.

        UniProt uses a bespoke id-mapping / stream flow rather than the generic
        ``fetch`` machinery, but inherits ``BaseAPIInterface`` for shared session,
        cache, and directory handling. ``use_config`` defaults to ``False`` since
        UniProt ships no per-database YAML config.
        """
        kwargs.setdefault("use_config", False)
        super().__init__(cache_dir=cache_dir, config_dir=config_dir, total_retries=total_retries, **kwargs)
        self.timeout = timeout
        self.db_config = {
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
        self.field_map_base = {
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

    def check_response(self, response):
        try:
            response.raise_for_status()
        except requests.HTTPError:
            log.error(f"HTTP error occurred: {response.status_code} - {response.text}")
            log.error(f"Response JSON: {response.json()}")
            raise

    def submit_id_mapping(self, from_db: str, to_db: str, ids: list):
        request = requests.post(
            f"{API_URL}/idmapping/run",
            data={"from": from_db, "to": to_db, "ids": ",".join(ids)},
            timeout=self.timeout,
        )
        self.check_response(request)
        return request.json()["jobId"]

    def print_progress_batches(self, batch_index, size, total):
        n_fetched = min((batch_index + 1) * size, total)
        log.info(f"Fetched: {n_fetched} / {total}")

    def combine_batches(self, all_results, batch_results, file_format):
        if file_format == "json":
            for key in ("results", "failedIds"):
                if batch_results.get(key):
                    all_results[key] += batch_results[key]
        elif file_format == "tsv":
            return all_results + batch_results[1:]
        else:
            return all_results + batch_results
        return all_results

    def decode_results(self, response, file_format, compressed):
        if compressed:
            decompressed = zlib.decompress(response.content, 16 + zlib.MAX_WBITS)
            if file_format == "json":
                j = json.loads(decompressed.decode("utf-8"))
                return j
            if file_format == "tsv":
                return [line for line in decompressed.decode("utf-8").split("\n") if line]
            if file_format == "xlsx":
                return [decompressed]
            if file_format == "xml":
                return [decompressed.decode("utf-8")]
            return decompressed.decode("utf-8")
        if file_format == "json":
            return response.json()
        if file_format == "tsv":
            return [line for line in response.text.split("\n") if line]
        if file_format == "xlsx":
            return [response.content]
        if file_format == "xml":
            return [response.text]
        return response.text

    def get_xml_namespace(self, element):
        m = re.match(r"\{(.*)\}", element.tag)
        return m.groups()[0] if m else ""

    def merge_xml_results(self, xml_results):
        merged_root = ElementTree.fromstring(xml_results[0])
        for result in xml_results[1:]:
            root = ElementTree.fromstring(result)
            for child in root.findall("{http://uniprot.org/uniprot}entry"):
                merged_root.insert(-1, child)
        ElementTree.register_namespace("", self.get_xml_namespace(merged_root[0]))
        return ElementTree.tostring(merged_root, encoding="utf-8", xml_declaration=True)

    def get_id_mapping_results_search(self, url):
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        file_format = query["format"][0] if "format" in query else "json"
        if "size" in query:
            size = int(query["size"][0])
        else:
            size = 500
            query["size"] = size
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

    def get_id_mapping_results_link(self, job_id):
        url = f"{API_URL}/idmapping/details/{job_id}"
        request = self.session.get(url, timeout=self.timeout)
        self.check_response(request)
        return request.json()["redirectURL"]

    def get_next_link(self, headers):
        re_next_link = re.compile(r'<(.+)>; rel="next"')
        if "Link" in headers:
            match = re_next_link.match(headers["Link"])
            if match:
                return match.group(1)

    def get_batch(self, batch_response, file_format, compressed):
        batch_url = self.get_next_link(batch_response.headers)
        while batch_url:
            batch_response = self.session.get(batch_url, timeout=self.timeout)
            batch_response.raise_for_status()
            yield self.decode_results(batch_response, file_format, compressed)
            batch_url = self.get_next_link(batch_response.headers)

    def check_id_mapping_results_ready(self, job_id):
        while True:
            log.debug(f"Checking status for job ID: {job_id}")
            request = self.session.get(f"{API_URL}/idmapping/status/{job_id}", timeout=self.timeout)
            self.check_response(request)
            j = request.json()
            if "jobStatus" in j:
                if j["jobStatus"] == "RUNNING":
                    log.info(f"Job is still running. Retrying in {POLLING_INTERVAL}s")
                    time.sleep(POLLING_INTERVAL)
                else:
                    log.exception(f"Job failed with status: {j['jobStatus']}")
                    raise Exception(j["jobStatus"])
            else:
                return bool(j["results"] or j["failedIds"])

    def identify_id_type(self, id_str: str) -> str:
        """Identifica el tipo de ID basado en patrones regex"""
        if not isinstance(id_str, str):
            return ""

        for db_type, config in self.db_config.items():
            for pattern in config["patterns"]:
                if re.fullmatch(pattern, id_str):
                    return db_type

                return ""

    def group_ids_by_type(self, ids: list[str]) -> dict[str, list[str]]:
        """Agrupa IDs por su tipo detectado"""
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

        results = []
        metadata = {}
        batch_metadata = {}

        if auto_db:
            # Automatically detect and group IDs
            id_groups = self.group_ids_by_type(ids)

            log.debug(
                f"Auto db has identified the following ID groups: { {k: len(v) for k, v in id_groups.items()} }"
            )
            for db_type, id_list in id_groups.items():
                if not id_list or db_type == "unknown":
                    continue

                config = self.db_config[db_type]
                results, batch_metadata = self.process_id_batch(
                    ids=id_list,
                    from_db=config["from_db"],
                    to_db=config["to_db"],
                    batch_size=batch_size,
                    db_type=db_type,
                )
        else:
            # Manually use the provided from_db/to_db parameters
            results, batch_metadata = self.process_id_batch(
                ids=ids, from_db=from_db, to_db=to_db, batch_size=batch_size, db_type="manual"
            )

        metadata["search_process"] = batch_metadata
        metadata["search_params"] = {
            "query": {
                "type": type(pd.DataFrame()),
                "value": dataset[column_ids].tolist(),
                "total_rows": len(dataset),
                "columns": dataset.columns.tolist(),
                "id_column": column_ids,
            },
            "from_db": from_db,
            "to_db": to_db,
            "auto_db": auto_db,
            "batch_size": batch_size,
        }

        return results, metadata

    def process_id_batch(
        self, ids: list[str], from_db: str, to_db: str, batch_size: int, db_type: str
    ) -> tuple[list[dict], dict]:
        """Procesa un lote de IDs de un tipo específico"""
        downloader = UniprotInterface()
        metadata = {}
        time_started = time.time()
        job_id = None
        results = []
        progress_bar = tqdm(
            range(len(ids)),
            desc=f"Processing {db_type} IDs",
            total=len(ids),
            dynamic_ncols=True,
            ncols=0,
            bar_format="{l_bar}{bar} {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {desc}",
        )

        for start in range(0, len(ids), batch_size):
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

            progress_bar.update(len(batch))

        metadata["time_taken_seconds"] = time.time() - time_started
        metadata["started_at"] = datetime.fromtimestamp(time_started).isoformat()
        metadata["batch_size"] = batch_size
        metadata["num_batches"] = (len(ids) + batch_size - 1) // batch_size
        metadata["failed_ids_count"] = sum(len(res.get("failedIds", [])) for res in results)
        metadata["failed_ids"] = [fid for res in results for fid in res.get("failedIds", [])]

        return results, metadata

    def show_results(self, results: list[dict], raw=False):
        # Deliberate stdout helper for interactive inspection of fetched results.
        if results:
            if raw:
                for result in results:
                    print(result)  # noqa: T201
            else:
                print(f"{len(results)} results to show")  # noqa: T201
        else:
            print("No results to show")  # noqa: T201

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
            timeout (float, optional): Request timeout in seconds. Defaults to the interface timeout.
            format (str, optional): The format of the response. Defaults to "json".

        Returns:
            requests.Response: The response object.

        """
        parameters = {
            "query": query,
            "fields": fields,
            "sort": sort,
            "includeIsoform": include_isoform,
            "download": download,
            "format": "json",
        }
        metadata = {}
        response = None

        headers = {"Accept": "application/json"}

        effective_timeout = self.timeout if timeout is None else timeout
        endpoint_path = f"/{method}/stream"

        for attempt in range(self.total_retries):
            try:
                time_started = time.time()
                started_at = datetime.fromtimestamp(time_started).isoformat()
                log.info("UniProt stream request started (path=%s)", endpoint_path)
                log.debug(
                    "UniProt stream request details: query=%s fields=%s sort=%s include_isoform=%s timeout=%s started_at=%s",
                    query,
                    fields,
                    sort,
                    include_isoform,
                    effective_timeout,
                    started_at,
                )
                response = requests.get(
                    f"{API_URL}/{method}/stream",
                    params=parameters,
                    headers=headers,
                    timeout=effective_timeout,
                )
                response.raise_for_status()
                time_finished = time.time()
                finished_at = datetime.fromtimestamp(time_finished).isoformat()
                elapsed_seconds = time_finished - time_started
                size_header = response.headers.get("Content-Length")
                response_size_bytes = (
                    int(size_header) if size_header and size_header.isdigit() else len(response.content)
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
                metadata["search_process"] = {
                    "time_taken_seconds": elapsed_seconds,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "status_code": response.status_code,
                    "response_size_bytes": response_size_bytes,
                    "total_results": results_count,
                    "attempts": attempt + 1,
                }
                metadata["search_params"] = {
                    "api_url": API_URL,
                    "query": {
                        "type": type(query),
                        "value": query,
                    },
                    "fields": fields,
                    "sort": sort,
                    "include_isoform": include_isoform,
                    "download": download,
                    "timeout_seconds": effective_timeout,
                }

                return payload, metadata
            except requests.exceptions.Timeout as e:
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
                    log.error(message)
                    raise TimeoutError(message) from e
            except requests.exceptions.RequestException as e:
                if attempt < self.total_retries - 1:
                    log.info(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                    time.sleep(POLLING_INTERVAL)
                else:
                    message = f"UniProt request failed after all retry attempts: {e}"
                    log.error(message)
                    raise RuntimeError(message) from e

    def adapt_field_map(self, field_map: dict[str, tuple], use_prefix=False):
        """Adapt the field map to include a prefix if needed"""
        if not use_prefix:
            return field_map

        adapted_map = {}
        for key, (path, extractor) in field_map.items():
            new_path = f"to.{path}" if not path.startswith("to.") else path
            adapted_map[key] = (new_path, extractor)
        return adapted_map

    def _parse_result(self, result: dict, extract_fields: list[str] | None) -> tuple[dict, dict]:
        """Parse a single UniProt result"""
        parsed = {}
        field_map = {}
        metadata = {}

        # Change field_map if 'from' and 'to' keys are present
        if "from" in result and "to" in result:
            field_map = self.adapt_field_map(self.field_map_base, use_prefix=True)
        else:
            field_map = self.field_map_base

        log.debug(f"Parsing result with field map: {field_map.keys()}")
        for field, (path, extractor) in field_map.items():
            try:
                # Navigate through the path (e.g. 'to.proteinDescription...')
                data = result
                for key in path.split("."):
                    if key.isdigit():  # For array indices
                        key = int(key)
                    data = data.get(key, {})

                # Extract the value using the specific function
                if field in DATABASES.keys():
                    parsed[field] = extractor(data, DATABASES[field]) if data else None
                else:
                    parsed[field] = extractor(data) if data else None
            except (KeyError, AttributeError, IndexError):
                parsed[field] = None

        # Apply filtering
        if extract_fields is not None:
            parsed = {k: v for k, v in parsed.items() if k in extract_fields}

        metadata["extract_fields"] = extract_fields if extract_fields is not None else list(field_map.keys())
        metadata["parsed_fields"] = list(parsed.keys())
        metadata["failed_fields"] = [k for k in field_map.keys() if k not in parsed.keys()]

        return parsed, metadata

    # TODO eliminar bytes y str cuando ET este asegurado
    def parse(
        self,
        results: dict | list[dict],
        extract_fields: list[str] | None,
        format: Literal["json", "dataframe", "xml"] = "json",
    ) -> tuple[(pd.DataFrame | list[dict] | bytes | str | ET.ElementTree), dict | list[dict]]:
        """Parse UniProt JSON results into a DataFrame

        Args:
            results (Dict): The JSON results from UniProt.
            extract_fields (Optional[List[str]]): List of fields to extract.
            format (Literal["json", "dataframe", "xml"]): The output format.

        """
        parsed = []
        metadata = []

        # Process successful results
        if isinstance(results, dict):
            for result in results.get("results", []):
                p, m = self._parse_result(result, extract_fields)
                parsed.append(p)
                metadata.append(m)

            # Process failed IDs
            for failed_id in results.get("failedIds", []):
                parsed.append({"uniprot_id": failed_id, "status": "failed"})
                metadata.append({})
        elif isinstance(results, list):
            for res in results:
                if isinstance(res, dict):
                    for result in res.get("results", []):
                        p, m = self._parse_result(result, extract_fields)
                        parsed.append(p)
                        metadata.append(m)

                    # Process failed IDs
                    for failed_id in res.get("failedIds", []):
                        parsed.append({"uniprot_id": failed_id, "status": "failed"})
                        metadata.append({})
                else:
                    log.warning(f"Tried to parse non-dict result: {type(res)}, skipping.")
                    continue

        if format == "dataframe":
            return pd.DataFrame(parsed).dropna(axis=1, how="all"), metadata[0] if len(
                metadata
            ) > 0 else metadata
        if format == "xml":
            # xml_bytes = dicttoxml(parsed, custom_root='results', attr_type=False)
            # return xml_bytes, metadata[0] if len(metadata) > 0 else metadata

            return dict_to_elementtree(parsed, root_tag="results"), metadata[0] if len(
                metadata
            ) > 0 else metadata

        return parsed, metadata[0] if len(metadata) > 0 else metadata

    def fetch(self, query: str | dict | list, *, method: str = "uniprotkb", **kwargs):
        """UniProt does not use the generic fetch machinery.

        Data is retrieved through the dedicated flows instead:
        ``submit_stream`` (query search) and ``download_batch`` /
        ``submit_id_mapping`` (id mapping). ``parse`` then shapes the results.
        """
        raise NotImplementedError(
            "UniprotInterface does not implement generic fetch(); use submit_stream() "
            "for query search or download_batch()/submit_id_mapping() for id mapping."
        )

    def query_usage(self) -> str:
        return (
            "UniProt interface. Retrieve data via submit_stream(query, fields, sort) for "
            "query/field search, or download_batch(dataframe, column_ids) / submit_id_mapping("
            "from_db, to_db, ids) for id mapping. Use parse(results, extract_fields, format) "
            "to shape results into json / dataframe / xml."
        )

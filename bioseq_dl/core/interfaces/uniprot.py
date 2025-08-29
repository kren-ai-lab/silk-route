import requests, re, zlib, json, time
from typing import List, Dict, Optional
import csv
import pandas as pd
from tqdm import tqdm
from requests.adapters import HTTPAdapter, Retry
from xml.etree import ElementTree
from io import StringIO

from urllib.parse import urlparse, parse_qs, urlencode

from ..utils.uniprot_auxiliary_methods import (
    extract_simple,
    extract_ec_numbers,
    extract_gene_names,
    extract_database_terms,
    extract_references,
    extract_features,
    extract_keywords,
)

from ...constants.databases import DATABASES

API_URL = "https://rest.uniprot.org"
POLLING_INTERVAL = 3 

# TODO for some reason xref_string is not working

class UniprotBase():
    def __init__(self, total_retries=5):
        self.retries = Retry(total=total_retries, backoff_factor=0.25, status_forcelist=[ 500, 502, 503, 504 ])
        self.session = requests.Session()
        self.session.mount('https://', HTTPAdapter(max_retries=self.retries))

    def check_response(self, response):
        try:
            response.raise_for_status()
        except requests.HTTPError:
            print(response.json())
            raise

    def submit_id_mapping(self, from_db: str, to_db: str, ids: list):
        request = requests.post(
            f"{API_URL}/idmapping/run",
        data={"from": from_db, "to": to_db, "ids": ",".join(ids)},
        )
        self.check_response(request)
        return request.json()["jobId"]
    
    def print_progress_batches(self, batch_index, size, total):
        n_fetched = min((batch_index + 1) * size, total)
        print(f"Fetched: {n_fetched} / {total}")

    def combine_batches(self, all_results, batch_results, file_format):
        if file_format == "json":
            for key in ("results", "failedIds"):
                if key in batch_results and batch_results[key]:
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
            elif file_format == "tsv":
                return [line for line in decompressed.decode("utf-8").split("\n") if line]
            elif file_format == "xlsx":
                return [decompressed]
            elif file_format == "xml":
                return [decompressed.decode("utf-8")]
            else:
                return decompressed.decode("utf-8")
        elif file_format == "json":
            return response.json()
        elif file_format == "tsv":
            return [line for line in response.text.split("\n") if line]
        elif file_format == "xlsx":
            return [response.content]
        elif file_format == "xml":
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
        compressed = (
            query["compressed"][0].lower() == "true" if "compressed" in query else False
        )
        parsed = parsed._replace(query=urlencode(query, doseq=True))
        url = parsed.geturl()
        request = self.session.get(url)
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
        request = self.session.get(url)
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
            batch_response = self.session.get(batch_url)
            batch_response.raise_for_status()
            yield self.decode_results(batch_response, file_format, compressed)
            batch_url = self.get_next_link(batch_response.headers)

    def check_id_mapping_results_ready(self, job_id):
        while True:
            request = self.session.get(f"{API_URL}/idmapping/status/{job_id}")
            self.check_response(request)
            j = request.json()
            if "jobStatus" in j:
                if j["jobStatus"] == "RUNNING":
                    #print(f"Retrying in {POLLING_INTERVAL}s")
                    time.sleep(POLLING_INTERVAL)
                else:
                    raise Exception(j["jobStatus"])
            else:
                return bool(j["results"] or j["failedIds"])


class UniprotInterface(UniprotBase):
    def __init__(self, total_retries=5):
        super().__init__(total_retries)
        self.db_config = {
            'uniprot': {
                'patterns': [r'^[A-N,R-Z][0-9][A-Z][A-Z, 0-9][A-Z, 0-9][0-9]$',
                            r'^[A-N,R-Z][0-9][A-Z][A-Z, 0-9][A-Z, 0-9][0-9][A-Z][A-Z, 0-9][A-Z, 0-9][0-9]$',
                            r'^[OPQ][0-9][A-Z0-9][A-Z0-9][A-Z0-9][0-9]$'],
                'from_db': 'UniProtKB_AC-ID',
                'to_db': 'UniProtKB'
            },
            'pdb': {
                'patterns': [r'^[0-9][A-Z0-9]{3}$'],
                'from_db': 'PDB',
                'to_db': 'UniProtKB'
            }
        }

        # Base field map for parsing UniProt results
        # To add more possible fields, just add them to this map.
        # Remember to add the extractor function if needed.
        # The extractor function should take the data and return the desired value.
        # See utils.py for available extractor functions.
        self.field_map_base = {
            'accession': ('primaryAccession', extract_simple),
            'protein_name': ('proteinDescription.recommendedName.fullName.value', extract_simple),
            'ec_numbers': ('proteinDescription.recommendedName.ecNumbers', extract_ec_numbers),
            'organism_name': ('organism.scientificName', extract_simple),
            'gene_primary': ('genes', extract_gene_names),
            'taxon_id': ('organism.taxonId', extract_simple),
            'ineage': ('organism.lineage', extract_simple),
            'sequence': ('sequence.value', extract_simple),
            'length': ('sequence.length', extract_simple),
            'alphafold_ids': ('uniProtKBCrossReferences', extract_database_terms),
            'biogrid_ids': ('uniProtKBCrossReferences', extract_database_terms),
            'brenda_ids': ('uniProtKBCrossReferences', extract_database_terms),
            'chebi_ids': ('comments', extract_database_terms),
            'chembl_ids': ('uniProtKBCrossReferences', extract_database_terms),
            'go_terms': ('uniProtKBCrossReferences', extract_database_terms),
            'interpro_ids': ('uniProtKBCrossReferences', extract_database_terms),
            'kegg_ids': ('uniProtKBCrossReferences', extract_database_terms),
            'panther_ids': ('uniProtKBCrossReferences', extract_database_terms),
            'pathwaycommons_ids': ('uniProtKBCrossReferences', extract_database_terms),
            'pdb_ids': ('uniProtKBCrossReferences', extract_database_terms),
            'pfam_ids': ('uniProtKBCrossReferences', extract_database_terms),
            'pride_ids': ('uniProtKBCrossReferences', extract_database_terms),
            'reactome_ids': ('uniProtKBCrossReferences', extract_database_terms),
            'refseq_ids': ('uniProtKBCrossReferences', extract_database_terms),
            'rhea_ids': ('comments', extract_database_terms),
            'string_ids': ('uniProtKBCrossReferences', extract_database_terms),
            'references': ('references', extract_references),
            'features': ('features', extract_features),
            'keywords': ('keywords', extract_keywords),
        }
        self.format = None
    
    def identify_id_type(self, id_str: str) -> str:
        """Identifica el tipo de ID basado en patrones regex"""
        if not isinstance(id_str, str):
            return ""
            
        for db_type, config in self.db_config.items():
            for pattern in config['patterns']:
                if re.fullmatch(pattern, id_str):
                    return db_type
                
                return ""

    def group_ids_by_type(self, ids: List[str]) -> Dict[str, List[str]]:
        """Agrupa IDs por su tipo detectado"""
        grouped = {db_type: [] for db_type in self.db_config}
        grouped['unknown'] = []
        
        for id_str in ids:
            if not isinstance(id_str, str):
                continue
                
            id_type = self.identify_id_type(id_str)
            if id_type in grouped:
                grouped[id_type].append(id_str)
            else:
                grouped['unknown'].append(id_str)
        return grouped


    def download_batch(
            self,
            dataset: pd.DataFrame, 
            column_ids: str, 
            auto_db: bool, 
            from_db: str, 
            to_db: str, 
            batch_size: int
            ):
        ids = dataset[column_ids].dropna().unique().tolist()

        results = []

        if auto_db:
            # Automatically detect and group IDs
            id_groups = self.group_ids_by_type(ids)
            
            for db_type, id_list in id_groups.items():
                if not id_list or db_type == 'unknown':
                    continue
                    
                config = self.db_config[db_type]
                results = self.process_id_batch(
                    ids=id_list,
                    from_db=config['from_db'],
                    to_db=config['to_db'],
                    batch_size=batch_size,
                    db_type=db_type
                )
        else:
            # Manually use the provided from_db/to_db parameters
            results = self.process_id_batch(
                ids=ids,
                from_db=from_db,
                to_db=to_db,
                batch_size=batch_size,
                db_type='manual'
            )
        
        return results

    def process_id_batch(
            self,
            ids: List[str], 
            from_db: str, 
            to_db: str, 
            batch_size: int, 
            db_type: str
        ):
        """Procesa un lote de IDs de un tipo específico"""
        downloader = UniprotInterface()
        results = []
        progress_bar = tqdm(
            range(0, len(ids)), 
            desc=f"Processing {db_type} IDs", 
            total=len(ids),
            dynamic_ncols=True,
            ncols=0,
            bar_format="{l_bar}{bar} {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {desc}"
        )
        
        for start in range(0, len(ids), batch_size):
            batch = ids[start:start+batch_size]
            job_id = downloader.submit_id_mapping(from_db, to_db, batch)
            
            if downloader.check_id_mapping_results_ready(job_id):
                link = downloader.get_id_mapping_results_link(job_id)
                search = downloader.get_id_mapping_results_search(link)
                
                # Add information about the source to the results
                if isinstance(search, dict):
                    for result in search.get('results', []):
                        result['source_db'] = db_type
                    results.append(search)
                    
            progress_bar.update(len(batch))
        
        return results

    def show_results(
            self,
            results: List[Dict],
            raw=False
        ):
        if results:
            if raw:
                for result in results:
                    print(result)
            else:
                print(f"{len(results)} results to show")
        else:
            print("No results to show")

    # TODO Add more formats like fasta
    def submit_stream(
            self, 
            query: str, 
            fields: str, 
            sort: str, 
            include_isoform: Optional[bool] = False, 
            download: Optional[bool] = False,
            format: Optional[str] = "json"
            ):
        """
        Submit a query to the Uniprot stream API.
        Args:
            query (str): The query string.
            fields (str): The fields to include in the response.
            sort (str): The sorting order.
            include_isoform (bool, optional): Whether to include isoforms. Defaults to False.
            download (bool, optional): Whether to download the results. Defaults to False.
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
            "format": format,
        }

        if format == "json":
            headers = {"Accept": "application/json"}
        elif format == "tsv":
            headers = {"Accept": "text/plain;format=tsv"}
        else:
            raise ValueError("Unsupported format. Supported formats are: json, xml, fasta, tsv.")
        
        self.format = format

        for attempt in range(self.retries.total):
            try:
                response = requests.get(
                    f"{API_URL}/uniprotkb/stream",
                    params=parameters,
                    headers=headers,
                )
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                if attempt < self.retries - 1:
                    print(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                    time.sleep(POLLING_INTERVAL)
                else:
                    print(f"All attempts failed: {e}.")
                    return response

    def parse_stream_response(self, query: str, response: requests.Response, extract_fields: Optional[List[str]]) -> pd.DataFrame:
        """
        Parse the response from the UniProt stream API depending on the format.
        Args:
            query (str): The query string.
            response (requests.Response): The response from the stream API.
            file_format (str): The format of the response (json, tsv, fasta).
            mapping (dict, optional): Mapping for parsing JSON response. Defaults to None.
        Returns:
            Parsed data in appropriate Python data structure.
        """
        return_df = pd.DataFrame()

        if self.format == "json":
            return_df = self.parse(response.json(), extract_fields)
        
        elif self.format == "tsv":
            tsv_data = response.text
            reader = csv.DictReader(StringIO(tsv_data), delimiter="\t")
            return_df = pd.DataFrame(reader)

        else:
            raise ValueError(f"Unsupported format: {self.format}")
        
        return_df.insert(0, "query", query)

        return return_df
    
    def adapt_field_map(self, field_map: Dict[str, tuple], use_prefix=False):
        """Adapt the field map to include a prefix if needed"""
        if not use_prefix:
            return field_map

        adapted_map = {}
        for key, (path, extractor) in field_map.items():
            new_path = f"to.{path}" if not path.startswith("to.") else path
            adapted_map[key] = (new_path, extractor)
        return adapted_map

    def _parse_result(self, result: Dict, extract_fields: Optional[List[str]]) -> Dict:
        """Parse a single UniProt result"""
        parsed = {}
        field_map = {}

        # Change field_map if 'from' and 'to' keys are present
        if 'from' in result and 'to' in result:
            field_map = self.adapt_field_map(self.field_map_base, use_prefix=True)
        else:
            field_map = self.field_map_base
        
        for field, (path, extractor) in field_map.items():
            try:
                # Navigate through the path (e.g. 'to.proteinDescription...')
                data = result
                for key in path.split('.'):
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

        return parsed

    def parse(self, results: Dict, extract_fields: Optional[List[str]]) -> pd.DataFrame:
        """Parse UniProt JSON results into a DataFrame"""
        parsed_data = []
        
        # Process successful results
        for result in results.get('results', []):
            parsed = self._parse_result(result, extract_fields)
            if 'source_db' in result:
                parsed['source_db'] = results.get('source_db', 'unknown')
            parsed_data.append(parsed)
            
        # Process failed IDs
        for failed_id in results.get('failedIds', []):
            parsed_data.append({
                'uniprot_id': failed_id,
                #'source_db': results.get('source_db', 'unknown'),
                'status': 'failed'
            })
            
        return pd.DataFrame(parsed_data).dropna(axis=1, how='all')
    
    def parse_results(self, results: List[Dict], extract_fields: Optional[List[str]]) -> pd.DataFrame:
        export_df = pd.DataFrame()

        for result in results:
            parsed_results = self.parse(result, extract_fields)
            export_df = pd.concat([export_df, parsed_results], ignore_index=True)

        return export_df

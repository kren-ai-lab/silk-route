"""PubChem API interface."""

import json
import urllib.parse
from typing import Any, ClassVar

from niquests import Request, Response
from niquests.exceptions import RequestException

# Add the import for your database in constants
from bioseq_dl.constants.databases import PUBCHEM
from bioseq_dl.constants.pubchem import COMPOUND_TEMPLATE, GENE_TEMPLATE, OPTIONS, PROTEIN_TEMPLATE
from bioseq_dl.core.exceptions import RequestError
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.pubchem")
WORKFLOW_COMPOUND_PROPERTIES_METHOD = "workflow/compound-properties"
WORKFLOW_COMPOUND_PROPERTIES = (
    "MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,InChI,InChIKey,IUPACName"
)
# Default Threshold for a similarity_2d search. The request builder and the cache-identifier
# builder must agree on this so an unset threshold and an explicit 90 map to one cache entry.
DEFAULT_SIMILARITY_THRESHOLD = 90

# PubChem has 2 main API access points: PUG-REST and PUG-View.
# PUG-REST is used for short requests with simple inputs and outputs.
# PUG-View is used for getting full reports, including third-party textual annotation.


class PubChemInterface(BaseAPIInterface):
    """PubChem compound and protein database API interface."""

    API_NAME = "PubChem"
    DB_CONFIG = PUBCHEM
    DEFAULT_OPTION: ClassVar[str | None] = "default"
    METHODS: ClassVar[dict[str, Any]] = {
        "pug/compound": {
            **dict.fromkeys(OPTIONS["pug/compound"], COMPOUND_TEMPLATE),
        },
        "pug/protein": {
            **dict.fromkeys(OPTIONS["pug/protein"], PROTEIN_TEMPLATE),
        },
        "pug/gene": {
            **dict.fromkeys(OPTIONS["pug/gene"], GENE_TEMPLATE),
        },
        "autocomplete": {
            "default": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "dictionary": (str, None, True),
                    "search_term": (str, None, True),
                    "output_format": (str, None, False),
                },
                "group_queries": [None],
                "separator": None,
            }
        },
        "pug_view/compound": {
            "default": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "cid": (str, None, True),
                },
                "group_queries": [None],
                "separator": None,
            }
        },
        "pug_view/protein": {
            "default": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "accession": (str, None, True),
                },
                "group_queries": [None],
                "separator": None,
            }
        },
        "pug_view/gene": {
            "default": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "geneid": (str, None, True),
                },
                "group_queries": [None],
                "separator": None,
            }
        },
        "pug_view/pathway": {
            "default": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "source": (str, None, True),
                    "id": (str, None, True),
                },
                "group_queries": [None],
                "separator": None,
            }
        },
        "pug_view/taxonomy": {
            "default": {
                "http_method": "GET",
                "path_param": None,
                "parameters": {
                    "taxid": (str, None, True),
                },
                "group_queries": [None],
                "separator": None,
            }
        },
        WORKFLOW_COMPOUND_PROPERTIES_METHOD: {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "namespace": (str, None, True),
                "identifier": (str, None, True),
                "search_mode": (str, "lookup", False),
                "max_records": (int, 100, False),
                "threshold": (int, None, False),
            },
            "group_queries": [None],
            "separator": None,
        },
    }

    @staticmethod
    def _has_exactly_one_identifier(method: str, inputs: dict) -> bool:
        """Validate that exactly one main identifier is supplied for compound/gene methods.

        Args:
            method (str): Method family being requested (e.g. ``pug/compound``).
            inputs (dict): Resolved input parameters for the request.

        Returns:
            bool: True if exactly one main identifier is present (or the method has no
            such constraint), False otherwise.

        """
        if method == "pug/compound":
            keys = ["cid", "name", "smiles", "inchi"]
            if sum(bool(inputs.get(k)) for k in keys) != 1:
                log.error("Only one 'cid', 'name', 'smiles', or 'inchi' parameters must be specified.")
                return False
        elif method == "pug/gene":
            keys = ["genesymbol", "geneid", "synonym"]
            if sum(bool(inputs.get(k)) for k in keys) != 1:
                log.error("Only one 'genesymbol', 'geneid', or 'synonym' parameters must be specified.")
                return False
        return True

    # Envelope key -> nested path to the payload (handled generically below).
    _PUG_ENVELOPES: ClassVar[dict[str, tuple[str, ...]]] = {
        "PropertyTable": ("Properties",),
        "PC_Compounds": (),
        "IdentifierList": (),
        "ProteinSummaries": ("ProteinSummary",),
        "GeneSummaries": ("GeneSummary",),
    }

    @staticmethod
    def _build_pug_url(method: str, validated_params: dict, option: str) -> str:
        """Build a PUG-REST (``pug/``) request URL.

        Args:
            method (str): Method family (e.g. ``pug/compound``).
            validated_params (dict): Validated request parameters used to compose the path.
            option (str): Fetch option appended to the path unless it is ``default``.

        Returns:
            str: The fully composed PUG-REST request URL.

        """
        url = f"{PUBCHEM.API_URL}{method}"
        if "inchi" not in validated_params:
            for key, value in validated_params.items():
                url += f"/{key}/{value}" if key != "taxid" else ""
            if "taxid" in validated_params:
                url += f"/{validated_params['taxid']}"
        else:
            url += "/inchi"
        if option and option != "default":
            url += f"/{option}"
        url += "/json"  # Assuming JSON output for simplicity
        if "inchi" in validated_params:
            inchi_url = urllib.parse.quote_plus(str(validated_params.get("inchi", "")))
            url += f"?inchi={inchi_url}"
        return url

    @staticmethod
    def _build_pug_view_url(method: str, validated_params: dict) -> str:
        """Build a PUG-View (``pug_view/``) request URL.

        Args:
            method (str): Method family (e.g. ``pug_view/compound``).
            validated_params (dict): Validated request parameters supplying the path identifier(s).

        Returns:
            str: The fully composed PUG-View request URL.

        """
        m = method.replace("pug_view/", "")
        path_keys = {
            "compound": "cid",
            "protein": "accession",
            "gene": "geneid",
            "taxonomy": "taxid",
        }
        url = f"{PUBCHEM.API_URL}/pug_view/data/{m}"
        if m == "pathway":
            url += f"/{validated_params['source']}:{validated_params['id']}"
        elif m in path_keys:
            url += f"/{validated_params[path_keys[m]]}"
        return f"{url}/JSON"  # Assuming JSON output for simplicity

    @classmethod
    def _build_request_url(
        cls, method: str, validated_params: dict, option: str, name_type: str | None
    ) -> str:
        """Build the PubChem request URL for the given method family and parameters.

        Dispatches to the autocomplete, PUG-REST, or PUG-View URL builders based on the
        method, then appends an optional ``name_type`` query parameter.

        Args:
            method (str): Method family being requested.
            validated_params (dict): Validated request parameters.
            option (str): Fetch option used by PUG-REST URLs.
            name_type (str | None): Optional ``name_type`` query parameter to append.

        Returns:
            str: The fully composed request URL.

        """
        if method == "autocomplete":
            url = f"{PUBCHEM.API_URL}{method}"
            for value in validated_params.values():
                if value is not None:
                    url += f"/{value}"
        elif method.startswith("pug/"):
            url = cls._build_pug_url(method, validated_params, option)
        else:
            url = cls._build_pug_view_url(method, validated_params)

        if name_type:
            url += f"?name_type={name_type}"
        return url

    @classmethod
    def _unwrap_pug_envelope(
        cls, response: dict, method: str, option: str, validated_params: dict
    ) -> dict | list:
        """Unwrap a single ``pug/`` response envelope into its payload list.

        Handles ``InformationList``, ``Table``, and the envelopes declared in
        ``_PUG_ENVELOPES``, returning the response unchanged if none match.

        Args:
            response (dict): Raw PUG-REST response body.
            method (str): Method family the response belongs to.
            option (str): Fetch option used for the request.
            validated_params (dict): Validated request parameters, used to backfill
                missing keys (e.g. ``GeneSymbol``).

        Returns:
            dict | list: The unwrapped payload.

        """
        if "InformationList" in response:
            information = response.get("InformationList", {}).get("Information", [])
            if method == "gene" and option == "pwaccs":
                # A little hack to force the response to have a "GeneSymbol" key
                for r in information:
                    r["GeneSymbol"] = validated_params.get("genesymbol", [])
            return information
        if "Table" in response:
            # Convert Table response to list of dicts with key:value pairs
            table = response.get("Table", {})
            columns = table.get("Columns", {}).get("Column", [])
            rows = table.get("Row", [])
            return [dict(zip(columns, row.get("Cell", []), strict=False)) for row in rows]
        for key, path in cls._PUG_ENVELOPES.items():
            if key in response:
                payload = response[key]
                for step in path:
                    payload = payload.get(step, []) if isinstance(payload, dict) else payload
                return payload
        return response

    @classmethod
    def _postprocess_pug_response(
        cls, response: Any, method: str, option: str, validated_params: dict
    ) -> dict | list | str:
        """Unwrap the various PubChem response envelopes into a plain list/dict/str.

        Args:
            response (Any): Raw response body (dict for PUG-REST, str for PUG-View/autocomplete).
            method (str): Method family the response belongs to.
            option (str): Fetch option used for the request.
            validated_params (dict): Validated request parameters forwarded to the unwrapper.

        Returns:
            dict | list | str: The unwrapped payload.

        """
        if method.startswith("pug/") and isinstance(response, dict):
            return cls._unwrap_pug_envelope(response, method, option, validated_params)
        if (method.startswith("pug_view/") or method == "autocomplete") and isinstance(response, str):
            return json.loads(response)
        return response

    def _resolve_request(
        self, query: str | dict | list, method: str, kwargs: dict
    ) -> tuple[str, dict, dict, str, str | None] | None:
        """Validate the request and resolve its method, inputs, and parameters.

        Checks the method and option, validates parameters, and resolves the optional
        ``name_type`` for compound queries. Logs and returns ``None`` if the request is
        invalid.

        Args:
            query (str | dict | list): Identifier(s) or structured query to fetch.
            method (str): Method family being requested.
            kwargs (dict): Extra request options; notably ``option``.

        Returns:
            tuple[str, dict, dict, str, str | None] | None: ``(http_method, inputs,
            validated_params, option, name_type)`` if valid, otherwise ``None``.

        """
        option = kwargs.get("option")
        option_given = bool(option)
        option = option or "default"
        kwargs["option"] = option

        if method not in self.METHODS:
            log.error("Method %s is not supported. Available methods: %s", method, list(self.METHODS.keys()))
            return None
        if option and option not in OPTIONS.get(method, []):
            log.error(
                "Option '%s' is not valid for method '%s'. Allowed options: %s",
                option,
                method,
                OPTIONS.get(method, []),
            )
            return None

        http_method, _path_param, parameters, inputs = self.initialize_method_parameters(
            query, method, self.METHODS, **kwargs
        )
        if option_given and "property" in inputs:
            log.error("Cannot specify both 'option' and 'property' parameter. Please choose one.")
            return None

        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError:
            log.exception("Invalid parameters for method '%s'", method)
            return None

        name_type = None
        if "name_type" in validated_params and method == "pug/compound":
            if validated_params["name_type"] not in ["complete", "word"]:
                log.error("Invalid 'name_type'. Allowed values are: 'complete', 'word', 'fragment'.")
                return None
            name_type = validated_params.pop("name_type")
        return http_method, inputs, validated_params, option, name_type

    @staticmethod
    def _build_workflow_compound_properties_request(query: dict[str, Any]) -> Request:
        """Build a PUG-REST property request for workflow compound lookups."""
        namespace = str(query.get("namespace") or "")
        identifier = str(query.get("identifier") or "")
        search_mode = str(query.get("search_mode") or "lookup")
        if not namespace or not identifier:
            msg = "PubChem workflow compound property queries require namespace and identifier."
            raise ValueError(msg)

        base_url = PUBCHEM.API_URL.rstrip("/")
        params: dict[str, Any] = {}
        data: dict[str, Any] | None = None
        headers: dict[str, str] | None = None
        http_method = "GET"
        if search_mode == "lookup":
            if namespace == "inchi":
                url = f"{base_url}/pug/compound/inchi/property/{WORKFLOW_COMPOUND_PROPERTIES}/JSON"
                http_method = "POST"
                data = {"inchi": identifier}
                headers = {"Content-Type": "application/x-www-form-urlencoded"}
            else:
                namespace_path = urllib.parse.quote(namespace, safe="")
                identifier_path = urllib.parse.quote(identifier, safe="")
                url = (
                    f"{base_url}/pug/compound/{namespace_path}/{identifier_path}/property/"
                    f"{WORKFLOW_COMPOUND_PROPERTIES}/JSON"
                )
        elif search_mode in {"identity", "substructure"}:
            search_prefixes = {"identity": "fastidentity", "substructure": "fastsubstructure"}
            identifier_path = urllib.parse.quote(identifier, safe="")
            url = (
                f"{base_url}/pug/compound/{search_prefixes[search_mode]}/smiles/{identifier_path}/property/"
                f"{WORKFLOW_COMPOUND_PROPERTIES}/JSON"
            )
            params["MaxRecords"] = int(query.get("max_records") or 100)
        elif search_mode == "similarity_2d":
            identifier_path = urllib.parse.quote(identifier, safe="")
            url = (
                f"{base_url}/pug/compound/fastsimilarity_2d/cid/{identifier_path}/property/"
                f"{WORKFLOW_COMPOUND_PROPERTIES}/JSON"
            )
            params["MaxRecords"] = int(query.get("max_records") or 100)
            threshold = query.get("threshold")
            params["Threshold"] = int(threshold) if threshold is not None else DEFAULT_SIMILARITY_THRESHOLD
        else:
            msg = (
                "Unsupported PubChem workflow search mode "
                f"'{search_mode}'. Supported modes are: lookup, identity, substructure, similarity_2d."
            )
            raise ValueError(msg)

        return Request(method=http_method, url=url, params=params, data=data, headers=headers)

    def _fetch_workflow_compound_properties(self, query: object) -> dict | list:
        """Fetch PubChem compound properties for an executable workflow request."""
        if not isinstance(query, dict):
            msg = "PubChem workflow compound property queries must be mappings."
            raise TypeError(msg)

        request = self._build_workflow_compound_properties_request(query)
        prepared = self.session.prepare_request(request)
        log.debug("Prepared PubChem workflow request: %s", prepared.url)

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()
            payload = response.json()
        except (RequestException, ValueError) as exc:
            log.exception("Error fetching PubChem workflow properties for %s", query.get("identifier"))
            msg = f"PubChem workflow request failed for {query.get('identifier')}: {exc}"
            raise RequestError(msg) from exc
        return self._unwrap_pug_envelope(payload, "pug/compound", "property", query)

    def _make_identifier(self, query: str | dict | list, spec: dict) -> str:
        """Build cache identifiers for PubChem requests."""
        if spec == self.METHODS[WORKFLOW_COMPOUND_PROPERTIES_METHOD] and isinstance(query, dict):
            search_mode = query.get("search_mode", "lookup")
            identifier = {
                "namespace": query.get("namespace"),
                "identifier": query.get("identifier"),
                "search_mode": search_mode,
                "max_records": query.get("max_records", 100),
                "properties": WORKFLOW_COMPOUND_PROPERTIES,
            }
            # Only similarity_2d sends Threshold; mirror the request default so an
            # unset threshold and an explicit default map to the same cache entry.
            if search_mode == "similarity_2d":
                threshold = query.get("threshold")
                identifier["threshold"] = (
                    int(threshold) if threshold is not None else DEFAULT_SIMILARITY_THRESHOLD
                )
            return json.dumps(identifier, sort_keys=True)
        return super()._make_identifier(query, spec)

    def fetch(self, query: str | dict | list, *, method: str = "DEFAULT", **kwargs: Any) -> dict | list | str:
        """Fetch compound or protein data from PubChem.

        Resolves and validates the request, builds the URL, sends it, and unwraps the
        response envelope. Returns an empty dict on validation or request failure.

        Args:
            query (str | dict | list): Identifier(s) or structured query to fetch.
            method (str): Method family to use (e.g. ``pug/compound``, ``pug_view/gene``).
            **kwargs: Extra request options; notably ``option``.

        Returns:
            dict | list | str: The fetched, envelope-unwrapped response, or ``{}`` on failure.

        """
        if method == WORKFLOW_COMPOUND_PROPERTIES_METHOD:
            return self._fetch_workflow_compound_properties(query)

        resolved = self._resolve_request(query, method, kwargs)
        if resolved is None:
            return {}
        http_method, inputs, validated_params, option, name_type = resolved

        # Validate if one and only one of the main identifiers is provided
        if not self._has_exactly_one_identifier(method, inputs):
            return {}

        url = self._build_request_url(method, validated_params, option, name_type)

        response = Request(url=url, method=http_method)

        prepared = self.session.prepare_request(response)
        log.debug("Prepared request: %s", prepared.url)

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()
            response = (
                response.json()
                if response.headers.get("Content-Type") == "application/json"
                else response.text
            )

            response = self._postprocess_pug_response(response, method, option, validated_params)

        except RequestException:
            log.exception("Error fetching %s for method '%s'", query, method)
            return {}
        else:
            return response

    def parse(self, data: list | dict, fields_to_extract: list | dict | None, **kwargs: Any) -> list | dict:
        """Parse PubChem response data.

        Selects the fields to extract based on the fetch ``option``, extracts them, and
        flattens PUG-View records via ``process_sections``.

        Args:
            data (list | dict): Raw response data to parse.
            fields_to_extract (list | dict | None): Fields to extract; when a dict, it is
                keyed by option (or ``properties``).
            **kwargs: Extra options; notably ``option``.

        Returns:
            list | dict: The parsed (and, for PUG-View records, flattened) data, or ``{}``
            for empty or unsupported input.

        """
        if not data:
            return {}
        option = kwargs.get("option", "default")

        if option:
            if isinstance(fields_to_extract, dict) and option in fields_to_extract:
                fields_to_extract = fields_to_extract.get(option, [])
            else:
                fields_to_extract = {}
        elif isinstance(fields_to_extract, dict):
            fields_to_extract = fields_to_extract.get("properties", [])
        else:
            log.warning("Option not specified and fields_to_extract is not a dict. Defaulting to empty list.")
            fields_to_extract = []

        if isinstance(data, Response):
            data = data.json()
        elif not isinstance(data, dict):
            log.error(
                "Tried to parse data but the type is not supported. Response should be a dict or a "
                "niquests.Response "
                "object."
            )
            return {}

        parsed_data = self._extract_fields(data, fields_to_extract)
        processed_data = []

        if isinstance(parsed_data, list) and self.is_pug_view_record(parsed_data[0]):
            processed_data = []
            for item in parsed_data:
                processed_data.append(self.process_sections(item))

        elif isinstance(parsed_data, dict) and self.is_pug_view_record(parsed_data):
            processed_data.append(self.process_sections(parsed_data))

        else:
            processed_data = parsed_data

        return processed_data

    def is_pug_view_record(self, data: dict) -> bool:
        """Return True if data is a PUG-View record.

        Args:
            data (dict): Candidate record to check.

        Returns:
            bool: True if ``data`` has the ``record_type``, ``record_number``, and
            ``sections`` keys.

        """
        return all(key in data for key in ["record_type", "record_number", "sections"])

    def _proccess_information_value(self, info_value: dict) -> str | list | dict:
        """Extract the scalar or list value from a PUG-View ``Value`` object.

        Inspects the known value keys (``StringWithMarkup``, ``Number``, ``String``,
        ``URL``, ``Boolean``), collapsing single-element lists to a scalar.

        Args:
            info_value (dict): A PUG-View ``Value`` object.

        Returns:
            str | list | dict: The extracted value, or ``info_value`` unchanged if no
            known key is present.

        """
        if "StringWithMarkup" in info_value:
            texts = [text_entry.get("String", "") for text_entry in info_value["StringWithMarkup"]]
            return texts if len(texts) > 1 else texts[0]
        if "Number" in info_value:
            numbers = info_value["Number"]
            if isinstance(numbers, list) and len(numbers) == 1:
                return numbers[0]
            return numbers
        if "String" in info_value:
            return info_value["String"]
        if "URL" in info_value:
            return info_value["URL"]
        if "Boolean" in info_value:
            booleans = info_value["Boolean"]
            if isinstance(booleans, list) and len(booleans) == 1:
                return booleans[0]
            return booleans
        return info_value  # Return as is if no known key is found

    def process_tocheadings(self, sections: list[dict]) -> dict:
        """Process PubChem compound sections into a flat dict.

        Recurses into nested ``Section`` entries and maps each ``TOCHeading`` to its
        extracted value(s).

        Args:
            sections (list[dict]): PUG-View section objects.

        Returns:
            dict: Mapping of heading name to its extracted value(s).

        """
        headings = {}
        for section in sections:
            if "TOCHeading" in section and "Information" in section:
                heading = section["TOCHeading"]
                extracted_values = [
                    self._proccess_information_value(info["Value"])
                    for info in section["Information"]
                    if "Value" in info
                ]

                headings[heading] = extracted_values if len(extracted_values) > 1 else extracted_values[0]

            if "TOCHeading" in section and "Section" in section:
                sub_headings = self.process_tocheadings(section["Section"])
                headings.update(sub_headings)

        return headings

    def process_sections(self, data: dict) -> dict:
        """Flatten a single PUG-View record into a plain dict.

        Args:
            data (dict): A PUG-View record with ``record_type``/``record_number`` and
                ``sections``.

        Returns:
            dict: The record id paired with its flattened heading values.

        """
        export_data = {}
        if "record_type" in data and "record_number" in data:
            record_type = data["record_type"]
            record_number = data["record_number"]
            export_data[record_type] = record_number

        if "sections" in data:
            headings = self.process_tocheadings(data["sections"])
            export_data.update(headings)

        return export_data

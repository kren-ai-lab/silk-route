import json
import urllib.parse
from typing import Any

import pandas as pd
from requests import Request, Response
from requests.exceptions import RequestException

# Add the import for your database in constants
from bioseq_dl.constants.databases import PUBCHEM
from bioseq_dl.constants.pubchem import COMPOUND_TEMPLATE, GENE_TEMPLATE, OPTIONS, PROTEIN_TEMPLATE
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("bioseq_dl.interfaces.pubchem")

# PubChem has 2 main API access points: PUG-REST and PUG-View.
# PUG-REST is used for short requests with simple inputs and outputs.
# PUG-View is used for getting full reports, including third-party textual annotation.


class PubChemInterface(BaseAPIInterface):
    API_NAME = "PubChem"
    DB_CONFIG = PUBCHEM
    METHODS = {
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
    }

    def fetch(self, query: str | dict | list, *, method: str = "DEFAULT", **kwargs: Any) -> dict | list | str:
        option_given = False
        name_type = None
        option = kwargs.get("option")
        if option:
            option_given = True
        else:
            option = "default"  # Default option if not provided

        kwargs["option"] = option

        if method not in self.METHODS:
            log.error(f"Method {method} is not supported. Available methods: {list(self.METHODS.keys())}")
            return {}
        if option and option not in OPTIONS.get(method, []):
            log.error(
                f"Option '{option}' is not valid for method '{method}'. Allowed options: {OPTIONS.get(method, [])}"
            )
            return {}

        http_method, _path_param, parameters, inputs = self.initialize_method_parameters(
            query, method, self.METHODS, **kwargs
        )

        if option_given and "property" in inputs:
            log.error("Cannot specify both 'option' and 'property' parameter. Please choose one.")
            return {}

        option = "default" if option is None else option

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError:
            log.exception(f"Invalid parameters for method '{method}'")
            return {}

        if "name_type" in validated_params and method == "pug/compound":
            if validated_params["name_type"] not in ["complete", "word"]:
                log.error(
                    "Invalid value for 'name_type'. Allowed values are: 'complete', 'word', 'fragment'."
                )
                return {}
            name_type = validated_params.pop("name_type")

        # Validate if one and only one of the main identifiers is provided
        if method == "pug/compound":
            if (
                sum(
                    bool(inputs.get(validated_params))
                    for validated_params in ["cid", "name", "smiles", "inchi"]
                )
                != 1
            ):
                log.error("Only one 'cid', 'name', 'smiles', or 'inchi' parameters must be specified.")
                return {}
        elif method == "pug/gene":
            if (
                sum(
                    bool(inputs.get(validated_params))
                    for validated_params in ["genesymbol", "geneid", "synonym"]
                )
                != 1
            ):
                log.error("Only one 'genesymbol', 'geneid', or 'synonym' parameters must be specified.")
                return {}

        if method == "autocomplete":
            url = f"{PUBCHEM.API_URL}{method}"
            for key, value in validated_params.items():
                if value is not None:
                    url += f"/{value}"
        elif method.startswith("pug/"):
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
        else:
            # Method starts with pug_view
            m = method.replace("pug_view/", "")
            url = f"{PUBCHEM.API_URL}/pug_view/data/{m}"
            if m == "compound":
                url += f"/{validated_params['cid']}"
            elif m == "protein":
                url += f"/{validated_params['accession']}"
            elif m == "gene":
                url += f"/{validated_params['geneid']}"
            elif m == "pathway":
                url += f"/{validated_params['source']}:{validated_params['id']}"
            elif m == "taxonomy":
                url += f"/{validated_params['taxid']}"
            url += "/JSON"  # Assuming JSON output for simplicity

        if name_type:
            url += f"?name_type={name_type}"

        response = Request(url=url, method=http_method)

        prepared = self.session.prepare_request(response)
        log.debug(f"Prepared request: {prepared.url}")
        log.info(f"Prepared request: {prepared.url}")

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()
            response = (
                response.json()
                if response.headers.get("Content-Type") == "application/json"
                else response.text
            )

            # --------------- Process response based on method and option ---------------
            if method.startswith("pug/"):
                # Me pertuba ver tantos elif
                if isinstance(response, dict) and "PropertyTable" in response:
                    response = response.get("PropertyTable", {}).get("Properties", [])
                elif isinstance(response, dict) and "InformationList" in response:
                    response = response.get("InformationList", {}).get("Information", [])
                    if method == "gene" and option == "pwaccs":
                        # A little hack to force the response to have a "GeneSymbol" key
                        for r in response:
                            r["GeneSymbol"] = validated_params.get("genesymbol", [])

                elif isinstance(response, dict) and "Table" in response:
                    # Convert Table response to list of dicts with key:value pairs
                    table = response.get("Table", {})
                    columns = table.get("Columns", {}).get("Column", [])
                    rows = table.get("Row", [])
                    response = [dict(zip(columns, row.get("Cell", []))) for row in rows]
                elif isinstance(response, dict) and "PC_Compounds" in response:
                    response = response.get("PC_Compounds", [])
                elif isinstance(response, dict) and "IdentifierList" in response:
                    response = response.get("IdentifierList", [])
                elif isinstance(response, dict) and "ProteinSummaries" in response:
                    response = response.get("ProteinSummaries", {}).get("ProteinSummary", [])
                elif isinstance(response, dict) and "GeneSummaries" in response:
                    response = response.get("GeneSummaries", {}).get("GeneSummary", [])
            elif method.startswith("pug_view/") or method == "autocomplete":
                # Convert from string to dict if needed
                if isinstance(response, str):
                    response = json.loads(response)

        except RequestException:
            log.exception(f"Error fetching {query} for method '{method}'")
            return {}
        else:
            return response

    def parse(self, data: list | dict, fields_to_extract: list | dict | None, **kwargs: Any) -> list | dict:
        if not data:
            return {}
        option = kwargs.get("option", "default")

        if option:
            if isinstance(fields_to_extract, dict) and option in fields_to_extract.keys():
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
                "Tried to parse data but the type is not supported. Response should be a dict or a requests.Response object."
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
        return all(key in data for key in ["record_type", "record_number", "sections"])

    def _proccess_information_value(self, info_value: dict) -> str | list | dict:
        if "StringWithMarkup" in info_value:
            texts = []
            for text_entry in info_value["StringWithMarkup"]:
                texts.append(text_entry.get("String", ""))
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
        headings = {}
        for section in sections:
            if "TOCHeading" in section and "Information" in section:
                heading = section["TOCHeading"]
                extracted_values = []
                for info in section["Information"]:
                    if "Value" in info:
                        extracted_values.append(self._proccess_information_value(info["Value"]))

                headings[heading] = extracted_values if len(extracted_values) > 1 else extracted_values[0]

            if "TOCHeading" in section and "Section" in section:
                sub_headings = self.process_tocheadings(section["Section"])
                headings.update(sub_headings)

        return headings

    def process_sections(self, data: dict) -> dict:
        export_data = {}
        if "record_type" in data and "record_number" in data:
            record_type = data["record_type"]
            record_number = data["record_number"]
            export_data[record_type] = record_number

        if "sections" in data:
            headings = self.process_tocheadings(data["sections"])
            export_data.update(headings)

        return export_data

    def fetch_single(
        self, query: str | dict, parse: bool = False, *args: Any, **kwargs: Any
    ) -> tuple[list | dict | pd.DataFrame, dict]:
        option = kwargs.pop("option", "default")
        return super().fetch_single(*args, query=query, parse=parse, option=option, **kwargs)

    def fetch_batch(
        self, queries: list[str | dict], parse: bool = False, *args: Any, **kwargs: Any
    ) -> tuple[list | pd.DataFrame, dict]:
        option = kwargs.pop("option", "default")
        return super().fetch_batch(*args, queries=queries, parse=parse, option=option, **kwargs)

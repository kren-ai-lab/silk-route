import os, json
from typing import Union, List, Dict, Optional, Literal
from requests import Request
from requests.exceptions import RequestException

import pandas as pd

from .base import BaseAPIInterface
from ...constants.databases import ALPHAFOLD
from ..utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.core.interfacesconfig import ConfigLoader

class AlphafoldInterface(BaseAPIInterface):
    METHODS = {
        "prediction": {
            "http_method": "GET",
            "path_param": "qualifier",
            "parameters": {
                "qualifier": (str, None, True),
            },
            "group_queries": [None],
            "separator": None
        }
    }

    def __init__(
            self,  
            structures: Optional[List[Literal["pdb", "cif", "bcif"]]] = ["pdb"],
            cache_dir: Optional[str] = None,
            config_dir: Optional[str] = None,
            output_dir: Optional[str] = None,
            **kwargs
        ):
        """
        Initialize the AlphafoldInterface.
        Args:
            structures (List[str]): List of structures extensions to download. Available options are pdb, cif, bcif, none.
            cache_dir (str): Directory to cache API responses. If None, defaults to the cache directory defined in constants.
            config_dir (str): Directory for configuration files. If None, defaults to the config directory defined in constants.
            output_dir (str): Directory to save downloaded files. If None, defaults to the cache directory.
        """
        if cache_dir:
            cache_dir = os.path.abspath(cache_dir)
        else:
            cache_dir = ALPHAFOLD.CACHE_DIR if ALPHAFOLD.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = ALPHAFOLD.CONFIG_DIR if ALPHAFOLD.CONFIG_DIR is not None else ""

        download_folder_fallback = cache_dir

        config = ConfigLoader(config_dir=config_dir)
        if config.load_config("init"):
            download_folder_fallback = config.get_parameter("download_folder") or cache_dir

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)
        self.output_dir = output_dir or download_folder_fallback
        os.makedirs(self.output_dir, exist_ok=True)

        self.structures = structures

    def fetch_single(self, query: Union[str, dict], parse: bool = False, *args, **kwargs) -> Union[List, Dict, pd.DataFrame]:
        if not isinstance(query, str):
            raise ValueError("Query must be a string representing a UniProt ID.")

        result = super().fetch_single(query, parse=parse, *args, **kwargs)

        new_result = {}
        if self.structures:
            if isinstance(result, list):
                for res in result:
                    self.download_structures(res)
            elif isinstance(result, pd.DataFrame):
                for _, row in result.iterrows():
                    row_dict = row.to_dict()
                    self.download_structures(row_dict)
            elif isinstance(result, dict):
                self.download_structures(result)
            
        return result
    
    def fetch_batch(self, queries: List[Union[str, dict]], parse: bool = False, *args, **kwargs) -> Union[List, pd.DataFrame]:
        if not isinstance(queries, list) or not isinstance(queries[0], str):
            raise ValueError("Queries must be a list of strings representing UniProt IDs.")
        
        results = super().fetch_batch(queries, parse=parse, *args, **kwargs)

        new_results = []
        if self.structures:
            for result in results:
                if isinstance(result, list):
                    for res in result:
                        new_results.append(self.download_structures(res))
                elif isinstance(result, pd.DataFrame):
                    for _, row in result.iterrows():
                        row_dict = row.to_dict()
                        new_results.append(self.download_structures(row_dict))
                elif isinstance(result, dict):
                    new_results = [self.download_structures(result)]
        
        if new_results:
            return new_results
        return results


    def fetch(self, query: Union[str, dict, list], *, method: str = "prediction", **kwargs):
        """
        Get prediction for a given UniProt ID.
        Args:
            query (str): UniProt ID to fetch prediction for.
            method (str): Method to use for fetching data. Currently only "prediction" is supported.
        Returns:
            Dict: Prediction data.
        """
        if method not in self.METHODS.keys():
            raise ValueError(f"Method {method} is not supported. Supported methods are: prediction.")

        http_method, path_param, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError as e:
            raise ValueError(f"Invalid parameters for method '{method}': {e}")
        
        url = f"{ALPHAFOLD.API_URL}{method}/"
        
        if path_param:
            path_value = validated_params.pop(path_param)
            url += f"{path_value}"
        
        req = Request(
            method=http_method,
            url=url,
            params=validated_params
        )
        prepared = self.session.prepare_request(req)
        print(f"Prepared request: {prepared.url}")

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()
            response = response.json()

            if "results" in response:
                response = response["results"]  

            return response
        except RequestException as e:
            print(f"Error fetching prediction for {query}: {e}")
            return {}
        

    def download_structures(self, parsed: Dict) -> Dict:
        """
        Download structure files based on parsed prediction info.

        Args:
            parsed (Dict): Parsed data containing URLs for structures.
        Returns:
            Dict: Parsed data without the structure URLs.
        """
        if not self.structures:
            return parsed if parsed is not None else {}

        for ext in self.structures:
            url_key = f"{ext}Url"
            if url_key not in parsed:
                print(f"Warning: {url_key} not found in parsed data. {parsed}")
                continue

            structure_url = parsed[url_key]
            file_name = structure_url.split("/")[-1]
            file_path = os.path.join(self.output_dir, file_name)

            # Delete the URL from parsed data
            del parsed[url_key]

            # Check if the file already exists
            if os.path.exists(file_path):
                print(f"Structure {file_name} already exists. Skipping download.")
                continue

            try:
                response = self.session.get(structure_url)
                with open(file_path, "wb") as f:
                    print(f"Downloading structure {file_name}...")
                    f.write(response.content)

            except Exception as e:
                print(f"Error downloading structure {file_name}: {e}")

        return parsed if parsed is not None else {}

    def parse(
            self, 
            data: Union[List, Dict],
            fields_to_extract: Optional[Union[list, dict]],
            **kwargs
        ) -> Union[List, Dict]:
        """
        Parse data by extracting specified fields or returning the entire structure.
        Args:
            data (Union[List, Dict]): Data to parse.
            fields_to_extract (List|Dict): Fields to keep from the original response.
                - If List: Keep those keys.
                - If Dict: Maps {desired_name: real_field_name}.
            for more information, see: https://alphafold.ebi.ac.uk/#/public-api/get_predictions_api_prediction__qualifier__get
        Returns:
            Union[List, Dict]: Parsed data with specified fields or the entire structure.
        """
        # Check input data type
        if not isinstance(data, (List, Dict)):
            raise ValueError("Data must be a list or a dictionary.")
        
        # Check if structures are requested
        if self.structures:
            # Add new key in fields_to_extract for each structure type
            for ext in self.structures:
                if isinstance(fields_to_extract, List):
                    fields_to_extract.append(f"{ext}Url")
                elif isinstance(fields_to_extract, Dict):
                    fields_to_extract[f"{ext}Url"] = f"{ext}Url"

        return self._extract_fields(data, fields_to_extract)
    
    def get_dummy(self, **kwargs) -> dict:
        """
        Get a dummy response.
        Useful for knowing the structure of the data returned by the API.
        Returns:
            Dict: Dummy response with example fields.
        """
        parse = kwargs.get("parse", False)

        return super().get_dummy(
            query="P02666",
            parse=parse
        )
    
    def query_usage(self):
        """
        Get usage information for the Alphafold API.
        Returns:
            str: Usage information.
        """
        usage = """Usage: To fetch predictions, use the UniProt ID as the query.
        Example: 
            - fetch_single("P02666", parse=True)
            - fetch_batch(["P02666", "P12345"])

        Also you can download structures by setting the `structures` parameter in the constructor.
        Example:
            - alphafold = AlphafoldInterface(structures=["pdb", "cif"])
            - prediction = alphafold.fetch_single("P02666")

        Available structures to download:
            - pdb: Protein Data Bank format
            - cif: Crystallographic Information File format
            - bcif: Binary Crystallographic Information File format
        """
        dummy = self.get_dummy()

        usage += "\n\nExample fields in the response:\n"
        for key in dummy.keys():
            usage += f"\t- {key}: {dummy[key]}\n"
        return usage
    
    def save(self, data: Union[List, Dict], filename: str, extension: str = "csv"):
        """
        Save the parsed data to a file.
        Args:
            data (Union[List, Dict]): Data to save.
            file_name (str): Name of the file to save the data to.
        """
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        if extension not in ["csv", "tsv", "json"]:
            raise ValueError("Unsupported file extension. Use 'csv', 'tsv', or 'json'.")
        
        if extension == "csv":
            df = pd.DataFrame(data)
            df.to_csv(os.path.join(self.output_dir, f"{filename}.{extension}"), index=False)
        
        elif extension == "tsv":
            df = pd.DataFrame(data)
            df.to_csv(os.path.join(self.output_dir, f"{filename}.{extension}"), sep="\t", index=False)
           
        elif extension == "json":
            with open(os.path.join(self.output_dir, f"{filename}.{extension}"), 'w') as f:
                json.dump(data, f, indent=4)
            
        return os.path.join(self.output_dir, f"{filename}.{extension}")


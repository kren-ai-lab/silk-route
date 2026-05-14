import os, logging

from typing import Union, List, Dict, Set, Optional

from requests import Request
from requests.exceptions import RequestException

import pandas as pd

from .base import BaseAPIInterface
# Add the import for your database in constants
from ...constants.databases import BIODBNET
# Some deprecated imports, you can remove them if not needed
#from ...constants.biodbnet import inputs, outputs

from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.interfaces.biodbnet")


class BioDBNetInterface(BaseAPIInterface):
    API_NAME = "BioDBNet"
    METHODS = {
        "getpathways": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "pathways": (str, "1", True),
                "taxonId": (str, None, True)
            },
            "group_queries": [None],
            "separator": None
        },
        "db2db": {
            "http_method": "GET",
            "path_param": None,
            "parameters": {
                "input": (str, None, True),
                "inputValues": (str, None, True),
                "outputs": (str, "genesymbol,affyid,go-biologicalprocess,go-cellularcomponent,go-molecularfunction,goid", True),
                "taxonId": (str, None, True)
            },
            "group_queries": ["inputValues"],
            "separator": ","
        }
    }
    def __init__(
            self,  
            cache_dir: Optional[str] = None,
            config_dir: Optional[str] = None,
            **kwargs
        ):

        if cache_dir:
            cache_dir = os.path.abspath(cache_dir)
        else:
            cache_dir = BIODBNET.CACHE_DIR if BIODBNET.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = BIODBNET.CONFIG_DIR if BIODBNET.CONFIG_DIR is not None else ""

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)

    def fetch(
            self, 
            query: Union[str, dict, list], 
            *, 
            method: str = "getpathways", 
            **kwargs
        ):
        if method not in self.METHODS.keys():
            log.error(f"Method {method} is not supported. Available methods: {list(self.METHODS.keys())}")
            return {}
        
        http_method, _, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        inputs.update({"method": method})

        inputs["outputs"] = ",".join(inputs.get("outputs", [])) if isinstance(inputs.get("outputs"), list) else inputs.get("outputs", "")

        req = Request(
            method=http_method,
            url=BIODBNET.API_URL,
            params=inputs
        )
        prepared = self.session.prepare_request(req)
        log.debug(f"Prepared request: {prepared.url}")

        try:
            response = self.session.send(prepared)
            self._delay()
            response.raise_for_status()
            
            match method:
                case "db2db":
                    response = response.json()
                    response = [
                        v["outputs"] for k, v in response.items() if isinstance(v, dict) and k not in inputs
                    ]
                    return response
                case _:
                    return response.json()
        except RequestException as e:
            log.error(f"Error fetching {query} for method '{method}': {e}")
            return {}


    def parse(
            self, 
            data: Union[List, Dict],
            fields_to_extract: Optional[Union[list, dict]],
            **kwargs
        ) -> Union[List, Dict]:
        
        if not data:
            log.warning("Tried to parse data but the data is empty or None.")
            return {}

        elif isinstance(data, (dict, list)):
            data = data
        else:
            log.error("Tried to parse data but the type is not supported. Response should be a dict or a requests.Response object.")
            return {}

        return self._extract_fields(data, fields_to_extract)
    
    def get_dummy(self, **kwargs) -> Dict:
        return {
            "message": "This is a dummy response.",
            "status": "success"
        }
    
    def query_usage(self) -> str:
        return """
        This is a dummy query usage for YourDatabaseInterface.
        """
import os
import requests

from typing import Union, List, Dict, Set, Optional
from requests import Request

import pandas as pd

from bioseq_dl.core.interfaces.base import BaseAPIInterface
from bioseq_dl.constants.databases import SABIORK
from bioseq_dl.core.utils.base_auxiliary_methods import validate_parameters

from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.interfaces.sabiork")

class SabiorkInterface(BaseAPIInterface):
    API_NAME = "Sabio-RK"
    METHODS = {
        "kineticlaws": {
                "http_method": "POST",
                "path_param": None,
                "parameters": {
                    "ECNumber": (str, None, True),
                    "Organism": (str, None, True),
                    "UniProtKB_AC": (str, None, True)
                },
                "group_queries": [None],
                "separator": None
        }
    }

    def __init__(
            self,  
            cache_dir: Optional[str] = None,
            config_dir: Optional[str] = None,
            output_dir: Optional[str] = None,
            **kwargs
        ):

        if cache_dir:
            cache_dir = os.path.abspath(cache_dir)
        else:
            cache_dir = SABIORK.CACHE_DIR if SABIORK.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = SABIORK.CONFIG_DIR if SABIORK.CONFIG_DIR is not None else ""

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)
        self.output_dir = output_dir or cache_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def fetch(
            self, 
            query: Union[str, dict, list], 
            *, 
            method: str = "kineticlaws", 
            **kwargs
        ):
        '''Fetch data from the Sabio-RK API based on the provided query.'''
        if method not in self.METHODS:
            raise ValueError(f"Method '{method}' is not supported. Available methods: {list(self.METHODS.keys())}")
        
        http_method, _, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError as e:
            log.error(f"Invalid parameters for method '{method}': {e}")
            return {}

        query_string = ' AND '.join([f'{k}:"{v}"' if any(c.isspace() for c in v) else f'{k}:{v}' for k, v in validated_params.items()])

        fields = []
        if method == "kineticlaws":
            method = "kineticlawsExportTsv"
            fields = ['EntryID', 'Organism', 'UniprotID','ECNumber', 'Parameter', 'Reaction', 'Temperature', 'pH', 'Tissue']
        else:
            log.error(f"Method '{method}' is not implemented.")
            return {}
        
        url = SABIORK.API_URL + method
       
        request = Request(
            url=url,
            method=http_method,
            params = {
                'fields[]': fields,
                'q': query_string
            }
        )
        
        prepared = self.session.prepare_request(request)

        try:
            response = self.session.send(prepared)
            print(prepared.url)
            self._delay()
            response.raise_for_status()

            if method == "kineticlawsExportTsv":
                results = [line.split('\t') for line in response.text.strip().split('\n')]
                response = [
                    {results[0][i]: row[i] for i in range(len(results[0]))}
                    for row in results[1:]
                ]
                return response

        
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Error fetching prediction for {query}: {e}")
            return {}
        
    def parse(
            self, 
            data: Union[List, Dict],
            fields_to_extract: Optional[Union[list, dict]],
            **kwargs
        ) -> Union[List, Dict]:
        return self._extract_fields(data, fields_to_extract)
    
    def query_usage(self) -> str:
        return "Use SABIO-RK methods with supported kinetic law query parameters."
    

import os
from typing import Optional, List, Any, Union
import hashlib
from zeep import Client
from zeep.helpers import serialize_object


from .base import BaseAPIInterface
from ...constants.databases import BRENDA
from ...constants.brenda import METHODS as BRENDA_METHODS
from ..utils.base_auxiliary_methods import validate_parameters
from bioseq_dl.core.credentials import load_environment_files, resolve_secret, is_valid_secret

from bioseq_dl.logging import get_logger

log = get_logger("bioseq_dl.interfaces.brenda")

BRENDA_EMAIL_ENV_VARS = (
    "BIOSEQ_DL_BRENDA_EMAIL",
    "BRENDA_EMAIL",
)
BRENDA_PASSWORD_ENV_VARS = (
    "BIOSEQ_DL_BRENDA_PASSWORD",
    "BRENDA_PASSWORD",
)

# For aditional implementations see: https://www.brenda-enzymes.org/soap.php
class BrendaInterface(BaseAPIInterface):
    API_NAME = "BRENDA"
    METHODS = BRENDA_METHODS

    def __init__(
            self, 
            email: Optional[str] = None, 
            password: Optional[str] = None,
            cache_dir: Optional[str] = None,
            config_dir: Optional[str] = None,
            **kwargs
        ):
        """
        Initialize the BrendaInstance.
        Args:
            email (str): Email address for BRENDA API.
            password (str): Password for BRENDA API.
            cache_dir (str): Directory to cache results.
            config_dir (str): Directory for configuration files.
            output_dir (str): Directory to save output files.
        """
        if cache_dir:
            cache_dir = os.path.abspath(cache_dir)
        else:
            cache_dir = BRENDA.CACHE_DIR if BRENDA.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = BRENDA.CONFIG_DIR if BRENDA.CONFIG_DIR is not None else ""

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs, min_wait=2.0, max_wait=5.0)

        load_environment_files(config_dir=config_dir)

        self.email = resolve_secret(email, BRENDA_EMAIL_ENV_VARS)
        raw_password = resolve_secret(password, BRENDA_PASSWORD_ENV_VARS)
        self.password = (
            hashlib.sha256(raw_password.encode("utf-8")).hexdigest()
            if raw_password
            else None
        )
        self.client = Client(BRENDA.API_URL)


    def show_all_methods(self):
        print("Available methods:")
        for service in self.client.wsdl.services.values():
            for port in service.ports.values():
                for method_name in port.binding._methods.keys():
                    print(f"- {method_name}")
    
    def fetch(self, query: Union[str, dict, list], *, method: str = "getKmValue", **kwargs):
        """
        Fetch data from BRENDA for a given EC number and organism.
        Args:
            query (dict): Query parameters to filter the results.
                - `ecNumber`: Enzyme Commission number (e.g., '1.1.1.1').
                - `organism`: Organism name (e.g., 'Escherichia coli').
            method (str): Name of the method to perform (e.g., 'getKmValue').
        Returns:
            list: List of results from the BRENDA API.
        """
        if method not in self.METHODS.keys():
            print(f"method {method} is not supported. Available methods: {list(self.METHODS.keys())}")
            return []
        if not isinstance(query, dict):
            print("Query must be a dictionary with keys matching the method parameters.")
            return []
        
        if not is_valid_secret(self.email) or self.password is None:
            raise ValueError(
                "Missing BRENDA credentials. Set BIOSEQ_DL_BRENDA_EMAIL and "
                "BIOSEQ_DL_BRENDA_PASSWORD or pass them explicitly."
            )
        
        _, _, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError as e:
            log.error(f"Invalid parameters for method '{method}': {e}")
            return []

        results = []
        try:
            params = self.METHODS[method]["parameters"].keys()

            # Build parameters in order
            param_list = [f"{k}*{validated_params.get(k, '')}" for k in params]

            # Add credentials
            parameters = [self.email, self.password] + param_list
            
            func = getattr(self.client.service, method)
            result = serialize_object(func(*parameters))
            result = [dict(entry) for entry in result] if isinstance(result, list) else dict(result)

            self._delay()


            results.extend(result if isinstance(result, list) else [result])
        
        except Exception as e:
            print(f"Error fetching data for {method} with parameters {query}: {e}")
            return []
        
        return results

    
    def get_methods(self) -> List[str]:
        """
        Get the list of available methods.
        Returns:
            List[str]: List of method names.
        """
        return list(self.METHODS.keys())

    def query_usage(self) -> str:
        """
        Get the usage of the BRENDA API.
        Returns:
            str: Usage information.
        """
        usage = """Usage: To fetch data from BRENDA, use the following parameters.
        Example:
            - fetch(query={}, methods=["getKmValue", "getIc50Value"])
        Available methods: """ + ", ".join(self.METHODS.keys()) + "\n\n"
        usage += "For more information about each method, please refer to the BRENDA documentation."
        usage += "\nOr use `show_method({method_name})` to see the parameters required for each method."
        return usage
    
    
    def show_method(self, method_name: str) -> str:
        """
        Show the parameters required for a specific method.
        Args:
            method_name (str): Name of the method.
        Returns:
            str: Parameters required for the method.
        """
        if method_name not in self.METHODS.keys():
            return f"method {method_name} is not supported."

        params = self.METHODS[method_name]
        return f"Parameters for {method_name}: {', '.join(params)}"
    
    def parse(self, data: Any, fields_to_extract: Optional[Union[list, dict]], **kwargs):
        """
        Parse the response from the BioGRID API.
        Args:
            data (dict): The fetched data.
            fields_to_extract (List|Dict): Fields to keep from the original response.
                - If List: Keep those keys.
                - If Dict: Maps {desired_name: real_field_name}.
        Returns:
            any: Parsed data from the response.
        """
        if not data:
            log.warning("Tried to parse data but the data is empty or None.")
            return {}

        if not isinstance(data, (dict, list)):
            log.error("Tried to parse data but the type is not supported. Response should be a dict or a requests.Response object.")
            return {}

        return self._extract_fields(data, fields_to_extract)
    

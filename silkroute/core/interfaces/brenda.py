"""BRENDA SOAP API interface."""

import hashlib
from typing import Any, ClassVar

from zeep import Client
from zeep.helpers import serialize_object

from silkroute.constants.brenda import METHODS as BRENDA_METHODS
from silkroute.constants.databases import BRENDA
from silkroute.core.credentials import is_valid_secret, load_environment_files, resolve_secret
from silkroute.core.utils.base_auxiliary_methods import validate_parameters
from silkroute.logging import get_logger

from .base import BaseAPIInterface

log = get_logger("silkroute.interfaces.brenda")

BRENDA_EMAIL_ENV_VARS = ("SILKROUTE_BRENDA_EMAIL",)
BRENDA_PASSWORD_ENV_VARS = ("SILKROUTE_BRENDA_PASSWORD",)


# For additional implementations see: https://www.brenda-enzymes.org/soap.php
class BrendaInterface(BaseAPIInterface):
    """BRENDA enzyme kinetics database SOAP API interface."""

    API_NAME = "BRENDA"
    DB_CONFIG = BRENDA
    METHODS: ClassVar[dict[str, Any]] = BRENDA_METHODS

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        cache_dir: str | None = None,
        config_dir: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the BrendaInstance.

        Args:
            email (str | None): Email address for BRENDA API.
            password (str | None): Password for BRENDA API.
            cache_dir (str | None): Directory to cache results.
            config_dir (str | None): Directory for configuration files.
            **kwargs: Passed through to the base class.

        """
        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs, min_wait=2.0, max_wait=5.0)

        load_environment_files(config_dir=self.config_dir)

        self.email = resolve_secret(email, BRENDA_EMAIL_ENV_VARS)
        raw_password = resolve_secret(password, BRENDA_PASSWORD_ENV_VARS)
        self.password = hashlib.sha256(raw_password.encode("utf-8")).hexdigest() if raw_password else None
        self.client = Client(BRENDA.API_URL)

    def fetch(self, query: str | dict | list, *, method: str = "getKmValue", **kwargs: Any) -> dict | list:
        """Fetch data from BRENDA for a given EC number and organism.

        Args:
            query (str | dict | list): Query parameters to filter the results. Expected as a dict with:
                - ``ecNumber``: Enzyme Commission number (e.g., '1.1.1.1').
                - ``organism``: Organism name (e.g., 'Escherichia coli').
            method (str): Name of the method to perform (e.g., 'getKmValue').
            **kwargs: Additional keyword arguments passed to the request builder.

        Returns:
            dict | list: List of results from the BRENDA API.

        Raises:
            ValueError: If BRENDA credentials are missing.

        """
        if method not in self.METHODS:
            log.error("method %s is not supported. Available methods: %s", method, list(self.METHODS.keys()))
            return []
        if not isinstance(query, dict):
            log.error("Query must be a dictionary with keys matching the method parameters.")
            return []

        if not is_valid_secret(self.email) or self.password is None:
            msg = (
                "Missing BRENDA credentials. Set SILKROUTE_BRENDA_EMAIL and "
                "SILKROUTE_BRENDA_PASSWORD or pass them explicitly."
            )
            raise ValueError(msg)

        _, _, parameters, inputs = self.initialize_method_parameters(query, method, self.METHODS, **kwargs)

        # Validate and clean parameters
        try:
            validated_params = validate_parameters(inputs, parameters)
        except ValueError:
            log.exception("Invalid parameters for method '%s'", method)
            return []

        results = []
        try:
            params = self.METHODS[method]["parameters"].keys()

            # Build parameters in order
            param_list = [f"{k}*{validated_params.get(k, '')}" for k in params]

            # Add credentials
            parameters = [self.email, self.password, *param_list]

            func = getattr(self.client.service, method)
            result = serialize_object(func(*parameters))
            if isinstance(result, list):  # noqa: SIM108  # split for per-branch type:ignore
                result = [dict(entry) for entry in result]  # type: ignore[no-matching-overload]
            else:
                result = dict(result)  # type: ignore[no-matching-overload]  # zeep OrderedDict

            self._delay()

            results.extend(result if isinstance(result, list) else [result])

        except Exception:
            log.exception("Error fetching data for %s with parameters %s", method, query)
            return []

        return results

    def get_methods(self) -> list[str]:
        """Get the list of available methods.

        Returns:
            list[str]: List of method names.

        """
        return list(self.METHODS.keys())

    def show_method(self, method_name: str) -> str:
        """Show the parameters required for a specific method.

        Args:
            method_name (str): Name of the method.

        Returns:
            str: Parameters required for the method.

        """
        if method_name not in self.METHODS:
            return f"method {method_name} is not supported."

        params = self.METHODS[method_name]
        return f"Parameters for {method_name}: {', '.join(params)}"

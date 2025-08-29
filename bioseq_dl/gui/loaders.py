from typing import Dict, List, Any
import pkgutil
import inspect
import importlib
from bioseq_dl import BaseAPIInterface
import bioseq_dl.core.interfaces as interfaces_pkg

def is_required_param(param: inspect.Parameter) -> bool:
    """Return True if parameter is required (no default) and not var-pos/var-key."""
    if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
        return False
    return param.default is inspect._empty

def get_required_init_params(cls) -> List[str]:
    """Return required __init__ parameters (excluding 'self')."""
    sig = inspect.signature(cls.__init__)
    required = []
    for name, p in sig.parameters.items():
        if name == "self":
            continue
        if is_required_param(p):
            required.append(name)
    return required

def build_interface_metadata(cls) -> Dict[str, Any]:
    """Build metadata for an interface class, including required init params and auth hint."""
    required = get_required_init_params(cls)
    requires_auth = all(x in required for x in ("email", "password"))
    return {
        "name": cls.__name__,
        "class": cls,
        "required_init_params": required,
        "requires_auth": requires_auth
    }

def load_interfaces() -> List[Dict[str, Any]]:
    """
    Discover interface classes under `bioseq_dl.core.interfaces` and return metadata.
    - `requires_auth` will be True for classes like Brenda that need email/password.
    """
    api_classes_meta: List[Dict[str, Any]] = []
    for _, module_name, _ in pkgutil.iter_modules(interfaces_pkg.__path__):
        if module_name.startswith("_"):
            continue
        module = importlib.import_module(f"{interfaces_pkg.__name__}.{module_name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseAPIInterface) and obj is not BaseAPIInterface:
                api_classes_meta.append(build_interface_metadata(obj))
    return api_classes_meta
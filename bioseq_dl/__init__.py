"""BioSeqDownloader — download and integrate biological data from multiple APIs."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

__version__ = "0.1.0"

# Map public name -> module path (relative to this package). Loaded lazily via
# __getattr__ (PEP 562) so `import bioseq_dl` does not pull every interface and
# its heavy dependencies (e.g. zeep/SOAP for BRENDA) at import time.
_LAZY_EXPORTS: dict[str, str] = {
    "BaseAPIInterface": ".core.interfaces.base",
    "AlphafoldInterface": ".core.interfaces.alphafold",
    "BioDBNetInterface": ".core.interfaces.biodbnet",
    "BioGRIDInterface": ".core.interfaces.biogrid",
    "BrendaInterface": ".core.interfaces.brenda",
    "ChEBIInterface": ".core.interfaces.chebi",
    "ChEMBLInterface": ".core.interfaces.chembl",
    "GenOntologyInterface": ".core.interfaces.genontology",
    "InterproInterface": ".core.interfaces.interpro",
    "KEGGInterface": ".core.interfaces.kegg",
    "PantherInterface": ".core.interfaces.panther",
    "PathwayCommonsInterface": ".core.interfaces.pathwaycommons",
    "PDBInterface": ".core.interfaces.proteindatabank",
    "PrideInterface": ".core.interfaces.pride",
    "PubChemInterface": ".core.interfaces.pubchem",
    "ReactomeInterface": ".core.interfaces.reactome",
    "RefSeqInterface": ".core.interfaces.refseq",
    "RheaInterface": ".core.interfaces.rhea",
    "SabiorkInterface": ".core.interfaces.sabiork",
    "StringInterface": ".core.interfaces.stringdb",
    "UniprotInterface": ".core.interfaces.uniprot",
    "Workflow": ".core.workflow.main_workflow",
}

# Public names whose attribute in the source module differs from the export name.
_EXPORT_ALIASES: dict[str, str] = {"Workflow": "MainWorkflow"}

if TYPE_CHECKING:
    from .core.interfaces.alphafold import AlphafoldInterface
    from .core.interfaces.base import BaseAPIInterface
    from .core.interfaces.biodbnet import BioDBNetInterface
    from .core.interfaces.biogrid import BioGRIDInterface
    from .core.interfaces.brenda import BrendaInterface
    from .core.interfaces.chebi import ChEBIInterface
    from .core.interfaces.chembl import ChEMBLInterface
    from .core.interfaces.genontology import GenOntologyInterface
    from .core.interfaces.interpro import InterproInterface
    from .core.interfaces.kegg import KEGGInterface
    from .core.interfaces.panther import PantherInterface
    from .core.interfaces.pathwaycommons import PathwayCommonsInterface
    from .core.interfaces.pride import PrideInterface
    from .core.interfaces.proteindatabank import PDBInterface
    from .core.interfaces.pubchem import PubChemInterface
    from .core.interfaces.reactome import ReactomeInterface
    from .core.interfaces.refseq import RefSeqInterface
    from .core.interfaces.rhea import RheaInterface
    from .core.interfaces.sabiork import SabiorkInterface
    from .core.interfaces.stringdb import StringInterface
    from .core.interfaces.uniprot import UniprotInterface
    from .core.workflow.main_workflow import MainWorkflow as Workflow


def __getattr__(name: str) -> object:
    """Lazily import public exports on first access (PEP 562).

    Args:
        name (str): Attribute name being accessed on the package.

    Returns:
        object: The resolved export (interface class, workflow, etc.).

    Raises:
        AttributeError: If ``name`` is not a known public export.

    """
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    module = import_module(module_path, __name__)
    return getattr(module, _EXPORT_ALIASES.get(name, name))


def __dir__() -> list[str]:
    """Return the sorted public attribute names for tab-completion."""
    return sorted(__all__)


__all__ = [
    "AlphafoldInterface",
    "BaseAPIInterface",
    "BioDBNetInterface",
    "BioGRIDInterface",
    "BrendaInterface",
    "ChEBIInterface",
    "ChEMBLInterface",
    "GenOntologyInterface",
    "InterproInterface",
    "KEGGInterface",
    "PDBInterface",
    "PantherInterface",
    "PathwayCommonsInterface",
    "PrideInterface",
    "PubChemInterface",
    "ReactomeInterface",
    "RefSeqInterface",
    "RheaInterface",
    "SabiorkInterface",
    "StringInterface",
    "UniprotInterface",
    "Workflow",
    "__version__",
]

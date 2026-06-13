"""Package-level smoke tests: version and lazy public API."""

from __future__ import annotations

import subprocess
import sys


def test_version_is_exposed() -> None:
    import bioseq_dl

    assert isinstance(bioseq_dl.__version__, str)
    assert bioseq_dl.__version__


def test_public_exports_are_lazy_and_resolve() -> None:
    import bioseq_dl

    # Every advertised export must resolve via the lazy __getattr__.
    for name in bioseq_dl.__all__:
        assert getattr(bioseq_dl, name) is not None


def test_import_does_not_pull_heavy_deps() -> None:
    # In a clean interpreter, importing the package must not eagerly import heavy
    # optional backends such as zeep (SOAP, used only by BRENDA).
    code = "import bioseq_dl, sys; assert 'zeep' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr

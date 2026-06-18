"""Package-level smoke tests: version and lazy public API."""

from __future__ import annotations

import subprocess
import sys
from importlib import metadata


def raise_missing_distribution(distribution_name: str) -> str:
    from bioseq_dl._version import DISTRIBUTION_NAME

    assert distribution_name == DISTRIBUTION_NAME
    raise metadata.PackageNotFoundError


def test_version_is_exposed() -> None:
    import bioseq_dl

    assert isinstance(bioseq_dl.__version__, str)
    assert bioseq_dl.__version__


def test_runtime_version_falls_back_when_distribution_is_missing(monkeypatch) -> None:
    from bioseq_dl._version import UNKNOWN_VERSION, get_runtime_version

    monkeypatch.setattr(metadata, "version", raise_missing_distribution)

    assert get_runtime_version() == UNKNOWN_VERSION


def test_public_exports_are_lazy_and_resolve() -> None:
    import bioseq_dl

    # Every advertised export must resolve via the lazy __getattr__.
    for name in bioseq_dl.__all__:
        assert getattr(bioseq_dl, name) is not None


def test_import_does_not_pull_heavy_deps() -> None:
    # In a clean interpreter, importing the package must not eagerly import heavy
    # optional backends such as zeep (SOAP, used only by BRENDA).
    code = "import bioseq_dl, sys; assert 'zeep' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)  # noqa: S603  # sys.executable, trusted
    assert result.returncode == 0, result.stderr

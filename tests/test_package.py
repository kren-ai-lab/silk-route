"""Package-level smoke tests: version and lazy public API."""

from __future__ import annotations

import subprocess
import sys
from importlib import metadata


def test_version_is_exposed() -> None:
    import silkroute

    assert isinstance(silkroute.__version__, str)
    assert silkroute.__version__


def test_public_exports_are_lazy_and_resolve() -> None:
    import silkroute

    # Every advertised export must resolve via the lazy __getattr__.
    for name in silkroute.__all__:
        assert getattr(silkroute, name) is not None


def test_import_does_not_pull_heavy_deps() -> None:
    # In a clean interpreter, importing the package must not eagerly import heavy
    # optional backends such as zeep (SOAP, used only by BRENDA).
    code = "import silkroute, sys; assert 'zeep' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)  # noqa: S603  # sys.executable, trusted
    assert result.returncode == 0, result.stderr


def test_distribution_metadata_name() -> None:
    assert metadata.metadata("silkroute")["Name"] == "silkroute"


def test_packaged_config_resources_load() -> None:
    from silkroute.core.interfacesconfig import load_packaged_config

    fields = load_packaged_config("alphafold", "fields.yml")

    assert fields["prediction"]["entry"] == "entryId"

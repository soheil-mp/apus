"""Every workspace package is installed, versioned and ships type information."""

import importlib
from importlib.metadata import version
from importlib.resources import files

import pytest

PACKAGES = ["apus_api", "apus_core", "apus_edge", "apus_ingest", "apus_pipelines", "apus_sim"]


@pytest.mark.parametrize("module_name", PACKAGES)
def test_package_version_matches_distribution_metadata(module_name: str) -> None:
    module = importlib.import_module(module_name)
    distribution = module_name.replace("_", "-")
    assert module.__version__ == version(distribution)


@pytest.mark.parametrize("module_name", PACKAGES)
def test_package_is_marked_as_typed(module_name: str) -> None:
    assert files(module_name).joinpath("py.typed").is_file()


@pytest.mark.parametrize("module_name", PACKAGES)
def test_package_has_a_docstring(module_name: str) -> None:
    module = importlib.import_module(module_name)
    assert module.__doc__
    assert module.__doc__.strip()

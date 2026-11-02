"""Read-only HTTP API over the analysis-ready (gold) tables."""

from importlib.metadata import version

__all__ = ["__version__"]

__version__: str = version("apus-api")

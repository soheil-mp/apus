"""Dagster definitions: external-source ingestion, transformations and data-quality checks."""

from importlib.metadata import version

__all__ = ["__version__"]

__version__: str = version("apus-pipelines")

"""Domain types, coordinate frames, units and configuration shared by every Apus package."""

from importlib.metadata import version

__all__ = ["__version__"]

__version__: str = version("apus-core")

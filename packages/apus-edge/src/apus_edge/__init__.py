"""Edge runtime: frame assembly, detection, tracking, data reduction and publishing."""

from importlib.metadata import version

__all__ = ["__version__"]

__version__: str = version("apus-edge")

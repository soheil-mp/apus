"""Stream landing service: from NATS JetStream into the lakehouse."""

from importlib.metadata import version

__all__ = ["__version__"]

__version__: str = version("apus-ingest")

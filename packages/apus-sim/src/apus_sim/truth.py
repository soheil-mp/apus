"""Ground truth: what the simulator knows and the edge must never see (ADR-0003).

Only tests, evaluation and the end-to-end check read this module. Import-linter contracts in
``pyproject.toml`` keep every product package (core, edge, ingest, pipelines, API) from
importing it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import TextIO

__all__ = ["BirdTruth", "write_truth"]


@dataclass(frozen=True)
class BirdTruth:
    """The bird's true state at the start of one frame."""

    frame_id: int
    time_ns: int
    east_m: float
    north_m: float
    up_m: float
    velocity_east_mps: float
    velocity_north_mps: float
    velocity_up_mps: float
    radius_m: float


def write_truth(records: Iterable[BirdTruth], stream: TextIO) -> int:
    """Write ground-truth records as JSON Lines; returns the number written."""
    count = 0
    for record in records:
        stream.write(json.dumps(asdict(record), separators=(",", ":")) + "\n")
        count += 1
    return count

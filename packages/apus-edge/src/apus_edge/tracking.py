"""Minimal multi-target tracking: greedy nearest-neighbour association.

The walking-skeleton tracker (ROADMAP M1.2); M6 replaces it with Kalman filters, global
assignment and track scoring. Per frame:

1. Every live track predicts its position at the detection time from its velocity.
2. Track-detection pairs within ``gate_m`` are assigned greedily, closest first.
3. A track's position is its latest detection; its velocity is the least-squares slope of its
   last ``velocity_window`` positions.
4. Unassigned detections start ``TENTATIVE`` tracks, which become ``CONFIRMED`` after
   ``confirm_hits`` hits. A track missed in a frame is ``COASTING``; after ``max_misses``
   consecutive misses it is ``LOST`` and reported one last time.

Track identifiers are UUIDv5 values derived from the device and the track's first detection,
so the same input always gives the same identifiers.
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import numpy as np

from apus_core.domain import TrackState, TrackStatus

if TYPE_CHECKING:
    import numpy.typing as npt

__all__ = ["TRACK_NAMESPACE", "NearestNeighbourTracker", "TrackerConfig"]

TRACK_NAMESPACE = uuid.UUID("6f0c5d0e-8e0a-4c1e-9a43-2b6f3a1d7c55")
"""Namespace of the UUIDv5 track identifiers."""

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class TrackerConfig:
    """Parameters of the nearest-neighbour tracker.

    Attributes:
        gate_m: Largest distance between a prediction and a detection that may be associated.
        confirm_hits: Hits after which a track is confirmed.
        max_misses: Consecutive misses after which a track is lost. Ten frames (1 s at 10 Hz)
            bridge the gaps that appear when a distant bird slips between two beams.
        velocity_window: Positions used for the velocity estimate.
    """

    gate_m: float = 5.0
    confirm_hits: int = 3
    max_misses: int = 10
    velocity_window: int = 10


@dataclass
class _Track:
    track_id: uuid.UUID
    times_ns: deque[int]
    positions: deque[npt.NDArray[np.float64]]
    extent_m: float
    point_count: int
    hits: int = 1
    misses: int = 0
    confirmed: bool = False
    velocity: npt.NDArray[np.float64] = field(default_factory=lambda: np.zeros(3))

    def predict(self, time_ns: int) -> npt.NDArray[np.float64]:
        return self.positions[-1] + self.velocity * ((time_ns - self.times_ns[-1]) / 1e9)

    def update(self, time_ns: int, record: np.void, config: TrackerConfig) -> None:
        self.times_ns.append(time_ns)
        self.positions.append(np.array([record["east_m"], record["north_m"], record["up_m"]]))
        self.extent_m = float(record["extent_m"])
        self.point_count = int(record["point_count"])
        self.hits += 1
        self.misses = 0
        self.confirmed = self.confirmed or self.hits >= config.confirm_hits
        if len(self.positions) >= 2:  # noqa: PLR2004 - a slope needs two points
            t = (np.asarray(self.times_ns, dtype=np.int64) - self.times_ns[0]) / 1e9
            xyz = np.asarray(self.positions)
            self.velocity = np.polyfit(t, xyz, deg=1)[0]

    def state(self, time_ns: int, status: TrackStatus) -> TrackState:
        sigma = max(self.extent_m, 0.1) / 2.0
        variance = sigma**2
        coasting = status in {TrackStatus.COASTING, TrackStatus.LOST}
        position = self.predict(time_ns) if coasting else self.positions[-1]
        return TrackState(
            observed_at=_EPOCH + timedelta(microseconds=time_ns // 1_000),
            status=status,
            position_m=(float(position[0]), float(position[1]), float(position[2])),
            velocity_mps=(
                float(self.velocity[0]),
                float(self.velocity[1]),
                float(self.velocity[2]),
            ),
            position_covariance_m2=(variance, 0.0, 0.0, 0.0, variance, 0.0, 0.0, 0.0, variance),
            point_count=0 if coasting else self.point_count,
            quality=self.hits / (self.hits + self.misses),
        )


@dataclass
class NearestNeighbourTracker:
    """Tracks detections of one device across frames.

    Attributes:
        device_id: Device whose detections are tracked; part of the track identifiers.
        config: Tracker parameters.
    """

    device_id: str
    config: TrackerConfig = field(default_factory=TrackerConfig)
    _tracks: list[_Track] = field(default_factory=list, repr=False)

    @property
    def live_tracks(self) -> int:
        """Tracks that are not lost."""
        return len(self._tracks)

    def step(
        self, frame_time_ns: int, detections: npt.NDArray[np.void]
    ) -> list[tuple[uuid.UUID, TrackState]]:
        """Process the detections of one frame; returns one state per live or ended track."""
        cfg = self.config
        assigned: dict[int, int] = {}
        if self._tracks and len(detections):
            measured = np.stack(
                (detections["east_m"], detections["north_m"], detections["up_m"]), axis=-1
            )
            predicted = np.array([t.predict(frame_time_ns) for t in self._tracks])
            distance = np.linalg.norm(predicted[:, np.newaxis] - measured[np.newaxis], axis=-1)
            for flat in np.argsort(distance, axis=None, kind="stable"):
                ti, di = divmod(int(flat), len(detections))
                if distance[ti, di] > cfg.gate_m:
                    break
                if ti not in assigned and di not in assigned.values():
                    assigned[ti] = di
        updates: list[tuple[uuid.UUID, TrackState]] = []
        survivors: list[_Track] = []
        for ti, track in enumerate(self._tracks):
            if ti in assigned:
                record = detections[assigned[ti]]
                track.update(int(record["observed_time_ns"]), record, cfg)
                status = TrackStatus.CONFIRMED if track.confirmed else TrackStatus.TENTATIVE
                updates.append((track.track_id, track.state(track.times_ns[-1], status)))
                survivors.append(track)
                continue
            track.misses += 1
            if track.misses >= cfg.max_misses:
                if track.confirmed:
                    updates.append((track.track_id, track.state(frame_time_ns, TrackStatus.LOST)))
                continue
            if track.confirmed:
                updates.append((track.track_id, track.state(frame_time_ns, TrackStatus.COASTING)))
            survivors.append(track)
        for di in sorted(set(range(len(detections))) - set(assigned.values())):
            track = self._start(detections[di])
            updates.append((track.track_id, track.state(track.times_ns[-1], TrackStatus.TENTATIVE)))
            survivors.append(track)
        self._tracks = survivors
        return updates

    def finish(self, time_ns: int) -> list[tuple[uuid.UUID, TrackState]]:
        """End every live track, for example at the end of a stream."""
        ended = [
            (t.track_id, t.state(max(time_ns, t.times_ns[-1] + 1_000), TrackStatus.LOST))
            for t in self._tracks
            if t.confirmed
        ]
        self._tracks = []
        return ended

    def _start(self, record: np.void) -> _Track:
        time_ns = int(record["observed_time_ns"])
        name = f"{self.device_id}/{time_ns}/{float(record['east_m']):.3f}"
        name += f"/{float(record['north_m']):.3f}/{float(record['up_m']):.3f}"
        window = self.config.velocity_window
        return _Track(
            track_id=uuid.uuid5(TRACK_NAMESPACE, name),
            times_ns=deque([time_ns], maxlen=window),
            positions=deque(
                [np.array([record["east_m"], record["north_m"], record["up_m"]])], maxlen=window
            ),
            extent_m=float(record["extent_m"]),
            point_count=int(record["point_count"]),
        )

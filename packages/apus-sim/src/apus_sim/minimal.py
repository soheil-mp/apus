"""Minimal simulator for the walking skeleton (ROADMAP M1.1).

One sensor, an empty sky and one bird flying a straight line at constant speed, seen by an
ideal sensor: every beam is an infinitely thin ray, there is no noise, no dropout and no
clutter. The bird is a sphere. Later milestones (M3) replace each of these simplifications.

The simulator produces two streams that never mix (ADR-0003):

* **frames**, which the edge sees, encoded as UDP datagrams by :mod:`apus_core.packets`;
* **ground truth**, the bird's true state at every frame, which only tests and evaluation see.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

import numpy as np

from apus_core.coordinates import SensorPose, spherical_to_cartesian
from apus_core.domain import Frame
from apus_core.packets import SensorGeometry

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import TextIO

    import numpy.typing as npt

__all__ = [
    "DEFAULT_GEOMETRY",
    "DEFAULT_POSE",
    "BirdTruth",
    "StraightLineBird",
    "StraightLineScenario",
    "write_truth",
]

DEFAULT_GEOMETRY = SensorGeometry.uniform(
    rows=64, lowest_deg=5.0, highest_deg=45.0, cols_per_frame=1024, frame_rate_hz=10.0
)
"""A 64-beam sensor looking at the sky between 5 and 45 degrees elevation."""

DEFAULT_POSE = SensorPose(position_m=(0.0, 0.0, 2.0))
"""A level sensor 2 m above the site origin, its forward axis pointing east."""

_BIRD_INTENSITY = 80.0


@dataclass(frozen=True)
class StraightLineBird:
    """A spherical bird flying at constant velocity.

    Attributes:
        start_m: Position at the scenario start, site ENU metres.
        velocity_mps: Constant velocity, site ENU metres per second.
        radius_m: Radius of the sphere that stands in for body and wings.
    """

    start_m: tuple[float, float, float]
    velocity_mps: tuple[float, float, float]
    radius_m: float = 0.5

    def position_at(self, t_s: npt.ArrayLike) -> npt.NDArray[np.float64]:
        """Positions at times ``t_s`` (seconds since the start), shape ``(..., 3)``."""
        t = np.asarray(t_s, dtype=np.float64)[..., np.newaxis]
        start = np.asarray(self.start_m, dtype=np.float64)
        return start + t * np.asarray(self.velocity_mps, dtype=np.float64)


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


@dataclass(frozen=True)
class StraightLineScenario:
    """A seeded straight-line scenario.

    Attributes:
        bird: The bird and its flight line.
        pose: Sensor position and orientation in the site frame.
        geometry: Sensor geometry.
        start_time_ns: UTC time of the first frame, ns since the Unix epoch.
        device_id: Identifier the frames carry.
    """

    bird: StraightLineBird
    pose: SensorPose = DEFAULT_POSE
    geometry: SensorGeometry = DEFAULT_GEOMETRY
    start_time_ns: int = 1_777_593_600 * 1_000_000_000  # 2026-05-01T00:00:00Z
    device_id: str = "lidar-1"

    @classmethod
    def from_seed(
        cls,
        seed: int,
        *,
        duration_s: float = 30.0,
        closest_approach_m: float = 40.0,
    ) -> StraightLineScenario:
        """A scenario whose bird crosses the sensor's view at a seeded height and heading.

        The bird passes its closest point to the sensor half-way through the scenario, at
        ``closest_approach_m`` horizontal distance, between 15 and 30 m up, at 8 to 14 m/s.
        """
        rng = np.random.default_rng(seed)
        heading = rng.uniform(0.0, 2.0 * math.pi)
        speed = rng.uniform(8.0, 14.0)
        height = rng.uniform(15.0, 30.0)
        direction = np.array([math.cos(heading), math.sin(heading), 0.0])
        normal = np.array([-direction[1], direction[0], 0.0])
        midpoint = normal * closest_approach_m + np.array([0.0, 0.0, height])
        start = midpoint - direction * speed * duration_s / 2.0
        bird = StraightLineBird(
            start_m=(float(start[0]), float(start[1]), float(start[2])),
            velocity_mps=(float(direction[0] * speed), float(direction[1] * speed), 0.0),
        )
        return cls(bird=bird)

    def frame_count(self, duration_s: float) -> int:
        """Number of whole frames in ``duration_s``."""
        return int(duration_s * self.geometry.frame_rate_hz + 1e-9)

    @property
    def _ray_directions_site(self) -> npt.NDArray[np.float64]:
        """Unit beam directions in the site frame, shape ``(rows, cols, 3)``."""
        g = self.geometry
        az, el = np.meshgrid(g.azimuth_rad, g.elevation_rad)
        return spherical_to_cartesian(1.0, az, el) @ self.pose.rotation.T

    def frames(self, duration_s: float) -> Iterator[tuple[Frame, BirdTruth]]:
        """Generate every frame of the scenario together with its ground truth."""
        g = self.geometry
        rays = self._ray_directions_site
        origin = np.asarray(self.pose.position_m)
        col_offsets = g.column_time_offset_ns
        time_offset_ns = np.broadcast_to(col_offsets, (g.rows, g.cols_per_frame))
        for frame_id in range(self.frame_count(duration_s)):
            frame_t_ns = frame_id * g.frame_period_ns
            col_t_s = (frame_t_ns + col_offsets) / 1e9
            centres = self.bird.position_at(col_t_s) - origin  # (cols, 3), relative to sensor
            range_m = _ray_sphere(rays, centres[np.newaxis, :, :], self.bird.radius_m)
            range_m[range_m > g.max_range_m] = np.nan
            intensity = np.where(np.isfinite(range_m), _BIRD_INTENSITY, 0.0)
            frame = Frame(
                device_id=self.device_id,
                frame_id=frame_id,
                start_time_ns=self.start_time_ns + frame_t_ns,
                elevation_rad=g.elevation_rad,
                azimuth_rad=g.azimuth_rad,
                range_m=range_m.astype(np.float32),
                intensity=intensity.astype(np.float32),
                time_offset_ns=time_offset_ns,
            )
            yield frame, self._truth(frame_id, frame_t_ns)

    def _truth(self, frame_id: int, frame_t_ns: int) -> BirdTruth:
        east, north, up = self.bird.position_at(frame_t_ns / 1e9)
        ve, vn, vu = self.bird.velocity_mps
        return BirdTruth(
            frame_id=frame_id,
            time_ns=self.start_time_ns + frame_t_ns,
            east_m=float(east),
            north_m=float(north),
            up_m=float(up),
            velocity_east_mps=ve,
            velocity_north_mps=vn,
            velocity_up_mps=vu,
            radius_m=self.bird.radius_m,
        )


def _ray_sphere(
    directions: npt.NDArray[np.float64], centres: npt.NDArray[np.float64], radius: float
) -> npt.NDArray[np.float64]:
    """Distance along unit rays from the origin to the first hit on spheres; NaN for a miss."""
    along = np.einsum("...i,...i->...", directions, centres)
    closest_sq = np.einsum("...i,...i->...", centres, centres) - along**2
    half_chord_sq = radius**2 - closest_sq
    hit = (half_chord_sq >= 0) & (along > 0)
    distance = along - np.sqrt(np.where(hit, half_chord_sq, 0.0))
    return np.where(hit & (distance > 0), distance, np.nan)


def write_truth(records: Iterator[BirdTruth] | list[BirdTruth], stream: TextIO) -> int:
    """Write ground-truth records as JSON Lines; returns the number written."""
    count = 0
    for record in records:
        stream.write(json.dumps(asdict(record), separators=(",", ":")) + "\n")
        count += 1
    return count

"""Core domain types shared by the simulator, the edge runtime and the platform.

Two representations are used on purpose:

* **Pydantic models** validate data where it crosses a boundary: configuration, messages, API
  payloads. They are immutable, reject unknown fields and use SI units with unit suffixes.
* **NumPy structured arrays** hold many records in hot paths, for example every return in a
  frame or every detection in a batch. :data:`POINT_DTYPE` and :data:`DETECTION_DTYPE` define
  their layout; :meth:`Detection.from_record` and :meth:`Detection.to_records` convert between
  the two.

Positions are in the site's East-North-Up frame (:mod:`apus_core.coordinates`) unless a name
says otherwise. Times are UTC: aware :class:`~datetime.datetime` values in models and
nanoseconds since the Unix epoch (``*_time_ns``) in arrays.
"""

from __future__ import annotations

import enum
import itertools
import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Self

import numpy as np
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from apus_core.coordinates import LocalFrame, SensorPose, spherical_to_cartesian

if TYPE_CHECKING:
    from collections.abc import Iterable

    import numpy.typing as npt

__all__ = [
    "DETECTION_DTYPE",
    "POINT_DTYPE",
    "Advisory",
    "AdvisoryLevel",
    "Detection",
    "Frame",
    "SensorPose",
    "Site",
    "Track",
    "TrackState",
    "TrackStatus",
    "Vector3",
]

Vector3 = tuple[float, float, float]
"""East, north and up components in the site frame."""

_SLUG = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
SiteId = Annotated[str, Field(pattern=_SLUG, max_length=64)]
DeviceId = Annotated[str, Field(pattern=_SLUG, max_length=64)]
UnitInterval = Annotated[float, Field(ge=0.0, le=1.0)]

POINT_DTYPE = np.dtype(
    [
        ("x_m", np.float32),
        ("y_m", np.float32),
        ("z_m", np.float32),
        ("intensity", np.float32),
        ("time_offset_ns", np.int64),
        ("row", np.uint16),
        ("col", np.uint16),
    ]
)
"""One lidar return in the sensor frame, with its time offset from the frame start."""

DETECTION_DTYPE = np.dtype(
    [
        ("frame_id", np.uint64),
        ("observed_time_ns", np.int64),
        ("east_m", np.float64),
        ("north_m", np.float64),
        ("up_m", np.float64),
        ("extent_m", np.float32),
        ("point_count", np.uint32),
        ("mean_intensity", np.float32),
    ]
)
"""One detection: a group of foreground returns that probably belong to one target."""


class _Model(BaseModel):
    """Base for every boundary model: immutable, strict about unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


# --- Site and sensor ----------------------------------------------------------------------


class Site(_Model):
    """A monitoring site and the reference point of its East-North-Up frame.

    Attributes:
        site_id: Lower-case slug, for example ``demo-site``.
        name: Human-readable name.
        reference_lat_deg: WGS 84 latitude of the ENU origin.
        reference_lon_deg: WGS 84 longitude of the ENU origin.
        reference_height_m: Ellipsoidal height of the ENU origin.
    """

    site_id: SiteId
    name: str = Field(min_length=1, max_length=200)
    reference_lat_deg: float = Field(ge=-90.0, le=90.0)
    reference_lon_deg: float = Field(ge=-180.0, le=180.0)
    reference_height_m: float = 0.0

    def local_frame(self) -> LocalFrame:
        """The site's East-North-Up frame."""
        return LocalFrame(self.reference_lat_deg, self.reference_lon_deg, self.reference_height_m)


# --- Frames and points --------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class Frame:
    """One complete sweep of a lidar as a range image.

    Rows follow the beam elevations and columns the azimuths. A pixel without a return holds
    ``NaN`` in :attr:`range_m`. Each pixel has its own time offset from :attr:`start_time_ns`,
    because a spinning sensor measures its columns one after another.

    Attributes:
        device_id: Edge device that produced the frame.
        frame_id: Per-device counter, increasing by one per frame.
        start_time_ns: UTC time of the first measurement, in ns since the Unix epoch.
        elevation_rad: Beam elevations, shape ``(rows,)``.
        azimuth_rad: Column azimuths, shape ``(cols,)``.
        range_m: Range image, shape ``(rows, cols)``; ``NaN`` means no return.
        intensity: Return intensity on the sensor's scale, shape ``(rows, cols)``.
        time_offset_ns: Measurement time of each pixel after the frame start, shape
            ``(rows, cols)``, non-negative.
    """

    device_id: str
    frame_id: int
    start_time_ns: int
    elevation_rad: npt.NDArray[np.float64]
    azimuth_rad: npt.NDArray[np.float64]
    range_m: npt.NDArray[np.float32]
    intensity: npt.NDArray[np.float32]
    time_offset_ns: npt.NDArray[np.int64] = field(repr=False)

    def __post_init__(self) -> None:
        """Check that the arrays agree in shape and that times and ranges are valid."""
        shape = (self.elevation_rad.size, self.azimuth_rad.size)
        for name in ("range_m", "intensity", "time_offset_ns"):
            actual = getattr(self, name).shape
            if actual != shape:
                msg = f"{name} must have shape {shape} (rows, cols), got {actual}"
                raise ValueError(msg)
        if self.frame_id < 0:
            msg = f"frame_id must be non-negative, got {self.frame_id}"
            raise ValueError(msg)
        if np.any(self.time_offset_ns < 0):
            msg = "time_offset_ns must be non-negative"
            raise ValueError(msg)
        if np.any(self.range_m <= 0):  # NaN compares false, so empty pixels pass
            msg = "range_m must be positive where there is a return"
            raise ValueError(msg)

    @property
    def shape(self) -> tuple[int, int]:
        """``(rows, cols)`` of the range image."""
        return self.elevation_rad.size, self.azimuth_rad.size

    @property
    def return_mask(self) -> npt.NDArray[np.bool_]:
        """``True`` where a pixel holds a return."""
        return np.isfinite(self.range_m)

    @property
    def return_count(self) -> int:
        """Number of pixels with a return."""
        return int(np.count_nonzero(self.return_mask))

    def points(self) -> npt.NDArray[np.void]:
        """Every return as a :data:`POINT_DTYPE` record in the sensor frame."""
        rows, cols = np.nonzero(self.return_mask)
        xyz = spherical_to_cartesian(
            self.range_m[rows, cols], self.azimuth_rad[cols], self.elevation_rad[rows]
        )
        out = np.empty(rows.size, dtype=POINT_DTYPE)
        out["x_m"], out["y_m"], out["z_m"] = xyz[:, 0], xyz[:, 1], xyz[:, 2]
        out["intensity"] = self.intensity[rows, cols]
        out["time_offset_ns"] = self.time_offset_ns[rows, cols]
        out["row"], out["col"] = rows, cols
        return out


# --- Detections ---------------------------------------------------------------------------


class Detection(_Model):
    """A group of foreground returns in one frame that probably belong to one target.

    Attributes:
        frame_id: Frame the returns came from.
        observed_at: UTC time of the group's mean measurement time.
        position_m: Centroid in the site frame.
        extent_m: Largest distance between two returns of the group (0 for a single return).
        point_count: Number of returns in the group.
        mean_intensity: Mean return intensity on the sensor's scale.
    """

    frame_id: int = Field(ge=0)
    observed_at: AwareDatetime
    position_m: Vector3
    extent_m: float = Field(ge=0.0)
    point_count: int = Field(ge=1)
    mean_intensity: float = Field(ge=0.0)

    @classmethod
    def from_record(cls, record: np.void) -> Self:
        """Build a detection from one :data:`DETECTION_DTYPE` record."""
        return cls(
            frame_id=int(record["frame_id"]),
            observed_at=_from_ns(int(record["observed_time_ns"])),
            position_m=(float(record["east_m"]), float(record["north_m"]), float(record["up_m"])),
            extent_m=float(record["extent_m"]),
            point_count=int(record["point_count"]),
            mean_intensity=float(record["mean_intensity"]),
        )

    @staticmethod
    def to_records(detections: Iterable[Detection]) -> npt.NDArray[np.void]:
        """Pack detections into a :data:`DETECTION_DTYPE` array."""
        items = list(detections)
        out = np.empty(len(items), dtype=DETECTION_DTYPE)
        for i, d in enumerate(items):
            out[i] = (
                d.frame_id,
                _to_ns(d.observed_at),
                *d.position_m,
                d.extent_m,
                d.point_count,
                d.mean_intensity,
            )
        return out


# --- Tracks -------------------------------------------------------------------------------


class TrackStatus(enum.IntEnum):
    """Lifecycle state of a track; the values match ``apus.edge.v1.TrackStatus``."""

    UNSPECIFIED = 0
    TENTATIVE = 1
    CONFIRMED = 2
    COASTING = 3
    LOST = 4


class TrackState(_Model):
    """One state estimate of a track.

    Attributes:
        observed_at: UTC time of the measurements behind the estimate.
        status: Lifecycle state at that time.
        position_m: Estimated position in the site frame.
        velocity_mps: Estimated velocity in the site frame.
        position_covariance_m2: 3 x 3 position covariance, row-major, symmetric with a
            non-negative diagonal.
        point_count: Returns associated with the track in this update (0 while coasting).
        quality: Track quality between 0 (poor) and 1 (excellent).
    """

    observed_at: AwareDatetime
    status: TrackStatus
    position_m: Vector3
    velocity_mps: Vector3 = (0.0, 0.0, 0.0)
    position_covariance_m2: tuple[float, ...] = Field(
        default=(0.0,) * 9, min_length=9, max_length=9
    )
    point_count: int = Field(default=0, ge=0)
    quality: UnitInterval = 0.0

    @model_validator(mode="after")
    def _check_covariance(self) -> Self:
        cov = np.asarray(self.position_covariance_m2).reshape(3, 3)
        if not np.allclose(cov, cov.T, rtol=1e-9, atol=1e-12):
            msg = "position_covariance_m2 must be symmetric"
            raise ValueError(msg)
        if np.any(np.diag(cov) < 0):
            msg = "position_covariance_m2 must have a non-negative diagonal"
            raise ValueError(msg)
        return self

    @property
    def speed_mps(self) -> float:
        """Magnitude of the velocity."""
        return math.hypot(*self.velocity_mps)


class Track(_Model):
    """The history of one tracked target.

    Attributes:
        track_id: Identifier that stays the same for the life of the track.
        site_id: Site that observed the track.
        device_id: Edge device that tracked it.
        states: State estimates in strictly increasing time order (at least one).
    """

    track_id: uuid.UUID
    site_id: SiteId
    device_id: DeviceId
    states: tuple[TrackState, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        times = [s.observed_at for s in self.states]
        if any(later <= earlier for earlier, later in itertools.pairwise(times)):
            msg = "states must be in strictly increasing time order"
            raise ValueError(msg)
        if any(s.status is TrackStatus.LOST for s in self.states[:-1]):
            msg = "only the last state of a track may be LOST"
            raise ValueError(msg)
        return self

    @property
    def first(self) -> TrackState:
        """Earliest state."""
        return self.states[0]

    @property
    def last(self) -> TrackState:
        """Latest state."""
        return self.states[-1]

    @property
    def duration_s(self) -> float:
        """Time between the first and the last state."""
        return (self.last.observed_at - self.first.observed_at).total_seconds()

    @property
    def path_length_m(self) -> float:
        """Length of the polyline through the state positions."""
        positions = np.asarray([s.position_m for s in self.states])
        return float(np.linalg.norm(np.diff(positions, axis=0), axis=1).sum())


# --- Advisories ---------------------------------------------------------------------------


class AdvisoryLevel(enum.StrEnum):
    """How strongly an advisory asks the (simulated) operator to act."""

    INFO = "info"
    CAUTION = "caution"
    CURTAIL = "curtail"


class Advisory(_Model):
    """A simulated, advisory-only message about birds near a virtual turbine.

    Every advisory names the rule that raised it, so it can be explained (ADR-0002).

    Attributes:
        advisory_id: Unique identifier.
        site_id: Site the advisory is for.
        issued_at: UTC time the advisory was raised.
        valid_until: UTC time after which it no longer applies.
        level: How strongly it asks for action.
        rule_id: Identifier of the rule, including the rule-set version.
        reason: Short explanation in plain words.
        track_ids: Tracks that triggered the rule (at least one).
    """

    advisory_id: uuid.UUID
    site_id: SiteId
    issued_at: AwareDatetime
    valid_until: AwareDatetime
    level: AdvisoryLevel
    rule_id: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)
    track_ids: tuple[uuid.UUID, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_validity(self) -> Self:
        if self.valid_until <= self.issued_at:
            msg = "valid_until must be after issued_at"
            raise ValueError(msg)
        return self


# --- Helpers ------------------------------------------------------------------------------

_NS_PER_S = 1_000_000_000
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _to_ns(moment: datetime) -> int:
    """Nanoseconds since the Unix epoch for an aware datetime (microsecond precision)."""
    delta = moment - _EPOCH
    return (delta.days * 86_400 + delta.seconds) * _NS_PER_S + delta.microseconds * 1_000


def _from_ns(time_ns: int) -> datetime:
    """Aware UTC datetime for nanoseconds since the Unix epoch, truncated to microseconds."""
    return _EPOCH + timedelta(microseconds=time_ns // 1_000)

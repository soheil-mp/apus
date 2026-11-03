"""Time model: device monotonic clock, UTC, clock offsets and the clock-skew policy.

An edge device measures with its **monotonic clock**, which never jumps but has an arbitrary
origin. Messages and tables use **UTC** (nanoseconds since the Unix epoch). The two are linked by
a **clock offset**, ``utc_ns = monotonic_ns + offset_ns``, which the device learns from a time
source (PTP, NTP or GNSS PPS) and refreshes over time.

Rules (see ``docs/reference/time.md``):

* Perception (frame assembly, tracking) runs on monotonic time only, so a UTC correction never
  breaks a track.
* UTC is attached at the edge when a message is built, together with the offset's uncertainty
  and a :class:`ClockQuality` grade.
* Data is never dropped because of clock skew. Poorly synchronised data is graded so that
  consumers can filter it.
* An offset change larger than :attr:`SkewPolicy.jump_threshold_ns` is a **clock jump**; the
  edge reports it in its health telemetry.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

__all__ = [
    "NS_PER_MS",
    "NS_PER_S",
    "ClockOffset",
    "ClockQuality",
    "DeviceClock",
    "SkewPolicy",
    "TimeSource",
    "point_times_ns",
]

NS_PER_S = 1_000_000_000
NS_PER_MS = 1_000_000


class TimeSource(enum.StrEnum):
    """Where a clock offset came from, best first."""

    PTP = "ptp"
    GNSS_PPS = "gnss-pps"
    NTP = "ntp"
    NONE = "none"


class ClockQuality(enum.StrEnum):
    """Grade of a UTC timestamp, attached to every message."""

    GOOD = "good"
    DEGRADED = "degraded"
    UNSYNCHRONISED = "unsynchronised"


@dataclass(frozen=True)
class ClockOffset:
    """One measurement of the offset between the monotonic clock and UTC.

    Attributes:
        offset_ns: ``utc_ns - monotonic_ns`` at the time of measurement.
        uncertainty_ns: One-sigma uncertainty of the offset, non-negative.
        measured_at_monotonic_ns: Monotonic time at which the offset was measured.
        source: Time source that produced the measurement.
    """

    offset_ns: int
    uncertainty_ns: int
    measured_at_monotonic_ns: int
    source: TimeSource

    def __post_init__(self) -> None:
        """Reject a negative uncertainty."""
        if self.uncertainty_ns < 0:
            msg = f"uncertainty_ns must be non-negative, got {self.uncertainty_ns}"
            raise ValueError(msg)


@dataclass(frozen=True)
class SkewPolicy:
    """Thresholds that turn a clock offset into a :class:`ClockQuality`.

    The defaults allow a 10 m/s bird to be placed within about 5 cm (``good``) or 1 m
    (``degraded``) by time alone.

    Attributes:
        good_uncertainty_ns: Largest uncertainty, after ageing, still graded ``good``.
        degraded_uncertainty_ns: Largest uncertainty, after ageing, still graded ``degraded``.
        max_age_ns: Offsets older than this are ``unsynchronised`` whatever their uncertainty.
        drift_ppm: Assumed worst-case oscillator drift; uncertainty grows by this much per
            second since the measurement.
        jump_threshold_ns: Offset change between two measurements that counts as a jump.
    """

    good_uncertainty_ns: int = 5 * NS_PER_MS
    degraded_uncertainty_ns: int = 100 * NS_PER_MS
    max_age_ns: int = 3_600 * NS_PER_S
    drift_ppm: float = 50.0
    jump_threshold_ns: int = 50 * NS_PER_MS

    def aged_uncertainty_ns(self, offset: ClockOffset, now_monotonic_ns: int) -> int:
        """Offset uncertainty at ``now_monotonic_ns``, grown by the assumed drift."""
        age_ns = max(0, now_monotonic_ns - offset.measured_at_monotonic_ns)
        return offset.uncertainty_ns + round(age_ns * self.drift_ppm * 1e-6)

    def grade(self, offset: ClockOffset | None, now_monotonic_ns: int) -> ClockQuality:
        """Grade the UTC timestamps produced with ``offset`` at ``now_monotonic_ns``."""
        if offset is None or offset.source is TimeSource.NONE:
            return ClockQuality.UNSYNCHRONISED
        if now_monotonic_ns - offset.measured_at_monotonic_ns > self.max_age_ns:
            return ClockQuality.UNSYNCHRONISED
        uncertainty = self.aged_uncertainty_ns(offset, now_monotonic_ns)
        if uncertainty <= self.good_uncertainty_ns:
            return ClockQuality.GOOD
        if uncertainty <= self.degraded_uncertainty_ns:
            return ClockQuality.DEGRADED
        return ClockQuality.UNSYNCHRONISED

    def is_jump(self, previous: ClockOffset, current: ClockOffset) -> bool:
        """Whether the offset changed by more than the jump threshold."""
        return abs(current.offset_ns - previous.offset_ns) > self.jump_threshold_ns


class DeviceClock:
    """Converts device monotonic time to UTC using the latest clock offset.

    Until the first offset arrives, conversions use an offset of zero and are graded
    ``unsynchronised``.
    """

    def __init__(self, policy: SkewPolicy | None = None) -> None:
        """Create a clock that has not been synchronised yet."""
        self.policy = policy or SkewPolicy()
        self._offset: ClockOffset | None = None
        self.jump_count = 0

    @property
    def offset(self) -> ClockOffset | None:
        """The offset currently in use."""
        return self._offset

    def update(self, offset: ClockOffset) -> bool:
        """Start using a new offset measurement.

        Measurements older than the current one are ignored.

        Returns:
            ``True`` if the change from the previous offset is a clock jump.
        """
        previous = self._offset
        if previous is not None and (
            offset.measured_at_monotonic_ns < previous.measured_at_monotonic_ns
        ):
            return False
        self._offset = offset
        jumped = previous is not None and self.policy.is_jump(previous, offset)
        self.jump_count += jumped
        return jumped

    def to_utc_ns(self, monotonic_ns: int) -> int:
        """UTC nanoseconds for a monotonic time."""
        return monotonic_ns + (self._offset.offset_ns if self._offset else 0)

    def quality(self, now_monotonic_ns: int) -> ClockQuality:
        """Grade of UTC timestamps produced now."""
        return self.policy.grade(self._offset, now_monotonic_ns)


def point_times_ns(
    frame_start_utc_ns: int, time_offset_ns: npt.NDArray[np.int64]
) -> npt.NDArray[np.int64]:
    """Absolute UTC time of every pixel of a frame from its per-pixel offsets."""
    return np.int64(frame_start_utc_ns) + time_offset_ns.astype(np.int64, copy=False)

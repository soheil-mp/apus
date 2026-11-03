"""Tests for the time model."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from apus_core.clock import (
    NS_PER_MS,
    NS_PER_S,
    ClockOffset,
    ClockQuality,
    DeviceClock,
    SkewPolicy,
    TimeSource,
    point_times_ns,
)

UTC_2026 = 1_777_593_600 * NS_PER_S  # 2026-05-01T00:00:00Z


def offset(
    at_s: float = 0.0,
    uncertainty_ms: float = 1.0,
    offset_ns: int = UTC_2026,
    source: TimeSource = TimeSource.NTP,
) -> ClockOffset:
    return ClockOffset(
        offset_ns=offset_ns,
        uncertainty_ns=round(uncertainty_ms * NS_PER_MS),
        measured_at_monotonic_ns=round(at_s * NS_PER_S),
        source=source,
    )


class TestSkewPolicy:
    policy = SkewPolicy()

    @pytest.mark.parametrize(
        ("uncertainty_ms", "expected"),
        [
            (0.001, ClockQuality.GOOD),
            (5.0, ClockQuality.GOOD),
            (5.1, ClockQuality.DEGRADED),
            (100.0, ClockQuality.DEGRADED),
            (100.1, ClockQuality.UNSYNCHRONISED),
        ],
    )
    def test_grades_by_uncertainty(self, uncertainty_ms: float, expected: ClockQuality) -> None:
        assert self.policy.grade(offset(uncertainty_ms=uncertainty_ms), 0) is expected

    def test_uncertainty_grows_with_age(self) -> None:
        # 1 ms + 50 ppm x 100 s = 6 ms: no longer good.
        sync = offset(uncertainty_ms=1.0)
        assert self.policy.aged_uncertainty_ns(sync, 100 * NS_PER_S) == 6 * NS_PER_MS
        assert self.policy.grade(sync, 100 * NS_PER_S) is ClockQuality.DEGRADED

    def test_old_offsets_are_unsynchronised(self) -> None:
        sync = offset(uncertainty_ms=0.0, source=TimeSource.PTP)
        policy = SkewPolicy(drift_ppm=0.0)
        assert policy.grade(sync, policy.max_age_ns) is ClockQuality.GOOD
        assert policy.grade(sync, policy.max_age_ns + 1) is ClockQuality.UNSYNCHRONISED

    def test_without_a_source_nothing_is_synchronised(self) -> None:
        assert self.policy.grade(None, 0) is ClockQuality.UNSYNCHRONISED
        sync = offset(source=TimeSource.NONE, uncertainty_ms=0)
        assert self.policy.grade(sync, 0) is ClockQuality.UNSYNCHRONISED

    def test_detects_jumps_above_the_threshold(self) -> None:
        a = offset()
        assert not self.policy.is_jump(a, offset(offset_ns=UTC_2026 + 50 * NS_PER_MS))
        assert self.policy.is_jump(a, offset(offset_ns=UTC_2026 - 51 * NS_PER_MS))

    def test_rejects_negative_uncertainty(self) -> None:
        with pytest.raises(ValueError, match="uncertainty_ns"):
            offset(uncertainty_ms=-1)


class TestDeviceClock:
    def test_unsynchronised_until_the_first_offset(self) -> None:
        clock = DeviceClock()
        assert clock.offset is None
        assert clock.to_utc_ns(123) == 123
        assert clock.quality(0) is ClockQuality.UNSYNCHRONISED

    @given(st.integers(0, 10**15), st.integers(-(10**18), 10**18))
    def test_converts_monotonic_time_with_the_offset(self, mono: int, off: int) -> None:
        clock = DeviceClock()
        clock.update(offset(offset_ns=off))
        assert clock.to_utc_ns(mono) == mono + off

    def test_counts_jumps(self) -> None:
        clock = DeviceClock()
        assert not clock.update(offset(at_s=0))
        assert not clock.update(offset(at_s=1, offset_ns=UTC_2026 + NS_PER_MS))
        assert clock.update(offset(at_s=2, offset_ns=UTC_2026 + NS_PER_S))
        assert clock.jump_count == 1

    def test_ignores_out_of_order_measurements(self) -> None:
        clock = DeviceClock()
        clock.update(offset(at_s=10, offset_ns=UTC_2026))
        assert not clock.update(offset(at_s=5, offset_ns=UTC_2026 + NS_PER_S))
        assert clock.to_utc_ns(0) == UTC_2026


def test_point_times_add_per_pixel_offsets_to_the_frame_start() -> None:
    offsets = np.array([[0, 50_000], [10, 50_010]], dtype=np.int64)
    times = point_times_ns(UTC_2026, offsets)
    assert times.dtype == np.int64
    np.testing.assert_array_equal(times, UTC_2026 + offsets)

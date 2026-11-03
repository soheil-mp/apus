"""Tests for the core domain types."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from apus_core.domain import (
    DETECTION_DTYPE,
    POINT_DTYPE,
    Advisory,
    AdvisoryLevel,
    Detection,
    Frame,
    Site,
    Track,
    TrackState,
    TrackStatus,
)

T0 = datetime(2026, 5, 1, 4, 30, tzinfo=UTC)


def make_frame(rows: int = 4, cols: int = 8) -> Frame:
    rng = np.random.default_rng(7)
    range_m = np.full((rows, cols), np.nan, dtype=np.float32)
    range_m[1, 2] = 50.0
    range_m[2, 5] = 120.0
    return Frame(
        device_id="lidar-1",
        frame_id=3,
        start_time_ns=1_000,
        elevation_rad=np.linspace(0.1, 0.4, rows),
        azimuth_rad=np.linspace(-0.5, 0.5, cols),
        range_m=range_m,
        intensity=rng.uniform(0, 255, (rows, cols)).astype(np.float32),
        time_offset_ns=np.broadcast_to(np.arange(cols, dtype=np.int64) * 100, (rows, cols)),
    )


class TestSite:
    def test_local_frame_origin_is_the_reference_point(self) -> None:
        site = Site(site_id="demo-site", name="Demo", reference_lat_deg=51.9, reference_lon_deg=5.1)
        enu = site.local_frame().geodetic_to_enu(51.9, 5.1, 0.0)
        np.testing.assert_allclose(enu, 0.0, atol=1e-6)

    @pytest.mark.parametrize("site_id", ["Demo", "demo_site", "-demo", "demo-", ""])
    def test_rejects_ids_that_are_not_slugs(self, site_id: str) -> None:
        with pytest.raises(ValidationError):
            Site(site_id=site_id, name="x", reference_lat_deg=0, reference_lon_deg=0)

    def test_is_immutable_and_strict(self) -> None:
        site = Site(site_id="a", name="x", reference_lat_deg=0, reference_lon_deg=0)
        with pytest.raises(ValidationError):
            site.name = "y"
        with pytest.raises(ValidationError):
            Site.model_validate(
                {
                    "site_id": "a",
                    "name": "x",
                    "reference_lat_deg": 0,
                    "reference_lon_deg": 0,
                    "x": 1,
                }
            )


class TestFrame:
    def test_points_returns_only_pixels_with_a_return(self) -> None:
        frame = make_frame()
        points = frame.points()
        assert points.dtype == POINT_DTYPE
        assert frame.return_count == 2
        assert sorted(zip(points["row"], points["col"], strict=True)) == [(1, 2), (2, 5)]

    def test_points_lie_at_the_measured_range(self) -> None:
        points = make_frame().points()
        ranges = np.sqrt(points["x_m"] ** 2 + points["y_m"] ** 2 + points["z_m"] ** 2)
        np.testing.assert_allclose(sorted(ranges), [50.0, 120.0], rtol=1e-6)

    def test_points_carry_their_time_offset(self) -> None:
        points = make_frame().points()
        assert sorted(points["time_offset_ns"].tolist()) == [200, 500]

    def test_rejects_mismatched_shapes(self) -> None:
        good = make_frame()
        with pytest.raises(ValueError, match="range_m must have shape"):
            Frame(
                device_id="d",
                frame_id=0,
                start_time_ns=0,
                elevation_rad=good.elevation_rad,
                azimuth_rad=good.azimuth_rad[:-1],
                range_m=good.range_m,
                intensity=good.intensity,
                time_offset_ns=good.time_offset_ns,
            )

    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [
            ("range_m", -1.0, "range_m must be positive"),
            ("time_offset_ns", -1, "time_offset_ns must be non-negative"),
        ],
    )
    def test_rejects_invalid_values(self, field: str, value: float, message: str) -> None:
        frame = make_frame()
        arrays: dict[str, Any] = {
            "range_m": frame.range_m.copy(),
            "intensity": frame.intensity,
            "time_offset_ns": frame.time_offset_ns.copy(),
        }
        arrays[field][0, 0] = value
        with pytest.raises(ValueError, match=message):
            Frame(
                device_id="d",
                frame_id=0,
                start_time_ns=0,
                elevation_rad=frame.elevation_rad,
                azimuth_rad=frame.azimuth_rad,
                **arrays,
            )

    def test_rejects_negative_frame_id(self) -> None:
        frame = make_frame()
        with pytest.raises(ValueError, match="frame_id"):
            Frame(
                device_id="d",
                frame_id=-1,
                start_time_ns=0,
                elevation_rad=frame.elevation_rad,
                azimuth_rad=frame.azimuth_rad,
                range_m=frame.range_m,
                intensity=frame.intensity,
                time_offset_ns=frame.time_offset_ns,
            )


detections = st.builds(
    Detection,
    frame_id=st.integers(0, 2**63),
    observed_at=st.integers(0, 10**12).map(lambda us: T0 + timedelta(microseconds=us)),
    position_m=st.tuples(*[st.floats(-5e3, 5e3, allow_nan=False)] * 3),
    extent_m=st.floats(0, 50, width=32),
    point_count=st.integers(1, 10_000),
    mean_intensity=st.floats(0, 1e4, width=32),
)


class TestDetection:
    @given(detections)
    def test_round_trips_through_a_structured_array(self, detection: Detection) -> None:
        records = Detection.to_records([detection])
        assert records.dtype == DETECTION_DTYPE
        assert Detection.from_record(records[0]) == detection

    def test_requires_an_aware_time(self) -> None:
        with pytest.raises(ValidationError):
            Detection(
                frame_id=0,
                observed_at=datetime(2026, 1, 1),  # noqa: DTZ001 - testing the rejection
                position_m=(0, 0, 0),
                extent_m=0,
                point_count=1,
                mean_intensity=0,
            )

    def test_rejects_non_finite_positions(self) -> None:
        with pytest.raises(ValidationError):
            Detection(
                frame_id=0,
                observed_at=T0,
                position_m=(math.nan, 0, 0),
                extent_m=0,
                point_count=1,
                mean_intensity=0,
            )


def state(
    seconds: float, status: TrackStatus = TrackStatus.CONFIRMED, **kwargs: object
) -> TrackState:
    east = 10.0 * seconds
    return TrackState.model_validate(
        {
            "observed_at": T0 + timedelta(seconds=seconds),
            "status": status,
            "position_m": (east, 0.0, 30.0),
            "velocity_mps": (10.0, 0.0, 0.0),
            **kwargs,
        }
    )


class TestTrack:
    def test_track_status_values_match_the_protobuf_enum(self) -> None:
        assert [s.value for s in TrackStatus] == [0, 1, 2, 3, 4]

    def test_summary_properties(self) -> None:
        track = Track(
            track_id=uuid.UUID(int=1),
            site_id="demo-site",
            device_id="lidar-1",
            states=(
                state(0, TrackStatus.TENTATIVE),
                state(1),
                state(2),
                state(3, TrackStatus.LOST),
            ),
        )
        assert track.duration_s == 3.0
        assert track.path_length_m == pytest.approx(30.0)
        assert track.last.speed_mps == pytest.approx(10.0)
        assert track.first.status is TrackStatus.TENTATIVE

    def test_rejects_states_out_of_order(self) -> None:
        with pytest.raises(ValidationError, match="increasing time order"):
            Track(track_id=uuid.uuid4(), site_id="s", device_id="d", states=(state(1), state(1)))

    def test_only_the_last_state_may_be_lost(self) -> None:
        with pytest.raises(ValidationError, match="LOST"):
            Track(
                track_id=uuid.uuid4(),
                site_id="s",
                device_id="d",
                states=(state(0, TrackStatus.LOST), state(1)),
            )

    def test_rejects_an_asymmetric_covariance(self) -> None:
        with pytest.raises(ValidationError, match="symmetric"):
            state(0, position_covariance_m2=(1, 0.5, 0, 0, 1, 0, 0, 0, 1))

    def test_rejects_a_negative_variance(self) -> None:
        with pytest.raises(ValidationError, match="non-negative diagonal"):
            state(0, position_covariance_m2=(-1, 0, 0, 0, 1, 0, 0, 0, 1))

    def test_rejects_quality_outside_the_unit_interval(self) -> None:
        with pytest.raises(ValidationError):
            state(0, quality=1.5)


class TestAdvisory:
    def make(self, **overrides: object) -> Advisory:
        values: dict[str, object] = {
            "advisory_id": uuid.UUID(int=9),
            "site_id": "demo-site",
            "issued_at": T0,
            "valid_until": T0 + timedelta(seconds=30),
            "level": "caution",
            "rule_id": "rsz-entry@1.0.0",
            "reason": "Confirmed large bird predicted to enter the rotor-swept zone in 8 s.",
            "track_ids": (uuid.UUID(int=1),),
        }
        return Advisory.model_validate(values | overrides)

    def test_parses_and_serialises(self) -> None:
        advisory = self.make()
        assert advisory.level is AdvisoryLevel.CAUTION
        assert Advisory.model_validate_json(advisory.model_dump_json()) == advisory

    def test_must_end_after_it_starts(self) -> None:
        with pytest.raises(ValidationError, match="valid_until"):
            self.make(valid_until=T0)

    def test_needs_at_least_one_track(self) -> None:
        with pytest.raises(ValidationError):
            self.make(track_ids=())

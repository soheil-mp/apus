"""Tests for the minimal detector."""

from __future__ import annotations

import numpy as np
import pytest

from apus_core.coordinates import SensorPose
from apus_core.domain import Frame
from apus_edge.detection import DetectorConfig, connected_groups, detect


def test_connected_groups_link_chains_of_close_points() -> None:
    points = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [10, 0, 0], [10.5, 0, 0], [30, 0, 0]])
    labels = connected_groups(points.astype(float), link_m=1.2)
    assert labels.tolist() == [0, 0, 0, 1, 1, 2]


def test_connected_groups_handles_empty_and_single_inputs() -> None:
    assert connected_groups(np.empty((0, 3)), 1.0).tolist() == []
    assert connected_groups(np.zeros((1, 3)), 1.0).tolist() == [0]


def test_connected_groups_merge_by_the_smallest_root() -> None:
    # 0 and 2 are far apart, 1 bridges them: all three share label 0.
    points = np.array([[0, 0, 0], [5, 0, 0], [2.5, 0, 0]], dtype=float)
    assert connected_groups(points, 3.0).tolist() == [0, 0, 0]


def frame_with_returns(pixels: dict[tuple[int, int], float]) -> Frame:
    rows, cols = 4, 360
    elevation = np.radians([40.0, 30.0, 20.0, 0.0])
    azimuth = np.radians(np.arange(cols, dtype=float))
    range_m = np.full((rows, cols), np.nan, dtype=np.float32)
    for (r, c), value in pixels.items():
        range_m[r, c] = value
    offsets = np.broadcast_to(np.arange(cols, dtype=np.int64) * 1000, (rows, cols))
    return Frame(
        device_id="d",
        frame_id=7,
        start_time_ns=10**18,
        elevation_rad=elevation,
        azimuth_rad=azimuth,
        range_m=range_m,
        intensity=np.full((rows, cols), 50.0, dtype=np.float32),
        time_offset_ns=offsets,
    )


def test_detect_groups_returns_into_detections() -> None:
    frame = frame_with_returns({(1, 10): 50.0, (1, 11): 50.0, (0, 200): 80.0})
    out = detect(frame, SensorPose(), DetectorConfig(link_m=1.5))
    # Groups are numbered by their first return in row-major order: the single return in row 0
    # comes first.
    assert out["point_count"].tolist() == [1, 2]
    assert out["frame_id"].tolist() == [7, 7]
    pair, single = out[1], out[0]
    assert pair["observed_time_ns"] == 10**18 + 10_500
    assert pair["extent_m"] == pytest.approx(
        2 * 50 * np.cos(np.radians(30)) * np.sin(np.radians(0.5)), rel=1e-3
    )
    assert single["extent_m"] == 0.0
    assert pair["up_m"] == pytest.approx(25.0, rel=1e-4)


def test_detect_ignores_returns_near_the_ground() -> None:
    frame = frame_with_returns({(3, 0): 30.0, (2, 0): 5.0})  # 0 m and 1.7 m up
    assert detect(frame, SensorPose(), DetectorConfig(min_height_m=5.0)).size == 0


def test_detect_refuses_crowded_frames() -> None:
    frame = frame_with_returns({(0, c): 50.0 for c in range(50)})
    with pytest.raises(OverflowError, match="exceed"):
        detect(frame, SensorPose(), DetectorConfig(max_points=10))


def test_detect_on_an_empty_frame() -> None:
    assert detect(frame_with_returns({}), SensorPose(), DetectorConfig()).size == 0

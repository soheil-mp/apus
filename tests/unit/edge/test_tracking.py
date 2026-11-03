"""Tests for the nearest-neighbour tracker."""

from __future__ import annotations

import uuid

import numpy as np
import pytest

from apus_core.domain import DETECTION_DTYPE, TrackState, TrackStatus
from apus_edge.tracking import NearestNeighbourTracker, TrackerConfig

PERIOD_NS = 100_000_000
Updates = list[tuple[uuid.UUID, TrackState]]


def detections(time_ns: int, *positions: tuple[float, float, float]) -> np.ndarray:
    out = np.zeros(len(positions), dtype=DETECTION_DTYPE)
    for i, (e, n, u) in enumerate(positions):
        out[i] = (0, time_ns, e, n, u, 0.4, 5, 80.0)
    return out


def run(frames: list[list[tuple[float, float, float]]], **config: int) -> list[Updates]:
    tracker = NearestNeighbourTracker("lidar-1", TrackerConfig(**config))
    out: list[Updates] = []
    for k, positions in enumerate(frames):
        out.append(tracker.step(k * PERIOD_NS, detections(k * PERIOD_NS, *positions)))
    out.append(tracker.finish(len(frames) * PERIOD_NS))
    return out


def test_a_steady_target_is_confirmed_and_estimates_its_velocity() -> None:
    steps = run([[(k * 1.0, 0.0, 20.0)] for k in range(12)], confirm_hits=3)
    statuses = [s.status for step in steps for _, s in step]
    assert statuses[:3] == [TrackStatus.TENTATIVE, TrackStatus.TENTATIVE, TrackStatus.CONFIRMED]
    assert statuses[-1] is TrackStatus.LOST
    assert len({tid for step in steps for tid, _ in step}) == 1
    last = steps[-2][0][1]
    assert last.velocity_mps == pytest.approx((10.0, 0.0, 0.0))
    assert last.quality == 1.0


def test_a_missed_target_coasts_then_is_lost() -> None:
    frames = [[(k * 1.0, 0.0, 20.0)] for k in range(5)] + [[]] * 3
    steps = run(frames, max_misses=3)
    statuses = [s.status for step in steps for _, s in step]
    assert statuses[-3:] == [TrackStatus.COASTING, TrackStatus.COASTING, TrackStatus.LOST]
    coast = steps[5][0][1]
    assert coast.position_m == pytest.approx((5.0, 0.0, 20.0))
    assert coast.point_count == 0
    assert steps[-1] == []  # nothing left to finish


def test_unconfirmed_tracks_disappear_silently() -> None:
    steps = run([[(0.0, 0.0, 20.0)], [], [], []], max_misses=2)
    assert [len(step) for step in steps] == [1, 0, 0, 0, 0]


def test_two_crossing_free_targets_keep_their_tracks() -> None:
    frames = [[(k * 1.0, 0.0, 20.0), (k * -1.0, 50.0, 30.0)] for k in range(6)]
    steps = run(frames)
    ids = {tid for step in steps for tid, _ in step}
    assert len(ids) == 2
    by_id: dict[uuid.UUID, list[float]] = {}
    for step in steps[:-1]:
        for tid, state in step:
            by_id.setdefault(tid, []).append(state.position_m[1])
    assert sorted({ys[0] for ys in by_id.values()}) == [0.0, 50.0]
    assert all(len(set(ys)) == 1 for ys in by_id.values())


def test_detections_outside_the_gate_start_new_tracks() -> None:
    steps = run([[(0.0, 0.0, 20.0)], [(30.0, 0.0, 20.0)]], gate_m=5)
    assert len({tid for step in steps for tid, _ in step}) == 2


def test_track_ids_are_deterministic() -> None:
    frames = [[(k * 1.0, 0.0, 20.0)] for k in range(4)]
    a = [tid for step in run(frames) for tid, _ in step]
    b = [tid for step in run(frames) for tid, _ in step]
    assert a == b
    assert a[0].version == 5

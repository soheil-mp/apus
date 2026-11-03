"""Tests for frame assembly."""

from __future__ import annotations

import numpy as np

from apus_core.domain import Frame
from apus_core.packets import SensorGeometry, encode_frame
from apus_edge.assembler import FrameAssembler

GEOMETRY = SensorGeometry.uniform(rows=8, lowest_deg=0, highest_deg=30, cols_per_frame=120)


def frame(frame_id: int, seed: int = 0) -> Frame:
    rng = np.random.default_rng(seed + frame_id)
    shape = (GEOMETRY.rows, GEOMETRY.cols_per_frame)
    range_m = np.round(rng.uniform(1, 100, shape), 3)
    range_m[rng.random(shape) < 0.5] = np.nan
    return Frame(
        device_id="lidar-1",
        frame_id=frame_id,
        start_time_ns=10**18 + frame_id * GEOMETRY.frame_period_ns,
        elevation_rad=GEOMETRY.elevation_rad,
        azimuth_rad=GEOMETRY.azimuth_rad,
        range_m=range_m.astype(np.float32),
        intensity=np.round(rng.uniform(0, 255, shape)).astype(np.float32),
        time_offset_ns=np.broadcast_to(GEOMETRY.column_time_offset_ns, shape),
    )


def datagrams(frame_id: int) -> list[bytes]:
    return list(encode_frame(frame(frame_id), max_bytes=400))


def assert_same(a: Frame, b: Frame) -> None:
    assert a.frame_id == b.frame_id
    assert a.start_time_ns == b.start_time_ns
    np.testing.assert_allclose(a.range_m, b.range_m, atol=5e-4)
    np.testing.assert_array_equal(a.intensity, b.intensity)
    np.testing.assert_array_equal(a.time_offset_ns, b.time_offset_ns)


def test_reassembles_complete_frames() -> None:
    assembler = FrameAssembler(GEOMETRY, "lidar-1")
    out = [f for d in datagrams(0) + datagrams(1) for f in assembler.push(d)]
    assert [f.frame_id for f in out] == [0, 1]
    assert_same(out[0], frame(0))
    assert assembler.stats.frames_complete == 2
    assert assembler.stats.frames_partial == 0


def test_any_datagram_order_within_a_frame() -> None:
    assembler = FrameAssembler(GEOMETRY, "lidar-1")
    shuffled = datagrams(4)
    np.random.default_rng(1).shuffle(shuffled)
    out = [f for d in shuffled for f in assembler.push(d)]
    assert len(out) == 1
    assert_same(out[0], frame(4))


def test_a_newer_frame_flushes_an_unfinished_one_as_partial() -> None:
    assembler = FrameAssembler(GEOMETRY, "lidar-1")
    first = datagrams(0)
    out = [f for d in first[1:] for f in assembler.push(d)]
    assert out == []
    out = assembler.push(datagrams(1)[0])
    assert [f.frame_id for f in out] == [0]
    assert np.isnan(out[0].range_m[:, : GEOMETRY.cols_per_frame // len(first)]).all()
    assert assembler.stats.frames_partial == 1
    assert assembler.stats.missing_columns > 0


def test_late_invalid_and_duplicate_datagrams_are_counted() -> None:
    assembler = FrameAssembler(GEOMETRY, "lidar-1")
    for d in datagrams(1):
        assembler.push(d)
    assembler.push(datagrams(0)[0])  # late: frame 1 was emitted already
    assembler.push(b"garbage")
    other = SensorGeometry.uniform(rows=4, lowest_deg=0, highest_deg=30, cols_per_frame=120)
    wrong = Frame(
        device_id="x",
        frame_id=9,
        start_time_ns=0,
        elevation_rad=other.elevation_rad,
        azimuth_rad=other.azimuth_rad,
        range_m=np.full((4, 120), np.nan, dtype=np.float32),
        intensity=np.zeros((4, 120), dtype=np.float32),
        time_offset_ns=np.zeros((4, 120), dtype=np.int64),
    )
    assembler.push(next(encode_frame(wrong)))
    second = datagrams(2)
    assembler.push(second[0])
    assembler.push(second[0])
    stats = assembler.stats
    assert (stats.late, stats.invalid, stats.duplicate_columns) == (1, 2, 120 // len(second))


def test_flush_emits_what_is_left() -> None:
    assembler = FrameAssembler(GEOMETRY, "lidar-1")
    assembler.push(datagrams(3)[0])
    assert [f.frame_id for f in assembler.flush()] == [3]
    assert assembler.flush() == []

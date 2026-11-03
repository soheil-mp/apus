"""Tests for the lidar packet wire format."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from apus_core.domain import Frame
from apus_core.packets import (
    HEADER_SIZE,
    MAX_DATAGRAM_BYTES,
    PacketError,
    SensorGeometry,
    column_dtype,
    decode,
    encode_frame,
)


def make_frame(geometry: SensorGeometry, seed: int = 0, frame_id: int = 5) -> Frame:
    rng = np.random.default_rng(seed)
    shape = (geometry.rows, geometry.cols_per_frame)
    range_m = rng.uniform(1.0, 150.0, shape)
    range_m[rng.random(shape) < 0.7] = np.nan
    return Frame(
        device_id="lidar-1",
        frame_id=frame_id,
        start_time_ns=1_777_593_600_000_000_000,
        elevation_rad=geometry.elevation_rad,
        azimuth_rad=geometry.azimuth_rad,
        range_m=range_m.astype(np.float32),
        intensity=rng.uniform(0, 255, shape).astype(np.float32),
        time_offset_ns=np.broadcast_to(geometry.column_time_offset_ns, shape),
    )


def reassemble(datagrams: list[bytes], geometry: SensorGeometry) -> tuple[np.ndarray, np.ndarray]:
    range_mm = np.zeros((geometry.rows, geometry.cols_per_frame), dtype=np.uint32)
    seen = np.zeros(geometry.cols_per_frame, dtype=bool)
    intensity = np.zeros_like(range_mm, dtype=np.uint16)
    for datagram in datagrams:
        header, cols = decode(datagram)
        sl = slice(header.first_col, header.first_col + header.col_count)
        assert not seen[sl].any()
        seen[sl] = True
        range_mm[:, sl] = cols["range_mm"].T
        intensity[:, sl] = cols["intensity"].T
    assert seen.all()
    return range_mm, intensity


class TestSensorGeometry:
    def test_uniform_spreads_beams_top_first(self) -> None:
        g = SensorGeometry.uniform(rows=5, lowest_deg=0.0, highest_deg=40.0)
        assert g.elevation_deg == (40.0, 30.0, 20.0, 10.0, 0.0)
        assert g.rows == 5

    def test_columns_cover_one_revolution(self) -> None:
        g = SensorGeometry.uniform(rows=4, lowest_deg=0, highest_deg=10, cols_per_frame=8)
        np.testing.assert_allclose(g.azimuth_rad, np.arange(8) * np.pi / 4)
        np.testing.assert_array_equal(g.column_time_offset_ns, np.arange(8) * 12_500_000)
        assert g.frame_period_ns == 100_000_000

    def test_datagrams_fit_the_mtu(self) -> None:
        g = SensorGeometry.uniform(rows=64, lowest_deg=0, highest_deg=45)
        per_packet = g.cols_per_packet()
        assert HEADER_SIZE + per_packet * column_dtype(64).itemsize <= MAX_DATAGRAM_BYTES
        assert HEADER_SIZE + (per_packet + 1) * column_dtype(64).itemsize > MAX_DATAGRAM_BYTES

    def test_rejects_columns_that_cannot_fit(self) -> None:
        g = SensorGeometry.uniform(rows=300, lowest_deg=0, highest_deg=45)
        with pytest.raises(ValueError, match="does not fit"):
            g.cols_per_packet()

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"elevation_deg": ()},
            {"elevation_deg": (1.0,), "cols_per_frame": 0},
            {"elevation_deg": (1.0,), "frame_rate_hz": 0.0},
        ],
    )
    def test_rejects_invalid_geometry(self, kwargs: dict[str, object]) -> None:
        with pytest.raises(ValueError):  # noqa: PT011 - each case has its own message
            SensorGeometry(**kwargs)  # type: ignore[arg-type]


class TestEncodeDecode:
    @given(seed=st.integers(0, 2**32 - 1), rows=st.integers(1, 64), cols=st.integers(1, 300))
    def test_round_trip_to_millimetres(self, seed: int, rows: int, cols: int) -> None:
        g = SensorGeometry.uniform(rows=rows, lowest_deg=0, highest_deg=45, cols_per_frame=cols)
        frame = make_frame(g, seed)
        datagrams = list(encode_frame(frame, first_sequence=10))
        assert all(len(d) <= MAX_DATAGRAM_BYTES for d in datagrams)
        range_mm, intensity = reassemble(datagrams, g)
        expected = np.nan_to_num(np.round(frame.range_m.astype(np.float64) * 1000), nan=0)
        np.testing.assert_array_equal(range_mm, expected)
        np.testing.assert_array_equal(intensity, np.round(frame.intensity))

    def test_headers_describe_the_frame(self) -> None:
        g = SensorGeometry.uniform(rows=16, lowest_deg=0, highest_deg=30, cols_per_frame=100)
        frame = make_frame(g)
        datagrams = list(encode_frame(frame, first_sequence=2**32 - 1))
        headers = [decode(d)[0] for d in datagrams]
        assert [h.sequence for h in headers[:2]] == [2**32 - 1, 0]
        assert {h.frame_id for h in headers} == {5}
        assert {h.frame_start_ns for h in headers} == {frame.start_time_ns}
        assert sum(h.col_count for h in headers) == 100
        _, cols = decode(datagrams[1])
        np.testing.assert_array_equal(
            cols["time_offset_ns"], g.column_time_offset_ns[headers[1].first_col :][: cols.size]
        )

    @pytest.mark.parametrize(
        ("mutate", "message"),
        [
            (lambda d: d[:10], "shorter than"),
            (lambda d: b"XXXX" + d[4:], "unknown magic"),
            (lambda d: d[:-1], "expected"),
            (lambda d: d[:24] + (0).to_bytes(2, "little") + d[26:], "inconsistent"),
        ],
    )
    def test_rejects_malformed_datagrams(self, mutate: object, message: str) -> None:
        g = SensorGeometry.uniform(rows=4, lowest_deg=0, highest_deg=10, cols_per_frame=8)
        datagram = next(encode_frame(make_frame(g)))
        with pytest.raises(PacketError, match=message):
            decode(mutate(datagram))  # type: ignore[operator]

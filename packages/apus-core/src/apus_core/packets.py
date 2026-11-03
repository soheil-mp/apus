"""Wire format of lidar data packets, shared by the simulator and the edge runtime.

A sensor sends each frame as a series of UDP datagrams. Every datagram carries a block of
consecutive columns of one frame. All numbers are little-endian.

Header, 32 bytes:

=====  ======  ===================  ===========================================================
Bytes  Type    Field                Meaning
=====  ======  ===================  ===========================================================
0-3    char 4  ``magic``            ``b"APL1"``: Apus lidar packet, version 1
4-7    u32     ``sequence``         Per-sensor datagram counter, wraps at 2³²
8-15   u64     ``frame_id``         Per-sensor frame counter
16-23  i64     ``frame_start_ns``   Sensor time of the frame's first column (ns)
24-25  u16     ``rows``             Beams per column
26-27  u16     ``first_col``        Index of the first column in this datagram
28-29  u16     ``col_count``        Columns in this datagram
30-31  u16     ``cols_per_frame``   Columns in a complete frame
=====  ======  ===================  ===========================================================

Then ``col_count`` column blocks, each ``8 + 6 * rows`` bytes: the column's time offset from
the frame start (u32, ns), its azimuth (f32, rad), then per beam the range (u32, mm; 0 means no
return) and the intensity (u16).

Beam elevations are not sent: like real sensors, they are fixed by the sensor model and come
from :class:`SensorGeometry`.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Iterator

    import numpy.typing as npt

    from apus_core.domain import Frame

__all__ = [
    "HEADER_SIZE",
    "MAGIC",
    "MAX_DATAGRAM_BYTES",
    "PacketError",
    "PacketHeader",
    "SensorGeometry",
    "column_dtype",
    "decode",
    "encode_frame",
]

MAGIC = b"APL1"
HEADER_SIZE = 32
MAX_DATAGRAM_BYTES = 1472
"""Largest UDP payload that fits a 1500-byte Ethernet frame without IP fragmentation."""

_HEADER = struct.Struct("<4sIQqHHHH")
_MAX_RANGE_MM = 2**32 - 1
_MAX_INTENSITY = 2**16 - 1


class PacketError(ValueError):
    """A datagram is not a valid Apus lidar packet."""


@dataclass(frozen=True)
class PacketHeader:
    """Decoded header of one datagram (see the module docstring for the layout)."""

    sequence: int
    frame_id: int
    frame_start_ns: int
    rows: int
    first_col: int
    col_count: int
    cols_per_frame: int


def column_dtype(rows: int) -> np.dtype[np.void]:
    """Packed NumPy layout of one column block for a sensor with ``rows`` beams."""
    return np.dtype(
        [
            ("time_offset_ns", "<u4"),
            ("azimuth_rad", "<f4"),
            ("range_mm", "<u4", (rows,)),
            ("intensity", "<u2", (rows,)),
        ]
    )


@dataclass(frozen=True)
class SensorGeometry:
    """Fixed geometry of a spinning multi-beam lidar.

    Attributes:
        elevation_deg: Beam elevations in degrees, one per row, top row first.
        cols_per_frame: Columns in one full revolution.
        frame_rate_hz: Revolutions per second.
        max_range_m: Largest range the sensor reports.
    """

    elevation_deg: tuple[float, ...]
    cols_per_frame: int = 1024
    frame_rate_hz: float = 10.0
    max_range_m: float = 200.0

    def __post_init__(self) -> None:
        """Validate the geometry."""
        if not self.elevation_deg:
            msg = "elevation_deg needs at least one beam"
            raise ValueError(msg)
        if not 0 < self.cols_per_frame <= 2**16 - 1:
            msg = f"cols_per_frame must be in 1..65535, got {self.cols_per_frame}"
            raise ValueError(msg)
        if self.frame_rate_hz <= 0 or self.max_range_m <= 0:
            msg = "frame_rate_hz and max_range_m must be positive"
            raise ValueError(msg)

    @classmethod
    def uniform(  # noqa: PLR0913 - mirrors the dataclass fields
        cls,
        rows: int,
        lowest_deg: float,
        highest_deg: float,
        *,
        cols_per_frame: int = 1024,
        frame_rate_hz: float = 10.0,
        max_range_m: float = 200.0,
    ) -> SensorGeometry:
        """Geometry with ``rows`` beams spread evenly between two elevations, top row first."""
        elevations = np.linspace(highest_deg, lowest_deg, rows)
        return cls(
            tuple(float(e) for e in elevations),
            cols_per_frame=cols_per_frame,
            frame_rate_hz=frame_rate_hz,
            max_range_m=max_range_m,
        )

    @property
    def rows(self) -> int:
        """Number of beams."""
        return len(self.elevation_deg)

    @cached_property
    def elevation_rad(self) -> npt.NDArray[np.float64]:
        """Beam elevations in radians."""
        return np.radians(np.asarray(self.elevation_deg, dtype=np.float64))

    @cached_property
    def azimuth_rad(self) -> npt.NDArray[np.float64]:
        """Nominal column azimuths in radians, counter-clockwise from the forward axis."""
        return np.arange(self.cols_per_frame, dtype=np.float64) * (
            2 * math.pi / self.cols_per_frame
        )

    @cached_property
    def column_time_offset_ns(self) -> npt.NDArray[np.int64]:
        """Time of each column after the frame start, in ns."""
        period_ns = 1e9 / self.frame_rate_hz
        return np.round(np.arange(self.cols_per_frame) * period_ns / self.cols_per_frame).astype(
            np.int64
        )

    @property
    def frame_period_ns(self) -> int:
        """Duration of one revolution in ns."""
        return round(1e9 / self.frame_rate_hz)

    def cols_per_packet(self, max_bytes: int = MAX_DATAGRAM_BYTES) -> int:
        """Most columns that fit into one datagram of at most ``max_bytes``."""
        per_col = column_dtype(self.rows).itemsize
        cols = (max_bytes - HEADER_SIZE) // per_col
        if cols < 1:
            msg = f"a column of {self.rows} beams ({per_col} B) does not fit in {max_bytes} B"
            raise ValueError(msg)
        return min(cols, self.cols_per_frame)


def encode_frame(
    frame: Frame,
    *,
    first_sequence: int = 0,
    max_bytes: int = MAX_DATAGRAM_BYTES,
) -> Iterator[bytes]:
    """Split a frame into datagrams.

    Ranges are rounded to millimetres and intensities to integers, as a real sensor reports them.
    All beams of a column share one measurement time, the frame's ``time_offset_ns`` in row 0.

    Args:
        frame: The frame to send. ``frame.start_time_ns`` becomes ``frame_start_ns``.
        first_sequence: Sequence number of the first datagram; later ones count up and wrap.
        max_bytes: Largest datagram size.

    Yields:
        One datagram per block of columns, in column order.
    """
    rows, cols = frame.shape
    dtype = column_dtype(rows)
    per_packet = max(1, (max_bytes - HEADER_SIZE) // dtype.itemsize)
    columns = np.zeros(cols, dtype=dtype)
    columns["time_offset_ns"] = frame.time_offset_ns[0]
    columns["azimuth_rad"] = frame.azimuth_rad
    range_mm = np.nan_to_num(np.round(frame.range_m.astype(np.float64) * 1000.0), nan=0.0)
    columns["range_mm"] = np.clip(range_mm, 0, _MAX_RANGE_MM).T
    columns["intensity"] = np.clip(np.round(frame.intensity), 0, _MAX_INTENSITY).T
    for n, first in enumerate(range(0, cols, per_packet)):
        block = columns[first : first + per_packet]
        header = _HEADER.pack(
            MAGIC,
            (first_sequence + n) % 2**32,
            frame.frame_id,
            frame.start_time_ns,
            rows,
            first,
            block.size,
            cols,
        )
        yield header + block.tobytes()


def decode(datagram: bytes) -> tuple[PacketHeader, npt.NDArray[np.void]]:
    """Decode one datagram into its header and column blocks.

    Raises:
        PacketError: If the datagram is truncated, has the wrong magic or an inconsistent size.
    """
    if len(datagram) < HEADER_SIZE:
        msg = f"datagram of {len(datagram)} B is shorter than the {HEADER_SIZE} B header"
        raise PacketError(msg)
    magic, sequence, frame_id, start_ns, rows, first_col, col_count, cols_per_frame = (
        _HEADER.unpack_from(datagram)
    )
    if magic != MAGIC:
        msg = f"unknown magic {magic!r}"
        raise PacketError(msg)
    if rows == 0 or col_count == 0 or first_col + col_count > cols_per_frame:
        msg = f"inconsistent column range {first_col}+{col_count} of {cols_per_frame}, {rows} rows"
        raise PacketError(msg)
    dtype = column_dtype(rows)
    expected = HEADER_SIZE + col_count * dtype.itemsize
    if len(datagram) != expected:
        msg = f"datagram is {len(datagram)} B, expected {expected} B"
        raise PacketError(msg)
    header = PacketHeader(sequence, frame_id, start_ns, rows, first_col, col_count, cols_per_frame)
    return header, np.frombuffer(datagram, dtype=dtype, offset=HEADER_SIZE)

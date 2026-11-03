"""Frame assembly: turn a stream of lidar datagrams back into complete frames.

The minimal policy of the walking skeleton (ROADMAP M1.2), refined in M4.2:

* A frame is emitted as soon as every column has arrived.
* When a datagram of a newer frame arrives, every older unfinished frame is emitted as a
  **partial** frame: missing columns hold no returns, and the frame is counted.
* Datagrams of frames already emitted are **late** and dropped; invalid datagrams are dropped.
  Both are counted, so no loss is silent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from apus_core.domain import Frame
from apus_core.packets import PacketError, SensorGeometry, decode

if TYPE_CHECKING:
    import numpy.typing as npt

__all__ = ["AssemblerStats", "FrameAssembler"]


@dataclass
class AssemblerStats:
    """Counters kept by a :class:`FrameAssembler`."""

    datagrams: int = 0
    invalid: int = 0
    late: int = 0
    duplicate_columns: int = 0
    frames_complete: int = 0
    frames_partial: int = 0
    missing_columns: int = 0


@dataclass
class _Pending:
    start_ns: int
    range_mm: npt.NDArray[np.uint32]
    intensity: npt.NDArray[np.uint16]
    azimuth_rad: npt.NDArray[np.float64]
    time_offset_ns: npt.NDArray[np.int64]
    seen: npt.NDArray[np.bool_]
    column_count: int = 0


@dataclass
class FrameAssembler:
    """Assembles frames for one sensor whose geometry is known.

    Attributes:
        geometry: Beam layout of the sensor.
        device_id: Identifier given to the assembled frames.
        stats: Counters; read them for health telemetry.
    """

    geometry: SensorGeometry
    device_id: str
    stats: AssemblerStats = field(default_factory=AssemblerStats)
    _pending: dict[int, _Pending] = field(default_factory=dict, repr=False)
    _newest_emitted: int = field(default=-1, repr=False)

    def push(self, datagram: bytes) -> list[Frame]:
        """Add one datagram; returns the frames it completes, oldest first."""
        self.stats.datagrams += 1
        try:
            header, columns = decode(datagram)
        except PacketError:
            self.stats.invalid += 1
            return []
        g = self.geometry
        if header.rows != g.rows or header.cols_per_frame != g.cols_per_frame:
            self.stats.invalid += 1
            return []
        if header.frame_id <= self._newest_emitted:
            self.stats.late += 1
            return []
        out = self._flush_older_than(header.frame_id)
        pending = self._pending.get(header.frame_id)
        if pending is None:
            pending = self._pending[header.frame_id] = self._new_pending(header.frame_start_ns)
        cols = slice(header.first_col, header.first_col + header.col_count)
        repeats = int(np.count_nonzero(pending.seen[cols]))
        self.stats.duplicate_columns += repeats
        pending.range_mm[:, cols] = columns["range_mm"].T
        pending.intensity[:, cols] = columns["intensity"].T
        pending.azimuth_rad[cols] = columns["azimuth_rad"]
        pending.time_offset_ns[cols] = columns["time_offset_ns"]
        pending.seen[cols] = True
        pending.column_count += header.col_count - repeats
        if pending.column_count == g.cols_per_frame:
            out.append(self._emit(header.frame_id))
        return out

    def flush(self) -> list[Frame]:
        """Emit every unfinished frame as partial, for example at the end of a stream."""
        return [self._emit(frame_id) for frame_id in sorted(self._pending)]

    def _new_pending(self, start_ns: int) -> _Pending:
        rows, cols = self.geometry.rows, self.geometry.cols_per_frame
        return _Pending(
            start_ns=start_ns,
            range_mm=np.zeros((rows, cols), dtype=np.uint32),
            intensity=np.zeros((rows, cols), dtype=np.uint16),
            azimuth_rad=self.geometry.azimuth_rad.copy(),
            time_offset_ns=self.geometry.column_time_offset_ns.copy(),
            seen=np.zeros(cols, dtype=bool),
        )

    def _flush_older_than(self, frame_id: int) -> list[Frame]:
        return [self._emit(old) for old in sorted(self._pending) if old < frame_id]

    def _emit(self, frame_id: int) -> Frame:
        pending = self._pending.pop(frame_id)
        missing = self.geometry.cols_per_frame - pending.column_count
        if missing:
            self.stats.frames_partial += 1
            self.stats.missing_columns += missing
        else:
            self.stats.frames_complete += 1
        self._newest_emitted = max(self._newest_emitted, frame_id)
        range_m = pending.range_mm.astype(np.float32) / np.float32(1000.0)
        range_m[pending.range_mm == 0] = np.nan
        return Frame(
            device_id=self.device_id,
            frame_id=frame_id,
            start_time_ns=pending.start_ns,
            elevation_rad=self.geometry.elevation_rad,
            azimuth_rad=pending.azimuth_rad,
            range_m=range_m,
            intensity=pending.intensity.astype(np.float32),
            time_offset_ns=np.broadcast_to(pending.time_offset_ns, range_m.shape),
        )

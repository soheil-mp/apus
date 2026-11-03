"""Conversions between domain types and Protobuf messages, and a framing for message streams.

Generated message classes live in :mod:`apus_core.gen` (see ``scripts/gen_proto.py``); code
outside this module should use the functions here instead of building messages by hand.

Streams of messages in files use the standard Protobuf length-delimited framing: each message
is preceded by its size as a base-128 varint. :func:`write_delimited` and :func:`read_delimited`
implement it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC
from typing import TYPE_CHECKING

from apus_core.domain import TrackState, TrackStatus
from apus_core.gen.apus.edge.v1 import track_update_pb2

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import BinaryIO

__all__ = [
    "TrackUpdate",
    "TrackUpdateEnvelope",
    "read_delimited",
    "track_update_from_proto",
    "track_update_to_proto",
    "write_delimited",
]

TrackUpdate = track_update_pb2.TrackUpdate
"""Generated ``apus.edge.v1.TrackUpdate`` message class."""

_MAX_MESSAGE_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class TrackUpdateEnvelope:
    """Identifiers that travel with a track state in a ``TrackUpdate`` message."""

    site_id: str
    device_id: str
    track_id: uuid.UUID
    sequence: int


def track_update_to_proto(envelope: TrackUpdateEnvelope, state: TrackState) -> TrackUpdate:
    """Build a ``TrackUpdate`` message from a track state and its identifiers."""
    message = TrackUpdate(
        site_id=envelope.site_id,
        device_id=envelope.device_id,
        track_id=str(envelope.track_id),
        sequence=envelope.sequence,
        status=track_update_pb2.TrackStatus.ValueType(state.status.value),
        position_covariance_m2=state.position_covariance_m2,
        point_count=state.point_count,
        quality=state.quality,
    )
    message.observed_at.FromDatetime(state.observed_at)
    east, north, up = state.position_m
    message.position_m.east, message.position_m.north, message.position_m.up = east, north, up
    ve, vn, vu = state.velocity_mps
    message.velocity_mps.east, message.velocity_mps.north, message.velocity_mps.up = ve, vn, vu
    return message


def track_update_from_proto(message: TrackUpdate) -> tuple[TrackUpdateEnvelope, TrackState]:
    """Split a ``TrackUpdate`` message into its identifiers and a validated track state."""
    envelope = TrackUpdateEnvelope(
        site_id=message.site_id,
        device_id=message.device_id,
        track_id=uuid.UUID(message.track_id),
        sequence=message.sequence,
    )
    p, v = message.position_m, message.velocity_mps
    state = TrackState(
        observed_at=message.observed_at.ToDatetime(tzinfo=UTC),
        status=TrackStatus(message.status),
        position_m=(p.east, p.north, p.up),
        velocity_mps=(v.east, v.north, v.up),
        position_covariance_m2=tuple(message.position_covariance_m2) or (0.0,) * 9,
        point_count=message.point_count,
        quality=message.quality,
    )
    return envelope, state


def write_delimited(stream: BinaryIO, message: TrackUpdate) -> int:
    """Append one length-delimited message to ``stream``; returns the bytes written."""
    payload = message.SerializeToString()
    frame = _encode_varint(len(payload)) + payload
    stream.write(frame)
    return len(frame)


def read_delimited(stream: BinaryIO) -> Iterator[TrackUpdate]:
    """Read length-delimited ``TrackUpdate`` messages until the end of ``stream``.

    Raises:
        ValueError: If the stream ends inside a message or a size is implausibly large.
    """
    while True:
        size = _decode_varint(stream)
        if size is None:
            return
        if size > _MAX_MESSAGE_BYTES:
            msg = f"message of {size} B exceeds the {_MAX_MESSAGE_BYTES} B limit"
            raise ValueError(msg)
        payload = stream.read(size)
        if len(payload) != size:
            msg = f"stream ended inside a message ({len(payload)} of {size} B)"
            raise ValueError(msg)
        yield TrackUpdate.FromString(payload)


def _encode_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _decode_varint(stream: BinaryIO) -> int | None:
    """Read one varint; ``None`` at a clean end of stream."""
    value = shift = 0
    while True:
        chunk = stream.read(1)
        if not chunk:
            if shift == 0:
                return None
            msg = "stream ended inside a length prefix"
            raise ValueError(msg)
        byte = chunk[0]
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value
        shift += 7
        if shift > 63:  # noqa: PLR2004 - a varint has at most 10 bytes
            msg = "length prefix is too long"
            raise ValueError(msg)

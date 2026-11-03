"""Tests for Protobuf conversions and message framing."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from apus_core.domain import TrackState, TrackStatus
from apus_core.messages import (
    TrackUpdate,
    TrackUpdateEnvelope,
    read_delimited,
    track_update_from_proto,
    track_update_to_proto,
    write_delimited,
)
from scripts import gen_proto

T0 = datetime(2026, 5, 1, 4, 30, tzinfo=UTC)
finite = st.floats(-1e4, 1e4, allow_nan=False)
states = st.builds(
    TrackState,
    observed_at=st.integers(0, 10**12).map(lambda us: T0 + timedelta(microseconds=us)),
    status=st.sampled_from(TrackStatus),
    position_m=st.tuples(finite, finite, finite),
    velocity_mps=st.tuples(finite, finite, finite),
    position_covariance_m2=st.floats(0, 100).map(lambda v: (v, 0, 0, 0, v, 0, 0, 0, v)),
    point_count=st.integers(0, 2**32 - 1),
    quality=st.floats(0, 1),
)
envelopes = st.builds(
    TrackUpdateEnvelope,
    site_id=st.just("demo-site"),
    device_id=st.just("lidar-1"),
    track_id=st.uuids(),
    sequence=st.integers(0, 2**64 - 1),
)


@given(envelopes, states)
def test_track_updates_round_trip(envelope: TrackUpdateEnvelope, state: TrackState) -> None:
    message = track_update_to_proto(envelope, state)
    decoded = TrackUpdate.FromString(message.SerializeToString())
    assert track_update_from_proto(decoded) == (envelope, state)


def test_missing_covariance_decodes_as_zeros() -> None:
    message = TrackUpdate(track_id=str(uuid.UUID(int=1)), status="TRACK_STATUS_CONFIRMED")
    message.observed_at.FromDatetime(T0)
    _, state = track_update_from_proto(message)
    assert state.position_covariance_m2 == (0.0,) * 9
    assert state.status is TrackStatus.CONFIRMED


def test_delimited_stream_round_trip() -> None:
    stream = io.BytesIO()
    messages = [TrackUpdate(sequence=n, site_id="x" * n) for n in (0, 1, 200, 20_000)]
    sizes = [write_delimited(stream, m) for m in messages]
    assert sum(sizes) == len(stream.getvalue())
    stream.seek(0)
    assert list(read_delimited(stream)) == messages


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"\x05abc", "ended inside a message"),
        (b"\x80", "ended inside a length prefix"),
        (b"\xff" * 11, "too long"),
        (b"\x80\x80\x80\x04", "exceeds"),
    ],
)
def test_delimited_stream_rejects_corrupt_input(data: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        list(read_delimited(io.BytesIO(data)))


def test_generated_code_is_current() -> None:
    assert gen_proto.main(["--check"]) == 0

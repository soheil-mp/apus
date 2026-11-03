"""Tests for the minimal edge pipeline and its CLI, fed by the minimal simulator."""

from __future__ import annotations

import io
import socket
import threading
from typing import TYPE_CHECKING

import numpy as np
import pytest

from apus_core.demo import DEMO_DEVICE_ID, DEMO_GEOMETRY, DEMO_POSE, DEMO_SITE_ID
from apus_core.domain import TrackState, TrackStatus
from apus_core.messages import TrackUpdateEnvelope, read_delimited, track_update_from_proto
from apus_core.packets import encode_frame
from apus_edge import cli
from apus_edge.detection import DetectorConfig
from apus_edge.pipeline import EdgePipeline, FilePublisher, MemoryPublisher
from apus_sim.cli import run_straight_line
from apus_sim.minimal import StraightLineScenario

if TYPE_CHECKING:
    from pathlib import Path


def run_pipeline(
    seed: int, duration_s: float = 30.0
) -> tuple[StraightLineScenario, list[tuple[TrackUpdateEnvelope, TrackState]]]:
    scenario = StraightLineScenario.from_seed(seed, duration_s=duration_s)
    publisher = MemoryPublisher()
    pipeline = EdgePipeline(DEMO_SITE_ID, DEMO_DEVICE_ID, DEMO_GEOMETRY, DEMO_POSE, publisher)
    sequence = 0
    for frame, _ in scenario.frames(duration_s):
        for datagram in encode_frame(frame, first_sequence=sequence):
            pipeline.push(datagram)
            sequence += 1
    pipeline.close()
    return scenario, [track_update_from_proto(m) for m in publisher.messages]


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_one_bird_gives_one_confirmed_track_at_the_right_speed(seed: int) -> None:
    scenario, updates = run_pipeline(seed)
    confirmed = [(e, s) for e, s in updates if s.status is TrackStatus.CONFIRMED]
    assert len({e.track_id for e, _ in confirmed}) == 1
    true_speed = float(np.linalg.norm(scenario.bird.velocity_mps))
    median_speed = float(np.median([s.speed_mps for _, s in confirmed]))
    assert median_speed == pytest.approx(true_speed, rel=0.02)
    assert updates[-1][1].status is TrackStatus.LOST


def test_messages_carry_increasing_sequence_numbers_and_the_site() -> None:
    _, updates = run_pipeline(3, duration_s=5.0)
    assert [e.sequence for e, _ in updates] == list(range(len(updates)))
    assert {(e.site_id, e.device_id) for e, _ in updates} == {(DEMO_SITE_ID, DEMO_DEVICE_ID)}


def test_identical_input_gives_identical_messages() -> None:
    assert run_pipeline(4, duration_s=5.0)[1] == run_pipeline(4, duration_s=5.0)[1]


def test_crowded_frames_are_skipped_and_counted() -> None:
    scenario = StraightLineScenario.from_seed(0, duration_s=1.0)
    publisher = MemoryPublisher()
    pipeline = EdgePipeline(
        DEMO_SITE_ID,
        DEMO_DEVICE_ID,
        DEMO_GEOMETRY,
        DEMO_POSE,
        publisher,
        detector=DetectorConfig(max_points=0),
    )
    frames = list(scenario.frames(1.0))
    for frame, _ in frames:
        for datagram in encode_frame(frame):
            pipeline.push(datagram)
    pipeline.close()
    hits = sum(frame.return_count > 0 for frame, _ in frames)
    assert pipeline.stats.frames_overloaded == hits > 0
    assert publisher.messages == []


def test_file_publisher_writes_a_readable_stream() -> None:
    stream = io.BytesIO()
    scenario = StraightLineScenario.from_seed(0, duration_s=3.0)
    pipeline = EdgePipeline(
        DEMO_SITE_ID, DEMO_DEVICE_ID, DEMO_GEOMETRY, DEMO_POSE, FilePublisher(stream)
    )
    for frame, _ in scenario.frames(3.0):
        for datagram in encode_frame(frame):
            pipeline.push(datagram)
    pipeline.close()
    stream.seek(0)
    assert len(list(read_delimited(stream))) == pipeline.stats.messages > 0


def test_parse_address_accepts_port_zero() -> None:
    assert cli.parse_address("127.0.0.1:0") == ("127.0.0.1", 0)
    with pytest.raises(Exception, match="host:port"):
        cli.parse_address("nope")


def test_simulator_to_edge_over_udp(tmp_path: Path) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16 * 1024 * 1024)
        sock.bind(("127.0.0.1", 0))
        publisher = MemoryPublisher()
        pipeline = EdgePipeline(DEMO_SITE_ID, DEMO_DEVICE_ID, DEMO_GEOMETRY, DEMO_POSE, publisher)
        edge = threading.Thread(
            target=cli.serve, args=(sock, pipeline), kwargs={"idle_timeout_s": 1.0}
        )
        edge.start()
        frames, datagrams = run_straight_line(
            seed=2,
            duration_s=2.0,
            target=sock.getsockname(),
            truth=tmp_path / "truth.jsonl",
            speed=4.0,
        )
        edge.join(timeout=10)
    assert not edge.is_alive()
    stats = pipeline.assembler.stats
    assert stats.datagrams == datagrams
    assert stats.frames_complete == frames
    assert pipeline.stats.messages > 0


def test_main_stops_after_max_seconds(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "tracks.pb"
    argv = ["run", "--listen", "127.0.0.1:0", "--out", str(out), "--idle-timeout-s", "5"]
    assert cli.main([*argv, "--max-seconds", "0.3"]) == 0
    printed = capsys.readouterr().out
    assert "listening on 127.0.0.1:" in printed
    assert "frames 0" in printed
    assert out.read_bytes() == b""

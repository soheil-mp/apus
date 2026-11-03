"""Tests for the minimal straight-line simulator."""

from __future__ import annotations

import io
import json
import socket
from typing import TYPE_CHECKING

import numpy as np
import pytest

from apus_core.packets import decode
from apus_sim.cli import main, parse_address, run_straight_line
from apus_sim.minimal import StraightLineBird, StraightLineScenario
from apus_sim.truth import write_truth

if TYPE_CHECKING:
    from pathlib import Path


def test_same_seed_gives_identical_frames() -> None:
    a = list(StraightLineScenario.from_seed(3).frames(2.0))
    b = list(StraightLineScenario.from_seed(3).frames(2.0))
    assert [t for _, t in a] == [t for _, t in b]
    for (fa, _), (fb, _) in zip(a, b, strict=True):
        np.testing.assert_array_equal(fa.range_m, fb.range_m)


def test_different_seeds_give_different_flight_lines() -> None:
    assert StraightLineScenario.from_seed(1).bird != StraightLineScenario.from_seed(2).bird


def test_seeded_bird_passes_at_the_requested_distance_half_way() -> None:
    scenario = StraightLineScenario.from_seed(11, duration_s=20.0, closest_approach_m=35.0)
    middle = scenario.bird.position_at(10.0)
    assert np.hypot(middle[0], middle[1]) == pytest.approx(35.0)
    assert 15.0 <= middle[2] <= 30.0
    assert 8.0 <= float(np.linalg.norm(scenario.bird.velocity_mps)) <= 14.0


def test_returns_lie_on_the_bird_surface() -> None:
    scenario = StraightLineScenario.from_seed(0)
    hits = 0
    for frame, _ in scenario.frames(30.0):
        points = frame.points()
        if points.size == 0:
            continue
        xyz = np.stack([points["x_m"], points["y_m"], points["z_m"]], axis=-1).astype(np.float64)
        site = scenario.pose.sensor_to_site(xyz)
        t_s = (frame.start_time_ns - scenario.start_time_ns + points["time_offset_ns"]) / 1e9
        centres = scenario.bird.position_at(t_s)
        distances = np.linalg.norm(site - centres, axis=1)
        np.testing.assert_allclose(distances, scenario.bird.radius_m, atol=1e-3)
        hits += points.size
    assert hits > 0


def test_empty_sky_has_no_returns_when_the_bird_is_out_of_range() -> None:
    far = StraightLineBird(start_m=(1_000.0, 0.0, 50.0), velocity_mps=(0.0, 10.0, 0.0))
    scenario = StraightLineScenario(bird=far)
    assert all(frame.return_count == 0 for frame, _ in scenario.frames(1.0))


def test_bird_below_the_lowest_beam_is_not_seen() -> None:
    low = StraightLineBird(start_m=(30.0, 0.0, 2.0), velocity_mps=(0.0, 10.0, 0.0))
    scenario = StraightLineScenario(bird=low)
    assert all(frame.return_count == 0 for frame, _ in scenario.frames(0.5))


def test_truth_follows_the_flight_line() -> None:
    scenario = StraightLineScenario.from_seed(5)
    truths = [t for _, t in scenario.frames(1.0)]
    assert [t.frame_id for t in truths] == list(range(10))
    np.testing.assert_allclose(
        [t.east_m for t in truths],
        scenario.bird.position_at(np.arange(10) * 0.1)[:, 0],
    )
    assert np.diff([t.time_ns for t in truths]).tolist() == [100_000_000] * 9


def test_write_truth_writes_json_lines() -> None:
    scenario = StraightLineScenario.from_seed(0)
    stream = io.StringIO()
    assert write_truth([t for _, t in scenario.frames(0.3)], stream) == 3
    rows = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert rows[2]["frame_id"] == 2
    assert set(rows[0]) >= {"time_ns", "east_m", "north_m", "up_m", "radius_m"}


class TestCli:
    def test_parse_address(self) -> None:
        assert parse_address("127.0.0.1:7502") == ("127.0.0.1", 7502)
        for bad in ("7502", "host:", ":1", "host:70000", "host:x"):
            with pytest.raises(Exception, match="host:port"):
                parse_address(bad)

    def test_sends_every_frame_over_udp(self, tmp_path: Path) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(2.0)
            target = receiver.getsockname()
            frames, datagrams = run_straight_line(
                seed=1, duration_s=0.3, target=target, truth=tmp_path / "t.jsonl", speed=0.0
            )
            received = [receiver.recv(65_536) for _ in range(datagrams)]
        assert frames == 3
        assert {decode(d)[0].frame_id for d in received} == {0, 1, 2}
        assert len((tmp_path / "t.jsonl").read_text().splitlines()) == 3

    def test_main_reports_what_it_sent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            port = receiver.getsockname()[1]
            argv = ["straight-line", "--duration-s", "0.2", "--speed", "20"]
            argv += ["--target", f"127.0.0.1:{port}", "--truth", str(tmp_path / "t.jsonl")]
            assert main(argv) == 0
        assert "sent 2 frames" in capsys.readouterr().out

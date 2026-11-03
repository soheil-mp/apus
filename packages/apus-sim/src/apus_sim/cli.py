"""Command-line interface: ``apus-sim``.

Example::

    apus-sim straight-line --seed 7 --duration-s 30 --target 127.0.0.1:7502 --truth truth.jsonl
"""

from __future__ import annotations

import argparse
import socket
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from apus_core.packets import encode_frame
from apus_sim.minimal import StraightLineScenario
from apus_sim.truth import write_truth

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["main", "parse_address"]

_PORTS = range(1, 65_536)


def parse_address(value: str) -> tuple[str, int]:
    """Parse ``host:port`` into a socket address."""
    host, sep, port = value.rpartition(":")
    if not sep or not host or not port.isdigit() or int(port) not in _PORTS:
        msg = f"expected host:port, got {value!r}"
        raise argparse.ArgumentTypeError(msg)
    return host, int(port)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apus-sim", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    line = commands.add_parser(
        "straight-line", help="one bird on a straight line, ideal sensor, empty sky"
    )
    line.add_argument("--seed", type=int, default=0, help="scenario seed (default: 0)")
    line.add_argument("--duration-s", type=float, default=30.0, help="length (default: 30)")
    line.add_argument(
        "--target",
        type=parse_address,
        default=("127.0.0.1", 7502),
        help="where to send UDP datagrams (default: 127.0.0.1:7502)",
    )
    line.add_argument("--truth", type=Path, required=True, help="ground-truth JSON Lines file")
    line.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="playback speed; 1 is real time, 0 sends as fast as possible (default: 1)",
    )
    return parser


def run_straight_line(  # noqa: PLR0913 - one argument per CLI option
    *,
    seed: int,
    duration_s: float,
    target: tuple[str, int],
    truth: Path,
    speed: float,
    sock: socket.socket | None = None,
) -> tuple[int, int]:
    """Run the straight-line scenario; returns ``(frames, datagrams)`` sent."""
    scenario = StraightLineScenario.from_seed(seed, duration_s=duration_s)
    period_s = scenario.geometry.frame_period_ns / 1e9
    own_socket = sock is None
    udp = sock or socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    frames = datagrams = 0
    started = time.monotonic()
    try:
        with truth.open("w", encoding="utf-8") as truth_file:
            for frame, record in scenario.frames(duration_s):
                if speed > 0:
                    delay = started + frames * period_s / speed - time.monotonic()
                    if delay > 0:
                        time.sleep(delay)
                for datagram in encode_frame(frame, first_sequence=datagrams):
                    udp.sendto(datagram, target)
                    datagrams += 1
                write_truth([record], truth_file)
                frames += 1
    finally:
        if own_socket:
            udp.close()
    return frames, datagrams


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of ``apus-sim``."""
    args = _parser().parse_args(argv)
    frames, datagrams = run_straight_line(
        seed=args.seed,
        duration_s=args.duration_s,
        target=args.target,
        truth=args.truth,
        speed=args.speed,
    )
    print(f"sent {frames} frames in {datagrams} datagrams to {args.target[0]}:{args.target[1]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

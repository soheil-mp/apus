"""Command-line interface: ``apus-edge``.

Example::

    apus-edge run --listen 127.0.0.1:7502 --out tracks.pb --idle-timeout-s 2
"""

from __future__ import annotations

import argparse
import socket
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from apus_core.demo import DEMO_DEVICE_ID, DEMO_GEOMETRY, DEMO_POSE, DEMO_SITE_ID
from apus_edge.pipeline import EdgePipeline, FilePublisher

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["main", "parse_address", "serve"]

_PORTS = range(1, 65_536)
_RECEIVE_BUFFER_BYTES = 16 * 1024 * 1024


def parse_address(value: str) -> tuple[str, int]:
    """Parse ``host:port``; port 0 asks the system for a free port."""
    host, sep, port = value.rpartition(":")
    if not sep or not host or not port.isdigit() or (int(port) not in _PORTS and port != "0"):
        msg = f"expected host:port, got {value!r}"
        raise argparse.ArgumentTypeError(msg)
    return host, int(port)


def serve(
    sock: socket.socket,
    pipeline: EdgePipeline,
    *,
    idle_timeout_s: float,
    max_seconds: float | None = None,
) -> None:
    """Feed datagrams from ``sock`` into ``pipeline`` until the stream goes quiet.

    The loop ends ``idle_timeout_s`` after the last datagram (or after the start, if nothing
    arrives), or after ``max_seconds``. Unfinished frames and live tracks are then closed.
    """
    started = last = time.monotonic()
    sock.settimeout(min(idle_timeout_s, 0.2))
    while True:
        now = time.monotonic()
        if now - last >= idle_timeout_s or (
            max_seconds is not None and now - started >= max_seconds
        ):
            break
        try:
            datagram = sock.recv(65_535)
        except TimeoutError:
            continue
        last = time.monotonic()
        pipeline.push(datagram)
    pipeline.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apus-edge", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="receive lidar datagrams and publish track updates")
    run.add_argument("--listen", type=parse_address, default=("127.0.0.1", 7502))
    run.add_argument("--out", type=Path, required=True, help="length-delimited TrackUpdate file")
    run.add_argument("--idle-timeout-s", type=float, default=2.0)
    run.add_argument("--max-seconds", type=float, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of ``apus-edge``."""
    args = _parser().parse_args(argv)
    with (
        args.out.open("wb") as out,
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock,
    ):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, _RECEIVE_BUFFER_BYTES)
        sock.bind(args.listen)
        pipeline = EdgePipeline(
            site_id=DEMO_SITE_ID,
            device_id=DEMO_DEVICE_ID,
            geometry=DEMO_GEOMETRY,
            pose=DEMO_POSE,
            publisher=FilePublisher(out),
        )
        print(f"listening on {sock.getsockname()[0]}:{sock.getsockname()[1]}", flush=True)
        serve(sock, pipeline, idle_timeout_s=args.idle_timeout_s, max_seconds=args.max_seconds)
    a, p = pipeline.assembler.stats, pipeline.stats
    print(
        f"frames {p.frames} ({a.frames_partial} partial, {p.frames_overloaded} overloaded), "
        f"datagrams {a.datagrams} ({a.invalid} invalid, {a.late} late), "
        f"detections {p.detections}, messages {p.messages}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

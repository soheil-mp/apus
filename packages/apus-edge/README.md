# apus-edge

Edge runtime: frame assembly, detection, tracking, data reduction and publishing.

Part of [Apus](../../README.md). Planned work for this package is in
[ROADMAP.md](../../ROADMAP.md).

## Minimal edge (walking skeleton)

```text
UDP datagrams → FrameAssembler → detect → NearestNeighbourTracker → Publisher
```

- `assembler`: rebuilds frames from the [packet format](../../docs/reference/packets.md);
  unfinished frames are emitted as partial when a newer frame starts, and every invalid, late
  or duplicate datagram is counted.
- `detection`: every return at least 5 m up is foreground (the sky is empty); returns closer
  than 1.5 m form one detection (connected components).
- `tracking`: greedy nearest-neighbour association within a 5 m gate, least-squares velocity
  over the last ten positions, confirmation after three hits, coasting for up to ten frames.
  Track IDs are UUIDv5, so identical input gives identical output.
- `pipeline`: ties the stages together and publishes `apus.edge.v1.TrackUpdate` messages.

Run it against the simulator:

```sh
uv run apus-edge run --listen 127.0.0.1:7502 --out tracks.pb &
uv run apus-sim straight-line --seed 7 --duration-s 30 --target 127.0.0.1:7502 --truth truth.jsonl
```

`tracks.pb` holds length-delimited `TrackUpdate` messages (`apus_core.messages.read_delimited`).
The edge stops two seconds after the last datagram and prints its counters. Publishing to NATS
JetStream arrives with roadmap item M1.4.

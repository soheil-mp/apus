# apus-sim

Physics-based lidar, scene and bird simulator: the digital twin of a monitoring site.

Part of [Apus](../../README.md). Planned work for this package is in
[ROADMAP.md](../../ROADMAP.md).

## Minimal scenario (walking skeleton)

`apus_sim.minimal` simulates one bird flying a straight line at constant speed past an ideal
64-beam sensor under an empty sky. The seed picks the bird's heading (any), speed (8–14 m/s)
and height (15–30 m); the bird passes 40 m from the sensor half-way through.

```sh
uv run apus-sim straight-line --seed 7 --duration-s 30 \
  --target 127.0.0.1:7502 --truth truth.jsonl
```

Frames go to the UDP target in the [packet format](../../docs/reference/packets.md). Ground
truth, the bird's true state at every frame, goes to the JSON Lines file and never into the
packet stream. `--speed 0` sends as fast as possible; the default plays back in real time.

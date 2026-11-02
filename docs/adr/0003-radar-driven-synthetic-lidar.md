# 0003. Radar-driven synthetic lidar as the primary data source

- Status: Accepted
- Date: 2026-11-02

## Context and problem statement

There is no affordable, openly licensed archive of ground-based lidar recordings of birds.
Buying a sensor and running a field campaign is out of scope for the first releases, and a
sensor stream at full rate is far larger than the storage available. Where does the lidar data
come from?

## Decision drivers

- Realistic data volumes, rates and failure modes, so the data engineering is real.
- Exact ground truth to measure detection and tracking quality.
- Realistic bird activity patterns, not uniform random noise.
- Small storage footprint and full reproducibility.
- Only synthetic or public, non-personal data.

## Considered options

1. A physics-based simulator whose bird arrivals are driven by real weather-radar profiles
   (Aloft), whose scene is real terrain (AHN), and whose clutter follows real weather
   (Open-Meteo).
2. A simulator with hand-written random scenarios only.
3. Third-party lidar recordings of other flying objects (for example drones).

## Decision outcome

Chosen: **option 1**, a "digital twin" of a virtual site. Hand-written scenarios (option 2) are
kept as a golden test library. Third-party recordings (option 3) are rejected because of
licences and context (see [data sources](../research/02-data-sources.md#5-sources-considered-and-rejected)).

The simulator emits the same wire format a real sensor adapter would, so the edge pipeline
cannot tell the difference. A separate ground-truth channel is never read by the pipeline,
only by evaluation code.

### Consequences

- Good: three public sources become meaningful inputs rather than decoration.
- Good: realistic nightly and seasonal patterns; busy migration nights in radar data become
  busy nights at the site.
- Good: data can be regenerated from seeds, so only small samples are stored.
- Bad: a simulation-to-reality gap. Mitigated by datasheet-based sensor models, documented
  assumptions, and real-sensor adapters in M18.
- Bad: lidar-versus-radar comparisons are partly circular while the lidar is simulated from the
  radar. Reports must say so, and the comparison becomes informative only with real recordings.

## Confirmation

- Golden scenarios with fixed seeds produce identical streams in CI.
- The edge pipeline has no import path to the ground-truth module (checked by an import-linter
  contract, M1).

## More information

- [Domain research §3](../research/01-domain.md#3-detection-physics)

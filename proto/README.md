# Message schemas

Protocol Buffers definitions for messages sent from edge devices to the platform
([ADR-0005](../docs/adr/0005-edge-transport-nats-jetstream.md),
[ADR-0009](../docs/adr/0009-schemas-and-data-contracts.md)).

| Package | Message | Subject |
| :-- | :-- | :-- |
| `apus.edge.v1` | `TrackUpdate` | `apus.{site}.{device}.tracks.v1` |

Further messages (detections, health, snippet notices, advisories) arrive in roadmap item M2.5.

## Conventions

- Packages are versioned (`apus.edge.v1`); the directory matches the package.
- Coordinates are in the site's local East-North-Up frame; units are SI and part of the field
  name (`position_m`, `velocity_mps`).
- Every message carries `site_id`, `device_id` and a per-device `sequence` so consumers can
  deduplicate.
- Fields are never renumbered or reused. Breaking changes need a new package version
  (`v2`); `buf breaking` enforces this on pull requests.

## Checks

```sh
buf lint          # style rules (STANDARD)
buf format -d     # formatting diff
buf breaking --against '.git#branch=main'
```

The same checks run in CI and in pre-commit.

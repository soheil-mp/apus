# Domain types

Module: `apus_core.domain`. These types describe the things every package talks about, from
the simulator through the edge runtime to the API.

## Two representations

| Where | Representation | Why |
| :-- | :-- | :-- |
| Boundaries: configuration, messages, API payloads | Immutable Pydantic models | Validation with clear errors; unknown fields and non-finite numbers are rejected |
| Hot paths: every return of a frame, detections of a batch | NumPy structured arrays (`POINT_DTYPE`, `DETECTION_DTYPE`) | Vectorised processing without per-object overhead |

`Detection.to_records()` and `Detection.from_record()` convert between the two.

## Types

| Type | Kind | What it is |
| :-- | :-- | :-- |
| `Site` | model | A monitoring site and the reference point of its East-North-Up frame (`local_frame()`) |
| `SensorPose` | dataclass | Position and orientation of a sensor in the site frame (from [coordinates](coordinates.md)) |
| `Frame` | dataclass of arrays | One sweep as a range image: `range_m` (`NaN` = no return), `intensity` and a per-pixel `time_offset_ns`; `points()` gives the returns as `POINT_DTYPE` records |
| `Detection` | model and `DETECTION_DTYPE` | A group of foreground returns in one frame: centroid, extent, point count, mean intensity |
| `TrackStatus` | enum | `TENTATIVE`, `CONFIRMED`, `COASTING`, `LOST`; values match the Protobuf enum |
| `TrackState` | model | One estimate: position, velocity, 3 × 3 position covariance (symmetric, non-negative diagonal), quality in [0, 1] |
| `Track` | model | A track's states in strictly increasing time order; only the last may be `LOST` |
| `Advisory` | model | A simulated, advisory-only message with its level (`info`, `caution`, `curtail`), the rule that raised it and the tracks behind it |

## Conventions

- Positions are metres in the site's East-North-Up frame, velocities metres per second.
- Times are UTC: aware `datetime` values in models, nanoseconds since the Unix epoch in arrays
  (`observed_time_ns`). Conversions keep microsecond precision.
- Site and device identifiers are lower-case slugs such as `demo-site` or `lidar-1`.

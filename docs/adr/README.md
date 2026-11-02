# Architecture decision records

Significant decisions are recorded here in the [MADR 4](https://adr.github.io/madr/) format. An
ADR is never edited after it is accepted, except to change its status; a new ADR supersedes it.

| ADR | Title | Status |
| :-- | :-- | :-- |
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-deterministic-explainable-perception.md) | Deterministic, explainable perception | Accepted |
| [0003](0003-radar-driven-synthetic-lidar.md) | Radar-driven synthetic lidar as the primary data source | Accepted |
| [0004](0004-edge-first-data-reduction.md) | Edge-first data reduction with event-triggered retention | Accepted |
| [0005](0005-edge-transport-nats-jetstream.md) | NATS JetStream with leaf nodes for edge-to-platform transport | Accepted |
| [0006](0006-lakehouse-ducklake.md) | DuckLake on S3-compatible storage as the lakehouse | Accepted |
| [0007](0007-orchestration-dagster.md) | Dagster for orchestration | Accepted |
| [0008](0008-transformations-dbt.md) | dbt-core on DuckDB for SQL transformations | Accepted |
| [0009](0009-schemas-and-data-contracts.md) | Protobuf messages, Parquet storage and ODCS data contracts | Accepted |
| [0010](0010-python-toolchain-monorepo.md) | Python 3.13 monorepo with uv workspaces, Ruff and strict mypy | Accepted |

Planned ADRs, written when the milestone that needs them starts: container base images (M14),
Kubernetes packaging and GitOps (M15), observability stack (M16), cloud provider for the demo
(M17), and Rust acceleration (M19).

## Template

```markdown
# NNNN. Title

- Status: Proposed | Accepted | Superseded by NNNN
- Date: YYYY-MM-DD

## Context and problem statement
## Decision drivers
## Considered options
## Decision outcome
### Consequences
## Confirmation
## More information
```

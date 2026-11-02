# 0007. Dagster for orchestration

- Status: Accepted
- Date: 2026-11-02

## Context and problem statement

Batch work includes daily radar ingestion with three-day latency, hourly weather, one-off terrain
extraction, micro-batch compaction, dbt builds, data-quality checks, retention jobs and
reports. Work is naturally partitioned by site and by day. Which orchestrator?

## Decision drivers

- Data assets and lineage as first-class concepts, not only tasks.
- Partitions (site × day) with back-fills and re-materialisation.
- Built-in data-quality checks tied to assets.
- Sensors for late-arriving files, schedules, and declarative freshness.
- Strong dbt integration and local development experience.

## Considered options

1. **Dagster 1.13** (software-defined assets).
2. **Apache Airflow 3.3** (task DAGs, assets added in 3.x).
3. **Prefect 3.9** (flows and tasks).

## Decision outcome

Chosen: **option 1**. Assets map one-to-one to lakehouse tables; multi-partitions model
site × day; asset checks hold data-quality rules; a sensor polls the Aloft bucket for the
three-day-late daily file; `dagster-dbt` loads dbt models as assets with their tests as checks.

### Consequences

- Good: lineage from radar file to collision-risk table is visible in one graph.
- Good: back-fills are partition operations, not ad-hoc scripts.
- Bad: `dagster-dbt` requires Python < 3.14, which pins the baseline to 3.13 (ADR-0010).
- Bad: Dagster's webserver and daemon are two more services in the stack.

## Confirmation

- Definitions load in a unit test; key assets materialise in-process in CI (M10).

## More information

- [Dagster](https://github.com/dagster-io/dagster)

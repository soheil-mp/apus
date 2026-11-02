# 0008. dbt-core on DuckDB for SQL transformations

- Status: Accepted
- Date: 2026-11-02

## Context and problem statement

Silver and gold tables (conformed tracks, hourly passage rates, height distributions,
radar comparisons, collision-risk inputs) are relational transformations that analysts should
be able to read and review. Which transformation framework?

## Decision drivers

- SQL that reviewers outside software engineering can read.
- Tests, documentation and lineage alongside the models.
- Runs locally and in CI on DuckDB without a warehouse.
- Apache-2.0 or similar licence.

## Considered options

1. **dbt-core 1.12 with dbt-duckdb**.
2. **SQLMesh**.
3. Python transformations only (Polars).

## Decision outcome

Chosen: **option 1**. dbt-core is the most widely known framework, it is Apache-2.0, and
dbt-duckdb can attach a DuckLake catalog. Models follow the staging → intermediate → marts
layout. Numerical work that SQL expresses poorly (Monte Carlo collision risk) runs as Python
assets in Dagster and lands in tables that dbt then reads.

### Consequences

- Good: models, tests and docs live together; `dagster-dbt` exposes them as assets.
- Good: dbt unit tests cover tricky SQL such as MTR integration.
- Bad: two transformation languages (SQL and Python). The boundary is documented: SQL for
  relational shaping, Python for numerical simulation.
- Neutral: the source-available dbt Fusion engine is not used.

## Confirmation

- `dbt build` runs on a seeded DuckDB in CI; SQLFluff lints every model (M11).

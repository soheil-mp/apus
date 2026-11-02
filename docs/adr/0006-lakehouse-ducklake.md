# 0006. DuckLake on S3-compatible storage as the lakehouse

- Status: Accepted
- Date: 2026-11-02

## Context and problem statement

Bronze, silver and gold data must be stored as versioned tables with ACID commits, schema
evolution and time travel, on modest hardware, with a total budget of about 2 GB. Which table
format and catalog?

## Decision drivers

- Transactions and snapshots for idempotent re-runs and back-fills.
- Light operations: no JVM services, no separate metastore to babysit.
- Works with DuckDB, dbt-duckdb and Python.
- Open specification and permissive licence.
- Object storage via the S3 API, so the backend can change.

## Considered options

1. **DuckLake 1.0**: metadata in PostgreSQL, data in Parquet on S3-compatible storage.
2. **Apache Iceberg** with a REST catalog (for example Lakekeeper) and PyIceberg/DuckDB.
3. **Delta Lake** via delta-rs.
4. Plain Parquet files with Hive-style partitioning.

## Decision outcome

Chosen: **option 1**. DuckLake reached 1.0 on 2026-04-13 with a stable specification and a
backward-compatibility guarantee. Its catalog is ordinary SQL tables, which makes multi-table
commits, snapshots and maintenance simple to reason about. The object store is SeaweedFS in
local development (MinIO's community edition is archived).

### Consequences

- Good: one PostgreSQL database and a bucket are the whole lakehouse.
- Good: dbt-duckdb attaches a DuckLake catalog directly.
- Good: small-file handling (data inlining, compaction) suits micro-batches from the edge.
- Bad: younger ecosystem than Iceberg; fewer engines read it. Mitigated by keeping Parquet as
  the data format and by an Iceberg-export spike (stretch, M9).
- Bad: DuckDB 2.0 was released on 2026-10-21; versions are pinned and tested together.

## Confirmation

- Integration tests run commit, snapshot, time-travel and compaction against PostgreSQL and
  SeaweedFS containers (M9).

## More information

- [DuckLake 1.0 announcement](https://ducklake.select/2026/04/13/ducklake-10/)
- [MotherDuck cookbook: dbt on a local DuckLake catalog](https://motherduck.com/docs/cookbook/dbt-local-ducklake/)

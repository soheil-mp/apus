# 0010. Python 3.13 monorepo with uv workspaces, Ruff and strict mypy

- Status: Accepted
- Date: 2026-11-02

## Context and problem statement

Apus has several deployable parts (simulator, edge runtime, ingestion, pipelines, API) that
share domain types and must change together. How is the Python code organised and checked?

## Decision drivers

- Atomic changes across packages; one lockfile.
- Clear boundaries between packages, enforced by tooling.
- Fast, reproducible installs in CI and containers.
- Strict typing for numerical and domain code.

## Considered options

1. One repository, **uv workspace** with several packages, one `uv.lock`.
2. One package with sub-modules.
3. Several repositories.

## Decision outcome

Chosen: **option 1**, with this layout:

```text
packages/
  apus-core/       domain types, coordinates, units, configuration
  apus-sim/        sensor, scene and bird simulator
  apus-edge/       frame assembly, detection, tracking, retention, publishing
  apus-ingest/     stream landing into the lakehouse
  apus-pipelines/  Dagster definitions and external-source ingestion
  apus-api/        FastAPI service
transform/         dbt project
proto/             Protobuf schemas
contracts/         ODCS data contracts
web/               TypeScript viewer
deploy/            Compose, Helm, Argo CD, OpenTofu
```

- **Python 3.13**: `dagster-dbt` requires < 3.14, and NumPy 2.5 and SciPy 1.18 require ≥ 3.12.
- **Ruff** for lint and format; **mypy --strict** for types; **import-linter** contracts keep
  `apus-edge` independent of `apus-pipelines` and keep the simulator's ground truth away from
  the edge.
- **pytest**, **Hypothesis** and **pytest-benchmark** for tests.

### Consequences

- Good: one `uv sync` sets up everything; containers install only the package they need.
- Good: boundaries are checked, not only documented.
- Bad: Python 3.14 features wait until the Dagster–dbt integration supports it; Renovate
  surfaces the change.

## Confirmation

- CI runs `ruff check`, `ruff format --check`, `mypy --strict`, `lint-imports` and `pytest`
  on every pull request (M0).

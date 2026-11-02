# Technology landscape and tool selection

> Versions were read from PyPI, npm and GitHub releases on 2026-11-02. They are the starting
> point; Renovate keeps them current once code exists (M0). Every choice below has an
> alternative that was considered, and the major ones have an ADR.

## 1. Ecosystem changes that shaped the choices

| Change (as of 2026-11-02) | Effect on Apus |
| :-- | :-- |
| MinIO's community edition went into maintenance mode in December 2025 and its repository was archived in April 2026 ([overview](https://wz-it.com/en/blog/minio-successor-s3-storage-comparison/)) | Local object storage uses **SeaweedFS** (Apache-2.0); code only talks to the S3 API, so the backend can be swapped. |
| DuckLake 1.0 shipped on 2026-04-13 with a stable spec and backward-compatibility guarantee ([announcement](https://ducklake.select/2026/04/13/ducklake-10/)) | Lakehouse table format is **DuckLake** with a PostgreSQL catalog ([ADR-0006](../adr/0006-lakehouse-ducklake.md)). |
| DuckDB 2.0.0 released on 2026-10-21 | Pin and test the DuckDB version used by dbt-duckdb and DuckLake together (M1). |
| `dagster-dbt` 0.29.28 declares `requires-python <3.14` | The Python baseline is **3.13** until the integration supports 3.14 ([ADR-0010](../adr/0010-python-toolchain-monorepo.md)). |
| Material for MkDocs entered maintenance mode on 2025-11-05; support ends on 2026-11-05 ([issue](https://github.com/squidfunk/mkdocs-material/issues/8523)) | Documentation uses **Zensical** (MIT, by the same team, reads `mkdocs.yml`). Still 0.0.x, so the docs build is pinned and has a fallback. |
| `soda-core` 4.x is published with a proprietary licence on PyPI | Not used. Data quality uses MIT/Apache tools only. |
| Astral `ty` is at 0.0.95 (pre-release) | **mypy 2.x in strict mode** is the type checker of record; `ty` may run as an advisory job. |
| TypeScript 7.0 (native compiler) and Vite 8 are current | The web viewer starts on these versions. |

## 2. Selected stack

### Languages and project tooling

| Concern | Choice | Version | Licence | Alternatives considered |
| :-- | :-- | :-- | :-- | :-- |
| Core language | Python | 3.13 | PSF | Rust for hot paths later (M19) |
| Packaging, environments, workspaces | uv | 0.13.6 | MIT/Apache-2.0 | Poetry, PDM |
| Lint and format | Ruff | 0.17.3 | MIT | flake8 + black + isort |
| Types | mypy (strict) | 2.4.1 | MIT | pyright, ty (advisory) |
| Tests | pytest + Hypothesis | 9.2.0 / 6.170 | MIT / MPL-2.0 | — |
| Benchmarks | pytest-benchmark | 5.3.1 | BSD-2 | CodSpeed (stretch) |
| Task runner | just | 1.59.0 | CC0 | Make |
| Commit hooks | pre-commit + gitleaks | 4.7 / 8.30.1 | MIT | lefthook |
| Web front end | TypeScript, Vite, Biome, Vitest, Playwright | 7.0 / 8.3 / 2.6 / 5.1 / 1.64 | Apache-2.0 / MIT | ESLint + Prettier |

### Numerical and geospatial core

| Concern | Choice | Version | Licence | Notes |
| :-- | :-- | :-- | :-- | :-- |
| Arrays | NumPy | 2.5.4 | BSD-3 | Structured arrays for points |
| Algorithms | SciPy | 1.18.1 | BSD-3 | `linear_sum_assignment`, `ndimage.label`, `signal.lombscargle` |
| JIT for hot loops | Numba | 0.68.1 | BSD-2 | Connected components, ray casting |
| Point cloud I/O | laspy + lazrs | 2.7.0 / 0.8.2 | BSD-2 / MIT | LAZ/COPC read and write |
| Coordinate reference systems | pyproj | current | MIT | RD New, WGS84, local ENU |
| DataFrames | Polars | 2.1.0 | MIT | Columnar transforms in Python |
| Columnar format | PyArrow | 26.0.0 | Apache-2.0 | Arrow IPC, Parquet |

Point-cloud processing deliberately avoids learned models. Open3D (MIT) is an optional
visual debugging aid only.

### Data platform

| Concern | Choice | Version | Licence | Alternatives considered |
| :-- | :-- | :-- | :-- | :-- |
| Edge-to-platform messaging | NATS JetStream (leaf nodes) | server 2.15.2, nats-py 2.16 | Apache-2.0 | Apache Kafka 4.x, MQTT (Mosquitto/EMQX), Redpanda (BSL) — [ADR-0005](../adr/0005-edge-transport-nats-jetstream.md) |
| Message schemas | Protocol Buffers + Buf | protobuf 7.36, buf 1.75 | BSD-3 / Apache-2.0 | Avro + schema registry |
| Object storage (local) | SeaweedFS S3 gateway | 4.52 | Apache-2.0 | RustFS 1.0 (young), Garage (AGPL, no versioning), MinIO (archived) |
| Table format and catalog | DuckLake on PostgreSQL | DuckLake 1.0 spec, DuckDB 2.0 | MIT | Apache Iceberg + REST catalog, Delta Lake — [ADR-0006](../adr/0006-lakehouse-ducklake.md) |
| Query engine | DuckDB | 2.0.0 | MIT | Polars SQL, Trino (too heavy) |
| Orchestration | Dagster | 1.13.28 | Apache-2.0 | Airflow 3.3, Prefect 3.9 — [ADR-0007](../adr/0007-orchestration-dagster.md) |
| Transformations | dbt-core + dbt-duckdb | 1.12.6 / 1.11.1 | Apache-2.0 | SQLMesh — [ADR-0008](../adr/0008-transformations-dbt.md) |
| DataFrame validation | Pandera (Polars backend) | 0.35.0 | MIT | Great Expectations 1.x |
| Data contracts | Open Data Contract Standard v3 + datacontract-cli | cli 1.2.9 | Apache-2.0 / MIT | Hand-written YAML — [ADR-0009](../adr/0009-schemas-and-data-contracts.md) |
| SQL lint | SQLFluff | 4.5.0 | MIT | — |
| Lineage (stretch) | OpenLineage + Marquez | openlineage-python 1.55 | Apache-2.0 | Dagster's built-in lineage only |

### Serving

| Concern | Choice | Version | Licence |
| :-- | :-- | :-- | :-- |
| HTTP API | FastAPI + Pydantic | 0.162 / 2.14 | MIT |
| 3D visualisation | deck.gl + MapLibre GL | 9.4.1 / 6.16 | MIT / BSD-3 |
| In-browser analytics | DuckDB-WASM over Parquet | 1.33 (dev) | MIT |
| Ops dashboards | Grafana (via the OTel LGTM image) | otel-lgtm 0.39.0 | AGPL-3.0 (run as a separate service, not linked) |

### DevOps and platform

| Concern | Choice | Version | Licence | Alternatives considered |
| :-- | :-- | :-- | :-- | :-- |
| Containers | Docker / BuildKit, multi-stage, non-root | Docker 29 | Apache-2.0 | Podman |
| Local stack | Docker Compose with profiles | — | — | Tilt |
| Local Kubernetes | k3d (k3s in Docker) | 5.9.0 | MIT | kind, minikube |
| Edge runtime | k3s on arm64 | — | Apache-2.0 | balena, plain systemd |
| Packaging for Kubernetes | Helm charts + chart-testing | — | Apache-2.0 | Kustomize only |
| GitOps | Argo CD | 3.5.6 | Apache-2.0 | Flux |
| Secrets | SOPS + age | 3.13.3 | MPL-2.0 | Sealed Secrets, External Secrets |
| Infrastructure as code | OpenTofu | 1.13.2 | MPL-2.0 | Terraform (BSL), Pulumi |
| Policy as code | Conftest (OPA/Rego) | — | Apache-2.0 | Kyverno |
| Observability | OpenTelemetry SDK + Collector, Grafana LGTM | sdk 1.45.2 | Apache-2.0 | Prometheus + Jaeger separately |
| CI/CD | GitHub Actions (pinned SHAs, least privilege) | — | — | — |
| Releases | release-please + Conventional Commits | 5.0.0 | Apache-2.0 | semantic-release |
| Supply chain | Syft SBOM, Cosign keyless signing, build provenance attestations, OpenSSF Scorecard | 1.56 / 3.1.4 / — / 2.5.0 | Apache-2.0 | — |
| Dependency updates | Renovate | — | AGPL-3.0 (hosted app) | Dependabot |
| Documentation | Zensical + Diátaxis structure, ADRs in MADR format | 0.0.74 | MIT | MkDocs Material (maintenance mode), Sphinx |

## 3. Algorithms

All perception is deterministic signal processing and estimation theory
([ADR-0002](../adr/0002-deterministic-explainable-perception.md)):

| Stage | Method | Reference |
| :-- | :-- | :-- |
| Background model | Per-pixel range statistics in the range image, sky mask, hysteresis | Standard range-image background subtraction |
| Segmentation | Connected components in range-image space with range gating | Union-find labelling |
| State estimation | Kalman filter (constant velocity / acceleration) | Kalman (1960) |
| Manoeuvring targets | Interacting Multiple Model (CV + coordinated turn) | Blom & Bar-Shalom (1988) |
| Data association | χ² gating on Mahalanobis distance, optimal assignment | Kuhn (1955); SciPy's Jonker–Volgenant variant |
| Track management | M-of-N confirmation, coasting, deletion | Blackman & Popoli (1999) |
| Offline smoothing | Rauch–Tung–Striebel smoother | Rauch, Tung & Striebel (1965) |
| Periodicity (wingbeat) | Lomb–Scargle periodogram on irregular samples | Lomb (1976); Scargle (1982); VanderPlas (2018) |
| Tracking metrics | CLEAR-MOT (MOTA/MOTP), HOTA | Bernardin & Stiefelhagen (2008); Luiten et al. (2021) |
| Sensor pose calibration | Point-to-plane ICP against AHN | Chen & Medioni (1992) |
| Collision risk | Band model options 1–4, Monte Carlo wrapper | Band (2012) |
| Data-quality anomaly bands | Robust z-scores (median / MAD) | Standard robust statistics |

### Algorithm references

- Bernardin, K., & Stiefelhagen, R. (2008). Evaluating multiple object tracking performance:
  the CLEAR MOT metrics. *EURASIP Journal on Image and Video Processing*.
- Blackman, S., & Popoli, R. (1999). *Design and Analysis of Modern Tracking Systems.* Artech
  House.
- Blom, H. A. P., & Bar-Shalom, Y. (1988). The interacting multiple model algorithm for systems
  with Markovian switching coefficients. *IEEE Transactions on Automatic Control* 33(8).
- Chen, Y., & Medioni, G. (1992). Object modelling by registration of multiple range images.
  *Image and Vision Computing* 10(3).
- Kalman, R. E. (1960). A new approach to linear filtering and prediction problems. *Journal of
  Basic Engineering* 82(1).
- Kuhn, H. W. (1955). The Hungarian method for the assignment problem. *Naval Research
  Logistics Quarterly* 2.
- Lomb, N. R. (1976). Least-squares frequency analysis of unequally spaced data. *Astrophysics
  and Space Science* 39.
- Luiten, J., et al. (2021). HOTA: a higher order metric for evaluating multi-object tracking.
  *International Journal of Computer Vision* 129.
- Rauch, H. E., Tung, F., & Striebel, C. T. (1965). Maximum likelihood estimates of linear
  dynamic systems. *AIAA Journal* 3(8).
- Scargle, J. D. (1982). Studies in astronomical time series analysis II. *The Astrophysical
  Journal* 263.
- VanderPlas, J. T. (2018). Understanding the Lomb–Scargle periodogram. *The Astrophysical
  Journal Supplement Series* 236(1).

## 4. Licence policy for dependencies

- Apus is MIT. Libraries linked into Apus code must be MIT, BSD, Apache-2.0, ISC, MPL-2.0,
  PSF or similarly permissive.
- Copyleft services (Grafana, Garage) may run **as separate processes** in the local stack;
  they are never linked or vendored.
- Optional real-sensor adapters (M18) live behind extras. The Ouster SDK is published as
  `BSD-3-Clause AND Ouster-Freeware`, so it is never a default dependency and is never vendored.
- A licence check runs in CI from M0 onwards; new dependencies need a passing check.

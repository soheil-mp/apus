# Environment variables

Configuration comes from environment variables, loaded from a local `.env` file that is never
committed. Copy `.env.example` to `.env` and fill in values. Every variable the code reads is
listed in `.env.example` with a placeholder; the milestone that introduces it is noted there.

| Variable | Purpose | Milestone |
| :-- | :-- | :-- |
| `APUS_S3_ENDPOINT`, `APUS_S3_REGION`, `APUS_S3_BUCKET` | S3-compatible object storage (SeaweedFS locally) | M1 |
| `APUS_S3_ACCESS_KEY_ID`, `APUS_S3_SECRET_ACCESS_KEY` | Object storage credentials | M1 |
| `APUS_CATALOG_DSN` | PostgreSQL connection for the DuckLake catalog | M1 |
| `APUS_NATS_URL`, `APUS_NATS_CREDS_FILE` | NATS JetStream server and credentials file | M1 |
| `APUS_SITE_ID`, `APUS_SENSOR_PROFILE` | Which virtual site and sensor model to use | M2 |
| `APUS_ALOFT_BASE_URL`, `APUS_ALOFT_RADAR` | Aloft bucket and reference radar (`nlhrw`) | M9 |
| `APUS_OPEN_METEO_BASE_URL` | Open-Meteo historical weather endpoint | M9 |
| `APUS_AHN_BASE_URL` | AHN cloud-optimised point cloud storage | M9 |
| `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME` | OpenTelemetry export | M16 |

None of the public data sources need an API key.

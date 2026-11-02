# 0009. Protobuf messages, Parquet storage and ODCS data contracts

- Status: Accepted
- Date: 2026-11-02

## Context and problem statement

Data crosses several boundaries: device to platform (messages), platform to lakehouse
(tables), lakehouse to consumers (API, web, reports). Each boundary needs a schema that can
evolve without breaking the other side. How are schemas defined and enforced?

## Decision drivers

- Compact, typed messages on constrained links.
- Automatic detection of breaking schema changes in CI.
- Explicit ownership, semantics, quality rules and budgets for published datasets.
- Machine-checkable, not only documentation.

## Considered options

1. **Protobuf + Buf** for messages; **Parquet/Arrow** schemas for tables; **Open Data Contract
   Standard (ODCS) v3** contracts checked with `datacontract-cli`.
2. Avro with a schema registry service.
3. JSON Schema everywhere.

## Decision outcome

Chosen: **option 1**.

- `proto/` holds message definitions. `buf lint` and `buf breaking` run in CI against the
  main branch. Messages carry a schema version in the subject name (ADR-0005).
- Table schemas are generated from one source of truth and checked against the contracts.
- `contracts/` holds one ODCS contract per published dataset: owner, description, schema,
  semantics and units, quality rules, freshness and storage budget.

### Consequences

- Good: breaking changes fail CI before they reach a device or a consumer.
- Good: contracts double as the data catalogue in the docs site.
- Bad: three schema languages to keep aligned. Mitigated by generating table schemas and by a
  CI check that compares contracts, dbt models and Parquet schemas.

## Confirmation

- CI jobs: `buf lint`, `buf breaking`, `datacontract lint`, `datacontract test` (M2, M12).

## More information

- [Buf](https://github.com/bufbuild/buf)
- [Open Data Contract Standard](https://github.com/bitol-io/open-data-contract-standard)
- [datacontract-cli](https://github.com/datacontract/datacontract-cli)

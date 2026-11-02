# 0005. NATS JetStream with leaf nodes for edge-to-platform transport

- Status: Accepted
- Date: 2026-11-02

## Context and problem statement

Edge devices publish detections, tracks, health telemetry and snippet notifications to a
central platform. Field links drop out for minutes or hours. Which messaging system carries
this traffic?

## Decision drivers

- Store-and-forward on the device when the uplink is down, with bounded disk use.
- Small footprint on an arm64 device (memory, disk, one process).
- At-least-once delivery with deduplication, replay for back-fills.
- Open-source licence (Apache-2.0 or similar) for every component.
- An established, well-documented system.

## Considered options

1. **NATS JetStream**, with a leaf-node server on each device and a hub cluster centrally.
2. **Apache Kafka 4.x** (KRaft) centrally, devices as remote producers.
3. **MQTT** (Mosquitto or EMQX) from devices, bridged into Kafka.
4. **Redpanda** (Kafka API).

## Decision outcome

Chosen: **option 1**. A leaf-node server on each device holds a local JetStream stream, so
publishes succeed while offline and are mirrored to the hub when the link returns. Subjects are
named `apus.{site}.{device}.{kind}.v{n}`. Payloads are Protobuf (ADR-0009). Message IDs make
publishes idempotent within JetStream's deduplication window.

### Consequences

- Good: store-and-forward is built in; no extra bridge or local database.
- Good: one ≈ 20 MB binary on the device; easy to run in Compose and Kubernetes.
- Good: replay from streams supports back-fills into the lakehouse.
- Bad: less common in data-engineering job descriptions than Kafka. Ingestion is written
  against a small transport interface so a Kafka adapter can be added (stretch, M8).
- Neutral: Redpanda was ruled out for its BSL licence; MQTT plus Kafka adds a moving part.

## Confirmation

- Integration tests (Testcontainers) cut the link between leaf and hub and assert that no
  message is lost or duplicated in the lakehouse after reconnection (M8).

## More information

- [NATS leaf nodes](https://docs.nats.io/running-a-nats-service/configuration/leafnodes)

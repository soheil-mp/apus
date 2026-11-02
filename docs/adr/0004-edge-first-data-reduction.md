# 0004. Edge-first data reduction with event-triggered retention

- Status: Accepted
- Date: 2026-11-02

## Context and problem statement

A 64×1024 spinning sensor at 10 Hz produces ≈ 7.9 MB/s, ≈ 680 GB per day. Field sites have
limited bandwidth and the project has limited storage. Almost all of the stream is static
background or empty sky. What should leave the device?

## Decision drivers

- Storage budget of ≤ 50 MB per site-day downstream.
- Keep enough raw evidence to audit and re-process interesting events.
- Privacy: near-ground returns, where people may be, must not leave the device.
- Graceful behaviour when the uplink is down.

## Considered options

1. Stream everything to the platform and reduce there.
2. Process on the edge; send detections, tracks and health only.
3. Process on the edge; send detections, tracks and health, plus **event snippets**: points in
   a small box around each confirmed track, for a few seconds before and after, and one full
   background frame per hour.

## Decision outcome

Chosen: **option 3**. The edge keeps a bounded in-memory ring buffer of recent frames. When a
track is confirmed, the buffer is cropped around the track and written as a compressed LAZ
snippet. Near-ground returns are removed before any snippet is written.

### Consequences

- Good: > 99.99 % volume reduction while keeping evidence for every confirmed track.
- Good: snippets let improved algorithms be replayed on real events later.
- Good: privacy is enforced on the device, not by policy downstream.
- Bad: events missed by the edge cannot be recovered. Mitigated by a small random sample of
  full frames for recall audits.
- Bad: edge memory and CPU budgets must be tested (M4, M19).

## Confirmation

- A storage-budget data-quality check fails when a site-day exceeds its budget (M12).
- A test asserts that no point below the near-ground threshold appears in any snippet (M5).

## More information

- [Data sources §1](../research/02-data-sources.md#1-synthetic-lidar-the-digital-twin-sensor)

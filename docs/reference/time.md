# Time model

Module: `apus_core.clock`. Bird tracks are only as good as their timestamps: at 10 m/s, a 10 ms
error moves a bird by 10 cm. This page fixes what every timestamp means and what happens when
clocks disagree.

## Clocks

| Clock | Where | Properties |
| :-- | :-- | :-- |
| Device monotonic | Every edge device | Never jumps, arbitrary origin; used for all perception |
| UTC | Messages, tables, API | Nanoseconds since the Unix epoch (`*_time_ns`) or aware `datetime` values |

The device links the two with a **clock offset**: `utc_ns = monotonic_ns + offset_ns`. It learns
the offset from a time source and refreshes it regularly. Sources, best first: PTP (IEEE 1588),
GNSS pulse-per-second, NTP. `ClockOffset` records the offset, its one-sigma uncertainty, when it
was measured and its source.

## Per-point timestamps

A frame has one start time and a per-pixel `time_offset_ns`, because a spinning lidar measures
its columns one after another (a 10 Hz sweep spreads them over 100 ms). `point_times_ns()` gives
each pixel's absolute UTC time. Detections use the mean time of their returns, never the frame
start.

## Clock-skew policy

1. **Perception runs on monotonic time.** Frame assembly, association and track filters never
   see UTC, so a UTC correction cannot break or duplicate a track.
2. **UTC is attached at the edge** when a message is built, using the latest offset.
3. **Every message is graded** with `ClockQuality`, using `SkewPolicy`:

   | Grade | Rule (defaults) |
   | :-- | :-- |
   | `good` | Aged uncertainty ≤ 5 ms |
   | `degraded` | Aged uncertainty ≤ 100 ms |
   | `unsynchronised` | Anything worse, no time source, or an offset older than 1 hour |

   The aged uncertainty is the measured uncertainty plus an assumed worst-case oscillator drift
   of 50 ppm times the offset's age (50 µs per second).
4. **Nothing is dropped for clock skew.** Consumers filter on the grade. Gold tables and the
   API exclude `unsynchronised` data by default and say so.
5. **Clock jumps are reported, not hidden.** An offset change of more than 50 ms between two
   measurements counts as a jump. The device increments a counter in its health telemetry
   (M4.5); fault-injection tests cover jumps (M4.6). Older measurements that arrive late are
   ignored.

# Lidar packet format

Module: `apus_core.packets`. Sensors (the simulator now, real sensors behind an adapter later)
send each frame to the edge as UDP datagrams. Every datagram holds a block of consecutive
columns of one frame and fits a 1500-byte Ethernet frame (at most 1,472 bytes of payload).

All numbers are little-endian.

## Header (32 bytes)

| Bytes | Type | Field | Meaning |
| :-- | :-- | :-- | :-- |
| 0–3 | 4 chars | `magic` | `APL1`: Apus lidar packet, version 1 |
| 4–7 | u32 | `sequence` | Per-sensor datagram counter; wraps at 2³² |
| 8–15 | u64 | `frame_id` | Per-sensor frame counter |
| 16–23 | i64 | `frame_start_ns` | Sensor time of the frame's first column, ns since the Unix epoch |
| 24–25 | u16 | `rows` | Beams per column |
| 26–27 | u16 | `first_col` | Index of the first column in this datagram |
| 28–29 | u16 | `col_count` | Columns in this datagram |
| 30–31 | u16 | `cols_per_frame` | Columns in a complete frame |

## Column block (8 + 6 × rows bytes)

| Type | Field | Meaning |
| :-- | :-- | :-- |
| u32 | `time_offset_ns` | Time of the column after the frame start |
| f32 | `azimuth_rad` | Azimuth of the column, counter-clockwise from the sensor's forward axis |
| u32 × rows | `range_mm` | Range per beam in millimetres; `0` means no return |
| u16 × rows | `intensity` | Return intensity per beam |

Beam elevations are not sent. As with real sensors they are fixed by the sensor model and come
from `SensorGeometry`, which both sides load from the site configuration.

A 64-beam sensor fits 3 columns into a datagram, so a 1,024-column frame takes 342 datagrams;
at 10 Hz that is about 4.1 MB/s.

`decode()` rejects truncated datagrams, unknown magic values, inconsistent column ranges and
sizes that do not match the header with a `PacketError`.

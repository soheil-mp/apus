"""Settings of the walking-skeleton demo sensor, shared by the simulator and the edge.

They stand in for the site configuration until it arrives (ROADMAP M2.6), so that both sides
agree on the beam layout and the sensor pose without the edge importing the simulator.
"""

from __future__ import annotations

from apus_core.coordinates import SensorPose
from apus_core.packets import SensorGeometry

__all__ = ["DEMO_DEVICE_ID", "DEMO_GEOMETRY", "DEMO_POSE", "DEMO_SITE_ID"]

DEMO_SITE_ID = "demo-site"
DEMO_DEVICE_ID = "lidar-1"

DEMO_GEOMETRY = SensorGeometry.uniform(
    rows=64, lowest_deg=5.0, highest_deg=45.0, cols_per_frame=1024, frame_rate_hz=10.0
)
"""A 64-beam sensor looking at the sky between 5 and 45 degrees elevation, 10 Hz."""

DEMO_POSE = SensorPose(position_m=(0.0, 0.0, 2.0))
"""A level sensor 2 m above the site origin, its forward axis pointing east."""

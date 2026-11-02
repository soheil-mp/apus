# Coordinate frames

Module: `apus_core.coordinates`. Every package uses these frames and conventions, so a point
means the same thing everywhere.

| Frame | Axes and units | Used for |
| :-- | :-- | :-- |
| Sensor (Cartesian) | `x` forward, `y` left, `z` up; metres; origin at the sensor | Raw lidar returns |
| Sensor (spherical) | range (m), azimuth (rad, counter-clockwise from `+x`), elevation (rad, up from horizontal) | Scan patterns, range images |
| Site (ENU) | east, north, up; metres; tangent to the WGS 84 ellipsoid at the site reference point | Detections, tracks, message payloads |
| Geodetic | WGS 84 latitude and longitude (degrees), ellipsoidal height (m); EPSG:4979 | Site location, exchange with other data |
| ECEF | WGS 84 Earth-centred, Earth-fixed (m); EPSG:4978 | Intermediate step between geodetic and ENU |
| RD New | Dutch national grid easting and northing (m); EPSG:28992 | AHN elevation tiles |

## Sensor orientation

`SensorPose` places a sensor in the site frame by its position and three angles. The rotation
from sensor to site axes is `Rz(yaw) @ Ry(pitch) @ Rx(roll)`, each following the right-hand rule:

- **yaw** about up: `0` points the sensor's forward axis east, `pi/2` points it north;
- **pitch** about the sensor's left axis: positive values tip the forward axis down;
- **roll** about the sensor's forward axis: positive values raise the left axis.

```python
import math
from apus_core.coordinates import SensorPose, spherical_to_cartesian

pose = SensorPose(position_m=(0.0, 0.0, 3.0), yaw_rad=math.pi / 2)  # facing north, 3 m up
points = spherical_to_cartesian(range_m=80.0, azimuth_rad=0.0, elevation_rad=0.2)
pose.sensor_to_site(points)  # -> about (0.0, 78.4, 18.9)
```

## Accuracy

- Sensor and pose transformations are exact up to floating-point rounding (tested to 1e-8 m).
- Geodetic, ECEF and ENU conversions use PROJ; round trips stay within 1 mm anywhere within
  5 km of a site and up to 3 km high (tested with Hypothesis).
- RD New conversions use the transformation PROJ selects. Without the national RDNAPTRANS grid
  files it is a Helmert datum shift accurate to about a metre: enough to place a site and select
  AHN tiles, not for survey work.

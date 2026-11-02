"""Coordinate frames and transformations used across Apus.

Frames:

* **Sensor frame**: right-handed, metres, origin at the sensor. ``x`` points forward, ``y``
  left and ``z`` up. Its spherical form uses range (m), azimuth (rad, counter-clockwise from
  ``+x`` in the ``x``-``y`` plane) and elevation (rad, up from the ``x``-``y`` plane).
* **Site frame**: local East-North-Up (ENU), metres, tangent to the WGS 84 ellipsoid at the
  site's reference point.
* **Geodetic**: WGS 84 latitude and longitude in degrees, ellipsoidal height in metres
  (EPSG:4979).
* **ECEF**: WGS 84 Earth-centred, Earth-fixed Cartesian coordinates in metres (EPSG:4978).
* **RD New**: the Dutch national grid (EPSG:28992), easting and northing in metres. AHN
  elevation tiles are named in this grid.

All functions accept scalars or arrays and broadcast like NumPy. Points are arrays whose last
axis has length 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache, cached_property
from typing import TYPE_CHECKING

import numpy as np
from pyproj import Transformer

if TYPE_CHECKING:
    import numpy.typing as npt

    FloatArray = npt.NDArray[np.float64]

__all__ = [
    "WGS84_SEMI_MAJOR_AXIS_M",
    "WGS84_SEMI_MINOR_AXIS_M",
    "LocalFrame",
    "SensorPose",
    "cartesian_to_spherical",
    "ecef_to_geodetic",
    "geodetic_to_ecef",
    "rd_to_wgs84",
    "rotation_matrix",
    "spherical_to_cartesian",
    "wgs84_to_rd",
]

WGS84_SEMI_MAJOR_AXIS_M = 6_378_137.0
"""Equatorial radius of the WGS 84 ellipsoid."""

WGS84_FLATTENING = 1 / 298.257223563
WGS84_SEMI_MINOR_AXIS_M = WGS84_SEMI_MAJOR_AXIS_M * (1 - WGS84_FLATTENING)
"""Polar radius of the WGS 84 ellipsoid."""

_GEODETIC_3D = "EPSG:4979"
_ECEF = "EPSG:4978"
_WGS84_2D = "EPSG:4326"
_RD_NEW = "EPSG:28992"


@cache
def _transformer(source: str, target: str) -> Transformer:
    """Cached PROJ transformer; ``always_xy`` means longitude/easting first."""
    return Transformer.from_crs(source, target, always_xy=True)


def _as_float(values: npt.ArrayLike) -> FloatArray:
    return np.asarray(values, dtype=np.float64)


def _as_points(points: npt.ArrayLike) -> FloatArray:
    array = _as_float(points)
    if array.shape[-1:] != (3,):
        msg = f"points must have a last axis of length 3, got shape {array.shape}"
        raise ValueError(msg)
    return array


# --- Sensor frame ---------------------------------------------------------------------------


def spherical_to_cartesian(
    range_m: npt.ArrayLike, azimuth_rad: npt.ArrayLike, elevation_rad: npt.ArrayLike
) -> FloatArray:
    """Convert sensor spherical coordinates to sensor Cartesian points.

    Args:
        range_m: Distance from the sensor in metres.
        azimuth_rad: Angle counter-clockwise from the sensor's forward axis, in radians.
        elevation_rad: Angle above the sensor's horizontal plane, in radians.

    Returns:
        Points with shape ``(..., 3)`` in metres.
    """
    r, az, el = _as_float(range_m), _as_float(azimuth_rad), _as_float(elevation_rad)
    horizontal = r * np.cos(el)
    return np.stack((horizontal * np.cos(az), horizontal * np.sin(az), r * np.sin(el)), axis=-1)


def cartesian_to_spherical(points: npt.ArrayLike) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Convert sensor Cartesian points to range, azimuth and elevation.

    Azimuth is in ``(-pi, pi]`` and elevation in ``[-pi/2, pi/2]``. At the origin all three are
    zero; straight up or down, azimuth is zero.

    Args:
        points: Points with shape ``(..., 3)`` in metres.

    Returns:
        ``(range_m, azimuth_rad, elevation_rad)``.
    """
    xyz = _as_points(points)
    x, y, z = xyz[..., 0], xyz[..., 1], xyz[..., 2]
    horizontal = np.hypot(x, y)
    return np.hypot(horizontal, z), np.arctan2(y, x), np.arctan2(z, horizontal)


def rotation_matrix(yaw_rad: float, pitch_rad: float, roll_rad: float) -> FloatArray:
    """Rotation from sensor axes to site (ENU) axes.

    The rotation is ``Rz(yaw) @ Ry(pitch) @ Rx(roll)`` (intrinsic z-y'-x''), each following the
    right-hand rule about its axis:

    * yaw about up: 0 points the sensor's forward axis east, ``pi/2`` points it north;
    * pitch about the sensor's left axis: positive values tip the forward axis down;
    * roll about the sensor's forward axis: positive values raise the left axis.

    Returns:
        A 3x3 orthonormal matrix ``R`` with ``site = R @ sensor``.
    """
    cy, sy = np.cos(yaw_rad), np.sin(yaw_rad)
    cp, sp = np.cos(pitch_rad), np.sin(pitch_rad)
    cr, sr = np.cos(roll_rad), np.sin(roll_rad)
    rz = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]])
    ry = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]])
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]])
    return _as_float(rz @ ry @ rx)


@dataclass(frozen=True)
class SensorPose:
    """Position and orientation of a sensor in the site frame.

    Attributes:
        position_m: Sensor origin as (east, north, up) in metres from the site reference point.
        yaw_rad: Rotation about up (see :func:`rotation_matrix`).
        pitch_rad: Rotation about the sensor's left axis.
        roll_rad: Rotation about the sensor's forward axis.
    """

    position_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    yaw_rad: float = 0.0
    pitch_rad: float = 0.0
    roll_rad: float = 0.0

    @cached_property
    def rotation(self) -> FloatArray:
        """Sensor-to-site rotation matrix."""
        return rotation_matrix(self.yaw_rad, self.pitch_rad, self.roll_rad)

    def sensor_to_site(self, points: npt.ArrayLike) -> FloatArray:
        """Transform points from the sensor frame to the site (ENU) frame."""
        return _as_points(points) @ self.rotation.T + _as_float(self.position_m)

    def site_to_sensor(self, points: npt.ArrayLike) -> FloatArray:
        """Transform points from the site (ENU) frame to the sensor frame."""
        return (_as_points(points) - _as_float(self.position_m)) @ self.rotation


# --- Earth frames ---------------------------------------------------------------------------


def geodetic_to_ecef(
    lat_deg: npt.ArrayLike, lon_deg: npt.ArrayLike, height_m: npt.ArrayLike
) -> FloatArray:
    """Convert WGS 84 geodetic coordinates to ECEF points with shape ``(..., 3)``."""
    x, y, z = _transformer(_GEODETIC_3D, _ECEF).transform(
        _as_float(lon_deg), _as_float(lat_deg), _as_float(height_m)
    )
    return np.stack((_as_float(x), _as_float(y), _as_float(z)), axis=-1)


def ecef_to_geodetic(points: npt.ArrayLike) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Convert ECEF points to WGS 84 ``(lat_deg, lon_deg, height_m)``."""
    xyz = _as_points(points)
    lon, lat, height = _transformer(_ECEF, _GEODETIC_3D).transform(
        xyz[..., 0], xyz[..., 1], xyz[..., 2]
    )
    return _as_float(lat), _as_float(lon), _as_float(height)


@dataclass(frozen=True)
class LocalFrame:
    """East-North-Up frame tangent to the WGS 84 ellipsoid at a reference point.

    Attributes:
        origin_lat_deg: Latitude of the reference point.
        origin_lon_deg: Longitude of the reference point.
        origin_height_m: Ellipsoidal height of the reference point.
    """

    origin_lat_deg: float
    origin_lon_deg: float
    origin_height_m: float = 0.0

    @cached_property
    def _origin_ecef(self) -> FloatArray:
        return geodetic_to_ecef(self.origin_lat_deg, self.origin_lon_deg, self.origin_height_m)

    @cached_property
    def _ecef_to_enu(self) -> FloatArray:
        lat, lon = np.radians(self.origin_lat_deg), np.radians(self.origin_lon_deg)
        sin_lat, cos_lat = np.sin(lat), np.cos(lat)
        sin_lon, cos_lon = np.sin(lon), np.cos(lon)
        return np.array(
            [
                [-sin_lon, cos_lon, 0.0],
                [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat],
                [cos_lat * cos_lon, cos_lat * sin_lon, sin_lat],
            ]
        )

    def geodetic_to_enu(
        self, lat_deg: npt.ArrayLike, lon_deg: npt.ArrayLike, height_m: npt.ArrayLike
    ) -> FloatArray:
        """Convert WGS 84 geodetic coordinates to ENU points in metres."""
        ecef = geodetic_to_ecef(lat_deg, lon_deg, height_m)
        return (ecef - self._origin_ecef) @ self._ecef_to_enu.T

    def enu_to_geodetic(self, points: npt.ArrayLike) -> tuple[FloatArray, FloatArray, FloatArray]:
        """Convert ENU points to WGS 84 ``(lat_deg, lon_deg, height_m)``."""
        ecef = _as_points(points) @ self._ecef_to_enu + self._origin_ecef
        return ecef_to_geodetic(ecef)


# --- Dutch national grid --------------------------------------------------------------------


def wgs84_to_rd(lat_deg: npt.ArrayLike, lon_deg: npt.ArrayLike) -> FloatArray:
    """Convert WGS 84 latitude and longitude to RD New easting and northing.

    PROJ chooses the transformation. Without the national RDNAPTRANS grid files installed it
    uses a Helmert datum shift that is accurate to about a metre, which is enough to place a
    site and select AHN tiles.

    Returns:
        Points with shape ``(..., 2)``: easting and northing in metres.
    """
    x, y = _transformer(_WGS84_2D, _RD_NEW).transform(_as_float(lon_deg), _as_float(lat_deg))
    return np.stack((_as_float(x), _as_float(y)), axis=-1)


def rd_to_wgs84(
    easting_m: npt.ArrayLike, northing_m: npt.ArrayLike
) -> tuple[FloatArray, FloatArray]:
    """Convert RD New easting and northing to WGS 84 ``(lat_deg, lon_deg)``."""
    lon, lat = _transformer(_RD_NEW, _WGS84_2D).transform(
        _as_float(easting_m), _as_float(northing_m)
    )
    return _as_float(lat), _as_float(lon)

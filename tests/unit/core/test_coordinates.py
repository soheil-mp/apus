"""Tests for coordinate frames: known values plus property-based round trips."""

import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from apus_core.coordinates import (
    WGS84_SEMI_MAJOR_AXIS_M,
    WGS84_SEMI_MINOR_AXIS_M,
    LocalFrame,
    SensorPose,
    cartesian_to_spherical,
    ecef_to_geodetic,
    geodetic_to_ecef,
    rd_to_wgs84,
    rotation_matrix,
    spherical_to_cartesian,
    wgs84_to_rd,
)

angles = st.floats(min_value=-math.pi, max_value=math.pi, allow_nan=False)
coordinates_m = st.floats(min_value=-2_000.0, max_value=2_000.0, allow_nan=False)
points_m = st.tuples(coordinates_m, coordinates_m, coordinates_m)

# A box around the Netherlands, where Apus sites are placed.
nl_latitudes = st.floats(min_value=50.75, max_value=53.55)
nl_longitudes = st.floats(min_value=3.4, max_value=7.2)


# --- Sensor frame ---------------------------------------------------------------------------


def test_spherical_axes() -> None:
    forward = spherical_to_cartesian(10.0, 0.0, 0.0)
    left = spherical_to_cartesian(10.0, math.pi / 2, 0.0)
    up = spherical_to_cartesian(10.0, 0.0, math.pi / 2)
    np.testing.assert_allclose(forward, [10.0, 0.0, 0.0], atol=1e-12)
    np.testing.assert_allclose(left, [0.0, 10.0, 0.0], atol=1e-12)
    np.testing.assert_allclose(up, [0.0, 0.0, 10.0], atol=1e-12)


def test_spherical_broadcasts_over_arrays() -> None:
    points = spherical_to_cartesian(np.full((4, 1024), 50.0), np.zeros((4, 1024)), 0.1)
    assert points.shape == (4, 1024, 3)


@given(
    st.floats(min_value=0.1, max_value=2_000.0),
    angles.filter(lambda a: a > -math.pi),
    st.floats(min_value=-1.5, max_value=1.5),
)
def test_spherical_round_trip(range_m: float, azimuth: float, elevation: float) -> None:
    r, az, el = cartesian_to_spherical(spherical_to_cartesian(range_m, azimuth, elevation))
    assert r == pytest.approx(range_m, rel=1e-12)
    assert az == pytest.approx(azimuth, abs=1e-9)
    assert el == pytest.approx(elevation, abs=1e-9)


@given(points_m)
def test_cartesian_round_trip(point: tuple[float, float, float]) -> None:
    r, az, el = cartesian_to_spherical(point)
    np.testing.assert_allclose(spherical_to_cartesian(r, az, el), point, atol=1e-9)


def test_points_must_have_three_coordinates() -> None:
    with pytest.raises(ValueError, match="last axis of length 3"):
        cartesian_to_spherical([1.0, 2.0])


# --- Sensor pose ----------------------------------------------------------------------------


@given(angles, angles, angles)
def test_rotation_is_proper_orthonormal(yaw: float, pitch: float, roll: float) -> None:
    rotation = rotation_matrix(yaw, pitch, roll)
    np.testing.assert_allclose(rotation @ rotation.T, np.eye(3), atol=1e-12)
    assert np.linalg.det(rotation) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize(
    ("yaw", "pitch", "roll", "sensor_axis", "expected_site_axis"),
    [
        (math.pi / 2, 0.0, 0.0, [1, 0, 0], [0, 1, 0]),  # yaw 90 deg: forward points north
        (0.0, math.pi / 2, 0.0, [1, 0, 0], [0, 0, -1]),  # positive pitch tips forward down
        (0.0, 0.0, math.pi / 2, [0, 1, 0], [0, 0, 1]),  # positive roll raises the left axis
    ],
)
def test_rotation_conventions(
    yaw: float,
    pitch: float,
    roll: float,
    sensor_axis: list[float],
    expected_site_axis: list[float],
) -> None:
    np.testing.assert_allclose(
        rotation_matrix(yaw, pitch, roll) @ sensor_axis, expected_site_axis, atol=1e-12
    )


def test_pose_translates_and_rotates() -> None:
    pose = SensorPose(position_m=(100.0, 200.0, 5.0), yaw_rad=math.pi / 2)
    np.testing.assert_allclose(pose.sensor_to_site([10.0, 0.0, 0.0]), [100.0, 210.0, 5.0])


@given(points_m, angles, angles, angles, points_m)
def test_pose_round_trip(
    position: tuple[float, float, float],
    yaw: float,
    pitch: float,
    roll: float,
    point: tuple[float, float, float],
) -> None:
    pose = SensorPose(position_m=position, yaw_rad=yaw, pitch_rad=pitch, roll_rad=roll)
    np.testing.assert_allclose(pose.site_to_sensor(pose.sensor_to_site(point)), point, atol=1e-8)


@given(points_m, angles, points_m)
def test_pose_preserves_distances(
    position: tuple[float, float, float], yaw: float, point: tuple[float, float, float]
) -> None:
    pose = SensorPose(position_m=position, yaw_rad=yaw, pitch_rad=0.3, roll_rad=-0.2)
    site = pose.sensor_to_site(point)
    assert np.linalg.norm(site - np.asarray(position)) == pytest.approx(
        np.linalg.norm(point), abs=1e-8
    )


# --- Earth frames ---------------------------------------------------------------------------


def test_ecef_on_the_equator_and_at_the_pole() -> None:
    np.testing.assert_allclose(geodetic_to_ecef(0.0, 0.0, 0.0), [WGS84_SEMI_MAJOR_AXIS_M, 0, 0])
    np.testing.assert_allclose(
        geodetic_to_ecef(90.0, 0.0, 0.0), [0, 0, WGS84_SEMI_MINOR_AXIS_M], atol=1e-6
    )


@given(nl_latitudes, nl_longitudes, st.floats(min_value=-100.0, max_value=5_000.0))
def test_ecef_round_trip(lat: float, lon: float, height: float) -> None:
    lat2, lon2, height2 = ecef_to_geodetic(geodetic_to_ecef(lat, lon, height))
    assert lat2 == pytest.approx(lat, abs=1e-9)
    assert lon2 == pytest.approx(lon, abs=1e-9)
    assert height2 == pytest.approx(height, abs=1e-4)


def test_enu_origin_and_vertical() -> None:
    frame = LocalFrame(51.8, 4.9, 2.0)
    np.testing.assert_allclose(frame.geodetic_to_enu(51.8, 4.9, 2.0), [0, 0, 0], atol=1e-6)
    np.testing.assert_allclose(frame.geodetic_to_enu(51.8, 4.9, 102.0), [0, 0, 100], atol=1e-6)


def test_enu_axes_point_east_and_north() -> None:
    frame = LocalFrame(51.8, 4.9)
    east = frame.geodetic_to_enu(51.8, 4.91, 0.0)
    north = frame.geodetic_to_enu(51.81, 4.9, 0.0)
    assert east[0] > 600
    assert abs(east[1]) < 1
    assert north[1] > 1_000
    assert abs(north[0]) < 1e-6


@given(
    nl_latitudes,
    nl_longitudes,
    st.tuples(
        st.floats(min_value=-5_000.0, max_value=5_000.0),
        st.floats(min_value=-5_000.0, max_value=5_000.0),
        st.floats(min_value=-50.0, max_value=3_000.0),
    ),
)
def test_enu_round_trip_within_a_millimetre(
    lat: float, lon: float, enu: tuple[float, float, float]
) -> None:
    frame = LocalFrame(lat, lon, 10.0)
    np.testing.assert_allclose(frame.geodetic_to_enu(*frame.enu_to_geodetic(enu)), enu, atol=1e-3)


# --- Dutch national grid --------------------------------------------------------------------


def test_rd_origin_is_amersfoort() -> None:
    # RD New's false origin (155 000, 463 000) is the Onze Lieve Vrouwetoren in Amersfoort,
    # at about 52.1552 N, 5.3872 E.
    lat, lon = rd_to_wgs84(155_000.0, 463_000.0)
    assert lat == pytest.approx(52.1552, abs=2e-3)
    assert lon == pytest.approx(5.3872, abs=2e-3)


def test_rd_grid_covers_the_herwijnen_radar() -> None:
    easting, northing = wgs84_to_rd(51.8369, 5.1381)
    assert 0 < easting < 300_000
    assert 300_000 < northing < 625_000


@given(nl_latitudes, nl_longitudes)
def test_rd_round_trip(lat: float, lon: float) -> None:
    easting, northing = wgs84_to_rd(lat, lon)
    lat2, lon2 = rd_to_wgs84(easting, northing)
    assert lat2 == pytest.approx(lat, abs=1e-8)
    assert lon2 == pytest.approx(lon, abs=1e-8)

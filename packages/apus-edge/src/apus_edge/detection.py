"""Minimal detection: every return in the sky is foreground, grouped by distance.

The walking skeleton (ROADMAP M1.2) assumes an empty sky, so it needs no background model:
each return is foreground. Returns closer than ``link_m`` to each other end up in the same
group (single-linkage connected components), and every group becomes one detection. The
background model, range-image segmentation and measurement covariance of M5 replace this.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from apus_core.domain import DETECTION_DTYPE

if TYPE_CHECKING:
    import numpy.typing as npt

    from apus_core.coordinates import SensorPose
    from apus_core.domain import Frame

__all__ = ["DetectorConfig", "connected_groups", "detect"]


@dataclass(frozen=True)
class DetectorConfig:
    """Parameters of the minimal detector.

    Attributes:
        link_m: Returns closer than this belong to the same group.
        min_height_m: Returns lower than this above the site origin are ignored, so the ground
            and anything on it never become detections.
        max_points: Frames with more foreground returns than this are skipped (and counted by
            the caller): the pairwise grouping is quadratic and meant for an empty sky.
    """

    link_m: float = 1.5
    min_height_m: float = 5.0
    max_points: int = 4_000


def connected_groups(points: npt.NDArray[np.float64], link_m: float) -> npt.NDArray[np.intp]:
    """Label points so that points closer than ``link_m`` share a label.

    Labels are ``0..k-1``, numbered by each group's first point, so the result depends only on
    the input order.
    """
    n = len(points)
    parent = np.arange(n)

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = int(parent[i])
        return i

    if n > 1:
        diff = points[:, np.newaxis, :] - points[np.newaxis, :, :]
        close = np.einsum("ijk,ijk->ij", diff, diff) < link_m**2
        for i, j in zip(*np.nonzero(np.triu(close, k=1)), strict=True):
            ri, rj = root(int(i)), root(int(j))
            if ri != rj:
                parent[max(ri, rj)] = min(ri, rj)
    roots = np.array([root(i) for i in range(n)], dtype=np.intp)
    _, labels = np.unique(roots, return_inverse=True)
    return labels.astype(np.intp)


def detect(frame: Frame, pose: SensorPose, config: DetectorConfig) -> npt.NDArray[np.void]:
    """Detections of one frame as a :data:`~apus_core.domain.DETECTION_DTYPE` array.

    Raises:
        OverflowError: If the frame has more foreground returns than ``config.max_points``.
    """
    points = frame.points()
    xyz = np.stack((points["x_m"], points["y_m"], points["z_m"]), axis=-1).astype(np.float64)
    site = pose.sensor_to_site(xyz) if len(points) else np.empty((0, 3))
    keep = site[:, 2] >= config.min_height_m
    points, site = points[keep], site[keep]
    if len(points) > config.max_points:
        msg = f"{len(points)} foreground returns exceed the limit of {config.max_points}"
        raise OverflowError(msg)
    labels = connected_groups(site, config.link_m)
    out = np.empty(int(labels.max()) + 1 if len(labels) else 0, dtype=DETECTION_DTYPE)
    for label in range(len(out)):
        members = labels == label
        group = site[members]
        spread = group[:, np.newaxis, :] - group[np.newaxis, :, :]
        out[label] = (
            frame.frame_id,
            frame.start_time_ns + round(float(points["time_offset_ns"][members].mean())),
            *group.mean(axis=0),
            float(np.sqrt(np.einsum("ijk,ijk->ij", spread, spread).max())),
            int(members.sum()),
            float(points["intensity"][members].mean()),
        )
    return out

"""The minimal edge pipeline: datagrams in, ``TrackUpdate`` messages out (ROADMAP M1.2).

``datagrams → FrameAssembler → detect → NearestNeighbourTracker → Publisher``

Publishers receive serialised-ready Protobuf messages. The walking skeleton writes them to a
length-delimited file; the NATS JetStream publisher arrives with the transport (M1.4, M8).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from apus_core.messages import TrackUpdateEnvelope, track_update_to_proto, write_delimited
from apus_edge.assembler import FrameAssembler
from apus_edge.detection import DetectorConfig, detect
from apus_edge.tracking import NearestNeighbourTracker, TrackerConfig

if TYPE_CHECKING:
    import uuid
    from typing import BinaryIO

    from apus_core.coordinates import SensorPose
    from apus_core.domain import Frame, TrackState
    from apus_core.messages import TrackUpdate
    from apus_core.packets import SensorGeometry

__all__ = ["EdgePipeline", "FilePublisher", "MemoryPublisher", "PipelineStats", "Publisher"]


class Publisher(Protocol):
    """Destination for track updates."""

    def publish(self, message: TrackUpdate) -> None:
        """Send one message."""


@dataclass
class MemoryPublisher:
    """Keeps every message in a list; for tests."""

    messages: list[TrackUpdate] = field(default_factory=list)

    def publish(self, message: TrackUpdate) -> None:
        """Append the message."""
        self.messages.append(message)


@dataclass
class FilePublisher:
    """Appends length-delimited messages to a binary stream."""

    stream: BinaryIO
    bytes_written: int = 0

    def publish(self, message: TrackUpdate) -> None:
        """Write the message with its length prefix."""
        self.bytes_written += write_delimited(self.stream, message)


@dataclass
class PipelineStats:
    """Counters kept by the pipeline, in addition to the assembler's."""

    frames: int = 0
    frames_overloaded: int = 0
    detections: int = 0
    messages: int = 0


@dataclass
class EdgePipeline:
    """Processes the datagrams of one sensor and publishes track updates.

    Attributes:
        site_id: Site of the device.
        device_id: The edge device.
        geometry: Beam layout of the sensor.
        pose: Sensor pose in the site frame.
        publisher: Where track updates go.
        detector: Detector parameters.
        tracker_config: Tracker parameters.
    """

    site_id: str
    device_id: str
    geometry: SensorGeometry
    pose: SensorPose
    publisher: Publisher
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    tracker_config: TrackerConfig = field(default_factory=TrackerConfig)
    stats: PipelineStats = field(default_factory=PipelineStats)
    _assembler: FrameAssembler = field(init=False, repr=False)
    _tracker: NearestNeighbourTracker = field(init=False, repr=False)
    _sequence: int = field(default=0, init=False, repr=False)
    _last_time_ns: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        """Create the assembler and the tracker."""
        self._assembler = FrameAssembler(self.geometry, self.device_id)
        self._tracker = NearestNeighbourTracker(self.device_id, self.tracker_config)

    @property
    def assembler(self) -> FrameAssembler:
        """The frame assembler, for its counters."""
        return self._assembler

    def push(self, datagram: bytes) -> None:
        """Process one datagram."""
        for frame in self._assembler.push(datagram):
            self._process(frame)

    def close(self) -> None:
        """Process unfinished frames and end every live track."""
        for frame in self._assembler.flush():
            self._process(frame)
        self._publish(self._tracker.finish(self._last_time_ns))

    def _process(self, frame: Frame) -> None:
        self.stats.frames += 1
        self._last_time_ns = frame.start_time_ns
        try:
            detections = detect(frame, self.pose, self.detector)
        except OverflowError:
            self.stats.frames_overloaded += 1
            return
        self.stats.detections += len(detections)
        self._publish(self._tracker.step(frame.start_time_ns, detections))

    def _publish(self, updates: list[tuple[uuid.UUID, TrackState]]) -> None:
        for track_id, state in updates:
            envelope = TrackUpdateEnvelope(self.site_id, self.device_id, track_id, self._sequence)
            self.publisher.publish(track_update_to_proto(envelope, state))
            self._sequence += 1
            self.stats.messages += 1

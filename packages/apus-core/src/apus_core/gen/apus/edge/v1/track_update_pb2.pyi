import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TrackStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TRACK_STATUS_UNSPECIFIED: _ClassVar[TrackStatus]
    TRACK_STATUS_TENTATIVE: _ClassVar[TrackStatus]
    TRACK_STATUS_CONFIRMED: _ClassVar[TrackStatus]
    TRACK_STATUS_COASTING: _ClassVar[TrackStatus]
    TRACK_STATUS_LOST: _ClassVar[TrackStatus]
TRACK_STATUS_UNSPECIFIED: TrackStatus
TRACK_STATUS_TENTATIVE: TrackStatus
TRACK_STATUS_CONFIRMED: TrackStatus
TRACK_STATUS_COASTING: TrackStatus
TRACK_STATUS_LOST: TrackStatus

class TrackUpdate(_message.Message):
    __slots__ = ("site_id", "device_id", "track_id", "sequence", "observed_at", "status", "position_m", "velocity_mps", "position_covariance_m2", "point_count", "quality")
    SITE_ID_FIELD_NUMBER: _ClassVar[int]
    DEVICE_ID_FIELD_NUMBER: _ClassVar[int]
    TRACK_ID_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    OBSERVED_AT_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    POSITION_M_FIELD_NUMBER: _ClassVar[int]
    VELOCITY_MPS_FIELD_NUMBER: _ClassVar[int]
    POSITION_COVARIANCE_M2_FIELD_NUMBER: _ClassVar[int]
    POINT_COUNT_FIELD_NUMBER: _ClassVar[int]
    QUALITY_FIELD_NUMBER: _ClassVar[int]
    site_id: str
    device_id: str
    track_id: str
    sequence: int
    observed_at: _timestamp_pb2.Timestamp
    status: TrackStatus
    position_m: EnuVector
    velocity_mps: EnuVector
    position_covariance_m2: _containers.RepeatedScalarFieldContainer[float]
    point_count: int
    quality: float
    def __init__(self, site_id: _Optional[str] = ..., device_id: _Optional[str] = ..., track_id: _Optional[str] = ..., sequence: _Optional[int] = ..., observed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., status: _Optional[_Union[TrackStatus, str]] = ..., position_m: _Optional[_Union[EnuVector, _Mapping]] = ..., velocity_mps: _Optional[_Union[EnuVector, _Mapping]] = ..., position_covariance_m2: _Optional[_Iterable[float]] = ..., point_count: _Optional[int] = ..., quality: _Optional[float] = ...) -> None: ...

class EnuVector(_message.Message):
    __slots__ = ("east", "north", "up")
    EAST_FIELD_NUMBER: _ClassVar[int]
    NORTH_FIELD_NUMBER: _ClassVar[int]
    UP_FIELD_NUMBER: _ClassVar[int]
    east: float
    north: float
    up: float
    def __init__(self, east: _Optional[float] = ..., north: _Optional[float] = ..., up: _Optional[float] = ...) -> None: ...

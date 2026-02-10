from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CommandRequest(_message.Message):
    __slots__ = ("command_id", "command_type", "payload")
    COMMAND_ID_FIELD_NUMBER: _ClassVar[int]
    COMMAND_TYPE_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    command_id: str
    command_type: str
    payload: _struct_pb2.Struct
    def __init__(self, command_id: _Optional[str] = ..., command_type: _Optional[str] = ..., payload: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class CommandResponse(_message.Message):
    __slots__ = ("accepted", "leader_id")
    ACCEPTED_FIELD_NUMBER: _ClassVar[int]
    LEADER_ID_FIELD_NUMBER: _ClassVar[int]
    accepted: bool
    leader_id: str
    def __init__(self, accepted: bool = ..., leader_id: _Optional[str] = ...) -> None: ...

class AppendEntriesRequest(_message.Message):
    __slots__ = ("leader_id", "term", "prev_log_index", "prev_log_term", "entries", "leader_commit")
    LEADER_ID_FIELD_NUMBER: _ClassVar[int]
    TERM_FIELD_NUMBER: _ClassVar[int]
    PREV_LOG_INDEX_FIELD_NUMBER: _ClassVar[int]
    PREV_LOG_TERM_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    LEADER_COMMIT_FIELD_NUMBER: _ClassVar[int]
    leader_id: str
    term: int
    prev_log_index: int
    prev_log_term: int
    entries: _containers.RepeatedCompositeFieldContainer[LogEntry]
    leader_commit: int
    def __init__(self, leader_id: _Optional[str] = ..., term: _Optional[int] = ..., prev_log_index: _Optional[int] = ..., prev_log_term: _Optional[int] = ..., entries: _Optional[_Iterable[_Union[LogEntry, _Mapping]]] = ..., leader_commit: _Optional[int] = ...) -> None: ...

class AppendEntriesResponse(_message.Message):
    __slots__ = ("term", "success")
    TERM_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    term: int
    success: bool
    def __init__(self, term: _Optional[int] = ..., success: bool = ...) -> None: ...

class RequestVoteRequest(_message.Message):
    __slots__ = ("candidate_id", "term", "last_log_index", "last_log_term")
    CANDIDATE_ID_FIELD_NUMBER: _ClassVar[int]
    TERM_FIELD_NUMBER: _ClassVar[int]
    LAST_LOG_INDEX_FIELD_NUMBER: _ClassVar[int]
    LAST_LOG_TERM_FIELD_NUMBER: _ClassVar[int]
    candidate_id: str
    term: int
    last_log_index: int
    last_log_term: int
    def __init__(self, candidate_id: _Optional[str] = ..., term: _Optional[int] = ..., last_log_index: _Optional[int] = ..., last_log_term: _Optional[int] = ...) -> None: ...

class RequestVoteResponse(_message.Message):
    __slots__ = ("term", "vote_granted")
    TERM_FIELD_NUMBER: _ClassVar[int]
    VOTE_GRANTED_FIELD_NUMBER: _ClassVar[int]
    term: int
    vote_granted: bool
    def __init__(self, term: _Optional[int] = ..., vote_granted: bool = ...) -> None: ...

class InstallSnapshotRequest(_message.Message):
    __slots__ = ("leader_id", "term", "last_included_index", "last_included_term", "snapshot")
    LEADER_ID_FIELD_NUMBER: _ClassVar[int]
    TERM_FIELD_NUMBER: _ClassVar[int]
    LAST_INCLUDED_INDEX_FIELD_NUMBER: _ClassVar[int]
    LAST_INCLUDED_TERM_FIELD_NUMBER: _ClassVar[int]
    SNAPSHOT_FIELD_NUMBER: _ClassVar[int]
    leader_id: str
    term: int
    last_included_index: int
    last_included_term: int
    snapshot: bytes
    def __init__(self, leader_id: _Optional[str] = ..., term: _Optional[int] = ..., last_included_index: _Optional[int] = ..., last_included_term: _Optional[int] = ..., snapshot: _Optional[bytes] = ...) -> None: ...

class InstallSnapshotResponse(_message.Message):
    __slots__ = ("term",)
    TERM_FIELD_NUMBER: _ClassVar[int]
    term: int
    def __init__(self, term: _Optional[int] = ...) -> None: ...

class LogEntry(_message.Message):
    __slots__ = ("index", "term", "command_id", "command_type", "payload")
    INDEX_FIELD_NUMBER: _ClassVar[int]
    TERM_FIELD_NUMBER: _ClassVar[int]
    COMMAND_ID_FIELD_NUMBER: _ClassVar[int]
    COMMAND_TYPE_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    index: int
    term: int
    command_id: str
    command_type: str
    payload: _struct_pb2.Struct
    def __init__(self, index: _Optional[int] = ..., term: _Optional[int] = ..., command_id: _Optional[str] = ..., command_type: _Optional[str] = ..., payload: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import time

from google.protobuf.struct_pb2 import Struct
import p2p_pb2.p2p_pb2 as p2p_pb2


@dataclass
class Event:
    cluster_id: str
    raft_index: int
    command_id: str
    command_type: str
    payload: Dict[str, Any]
    timestamp: Optional[float] = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = time.time()

    @classmethod
    def from_command_request(
        cls, request: p2p_pb2.CommandRequest, cluster_id: str, raft_index: int = 0
    ) -> "Event":
        payload_dict = {k: cls._parse_struct_value(v) for k, v in request.payload.fields.items()}
        return cls(
            cluster_id=cluster_id,
            raft_index=raft_index,
            command_id=request.command_id,
            command_type=request.command_type,
            payload=payload_dict,
        )

    def to_log_entry_proto(self, term: int) -> p2p_pb2.LogEntry:
        struct_payload = Struct()
        struct_payload.update(self.payload)
        return p2p_pb2.LogEntry(
            index=self.raft_index,
            term=term,
            command_id=self.command_id,
            command_type=self.command_type,
            payload=struct_payload,
        )

    @classmethod
    def from_log_entry_proto(cls, log_entry: p2p_pb2.LogEntry, cluster_id: str) -> "Event":
        payload_dict = {k: cls._parse_struct_value(v) for k, v in log_entry.payload.fields.items()}
        return cls(
            cluster_id=cluster_id,
            raft_index=log_entry.index,
            command_id=log_entry.command_id,
            command_type=log_entry.command_type,
            payload=payload_dict,
        )

    @staticmethod
    def _parse_struct_value(value: Any) -> Any:
        kind = value.WhichOneof("kind")
        if kind == "bool_value":
            return value.bool_value
        if kind == "number_value":
            return value.number_value
        if kind == "string_value":
            return value.string_value
        if kind == "null_value":
            return None
        if kind == "struct_value":
            return {
                k: Event._parse_struct_value(v)
                for k, v in value.struct_value.fields.items()
            }
        if kind == "list_value":
            return [Event._parse_struct_value(v) for v in value.list_value.values]
        return None

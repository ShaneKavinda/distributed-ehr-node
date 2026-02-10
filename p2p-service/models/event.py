from dataclasses import dataclass
from typing import Dict, Any, Optional
import time

from p2p_pb2.p2p_pb2 import CommandRequest, LogEntry
from google.protobuf.struct_pb2 import Struct

@dataclass
class Event:
    cluster_id : str    # Hospital/cluster identifier
    raft_index : int    # Raft log index (0 if not yet committed)
    command_id : str    # UUID for idempotency
    command_type : str  # e.g. PATIENT_CREATE
    payload: Dict[str, Any] # Event data as a dict
    timestamp: Optional[float] = None  # optional, set to time.time() if None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    #----------------------------------------------------------------
    #   Conversion helpers
    #----------------------------------------------------------------
    @classmethod
    def from_command_request(cls, request: CommandRequest, cluster_id: str, raft_index: int = 0) -> "Event":
        """
        Convert a CommandRequest proto to internal Event
        """
        payload_dict = dict(request.payload.fields)
        return cls(
            cluster_id=cluster_id,
            raft_index=raft_index,
            command_id=request.command_id,
            command_type=request.command_type,
            payload=payload_dict
        )

    def to_log_entry_proto(self) -> LogEntry:
        """
        Convert Event to LogEntry proto for Raft replication
        """
        struct_payload = Struct()
        for k, v in self.payload.items():
            # Automatically convert values to protobuf-compatible types
            if isinstance(v, bool):
                struct_payload.fields[k].bool_value = v
            elif isinstance(v, int):
                struct_payload.fields[k].number_value = v
            elif isinstance(v, float):
                struct_payload.fields[k].number_value = v
            elif isinstance(v, str):
                struct_payload.fields[k].string_value = v
            else:
                # fallback: convert to string
                struct_payload.fields[k].string_value = str(v)

        return LogEntry(
            index=self.raft_index,
            term=0,  # set by RaftNode when appending
            command_id=self.command_id,
            command_type=self.command_type,
            payload=struct_payload
        )

    @classmethod
    def from_log_entry_proto(cls, log_entry: LogEntry, cluster_id: str) -> "Event":
        """
        Convert a LogEntry proto from Raft into internal Event
        """
        payload_dict = {k: cls._parse_struct_value(v) for k, v in log_entry.payload.fields.items()}
        return cls(
            cluster_id=cluster_id,
            raft_index=log_entry.index,
            command_id=log_entry.command_id,
            command_type=log_entry.command_type,
            payload=payload_dict
        )

    @staticmethod
    def _parse_struct_value(value):
        """
        Helper to extract a value from a Struct Value
        """
        field = value.WhichOneof("kind")
        if field == "bool_value":
            return value.bool_value
        elif field == "number_value":
            return value.number_value
        elif field == "string_value":
            return value.string_value
        else:
            return None
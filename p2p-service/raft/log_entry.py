# raft/log_entry.py
from dataclasses import dataclass
from models.event import Event

@dataclass
class RaftLogEntry:
    index: int
    term: int
    event: Event

from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Dict, Set

from raft.log_entry import RaftLogEntry


@dataclass
class CommitTracker:
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _waiters: Dict[int, threading.Event] = field(default_factory=dict)
    _committed: Set[int] = field(default_factory=set)

    def wait_for_commit(self, index: int, timeout_s: float) -> bool:
        event = self._track(index)
        committed = event.wait(timeout=timeout_s)
        if not committed:
            with self._lock:
                self._waiters.pop(index, None)
        return committed

    def notify(self, entry: RaftLogEntry) -> None:
        index = entry.index
        with self._lock:
            event = self._waiters.pop(index, None)
            if event is None:
                self._committed.add(index)
                return
        event.set()

    def _track(self, index: int) -> threading.Event:
        with self._lock:
            if index in self._committed:
                self._committed.remove(index)
                event = threading.Event()
                event.set()
                return event
            event = threading.Event()
            self._waiters[index] = event
            return event

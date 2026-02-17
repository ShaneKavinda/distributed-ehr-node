from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
import random
import threading
import time
from typing import Callable, Dict, List, Optional

from models.event import Event
from raft.log_entry import RaftLogEntry
from raft.transport import GrpcTransport

import p2p_pb2.p2p_pb2 as p2p_pb2


class Role(Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


class RaftNode:
    def __init__(
        self,
        node_id: str,
        peer_ids: List[str],
        transport: GrpcTransport,
        election_timeout_ms: int,
        heartbeat_interval_ms: int,
        cluster_id: str,
    ) -> None:
        self.node_id = node_id
        self.peer_ids = peer_ids
        self.transport = transport
        self.cluster_id = cluster_id

        # Persistent state
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        self.log: List[RaftLogEntry] = []

        # Volatile state
        self.commit_index: int = 0
        self.last_applied: int = 0
        self.role: Role = Role.FOLLOWER
        self.leader_id: Optional[str] = None

        # Leader state
        self.next_index: Dict[str, int] = {}
        self.match_index: Dict[str, int] = {}

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._rpc_pool = ThreadPoolExecutor(max_workers=max(4, len(peer_ids) + 1))

        self._election_timeout_ms = election_timeout_ms
        self._heartbeat_interval_s = heartbeat_interval_ms / 1000.0
        self._reset_election_deadline()
        self._last_heartbeat_sent = 0.0

        self._commit_listeners: List[Callable[[RaftLogEntry], None]] = []

        print(f"📋 RaftNode initialized: {node_id} | Peers: {peer_ids} | Role: FOLLOWER")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._tick()
            time.sleep(0.05)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def is_leader(self) -> bool:
        return self.role == Role.LEADER

    def get_leader_id(self) -> str:
        return self.leader_id or ""

    def last_log_index(self) -> int:
        return len(self.log)

    def last_log_term(self) -> int:
        if not self.log:
            return 0
        return self.log[-1].term

    def _quorum_size(self) -> int:
        return (len(self.peer_ids) + 1) // 2 + 1

    def _reset_election_deadline(self) -> None:
        low = int(self._election_timeout_ms * 0.8)
        high = int(self._election_timeout_ms * 1.2)
        timeout_s = random.randint(low, high) / 1000.0
        self._election_deadline = time.monotonic() + timeout_s

    # ------------------------------------------------------------------
    # Main tick loop
    # ------------------------------------------------------------------
    def _tick(self) -> None:
        now = time.monotonic()
        with self._lock:
            role = self.role
            deadline = self._election_deadline
            last_sent = self._last_heartbeat_sent

        if role in (Role.FOLLOWER, Role.CANDIDATE) and now >= deadline:
            self._start_election()
            return

        if role == Role.LEADER and now - last_sent >= self._heartbeat_interval_s:
            self._send_heartbeats()

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def _start_election(self) -> None:
        with self._lock:
            self.role = Role.CANDIDATE
            self.current_term += 1
            term = self.current_term
            self.voted_for = self.node_id
            self._reset_election_deadline()
            last_log_index = self.last_log_index()
            last_log_term = self.last_log_term()

        print(f"🗳️  STARTING ELECTION - Node: {self.node_id} | Term: {term} | LastLogIndex: {last_log_index}")

        request = p2p_pb2.RequestVoteRequest(
            candidate_id=self.node_id,
            term=term,
            last_log_index=last_log_index,
            last_log_term=last_log_term,
        )

        votes = 1
        futures = {
            self._rpc_pool.submit(self.transport.request_vote, peer_id, request): peer_id
            for peer_id in self.peer_ids
        }

        for future in as_completed(futures):
            response = future.result()
            peer_id = futures[future]
            if response is None:
                print(f"❌ No response from {peer_id} during election (Term {term})")
                continue
            with self._lock:
                if response.term > self.current_term:
                    print(f"📉 Stepping down: Discovered higher term {response.term} > {self.current_term}")
                    self.current_term = response.term
                    self.role = Role.FOLLOWER
                    self.voted_for = None
                    self._reset_election_deadline()
                    return
                if self.role != Role.CANDIDATE or term != self.current_term:
                    return
                if response.vote_granted:
                    votes += 1
                    print(f"✅ Vote granted from {peer_id} | Total votes: {votes}/{self._quorum_size()}")
                    if votes >= self._quorum_size():
                        self._become_leader()
                        return
                else:
                    print(f"❌ Vote denied from {peer_id}")

    def _become_leader(self) -> None:
        self.role = Role.LEADER
        self.leader_id = self.node_id
        for peer in self.peer_ids:
            self.next_index[peer] = self.last_log_index() + 1
            self.match_index[peer] = 0
        self._last_heartbeat_sent = 0.0
        print(f"👑 ELECTED AS LEADER - Node: {self.node_id} | Term: {self.current_term}")

    # ------------------------------------------------------------------
    # Leader-side replication
    # ------------------------------------------------------------------
    def append_command(self, event: Event) -> int:
        with self._lock:
            if not self.is_leader():
                raise RuntimeError("Only the leader can append commands.")
            entry = RaftLogEntry(
                index=self.last_log_index() + 1,
                term=self.current_term,
                event=event,
            )
            entry.event.raft_index = entry.index
            self.log.append(entry)
            entry_index = entry.index
            print(f"📝 Leader appending command | Index: {entry_index} | Type: {event.command_type} | Term: {self.current_term}")
            if not self.peer_ids:
                # Single-node cluster commits immediately.
                self.commit_index = entry_index

        self._replicate_all()
        if not self.peer_ids:
            self._apply_committed_entries()
        return entry_index

    def _send_heartbeats(self) -> None:
        self._last_heartbeat_sent = time.monotonic()
        self._replicate_all()

    def _replicate_all(self) -> None:
        for peer_id in self.peer_ids:
            self._rpc_pool.submit(self._replicate_to_peer, peer_id)

    def _replicate_to_peer(self, peer_id: str) -> None:
        with self._lock:
            if self.role != Role.LEADER:
                return
            next_idx = self.next_index.get(peer_id, 1)
            prev_index = next_idx - 1
            prev_term = self.log[prev_index - 1].term if prev_index > 0 else 0
            entries = self.log[prev_index:]
            term = self.current_term

        proto_entries = [e.event.to_log_entry_proto(e.term) for e in entries]
        request = p2p_pb2.AppendEntriesRequest(
            leader_id=self.node_id,
            term=term,
            prev_log_index=prev_index,
            prev_log_term=prev_term,
            entries=proto_entries,
            leader_commit=self.commit_index,
        )

        response = self.transport.append_entries(peer_id, request)
        if response is None:
            return

        with self._lock:
            if response.term > self.current_term:
                self.current_term = response.term
                self.role = Role.FOLLOWER
                self.voted_for = None
                self._reset_election_deadline()
                return

            if self.role != Role.LEADER or term != self.current_term:
                return

            if response.success:
                match_index = prev_index + len(entries)
                self.match_index[peer_id] = match_index
                self.next_index[peer_id] = match_index + 1
                if len(entries) > 0:
                    print(f"✅ Replicated {len(entries)} entries to {peer_id} | Match index: {match_index}")
                advanced = self._advance_commit_index_locked()
            else:
                self.next_index[peer_id] = max(1, next_idx - 1)
                print(f"⚠️  Replication to {peer_id} failed, decrementing next_index to {self.next_index[peer_id]}")
                advanced = False

        if advanced:
            self._apply_committed_entries()

    def _advance_commit_index_locked(self) -> bool:
        advanced = False
        old_commit = self.commit_index
        for index in range(self.commit_index + 1, self.last_log_index() + 1):
            replicated = sum(1 for m in self.match_index.values() if m >= index)
            if replicated + 1 >= self._quorum_size():
                if self.log[index - 1].term == self.current_term:
                    self.commit_index = index
                    advanced = True
        if advanced:
            print(f"✅ COMMIT INDEX ADVANCED: {old_commit} → {self.commit_index} | Entries committed")
        return advanced

    # ------------------------------------------------------------------
    # Follower logic
    # ------------------------------------------------------------------
    def handle_append_entries(self, request: p2p_pb2.AppendEntriesRequest) -> bool:
        with self._lock:
            if request.term < self.current_term:
                return False

            if request.term > self.current_term:
                print(f"📈 Updating term: {self.current_term} → {request.term}")
                self.current_term = request.term
                self.voted_for = None

            self.role = Role.FOLLOWER
            if self.leader_id != request.leader_id:
                print(f"👤 Following leader: {request.leader_id} | Term: {request.term}")
            self.leader_id = request.leader_id
            self._reset_election_deadline()

            if not self._log_matches(request.prev_log_index, request.prev_log_term):
                return False

            entries = [self._from_proto_entry(e) for e in request.entries]
            self._delete_conflicting_entries(entries)
            self._append_new_entries(entries)

            if len(entries) > 0:
                print(f"📥 Received {len(entries)} entries from leader {request.leader_id}")

            old_commit = self.commit_index
            self.commit_index = min(request.leader_commit, self.last_log_index())
            if self.commit_index > old_commit:
                print(f"✅ Follower commit index advanced: {old_commit} → {self.commit_index}")

        self._apply_committed_entries()
        return True

    def handle_request_vote(self, request: p2p_pb2.RequestVoteRequest) -> bool:
        with self._lock:
            if request.term < self.current_term:
                return False

            if request.term > self.current_term:
                print(f"📈 Updating term: {self.current_term} → {request.term}")
                self.current_term = request.term
                self.voted_for = None
                self.role = Role.FOLLOWER

            if self.voted_for is not None and self.voted_for != request.candidate_id:
                return False

            up_to_date = (
                request.last_log_term > self.last_log_term()
                or (
                    request.last_log_term == self.last_log_term()
                    and request.last_log_index >= self.last_log_index()
                )
            )
            if not up_to_date:
                return False

            self.voted_for = request.candidate_id
            self._reset_election_deadline()
            print(f"✅ Voted for {request.candidate_id} in term {request.term}")
            return True

    def handle_install_snapshot(self, request: p2p_pb2.InstallSnapshotRequest) -> None:
        with self._lock:
            if request.term < self.current_term:
                return

            if request.term > self.current_term:
                self.current_term = request.term
                self.voted_for = None

            self.role = Role.FOLLOWER
            self.leader_id = request.leader_id
            self._reset_election_deadline()

            # Minimal placeholder snapshot behavior.
            self.log = []
            self.commit_index = request.last_included_index
            self.last_applied = request.last_included_index

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------
    def _log_matches(self, prev_log_index: int, prev_log_term: int) -> bool:
        if prev_log_index == 0:
            return True
        if prev_log_index > len(self.log):
            return False
        return self.log[prev_log_index - 1].term == prev_log_term

    def _delete_conflicting_entries(self, entries: List[RaftLogEntry]) -> None:
        for entry in entries:
            local_index = entry.index - 1
            if local_index >= len(self.log):
                return
            if self.log[local_index].term != entry.term:
                self.log = self.log[:local_index]
                return

    def _append_new_entries(self, entries: List[RaftLogEntry]) -> None:
        for entry in entries:
            if entry.index > self.last_log_index():
                self.log.append(entry)

    def _from_proto_entry(self, entry: p2p_pb2.LogEntry) -> RaftLogEntry:
        event = Event.from_log_entry_proto(entry, cluster_id=self.cluster_id)
        return RaftLogEntry(index=entry.index, term=entry.term, event=event)

    # ------------------------------------------------------------------
    # Commit listeners
    # ------------------------------------------------------------------
    def register_commit_listener(self, listener: Callable[[RaftLogEntry], None]) -> None:
        self._commit_listeners.append(listener)

    def _apply_committed_entries(self) -> None:
        entries_to_apply: List[RaftLogEntry] = []
        with self._lock:
            while self.last_applied < self.commit_index:
                self.last_applied += 1
                entries_to_apply.append(self.log[self.last_applied - 1])

        for entry in entries_to_apply:
            print(f"🔄 Applying committed entry | Index: {entry.index} | Type: {entry.event.command_type}")
            for listener in self._commit_listeners:
                listener(entry)

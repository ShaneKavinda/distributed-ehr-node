# raft/node.py

from enum import Enum
from typing import Callable, Dict, List, Optional
from threading import Lock
import asyncio

from models.event import Event
from raft.log_entry import RaftLogEntry

import grpc
import p2p_pb2.p2p_pb2 as p2p_pb2
from p2p_pb2.p2p_pb2_grpc import RaftServiceStub

from google.protobuf import struct_pb2

class Role(Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"

class RaftNode:
    def __init__(self, node_id: str, peer_ids: List[str]) -> None:
        self.node_id = node_id
        self.peer_ids = peer_ids

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

        self._lock = Lock()
        self._state_lock = asyncio.Lock()

        # Inject listeners
        self._commit_listeners: list[Callable[[RaftLogEntry], None]] = []

    # Helper logic
    def is_leader(self) -> bool:
        return self.role == Role.LEADER
    
    def last_log_index(self) -> int:
        return len(self.log)
    
    def last_log_term(self) -> int:
        if not self.log:
            return 0
        return self.log[-1].term
    
    def _quorom_size(self) -> int:
        return (int(len(self.peer_ids) / 2 + 1)) 
    
    def _dict_to_struct(self, data: dict) -> struct_pb2.Struct:
        s = struct_pb2.Struct()
        s.update(data)
        return s
    
    async def _persist_state(self):
        pass
    
    
    async def create_stub(self, peer_addr: str) -> RaftServiceStub:
        channel = grpc.aio.insecure_channel(peer_addr)
        return RaftServiceStub(channel)

    async def _become_follower(self, new_term: int):
        self.current_term = new_term
        self.role = Role.FOLLOWER
        self.voted_for = None

        # Reset leader state
        self.leader_id = None

        # Persist term + vote if you have persistence
        await self._persist_state()
    
    # When the node becomes the leader
    def _become_leader(self):
        '''
        Docstring for _become_leader
        
        :param self: current node
        '''
        self.role = Role.LEADER
        self.leader_id = self.node_id

        for peer in self.peer_ids:
            self.next_index[peer] = self.last_log_index() + 1   # First index the followers might be missing
            self.match_index[peer] = 0                          # Highest known replicated index on followers

    #-----------------------------------------------------------
    #  Leader-specific functions
    #-----------------------------------------------------------

    async def append_command(self, event: Event) -> None:
        '''
        Docstring for append_command
        
        :param self: Description
        :param event: Log event that is sent to the leader node to be appended
        :type event: RaftLogEntry
        '''
        with self._lock:
            if not self.is_leader():
                raise RuntimeError("Only leader can append commands.")
            entry = RaftLogEntry(
                index=self.last_log_index() + 1,
                term=self.current_term,
                event=event
            )

            self.log.append(entry)
            await self._replicate_log()
    def _build_append_entries_request(self, entries, prev_index, prev_term):
        proto_entries = []
        for entry in entries:
            proto_entries.append(
                p2p_pb2.LogEntry(
                    index=entry.index,
                    term=entry.term,
                    command_id=entry.event.command_id,
                    command_type=entry.event.command_type,
                    payload=self._dict_to_struct(entry.event.payload)
                )
            )

        request = p2p_pb2.AppendEntriesRequest(
                            leader_id=self.node_id,
                            term=self.current_term,
                            prev_log_index=prev_index,
                            prev_log_term=prev_term,
                            entries=proto_entries,
                            leader_commit=self.commit_index,
                        )
        return request

    async def _replicate_log(self):
        tasks = []

        for peer_id in self.peer_ids:
            if peer_id == self.node_id:
                continue
        
            next_idx = self.next_index.get(peer_id, 1)

            prev_index = next_idx - 1
            prev_term = 0
            if prev_index > 0:
                prev_term = self.log[prev_index - 1].term

            entries = self.log[prev_index:]
            # Build AppendEntriesRequest
            request = self._build_append_entries_request(entries, prev_index, prev_term)
            stub = self.create_stub(peer_id)

            tasks.append(
                asyncio.create_task(
                    self._send_append_entries(peer_id, stub, request)
                )
            )

        await asyncio.gather(*tasks, return_exceptions=True)


    
    async def _send_append_entries(
            self,
            peer_id: str,
            stub: RaftServiceStub,
            request: p2p_pb2.AppendEntriesRequest,
        ) -> None:
        '''
        Docstring for _send_append_entries
        
        :param self: Current (leader) node i.e. self
        :param peer_id: node_id of the peer node
        :type peer_id: str
        '''
        next_idx = self.next_index.get(peer_id, 1)

        prev_index = next_idx - 1
        prev_term = 0
        if prev_index > 0:
            prev_term = self.log[prev_index - 1].term

        entries = self.log[prev_index:]

        # Build AppendEntriesRequest
        request = self._build_append_entries_request(entries, prev_index, prev_term)

        # Send via gRPC
        # Handle response asynchronously
        try:
            response = await stub.AppendEntries(request)
            await self._handle_append_entries_response(peer_id, request, response)

        except grpc.aio.AioRpcError as e:
            # Network failure ≠ Raft failure
            self.logger.warning(
                "AppendEntries RPC to %s failed: %s",
                peer_id,
                e.details(),
            )

    # Advance commit index (leader specific function)
    def _advance_commit_index(self):
        for N in range(self.commit_index + 1, self.last_log_index() + 1):
            replicated = sum(
                1 for m in self.match_index.values() if m >= N
            )

            if (replicated + 1) >= self._quorom_size():
                if self.log[N-1].term == self.current_term:
                    self.commit_index = N
                    
    def _log_matches(self, prev_log_index: int, prev_log_term: int) -> bool:
        """
        Check whether the local log contains an entry at prev_log_index
        whose term matches prev_log_term.
        """
        # Case 1: Leader claims no previous entry
        if prev_log_index == 0:
            return True

        # Case 2: Local log is too short
        if prev_log_index > len(self.log):
            return False

        # Case 3: Term mismatch
        local_term = self.log[prev_log_index - 1].term
        return local_term == prev_log_term
    
    def _send_health_checks(self):
        '''
        Generate periodic heartbeats to followers

        Purpose:
        1. Replicate log entries (or empty for heartbeat)
        2. Prevent election timeouts (heartbeat resets timer)
        3. Update follower commit index
        :param self: Description
        '''
        with self._lock:
            if self.current_term != 
    #-----------------------------------------------------------------
    # Follower logic
    #-----------------------------------------------------------------

    # Handle response from the peers (followers)
    async def _handle_append_entries_response(
        self,
        peer_id: str,
        request: p2p_pb2.AppendEntriesRequest,
        response: p2p_pb2.AppendEntriesResponse,
    ):
        async with self._state_lock:

            # Step down if term is higher
            if response.term > self.current_term:
                await self._become_follower(response.term)
                return

            # Ignore stale responses
            if self.role != Role.LEADER:
                return

            if not response.success:
                # Backtrack nextIndex (Raft §5.3)
                self.next_index[peer_id] = max(
                    1,
                    self.next_index[peer_id] - 1
                )
                return

            # Success path
            last_replicated = (
                request.prev_log_index + len(request.entries)
            )

            self.match_index[peer_id] = last_replicated
            self.next_index[peer_id] = last_replicated + 1

            self._advance_commit_index()


    def _delete_conflicting_entries(self, log_entries: List[RaftLogEntry]) -> None:
        '''
        Docstring for _delete_conflicting_entries
        
        :param self: current node instance
        :param entries: List of Raft Log Entries
        :type entries: List[RaftLogEntry]
        '''
        for entry in log_entries:
            local_index = entry.index - 1   # Convert raft index into list index (starting from 0)

            # If the local index is shorter, nothing to conflict
            if local_index >= len(self.log):
                return 
            
            local_entry = self.log[local_index]

            # Confict: same index, different term
            if local_entry.term != entry.term:
                # Delete this entry and everything after it
                self.log = self.log[:local_index]
                return
            
    def _append_new_entries(self, entries: List[RaftLogEntry]) -> None:
        '''
        Docstring for _append_new_entries
        
        :param self: Description
        :param entries: List of Raft Log Entries to append to the current log
        :type entries: List[RaftLogEntry]
        '''
        for entry in entries:
            if entry.index > self.last_log_index():
                self.log.append(entry)

    def register_commit_listener(self, listener):
        self._commit_listeners.append(listener)

    def _on_commit(self, entry: RaftLogEntry) -> None:
        '''
        Docstring for _on_commit

        Called exactly once per committed log entry, in index order.

        e.g. :
        
        raft_node.register_commit_listener(ehr_dispatcher.on_commit)
    
        raft_node.register_commit_listener(audit_dispatcher.on_commit)
        
        :param self: Description
        :param entry: Description
        :type entry: RaftLogEntry
        '''
        for listener in self._commit_listeners:
            listener(entry)

    def _apply_committed_entries(self):
        '''
        Docstring for _apply_committed_entries

                
        :param self: current node instance
        '''
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.log[self.last_applied -1]  # Get the list index (start from 0 instead of 1)
            self._on_commit(entry)

    #------------------------------------------------------------------------
    #   Follower Logic
    #------------------------------------------------------------------------
    def handle_append_entries(self, request) -> bool:
        '''
        Docstring for handle_append_entries
        
        :param self: current (leader) node
        :param request: Request from the leader node to followers to append to their own logs
        :return: Return True on success, False on failure
        :rtype: bool
        '''
        with self._lock:
            if request.term < self.current_term:
                return False

            # Step down if term is newer
            if request.term > self.current_term:
                self.current_term = request.term
                self.voted_for = None
                self.role = Role.FOLLOWER

            self.leader_id = request.leader_id

            # 1: log consistency check
            if not self._log_matches(request.prev_log_index, request.prev_log_term)
                return False
            # 2: Delete conflicting entries
            self._delete_conflicting_entries(request.entries)
            # 3. Append new entries
            self._append_new_entries(request.entries)

            # 4. Update commit index
            self.commit_index = min(
                request.leader_commit,
                self.last_log_index()
            )

            return True
    
    #---------------------------------------------------
    #   Candidate (Voting) logic
    #---------------------------------------------------
    def handle_request_vote(self, request) -> bool:
        '''
        Docstring for handle_request_vote
        
        :param self: current node
        :param request: vote request containing term, last_log_term, candidate_id
        :return: Return if the current node is voting or not.
        :rtype: bool
        '''
        with self._lock:
            if request.term < self.current_term:
                return False

            if request.term > self.current_term:
                self.current_term = request.term
                self.voted_for = None
                self.role = Role.FOLLOWER

            if self.voted_for is not None:
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
            return True



   
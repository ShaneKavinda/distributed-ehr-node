from __future__ import annotations

import p2p_pb2.p2p_pb2 as p2p_pb2
import p2p_pb2.p2p_pb2_grpc as p2p_pb2_grpc

from models.event import Event
from raft.commit_tracker import CommitTracker


class CommandServiceServicer(p2p_pb2_grpc.CommandServiceServicer):
    def __init__(
        self,
        raft_node,
        cluster_id: str,
        commit_tracker: CommitTracker,
        peer_addresses: dict[str, str],
        self_address: str,
        command_timeout_s: float,
    ) -> None:
        self.raft_node = raft_node
        self.cluster_id = cluster_id
        self._commit_tracker = commit_tracker
        self._peer_addresses = peer_addresses
        self._self_address = self_address
        self._command_timeout_s = command_timeout_s

    def _leader_address(self) -> str:
        leader_id = self.raft_node.get_leader_id()
        if not leader_id:
            return ""
        if leader_id == self.raft_node.node_id:
            return self._self_address
        return self._peer_addresses.get(leader_id, "")

    def SubmitCommand(self, request, context) -> p2p_pb2.CommandResponse:
        if not self.raft_node.is_leader():
            return p2p_pb2.CommandResponse(
                accepted=False,
                leader_id=self.raft_node.get_leader_id(),
                leader_address=self._leader_address(),
                committed=False,
                commit_index=0,
            )

        event = Event.from_command_request(request, cluster_id=self.cluster_id)
        entry_index = self.raft_node.append_command(event)
        committed = self._commit_tracker.wait_for_commit(
            entry_index, timeout_s=self._command_timeout_s
        )

        return p2p_pb2.CommandResponse(
            accepted=True,
            leader_id=self.raft_node.get_leader_id(),
            leader_address=self._leader_address(),
            committed=committed,
            commit_index=entry_index if committed else 0,
        )

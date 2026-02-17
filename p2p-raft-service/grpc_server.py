from __future__ import annotations

from concurrent import futures
import time

import grpc

import p2p_pb2.p2p_pb2 as p2p_pb2
import p2p_pb2.p2p_pb2_grpc as p2p_pb2_grpc

from api.command_service import CommandServiceServicer


class RaftServiceServicer(p2p_pb2_grpc.RaftServiceServicer):
    def __init__(self, raft_node) -> None:
        self.raft_node = raft_node

    def AppendEntries(
        self, request: p2p_pb2.AppendEntriesRequest, context
    ) -> p2p_pb2.AppendEntriesResponse:
        success = self.raft_node.handle_append_entries(request)
        return p2p_pb2.AppendEntriesResponse(term=self.raft_node.current_term, success=success)

    def RequestVote(
        self, request: p2p_pb2.RequestVoteRequest, context
    ) -> p2p_pb2.RequestVoteResponse:
        vote_granted = self.raft_node.handle_request_vote(request)
        return p2p_pb2.RequestVoteResponse(
            term=self.raft_node.current_term, vote_granted=vote_granted
        )

    def InstallSnapshot(
        self, request: p2p_pb2.InstallSnapshotRequest, context
    ) -> p2p_pb2.InstallSnapshotResponse:
        self.raft_node.handle_install_snapshot(request)
        return p2p_pb2.InstallSnapshotResponse(term=self.raft_node.current_term)


class GrpcServer:
    def __init__(
        self,
        raft_node,
        cluster_id: str,
        port: int,
        commit_tracker,
        peer_addresses: dict[str, str],
        self_address: str,
        command_timeout_s: float,
    ) -> None:
        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

        p2p_pb2_grpc.add_CommandServiceServicer_to_server(
            CommandServiceServicer(
                raft_node,
                cluster_id,
                commit_tracker,
                peer_addresses,
                self_address,
                command_timeout_s,
            ),
            self._server,
        )
        p2p_pb2_grpc.add_RaftServiceServicer_to_server(
            RaftServiceServicer(raft_node), self._server
        )

        self._server.add_insecure_port(f"[::]:{port}")

    def start(self) -> None:
        self._server.start()

    def block_forever(self) -> None:
        try:
            while True:
                time.sleep(86400)
        except KeyboardInterrupt:
            self._server.stop(0)

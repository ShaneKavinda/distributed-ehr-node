from __future__ import annotations

from typing import Dict, Optional

import grpc

import p2p_pb2.p2p_pb2 as p2p_pb2
import p2p_pb2.p2p_pb2_grpc as p2p_pb2_grpc


class GrpcTransport:
    def __init__(self, peers: Dict[str, str], rpc_timeout_s: float) -> None:
        self._peers = peers
        self._rpc_timeout_s = rpc_timeout_s
        self._channels: Dict[str, grpc.Channel] = {}
        self._stubs: Dict[str, p2p_pb2_grpc.RaftServiceStub] = {}

    def _stub_for(self, peer_id: str) -> p2p_pb2_grpc.RaftServiceStub:
        if peer_id not in self._stubs:
            target = self._peers[peer_id]
            channel = grpc.insecure_channel(target)
            self._channels[peer_id] = channel
            self._stubs[peer_id] = p2p_pb2_grpc.RaftServiceStub(channel)
        return self._stubs[peer_id]

    def append_entries(
        self, peer_id: str, request: p2p_pb2.AppendEntriesRequest
    ) -> Optional[p2p_pb2.AppendEntriesResponse]:
        try:
            return self._stub_for(peer_id).AppendEntries(request, timeout=self._rpc_timeout_s)
        except grpc.RpcError:
            return None

    def request_vote(
        self, peer_id: str, request: p2p_pb2.RequestVoteRequest
    ) -> Optional[p2p_pb2.RequestVoteResponse]:
        try:
            return self._stub_for(peer_id).RequestVote(request, timeout=self._rpc_timeout_s)
        except grpc.RpcError:
            return None

    def install_snapshot(
        self, peer_id: str, request: p2p_pb2.InstallSnapshotRequest
    ) -> Optional[p2p_pb2.InstallSnapshotResponse]:
        try:
            return self._stub_for(peer_id).InstallSnapshot(request, timeout=self._rpc_timeout_s)
        except grpc.RpcError:
            return None

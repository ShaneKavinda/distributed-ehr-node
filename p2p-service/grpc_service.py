# grpc_service.py
import grpc
from concurrent import futures
import time

from p2p_pb2.p2p_pb2 import CommandRequest, CommandResponse
from p2p_pb2.p2p_pb2 import AppendEntriesRequest, AppendEntriesResponse
from p2p_pb2.p2p_pb2 import RequestVoteRequest, RequestVoteResponse
from p2p_pb2.p2p_pb2 import InstallSnapshotRequest, InstallSnapshotResponse

from api.command_service import CommandServiceServicer

import p2p_pb2.p2p_pb2_grpc as p2p_pb2_grpc

from models.event import Event

#-----------------------------------------------------------
#   P2P Raft service implementation
#-----------------------------------------------------------
class RaftServiceServicer(p2p_pb2_grpc.RaftServiceServicer):
    def __init__(self, raft_node) -> None:
        self.raft_node = raft_node
    
    def AppendEntries(self, request: AppendEntriesRequest, context) -> AppendEntriesResponse:
        success = self.raft_node.handle_append_entries(request)
        return AppendEntriesResponse(
            term=self.raft_node.current_term,
            success=success
        )

    def RequestVote(self, request: RequestVoteRequest, context) -> RequestVoteResponse:
        vote_granted = self.raft_node.handle_request_vote(request)
        return RequestVoteResponse(
            term=self.raft_node.current_term,
            vote_granted=vote_granted
        )
    
    def InstallSnapshot(self, request: InstallSnapshotRequest, context) -> InstallSnapshotResponse:
        self.raft_node.install_snapshot(request)
        return InstallSnapshotResponse(
            term=self.raft_node.current_term
        )
    
#----------------------------------------------------------
#   gRPC Server Endpoint
#----------------------------------------------------------

def serve(raft_node, cluster_id, port=50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # Add service handlers
    p2p_pb2_grpc.add_CommandServiceServicer_to_server(
        CommandServiceServicer(raft_node, cluster_id), server
    )
    p2p_pb2_grpc.add_RaftServiceServicer_to_server(
        RaftServiceServicer(raft_node), server
    )

    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"gRPC server started on port {port}")

    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)
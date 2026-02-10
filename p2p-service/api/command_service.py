# api/command_service.py
from models.event import Event
from p2p_pb2.p2p_pb2 import CommandResponse
import p2p_pb2.p2p_pb2_grpc as p2p_pb2_grpc

class CommandServiceServicer(p2p_pb2_grpc.CommandServiceServicer):
    def __init__(self, raft_node, cluster_id):
        self.raft_node = raft_node
        self.cluster_id = cluster_id

    def SubmitCommand(self, request, context) -> CommandResponse:
        if not self.raft_node.is_leader():
            return CommandResponse(
                accepted=False,
                leader_id=self.raft_node.leader_id()
            )

        event = Event.from_command_request(request, cluster_id=self.cluster_id)
        self.raft_node.append_command(event)

        return CommandResponse(
            accepted=True,
            leader_id=self.raft_node.leader_id()
        )

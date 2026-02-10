from raft.node import RaftNode
from dispatch.dispatcher import EventDispatcher
from grpc_service import GrpcServer
from config import config

def main():
    # load minimal config
    cfg = config or {}

    # instantiate components
    dispatcher = EventDispatcher()
    raft = RaftNode(cfg, dispatcher)
    grpc_server = GrpcServer(raft, dispatcher)

    dispatcher.start()
    raft.start()
    grpc_server.start()

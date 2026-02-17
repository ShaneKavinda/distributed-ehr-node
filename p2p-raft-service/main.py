from __future__ import annotations

from config import load_config
from grpc_server import GrpcServer
from raft.node import RaftNode
from raft.transport import GrpcTransport
from raft.commit_tracker import CommitTracker
from replication.ehr_applier import EhrCommandApplier


def main() -> None:
    cfg = load_config()

    transport = GrpcTransport(cfg.peers, cfg.rpc_timeout_ms / 1000.0)
    node = RaftNode(
        node_id=cfg.node_id,
        peer_ids=list(cfg.peers.keys()),
        transport=transport,
        election_timeout_ms=cfg.election_timeout_ms,
        heartbeat_interval_ms=cfg.heartbeat_interval_ms,
        cluster_id=cfg.cluster_id,
    )

    commit_tracker = CommitTracker()
    ehr_applier = EhrCommandApplier(
        host=cfg.ehr_grpc_host,
        port=cfg.ehr_grpc_port,
        timeout_s=cfg.ehr_rpc_timeout_ms / 1000.0,
    )

    node.register_commit_listener(ehr_applier.apply)
    node.register_commit_listener(commit_tracker.notify)

    grpc_server = GrpcServer(
        node,
        cfg.cluster_id,
        cfg.grpc_port,
        commit_tracker,
        cfg.peer_addresses,
        cfg.self_address,
        cfg.command_timeout_ms / 1000.0,
    )
    node.start()
    grpc_server.start()
    grpc_server.block_forever()


if __name__ == "__main__":
    main()

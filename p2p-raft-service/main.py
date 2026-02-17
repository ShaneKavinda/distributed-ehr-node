from __future__ import annotations

from config import load_config
from grpc_server import GrpcServer
from raft.node import RaftNode
from raft.transport import GrpcTransport
from raft.commit_tracker import CommitTracker
from replication.ehr_applier import EhrCommandApplier


def main() -> None:
    cfg = load_config()

    print("=" * 80)
    print(f"🚀 Starting P2P Raft Service - Node: {cfg.node_id}")
    print(f"📡 Cluster ID: {cfg.cluster_id}")
    print(f"🌐 gRPC Port: {cfg.grpc_port}")
    print(f"👥 Peers: {list(cfg.peers.keys())}")
    print(f"⏱️  Election Timeout: {cfg.election_timeout_ms}ms")
    print(f"💓 Heartbeat Interval: {cfg.heartbeat_interval_ms}ms")
    print("=" * 80)

    print("🔧 Initializing Raft transport layer...")
    transport = GrpcTransport(cfg.peers, cfg.rpc_timeout_ms / 1000.0)

    print("🔧 Initializing Raft consensus node...")
    node = RaftNode(
        node_id=cfg.node_id,
        peer_ids=list(cfg.peers.keys()),
        transport=transport,
        election_timeout_ms=cfg.election_timeout_ms,
        heartbeat_interval_ms=cfg.heartbeat_interval_ms,
        cluster_id=cfg.cluster_id,
    )

    print("🔧 Initializing commit tracker...")
    commit_tracker = CommitTracker()

    print(f"🔧 Initializing EHR applier (connecting to {cfg.ehr_grpc_host}:{cfg.ehr_grpc_port})...")
    ehr_applier = EhrCommandApplier(
        host=cfg.ehr_grpc_host,
        port=cfg.ehr_grpc_port,
        timeout_s=cfg.ehr_rpc_timeout_ms / 1000.0,
    )

    print("🔗 Registering commit listeners...")
    node.register_commit_listener(ehr_applier.apply)
    node.register_commit_listener(commit_tracker.notify)

    print("🔧 Initializing gRPC server...")
    grpc_server = GrpcServer(
        node,
        cfg.cluster_id,
        cfg.grpc_port,
        commit_tracker,
        cfg.peer_addresses,
        cfg.self_address,
        cfg.command_timeout_ms / 1000.0,
    )

    print("▶️  Starting Raft node...")
    node.start()

    print("▶️  Starting gRPC server...")
    grpc_server.start()

    print("✅ P2P Raft Service is ready and running!")
    print(f"👂 Listening on port {cfg.grpc_port}")
    print("⏳ Waiting for leader election...")

    grpc_server.block_forever()


if __name__ == "__main__":
    main()

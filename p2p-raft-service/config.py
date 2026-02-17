from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Dict, Optional


@dataclass(frozen=True)
class Config:
    node_id: str
    grpc_port: int
    peers: Dict[str, str]
    peer_addresses: Dict[str, str]
    self_address: str
    cluster_id: str
    election_timeout_ms: int
    heartbeat_interval_ms: int
    rpc_timeout_ms: int
    command_timeout_ms: int
    ehr_grpc_host: str
    ehr_grpc_port: int
    ehr_rpc_timeout_ms: int


def _parse_int(value: Optional[str], default: int) -> int:
    if value is None or value.strip() == "":
        return default
    return int(value)


def _parse_peers(value: str) -> Dict[str, str]:
    peers: Dict[str, str] = {}
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"Invalid peer entry '{part}'. Use id=host:port.")
        node_id, address = part.split("=", 1)
        node_id = node_id.strip()
        address = address.strip()
        if not node_id or not address:
            raise ValueError(f"Invalid peer entry '{part}'. Use id=host:port.")
        peers[node_id] = address
    return peers


def load_config() -> Config:
    node_id = os.environ.get("NODE_ID", "").strip()
    grpc_port = os.environ.get("GRPC_PORT", "").strip()
    peers_raw = os.environ.get("PEERS", "").strip()

    if not node_id:
        raise ValueError("NODE_ID is required.")
    if not grpc_port:
        raise ValueError("GRPC_PORT is required.")
    if not peers_raw:
        raise ValueError("PEERS is required.")

    peer_addresses = _parse_peers(peers_raw)

    # Remove self from peers list
    self_address = peer_addresses.get(node_id, "").strip()
    if not self_address:
        self_address = os.environ.get("SELF_ADDRESS", "").strip()
    if not self_address:
        raise ValueError("PEERS must include this NODE_ID or SELF_ADDRESS must be set.")

    peers = {k: v for k, v in peer_addresses.items() if k != node_id}

    return Config(
        node_id=node_id,
        grpc_port=int(grpc_port),
        peers=peers,
        peer_addresses=peer_addresses,
        self_address=self_address,
        cluster_id=os.environ.get("CLUSTER_ID", "default"),
        election_timeout_ms=_parse_int(os.environ.get("ELECTION_TIMEOUT_MS"), 1500),
        heartbeat_interval_ms=_parse_int(os.environ.get("HEARTBEAT_INTERVAL_MS"), 400),
        rpc_timeout_ms=_parse_int(os.environ.get("RPC_TIMEOUT_MS"), 800),
        command_timeout_ms=_parse_int(os.environ.get("COMMAND_TIMEOUT_MS"), 3000),
        ehr_grpc_host=os.environ.get("EHR_GRPC_HOST", "localhost"),
        ehr_grpc_port=_parse_int(os.environ.get("EHR_GRPC_PORT"), 50051),
        ehr_rpc_timeout_ms=_parse_int(os.environ.get("EHR_RPC_TIMEOUT_MS"), 800),
    )

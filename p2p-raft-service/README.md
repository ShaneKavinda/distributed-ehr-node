# P2P Raft Service

This folder contains a minimal peer-to-peer microservice layer that uses Raft
consensus and gRPC for node-to-node communication. It is designed as a small,
self-contained example you can run alongside the rest of the repository.

Quickstart:
1. `python -m venv .venv`
2. `.venv\Scripts\activate`
3. `pip install -r requirements.txt`
4. `python -m grpc_tools.protoc -I proto --python_out p2p_pb2 --grpc_python_out p2p_pb2 proto/p2p.proto`
5. Set environment variables listed below.
6. `python main.py`

Environment variables:
- `NODE_ID` (required). Unique ID for this node.
- `GRPC_PORT` (required). Port to bind the gRPC server.
- `PEERS` (required). Comma-separated list of `id=host:port`.
- `CLUSTER_ID` (optional). Cluster identifier used for events. Default `default`.
- `ELECTION_TIMEOUT_MS` (optional). Default `1500`.
- `HEARTBEAT_INTERVAL_MS` (optional). Default `400`.
- `RPC_TIMEOUT_MS` (optional). Default `800`.
- `COMMAND_TIMEOUT_MS` (optional). Max wait for a command to commit. Default `3000`.
- `EHR_GRPC_HOST` (optional). Hostname for local EHR CRUD gRPC. Default `localhost`.
- `EHR_GRPC_PORT` (optional). Port for local EHR CRUD gRPC. Default `50051`.
- `EHR_RPC_TIMEOUT_MS` (optional). Timeout for applying commands to EHR. Default `800`.

Example (three nodes on one machine):
- Node 1: `NODE_ID=node1`, `GRPC_PORT=50051`, `PEERS=node1=localhost:50051,node2=localhost:50052,node3=localhost:50053`
- Node 2: `NODE_ID=node2`, `GRPC_PORT=50052`, `PEERS=node1=localhost:50051,node2=localhost:50052,node3=localhost:50053`
- Node 3: `NODE_ID=node3`, `GRPC_PORT=50053`, `PEERS=node1=localhost:50051,node2=localhost:50052,node3=localhost:50053`

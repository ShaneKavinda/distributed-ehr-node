"""
P2P Cluster Client with automatic failover and pod discovery
"""
import grpc.aio
import asyncio
import os
from uuid import uuid4
from datetime import date, datetime
from typing import Optional, List
from google.protobuf.struct_pb2 import Struct

from proto import p2p_pb2_grpc, p2p_pb2


def serialize_dates(obj):
    """Recursively serialize date and datetime objects to ISO format strings"""
    if isinstance(obj, dict):
        return {key: serialize_dates(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [serialize_dates(item) for item in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    return obj


class P2PClusterClient:
    """
    P2P Client that can discover and connect to multiple pods in a StatefulSet.
    Automatically retries on different pods if one is unavailable.
    """

    def __init__(
        self,
        service_name: str,
        namespace: str,
        statefulset_name: str,
        replicas: int,
        port: int,
        timeout_s: float = 5.0
    ):
        self.service_name = service_name
        self.namespace = namespace
        self.statefulset_name = statefulset_name
        self.replicas = replicas
        self.port = port
        self.timeout_s = timeout_s
        self.channels = []

    def _get_pod_addresses(self) -> List[str]:
        """Generate list of pod addresses based on StatefulSet naming"""
        addresses = []
        for i in range(self.replicas):
            pod_name = f"{self.statefulset_name}-{i}"
            # Use headless service for direct pod access
            fqdn = f"{pod_name}.{self.service_name}.{self.namespace}.svc.cluster.local"
            addresses.append(f"{fqdn}:{self.port}")
        return addresses

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Close all channels
        await asyncio.gather(
            *[channel.close() for channel in self.channels],
            return_exceptions=True
        )
        self.channels.clear()

    async def submit_command(
        self,
        command_type: str,
        payload: dict
    ) -> p2p_pb2.CommandResponse:
        """
        Submit a command to the Raft cluster.
        Tries multiple pods until one accepts or redirects to the leader.
        """
        command_id = str(uuid4())
        struct_payload = Struct()
        struct_payload.update(serialize_dates(payload))

        request = p2p_pb2.CommandRequest(
            command_id=command_id,
            command_type=command_type,
            payload=struct_payload,
        )

        pod_addresses = self._get_pod_addresses()
        print(f"[P2P] Attempting to submit command {command_type} (ID: {command_id})")
        print(f"[P2P] Available pods: {pod_addresses}")

        last_error = None

        # Try each pod
        for address in pod_addresses:
            try:
                print(f"[P2P] Trying pod at {address}...")
                response = await self._try_submit_to_pod(address, request)

                if response.accepted:
                    print(f"[P2P] Command accepted by {address}")
                    if response.committed:
                        print(f"[P2P] Command committed successfully")
                    return response

                # If not accepted but has leader address, try the leader
                if response.leader_address:
                    print(f"[P2P] Pod {address} redirected to leader: {response.leader_address}")
                    return await self._submit_to_leader(response.leader_address, request)

            except grpc.aio.AioRpcError as e:
                last_error = e
                print(f"[P2P] Failed to connect to {address}: {e.code()} - {e.details()}")
                continue
            except Exception as e:
                last_error = e
                print(f"[P2P] Unexpected error with {address}: {str(e)}")
                continue

        # If all pods failed
        error_msg = f"All pods unavailable. Last error: {str(last_error)}"
        print(f"[P2P] ERROR: {error_msg}")
        raise Exception(error_msg)

    async def _try_submit_to_pod(
        self,
        address: str,
        request: p2p_pb2.CommandRequest
    ) -> p2p_pb2.CommandResponse:
        """Try to submit command to a specific pod"""
        channel = grpc.aio.insecure_channel(address)
        self.channels.append(channel)
        stub = p2p_pb2_grpc.CommandServiceStub(channel)

        response = await stub.SubmitCommand(request, timeout=self.timeout_s)
        return response

    async def _submit_to_leader(
        self,
        leader_address: str,
        request: p2p_pb2.CommandRequest
    ) -> p2p_pb2.CommandResponse:
        """Submit command directly to the leader"""
        print(f"[P2P] Connecting to leader at {leader_address}")
        channel = grpc.aio.insecure_channel(leader_address)
        stub = p2p_pb2_grpc.CommandServiceStub(channel)
        try:
            response = await stub.SubmitCommand(request, timeout=self.timeout_s)
            print(f"[P2P] Leader response: accepted={response.accepted}, committed={response.committed}")
            return response
        finally:
            await channel.close()


class P2PCommandClient:
    """
    Legacy single-host P2P client for backward compatibility
    """
    def __init__(self, host: str, port: int, timeout_s: float = 3.0) -> None:
        self.address = f"{host}:{port}"
        self.timeout_s = timeout_s
        self.channel = None
        self.stub = None

    async def __aenter__(self):
        self.channel = grpc.aio.insecure_channel(self.address)
        self.stub = p2p_pb2_grpc.CommandServiceStub(self.channel)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.channel:
            await self.channel.close()

    async def submit_command(self, command_type: str, payload: dict) -> p2p_pb2.CommandResponse:
        command_id = str(uuid4())
        struct_payload = Struct()
        struct_payload.update(serialize_dates(payload))

        request = p2p_pb2.CommandRequest(
            command_id=command_id,
            command_type=command_type,
            payload=struct_payload,
        )

        response = await self.stub.SubmitCommand(request, timeout=self.timeout_s)
        if response.accepted:
            return response

        if response.leader_address:
            return await self._submit_to_leader(response.leader_address, request)

        return response

    async def _submit_to_leader(
        self, leader_address: str, request: p2p_pb2.CommandRequest
    ) -> p2p_pb2.CommandResponse:
        channel = grpc.aio.insecure_channel(leader_address)
        stub = p2p_pb2_grpc.CommandServiceStub(channel)
        try:
            return await stub.SubmitCommand(request, timeout=self.timeout_s)
        finally:
            await channel.close()

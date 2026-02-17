import grpc.aio
from uuid import uuid4
from datetime import date, datetime
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


class P2PCommandClient:
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

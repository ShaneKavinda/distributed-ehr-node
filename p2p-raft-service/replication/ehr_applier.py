from __future__ import annotations

import grpc
from google.protobuf.struct_pb2 import Struct

from ehr_pb2 import ehr_service_pb2 as ehr_pb2
from ehr_pb2 import ehr_service_pb2_grpc as ehr_pb2_grpc
from raft.log_entry import RaftLogEntry


class EhrCommandApplier:
    def __init__(self, host: str, port: int, timeout_s: float) -> None:
        self._address = f"{host}:{port}"
        self._timeout_s = timeout_s
        self._channel = grpc.insecure_channel(self._address)
        self._stub = ehr_pb2_grpc.EhrServiceStub(self._channel)

    def apply(self, entry: RaftLogEntry) -> None:
        event = entry.event
        command_type = event.command_type

        if command_type == "PATIENT_CREATE":
            payload = Struct()
            payload.update(event.payload)
            request = ehr_pb2.CreatePatientRequest(patientData=payload)
            try:
                self._stub.CreatePatient(request, timeout=self._timeout_s)
            except grpc.RpcError as exc:
                print(f"[ehr-applier] CreatePatient failed: {exc}")
            return

        if command_type == "PATIENT_UPDATE":
            patient_uuid = str(event.payload.get("patient_uuid", "")).strip()
            update_data = event.payload.get("update", {}) or {}
            payload = Struct()
            payload.update(update_data)
            request = ehr_pb2.UpdatePatientRequest(
                patient_uuid=patient_uuid, updateData=payload
            )
            try:
                self._stub.UpdatePatient(request, timeout=self._timeout_s)
            except grpc.RpcError as exc:
                print(f"[ehr-applier] UpdatePatient failed: {exc}")
            return

        if command_type == "PATIENT_DELETE":
            patient_uuid = str(event.payload.get("patient_uuid", "")).strip()
            request = ehr_pb2.DeletePatientRequest(patient_uuid=patient_uuid)
            try:
                self._stub.DeletePatient(request, timeout=self._timeout_s)
            except grpc.RpcError as exc:
                print(f"[ehr-applier] DeletePatient failed: {exc}")
            return

        print(f"[ehr-applier] Unknown command type: {command_type}")

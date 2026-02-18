"""
gRPC Cluster Client with automatic failover and pod discovery
"""
import grpc.aio
import asyncio
from typing import List, Dict, Any
from datetime import date, datetime
from google.protobuf.struct_pb2 import Struct
from google.protobuf.json_format import MessageToDict

from proto import ehr_service_pb2, ehr_service_pb2_grpc


def serialize_dates(obj):
    """Recursively serialize date and datetime objects to ISO format strings"""
    if isinstance(obj, dict):
        return {key: serialize_dates(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_dates(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    else:
        return obj


def dict_to_struct(data: dict) -> Struct:
    """Convert Python dict to protobuf Struct, serializing dates first"""
    # Serialize dates to strings
    serialized_data = serialize_dates(data)

    # Convert to Struct
    struct = Struct()
    struct.update(serialized_data)
    return struct


class GrpcClusterClient:
    """
    gRPC Client that can discover and connect to multiple pods in a StatefulSet.
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

    async def _try_operation(self, operation_func, *args, **kwargs):
        """
        Generic method to try an operation on multiple pods.
        Returns result from first successful pod.
        """
        pod_addresses = self._get_pod_addresses()
        last_error = None

        for address in pod_addresses:
            try:
                channel = grpc.aio.insecure_channel(address)
                self.channels.append(channel)
                stub = ehr_service_pb2_grpc.EhrServiceStub(channel)

                # Call the operation
                result = await operation_func(stub, *args, **kwargs)
                return result

            except grpc.aio.AioRpcError as e:
                last_error = e
                # For NOT_FOUND errors, we should propagate immediately (data doesn't exist)
                if e.code() == grpc.StatusCode.NOT_FOUND:
                    raise
                # For other errors, try next pod
                print(f"[gRPC] Failed to connect to {address}: {e.code()} - {e.details()}")
                continue
            except Exception as e:
                last_error = e
                print(f"[gRPC] Unexpected error with {address}: {str(e)}")
                continue

        # If all pods failed
        if last_error:
            raise last_error
        raise Exception("All pods unavailable")

    async def create_patient(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new patient"""
        async def _create(stub):
            # Convert dict to protobuf Struct
            patient_struct = dict_to_struct(patient_data)

            request = ehr_service_pb2.CreatePatientRequest(
                patientData=patient_struct
            )
            response = await stub.CreatePatient(request, timeout=self.timeout_s)
            return self._patient_proto_to_dict(response.patient)

        return await self._try_operation(_create)

    async def get_patient(self, patient_uuid: str) -> Dict[str, Any]:
        """Get patient by UUID"""
        async def _get(stub):
            request = ehr_service_pb2.GetPatientRequest(patient_uuid=patient_uuid)
            response = await stub.GetPatient(request, timeout=self.timeout_s)
            return self._patient_proto_to_dict(response.patient)

        return await self._try_operation(_get)

    async def get_all_patients(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all patients with pagination"""
        async def _get_all(stub):
            request = ehr_service_pb2.GetAllPatientsRequest(skip=skip, limit=limit)
            response = await stub.GetAllPatients(request, timeout=self.timeout_s)
            return [self._patient_proto_to_dict(p) for p in response.patients]

        return await self._try_operation(_get_all)

    async def search_patient_by_id(self, patient_id: str) -> Dict[str, Any]:
        """Search patient by patient_id"""
        async def _search(stub):
            request = ehr_service_pb2.SearchPatientByIdRequest(patient_id=patient_id)
            response = await stub.SearchPatientById(request, timeout=self.timeout_s)
            return self._patient_proto_to_dict(response.patient)

        return await self._try_operation(_search)

    async def update_patient(self, patient_uuid: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update patient"""
        async def _update(stub):
            # Convert dict to protobuf Struct
            update_struct = dict_to_struct(update_data)

            request = ehr_service_pb2.UpdatePatientRequest(
                patient_uuid=patient_uuid,
                updateData=update_struct
            )
            response = await stub.UpdatePatient(request, timeout=self.timeout_s)
            return self._patient_proto_to_dict(response.patient)

        return await self._try_operation(_update)

    async def delete_patient(self, patient_uuid: str) -> Dict[str, Any]:
        """Delete patient"""
        async def _delete(stub):
            request = ehr_service_pb2.DeletePatientRequest(patient_uuid=patient_uuid)
            response = await stub.DeletePatient(request, timeout=self.timeout_s)
            return {
                'success': response.success,
                'message': response.message
            }

        return await self._try_operation(_delete)

    def _patient_proto_to_dict(self, patient_proto) -> Dict[str, Any]:
        """Convert protobuf patient message to dictionary"""
        result = {
            'id': patient_proto.id,
            'version': patient_proto.version,
            'lastUpdated': patient_proto.lastUpdated,
            'created_at': patient_proto.created_at,
            'updated_at': patient_proto.updated_at
        }

        # Convert Struct fields to dicts
        if patient_proto.HasField('identity'):
            result['identity'] = MessageToDict(patient_proto.identity)
        if patient_proto.HasField('demographics'):
            result['demographics'] = MessageToDict(patient_proto.demographics)
        if patient_proto.HasField('contacts'):
            result['contacts'] = MessageToDict(patient_proto.contacts)
        if patient_proto.HasField('meta'):
            result['meta'] = MessageToDict(patient_proto.meta)

        # Convert ListValue fields to Python lists
        result['conditions'] = [MessageToDict(item) for item in patient_proto.conditions]

        return result

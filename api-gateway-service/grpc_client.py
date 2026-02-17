import grpc
from datetime import date, datetime
from google.protobuf.struct_pb2 import Struct
from google.protobuf.json_format import MessageToDict
from proto import ehr_service_pb2_grpc, ehr_service_pb2


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


class GrpcClient:
    """gRPC client for EHR service"""

    def __init__(self, host: str = 'localhost', port: int = 50051):
        """Initialize gRPC client with server address"""
        self.address = f'{host}:{port}'
        self.channel = None
        self.stub = None

    async def __aenter__(self):
        """Async context manager entry"""
        self.channel = grpc.aio.insecure_channel(self.address)
        self.stub = ehr_service_pb2_grpc.EhrServiceStub(self.channel)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.channel:
            await self.channel.close()

    async def create_patient(self, patient_data: dict) -> dict:
        """Create a new patient via gRPC"""
        # Convert dict to protobuf Struct
        patient_struct = dict_to_struct(patient_data)

        request = ehr_service_pb2.CreatePatientRequest(
            patientData=patient_struct
        )

        response = await self.stub.CreatePatient(request)
        return self._patient_proto_to_dict(response.patient)

    async def get_patient(self, patient_uuid: str) -> dict:
        """Get a patient by UUID via gRPC"""
        request = ehr_service_pb2.GetPatientRequest(patient_uuid=patient_uuid)
        response = await self.stub.GetPatient(request)
        return self._patient_proto_to_dict(response.patient)

    async def get_all_patients(self, skip: int = 0, limit: int = 100) -> list:
        """Get all patients with pagination via gRPC"""
        request = ehr_service_pb2.GetAllPatientsRequest(skip=skip, limit=limit)
        response = await self.stub.GetAllPatients(request)
        return [self._patient_proto_to_dict(p) for p in response.patients]

    async def search_patient_by_id(self, patient_id: str) -> dict:
        """Search for a patient by patient_id via gRPC"""
        request = ehr_service_pb2.SearchPatientByIdRequest(patient_id=patient_id)
        response = await self.stub.SearchPatientById(request)
        return self._patient_proto_to_dict(response.patient)

    async def update_patient(self, patient_uuid: str, patient_data: dict) -> dict:
        """Update a patient via gRPC"""
        # Convert dict to protobuf Struct
        update_struct = dict_to_struct(patient_data)

        request = ehr_service_pb2.UpdatePatientRequest(
            patient_uuid=patient_uuid,
            updateData=update_struct
        )

        response = await self.stub.UpdatePatient(request)
        return self._patient_proto_to_dict(response.patient)

    async def delete_patient(self, patient_uuid: str) -> dict:
        """Delete a patient via gRPC"""
        request = ehr_service_pb2.DeletePatientRequest(patient_uuid=patient_uuid)
        response = await self.stub.DeletePatient(request)
        return {
            'success': response.success,
            'message': response.message
        }

    def _patient_proto_to_dict(self, patient_proto) -> dict:
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

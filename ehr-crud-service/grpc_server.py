import asyncio
import grpc
from concurrent import futures
from uuid import UUID
from datetime import date, datetime
import os
from dotenv import load_dotenv
from google.protobuf.struct_pb2 import Struct, ListValue
from google.protobuf.json_format import MessageToDict

from proto import ehr_service_pb2_grpc, ehr_service_pb2
import crud_service
from database import Database
from models import PatientCreate, PatientUpdate

load_dotenv()

# gRPC server configuration
GRPC_HOST = os.getenv('GRPC_HOST', '0.0.0.0')
GRPC_PORT = int(os.getenv('GRPC_PORT', '50051'))

# Date field mappings
DATE_FIELDS = {'dob', 'onset'}  # Fields that should be parsed as date
DATETIME_FIELDS = {'recordedAt'}  # Fields that should be parsed as datetime


def parse_dates_recursive(obj):
    """
    Recursively parse ISO date/datetime strings in nested structures.
    Handles both dict and list structures.
    """
    if isinstance(obj, dict):
        return {
            key: _parse_date_field(key, value) if isinstance(value, str)
            else parse_dates_recursive(value)
            for key, value in obj.items()
        }
    elif isinstance(obj, list):
        return [parse_dates_recursive(item) for item in obj]
    return obj


def _parse_date_field(key: str, value: str):
    """Parse a single date/datetime field based on its key."""
    try:
        if key in DATE_FIELDS:
            return date.fromisoformat(value)
        elif key in DATETIME_FIELDS:
            return datetime.fromisoformat(value)
    except (ValueError, AttributeError):
        pass  # Return original value if parsing fails
    return value


def dict_to_struct(data: dict) -> Struct:
    """Convert Python dict to protobuf Struct."""
    struct = Struct()
    struct.update(data)
    return struct


def list_to_listvalue(data: list) -> ListValue:
    """Convert Python list to protobuf ListValue."""
    list_value = ListValue()
    for item in data:
        if isinstance(item, dict):
            struct = Struct()
            struct.update(item)
            list_value.values.add().struct_value.CopyFrom(struct)
        else:
            list_value.values.add().string_value = str(item)
    return list_value


def patient_to_proto(patient) -> ehr_service_pb2.PatientMessage:
    """Convert Patient model to protobuf PatientMessage."""
    patient_dict = patient.model_dump(mode='json')

    return ehr_service_pb2.PatientMessage(
        id=str(patient.id),
        version=patient.version,
        lastUpdated=patient.lastUpdated.isoformat(),
        identity=dict_to_struct(patient_dict.get('identity', {})),
        demographics=dict_to_struct(patient_dict.get('demographics', {})),
        contacts=dict_to_struct(patient_dict.get('contacts', {})) if patient_dict.get('contacts') else Struct(),
        conditions=list_to_listvalue(patient_dict.get('conditions', [])),
        meta=dict_to_struct(patient_dict.get('meta', {})),
        created_at=patient.created_at.isoformat(),
        updated_at=patient.updated_at.isoformat(),
    )
class EhrServiceServicer(ehr_service_pb2_grpc.EhrServiceServicer):
    """gRPC service implementation for EHR operations."""

    def _set_error(self, context, code: grpc.StatusCode, message: str):
        """Helper to set error code and details."""
        context.set_code(code)
        context.set_details(message)

    def _parse_uuid(self, uuid_string: str, context) -> UUID | None:
        """Parse UUID string and set error if invalid."""
        try:
            return UUID(uuid_string)
        except ValueError:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, 'Invalid UUID format')
            return None

    async def CreatePatient(self, request, context):
        """Create a new patient record."""
        try:
            patient_data = parse_dates_recursive(MessageToDict(request.patientData))
            patient_create = PatientCreate(**patient_data)
            new_patient = await crud_service.create_patient(patient_create)

            return ehr_service_pb2.PatientResponse(patient=patient_to_proto(new_patient))

        except ValueError as e:
            self._set_error(context, grpc.StatusCode.ALREADY_EXISTS, str(e))
            return ehr_service_pb2.PatientResponse()
        except Exception as e:
            self._set_error(context, grpc.StatusCode.INTERNAL, f'Error creating patient: {str(e)}')
            return ehr_service_pb2.PatientResponse()

    async def GetPatient(self, request, context):
        """Get a patient by UUID."""
        try:
            patient_uuid = self._parse_uuid(request.patient_uuid, context)
            if not patient_uuid:
                return ehr_service_pb2.PatientResponse()

            patient = await crud_service.get_patient(patient_uuid)
            if not patient:
                self._set_error(context, grpc.StatusCode.NOT_FOUND,
                              f'Patient with UUID {patient_uuid} not found')
                return ehr_service_pb2.PatientResponse()

            return ehr_service_pb2.PatientResponse(patient=patient_to_proto(patient))

        except Exception as e:
            self._set_error(context, grpc.StatusCode.INTERNAL, f'Error retrieving patient: {str(e)}')
            return ehr_service_pb2.PatientResponse()

    async def GetAllPatients(self, request, context):
        """Get all patients with pagination."""
        try:
            skip = max(0, request.skip)
            limit = max(1, min(request.limit, 1000)) if request.limit > 0 else 100

            patients = await crud_service.get_all_patients(skip=skip, limit=limit)
            patient_messages = [patient_to_proto(p) for p in patients]

            return ehr_service_pb2.GetAllPatientsResponse(patients=patient_messages)

        except Exception as e:
            self._set_error(context, grpc.StatusCode.INTERNAL, f'Error retrieving patients: {str(e)}')
            return ehr_service_pb2.GetAllPatientsResponse()

    async def SearchPatientById(self, request, context):
        """Search for a patient by patient_id."""
        try:
            patient = await crud_service.get_patient_by_patient_id(request.patient_id)
            if not patient:
                self._set_error(context, grpc.StatusCode.NOT_FOUND,
                              f'Patient with patient_id {request.patient_id} not found')
                return ehr_service_pb2.PatientResponse()

            return ehr_service_pb2.PatientResponse(patient=patient_to_proto(patient))

        except Exception as e:
            self._set_error(context, grpc.StatusCode.INTERNAL, f'Error searching patient: {str(e)}')
            return ehr_service_pb2.PatientResponse()

    async def UpdatePatient(self, request, context):
        """Update a patient record."""
        try:
            patient_uuid = self._parse_uuid(request.patient_uuid, context)
            if not patient_uuid:
                return ehr_service_pb2.PatientResponse()

            update_data = parse_dates_recursive(MessageToDict(request.updateData))
            patient_update = PatientUpdate(**update_data)
            updated_patient = await crud_service.update_patient(patient_uuid, patient_update)

            if not updated_patient:
                self._set_error(context, grpc.StatusCode.NOT_FOUND,
                              f'Patient with UUID {patient_uuid} not found')
                return ehr_service_pb2.PatientResponse()

            return ehr_service_pb2.PatientResponse(patient=patient_to_proto(updated_patient))

        except Exception as e:
            self._set_error(context, grpc.StatusCode.INTERNAL, f'Error updating patient: {str(e)}')
            return ehr_service_pb2.PatientResponse()

    async def DeletePatient(self, request, context):
        """Delete a patient record."""
        try:
            patient_uuid = self._parse_uuid(request.patient_uuid, context)
            if not patient_uuid:
                return ehr_service_pb2.DeletePatientResponse(
                    success=False,
                    message='Invalid UUID format'
                )

            deleted = await crud_service.delete_patient(patient_uuid)
            if not deleted:
                # Set NOT_FOUND status code for missing patient
                self._set_error(context, grpc.StatusCode.NOT_FOUND,
                              f'Patient with UUID {patient_uuid} not found')
                return ehr_service_pb2.DeletePatientResponse(
                    success=False,
                    message=f'Patient with UUID {patient_uuid} not found'
                )

            return ehr_service_pb2.DeletePatientResponse(
                success=True,
                message='Patient deleted successfully'
            )

        except Exception as e:
            self._set_error(context, grpc.StatusCode.INTERNAL, f'Error deleting patient: {str(e)}')
            return ehr_service_pb2.DeletePatientResponse(
                success=False,
                message=f'Error deleting patient: {str(e)}'
            )
async def serve():
    """Start the gRPC server."""
    print("=" * 50)
    print("EHR CRUD Service - gRPC Server")
    print("=" * 50)

    # Initialize database
    await Database.initialize()
    print(f"✓ Database initialized")

    # Create and configure gRPC server
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    ehr_service_pb2_grpc.add_EhrServiceServicer_to_server(EhrServiceServicer(), server)

    listen_addr = f'{GRPC_HOST}:{GRPC_PORT}'
    server.add_insecure_port(listen_addr)

    print(f"✓ gRPC server listening on {listen_addr}")
    await server.start()
    print(f"✓ Server started successfully")
    print("=" * 50)

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
    finally:
        await server.stop(grace=5)
        await Database.close_connection()
        print("✓ Database connection closed")
        print("✓ Server stopped")


if __name__ == '__main__':
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        print("\nServer terminated by user")

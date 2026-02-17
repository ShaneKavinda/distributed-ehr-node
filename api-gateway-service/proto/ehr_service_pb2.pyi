from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PatientMessage(_message.Message):
    __slots__ = ("id", "version", "lastUpdated", "identity", "demographics", "contacts", "conditions", "meta", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    LASTUPDATED_FIELD_NUMBER: _ClassVar[int]
    IDENTITY_FIELD_NUMBER: _ClassVar[int]
    DEMOGRAPHICS_FIELD_NUMBER: _ClassVar[int]
    CONTACTS_FIELD_NUMBER: _ClassVar[int]
    CONDITIONS_FIELD_NUMBER: _ClassVar[int]
    META_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    version: int
    lastUpdated: str
    identity: _struct_pb2.Struct
    demographics: _struct_pb2.Struct
    contacts: _struct_pb2.Struct
    conditions: _struct_pb2.ListValue
    meta: _struct_pb2.Struct
    created_at: str
    updated_at: str
    def __init__(self, id: _Optional[str] = ..., version: _Optional[int] = ..., lastUpdated: _Optional[str] = ..., identity: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., demographics: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., contacts: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., conditions: _Optional[_Union[_struct_pb2.ListValue, _Mapping]] = ..., meta: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., created_at: _Optional[str] = ..., updated_at: _Optional[str] = ...) -> None: ...

class CreatePatientRequest(_message.Message):
    __slots__ = ("patientData",)
    PATIENTDATA_FIELD_NUMBER: _ClassVar[int]
    patientData: _struct_pb2.Struct
    def __init__(self, patientData: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class GetPatientRequest(_message.Message):
    __slots__ = ("patient_uuid",)
    PATIENT_UUID_FIELD_NUMBER: _ClassVar[int]
    patient_uuid: str
    def __init__(self, patient_uuid: _Optional[str] = ...) -> None: ...

class GetAllPatientsRequest(_message.Message):
    __slots__ = ("skip", "limit")
    SKIP_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    skip: int
    limit: int
    def __init__(self, skip: _Optional[int] = ..., limit: _Optional[int] = ...) -> None: ...

class SearchPatientByIdRequest(_message.Message):
    __slots__ = ("patient_id",)
    PATIENT_ID_FIELD_NUMBER: _ClassVar[int]
    patient_id: str
    def __init__(self, patient_id: _Optional[str] = ...) -> None: ...

class UpdatePatientRequest(_message.Message):
    __slots__ = ("patient_uuid", "updateData")
    PATIENT_UUID_FIELD_NUMBER: _ClassVar[int]
    UPDATEDATA_FIELD_NUMBER: _ClassVar[int]
    patient_uuid: str
    updateData: _struct_pb2.Struct
    def __init__(self, patient_uuid: _Optional[str] = ..., updateData: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class DeletePatientRequest(_message.Message):
    __slots__ = ("patient_uuid",)
    PATIENT_UUID_FIELD_NUMBER: _ClassVar[int]
    patient_uuid: str
    def __init__(self, patient_uuid: _Optional[str] = ...) -> None: ...

class PatientResponse(_message.Message):
    __slots__ = ("patient",)
    PATIENT_FIELD_NUMBER: _ClassVar[int]
    patient: PatientMessage
    def __init__(self, patient: _Optional[_Union[PatientMessage, _Mapping]] = ...) -> None: ...

class GetAllPatientsResponse(_message.Message):
    __slots__ = ("patients",)
    PATIENTS_FIELD_NUMBER: _ClassVar[int]
    patients: _containers.RepeatedCompositeFieldContainer[PatientMessage]
    def __init__(self, patients: _Optional[_Iterable[_Union[PatientMessage, _Mapping]]] = ...) -> None: ...

class DeletePatientResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

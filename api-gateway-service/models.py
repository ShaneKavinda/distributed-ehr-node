from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime


# Nested models matching ehr-crud-service
class IdentityInfo(BaseModel):
    """Patient identity information"""
    patientId: str = Field(..., description="Unique patient identifier")
    mrn: Optional[str] = Field(None, description="Medical Record Number")
    nationalId: Optional[str] = Field(None, description="National ID (hashed)")


class NameInfo(BaseModel):
    """Patient name structure"""
    given: str = Field(..., description="Given name")
    family: str = Field(..., description="Family name")


class Demographics(BaseModel):
    """Patient demographics"""
    name: NameInfo
    dob: date = Field(..., description="Date of birth")
    sexAtBirth: Optional[str] = Field(None, description="Sex at birth")
    genderIdentity: Optional[str] = Field(None, description="Gender identity")
    deceased: bool = Field(default=False)


class ContactInfo(BaseModel):
    """Patient contact information"""
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class Condition(BaseModel):
    """Patient condition/diagnosis"""
    code: Optional[str] = None
    system: Optional[str] = None
    description: str
    onset: Optional[date] = None
    status: str = "active"
    recordedAt: datetime
    encounterId: Optional[str] = None



class MetaInfo(BaseModel):
    """Metadata for distributed system"""
    sourceHospital: str
    replicaVector: Dict[str, Any] = Field(default_factory=dict)


# Request/Response models
class PatientCreate(BaseModel):
    """Model for creating a new patient"""
    identity: IdentityInfo
    demographics: Demographics
    contacts: Optional[ContactInfo] = None
    sourceHospital: str = Field(..., description="Name of the hospital node")

    class Config:
        json_schema_extra = {
            "example": {
                "identity": {
                    "patientId": "P-2026-001",
                    "mrn": "HOSP-A-123456"
                },
                "demographics": {
                    "name": {
                        "given": "Jane",
                        "family": "Doe"
                    },
                    "dob": "1984-03-12",
                    "sexAtBirth": "female",
                    "genderIdentity": "female",
                    "deceased": False
                },
                "contacts": {
                    "address": "Helsinki, FI",
                    "phone": "+358...",
                    "email": "jane.doe@example.com"
                },
                "sourceHospital": "HOSP-A"
            }
        }


class PatientUpdate(BaseModel):
    """Model for updating patient - all fields optional"""
    demographics: Optional[Demographics] = None
    contacts: Optional[ContactInfo] = None
    conditions: Optional[List[Condition]] = None


class PatientResponse(BaseModel):
    """Model for patient response"""
    id: str
    version: int
    lastUpdated: datetime
    identity: IdentityInfo
    demographics: Demographics
    contacts: Optional[ContactInfo] = None
    conditions: List[Condition] = Field(default_factory=list)
    meta: MetaInfo
    created_at: datetime
    updated_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "version": 1,
                "lastUpdated": "2026-01-25T10:42:31Z",
                "identity": {
                    "patientId": "P-2026-001",
                    "mrn": "HOSP-A-123456"
                },
                "demographics": {
                    "name": {
                        "given": "Jane",
                        "family": "Doe"
                    },
                    "dob": "1984-03-12",
                    "sexAtBirth": "female",
                    "genderIdentity": "female",
                    "deceased": False
                },
                "contacts": {
                    "address": "Helsinki, FI",
                    "phone": "+358..."
                },
                "conditions": [],
                "meta": {
                    "sourceHospital": "HOSP-A",
                    "replicaVector": {}
                },
                "created_at": "2026-01-25T10:42:31Z",
                "updated_at": "2026-01-25T10:42:31Z"
            }
        }


class DeleteResponse(BaseModel):
    """Response model for delete operations"""
    success: bool
    message: str


class ErrorResponse(BaseModel):
    """Error response model"""
    detail: str

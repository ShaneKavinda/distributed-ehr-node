from grpc_client import GrpcClient
from models import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    DeleteResponse,
    ErrorResponse
)
from fastapi import FastAPI, HTTPException, status, Depends, Query
from typing import List
import grpc.aio
from dotenv import load_dotenv
import os
from auth.auth import (
    get_current_user,
    require_doctor,
    require_doctor_or_patient
)
from auth.routes import router as auth_router

load_dotenv()


# Initialize FastAPI app
app = FastAPI(
    title="EHR API Gateway",
    description="REST API Gateway for Distributed EHR System using gRPC",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.include_router(auth_router)

# Configuration from environment variables
GRPC_HOST = os.getenv('GRPC_HOST', 'localhost')
GRPC_PORT = int(os.getenv('GRPC_PORT', '50051'))
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', '8080'))


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API health check"""
    return {
        "message": "EHR API Gateway is running",
        "version": "1.0.0",
        "grpc_server": f"{GRPC_HOST}:{GRPC_PORT}"
    }


@app.post(
    "/patients",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Patients"],
    summary="Create a new patient",
    responses={
        201: {"description": "Patient created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid input"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def create_patient(patient: PatientCreate, user=Depends(require_doctor)):
    """
    Create a new patient record.

    - **patientId**: Unique patient identifier (e.g., P-2026-001)
    - **identity**: Patient identity information (patientId, mrn, nationalId)
    - **demographics**: Name, date of birth, sex, gender, deceased status
    - **contacts**: Address, phone, email
    - **sourceHospital**: Name of the hospital node creating the record
    """

    try:
        async with GrpcClient(GRPC_HOST, GRPC_PORT) as client:
            patient_data = patient.model_dump()
            result = await client.create_patient(patient_data)
            return PatientResponse(**result)
    except grpc.aio.AioRpcError as e:
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(status_code=400, detail=e.details())
        elif e.code() == grpc.StatusCode.ALREADY_EXISTS:
            raise HTTPException(status_code=409, detail=e.details())
        else:
            raise HTTPException(
                status_code=500, detail=f"gRPC error: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/patients/{patient_uuid}",
    response_model=PatientResponse,
    tags=["Patients"],
    summary="Get patient by UUID",
    responses={
        200: {"description": "Patient found"},
        404: {"model": ErrorResponse, "description": "Patient not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_patient(patient_uuid: str, user=Depends(require_doctor_or_patient)):
    """
    Retrieve a patient by their UUID.

    - **patient_uuid**: The unique UUID of the patient
    """
    if user["role"] == "patient" and user["patient_uuid"] != patient_uuid:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        async with GrpcClient(GRPC_HOST, GRPC_PORT) as client:
            result = await client.get_patient(patient_uuid)
            return PatientResponse(**result)
    except grpc.aio.AioRpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail=e.details())
        elif e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(status_code=400, detail=e.details())
        else:
            raise HTTPException(
                status_code=500, detail=f"gRPC error: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/patients",
    response_model=List[PatientResponse],
    tags=["Patients"],
    summary="Get all patients",
    responses={
        200: {"description": "List of patients"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_all_patients(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000,
                       description="Maximum number of records to return"),
    user=Depends(require_doctor)
):
    """
    Retrieve all patients with pagination.

    - **skip**: Number of records to skip (default: 0)
    - **limit**: Maximum number of records to return (default: 100, max: 1000)
    """
    try:
        async with GrpcClient(GRPC_HOST, GRPC_PORT) as client:
            results = await client.get_all_patients(skip=skip, limit=limit)
            return [PatientResponse(**r) for r in results]
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC error: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/patients/search/{patient_id}",
    response_model=PatientResponse,
    tags=["Patients"],
    summary="Search patient by patient ID",
    responses={
        200: {"description": "Patient found"},
        404: {"model": ErrorResponse, "description": "Patient not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def search_patient_by_id(patient_id: str, user=Depends(require_doctor)):
    """
    Search for a patient by their patient_id.

    - **patient_id**: The patient identifier (e.g., P001)
    """
    try:
        async with GrpcClient(GRPC_HOST, GRPC_PORT) as client:
            result = await client.search_patient_by_id(patient_id)
            return PatientResponse(**result)
    except grpc.aio.AioRpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail=e.details())
        else:
            raise HTTPException(
                status_code=500, detail=f"gRPC error: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put(
    "/patients/{patient_uuid}",
    response_model=PatientResponse,
    tags=["Patients"],
    summary="Update patient",
    responses={
        200: {"description": "Patient updated successfully"},
        404: {"model": ErrorResponse, "description": "Patient not found"},
        400: {"model": ErrorResponse, "description": "Invalid input"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def update_patient(patient_uuid: str, patient: PatientUpdate, user=Depends(require_doctor)):
    """
    Update a patient's information.

    - **patient_uuid**: The unique UUID of the patient
    - All fields are optional - only provided fields will be updated
    """
    try:
        async with GrpcClient(GRPC_HOST, GRPC_PORT) as client:
            # Only include fields that are not None
            patient_data = patient.model_dump(exclude_none=True)
            if not patient_data:
                raise HTTPException(
                    status_code=400, detail="No fields to update")

            result = await client.update_patient(patient_uuid, patient_data)
            return PatientResponse(**result)
    except grpc.aio.AioRpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail=e.details())
        elif e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(status_code=400, detail=e.details())
        else:
            raise HTTPException(
                status_code=500, detail=f"gRPC error: {e.details()}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete(
    "/patients/{patient_uuid}",
    response_model=DeleteResponse,
    tags=["Patients"],
    summary="Delete patient",
    responses={
        200: {"description": "Patient deleted successfully"},
        404: {"model": ErrorResponse, "description": "Patient not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def delete_patient(patient_uuid: str, user=Depends(require_doctor)):
    """
    Delete a patient record.

    - **patient_uuid**: The unique UUID of the patient
    """
    try:
        async with GrpcClient(GRPC_HOST, GRPC_PORT) as client:
            result = await client.delete_patient(patient_uuid)
            return DeleteResponse(**result)
    except grpc.aio.AioRpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail=e.details())
        elif e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(status_code=400, detail=e.details())
        else:
            raise HTTPException(
                status_code=500, detail=f"gRPC error: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn

    print("=" * 60)
    print("EHR API Gateway - Starting Server")
    print("=" * 60)
    print(f"API Documentation: http://localhost:{API_PORT}/docs")
    print(f"Alternative Docs: http://localhost:{API_PORT}/redoc")
    print(f"gRPC Backend: {GRPC_HOST}:{GRPC_PORT}")
    print("=" * 60)

    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
        log_level="info"
    )

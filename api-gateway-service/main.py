import os
import asyncio
import grpc
import grpc.aio
from typing import List
from fastapi import FastAPI, HTTPException, Query, Depends, status
from grpc_client import GrpcClient
from models import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    DeleteResponse,
    ErrorResponse
)
from p2p_client import P2PCommandClient
from auth.auth import require_doctor, require_patient, require_doctor_or_patient
from auth.routes import router as auth_router

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
P2P_HOST = os.getenv('P2P_HOST', 'localhost')
P2P_PORT = int(os.getenv('P2P_PORT', '7001'))
P2P_TIMEOUT = float(os.getenv('P2P_TIMEOUT', '3.0'))


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
        patient_data = patient.model_dump()
        async with P2PCommandClient(P2P_HOST, P2P_PORT, P2P_TIMEOUT) as p2p:
            response = await p2p.submit_command("PATIENT_CREATE", patient_data)
            if not response.accepted:
                raise HTTPException(
                    status_code=503,
                    detail=f"Raft leader unavailable. leader_id={response.leader_id}"
                )
            if not response.committed:
                raise HTTPException(
                    status_code=503,
                    detail="Command accepted but not committed"
                )

        # Retry logic: Wait for the database to be updated after Raft commit
        # The Raft commit listener applies the change asynchronously
        max_retries = 5
        retry_delay = 0.1  # 100ms between retries

        for attempt in range(max_retries):
            try:
                async with GrpcClient(GRPC_HOST, GRPC_PORT) as client:
                    result = await client.search_patient_by_id(patient.identity.patientId)
                    return PatientResponse(**result)
            except grpc.aio.AioRpcError as e:
                if e.code() == grpc.StatusCode.NOT_FOUND and attempt < max_retries - 1:
                    # Patient not found yet, wait and retry
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    # Re-raise on last attempt or other errors
                    raise

    except grpc.aio.AioRpcError as e:
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(status_code=400, detail=e.details())
        elif e.code() == grpc.StatusCode.ALREADY_EXISTS:
            raise HTTPException(status_code=409, detail=e.details())
        elif e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(
                status_code=500,
                detail=f"Patient creation confirmed by Raft but not found in database. This might indicate a replication delay. Patient ID: {patient.identity.patientId}"
            )
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
        # Only include fields that are not None
        patient_data = patient.model_dump(exclude_none=True)
        if not patient_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        async with P2PCommandClient(P2P_HOST, P2P_PORT, P2P_TIMEOUT) as p2p:
            response = await p2p.submit_command(
                "PATIENT_UPDATE",
                {"patient_uuid": patient_uuid, "update": patient_data},
            )
            if not response.accepted:
                raise HTTPException(
                    status_code=503,
                    detail=f"Raft leader unavailable. leader_id={response.leader_id}"
                )
            if not response.committed:
                raise HTTPException(
                    status_code=503,
                    detail="Command accepted but not committed"
                )

        # Retry logic: Wait for the database to be updated after Raft commit
        max_retries = 5
        retry_delay = 0.1  # 100ms between retries

        for attempt in range(max_retries):
            try:
                async with GrpcClient(GRPC_HOST, GRPC_PORT) as client:
                    result = await client.get_patient(patient_uuid)
                    return PatientResponse(**result)
            except grpc.aio.AioRpcError as e:
                if e.code() == grpc.StatusCode.NOT_FOUND and attempt < max_retries - 1:
                    # Patient not found yet (shouldn't happen for update, but just in case)
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    # Re-raise on last attempt or other errors
                    raise

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
        async with P2PCommandClient(P2P_HOST, P2P_PORT, P2P_TIMEOUT) as p2p:
            response = await p2p.submit_command(
                "PATIENT_DELETE",
                {"patient_uuid": patient_uuid},
            )
            if not response.accepted:
                raise HTTPException(
                    status_code=503,
                    detail=f"Raft leader unavailable. leader_id={response.leader_id}"
                )
            if not response.committed:
                raise HTTPException(
                    status_code=503,
                    detail="Command accepted but not committed"
                )
        return DeleteResponse(success=True, message="Patient deleted successfully")
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

from fastapi import FastAPI, HTTPException, status, Query
from fastapi.responses import JSONResponse
from typing import List
import grpc.aio
from dotenv import load_dotenv
import os

load_dotenv()  # This loads the .env file

from models import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    DeleteResponse,
    ErrorResponse
)
from grpc_client import GrpcClient
from p2p_client import P2PCommandClient

# Initialize FastAPI app
app = FastAPI(
    title="EHR API Gateway",
    description="REST API Gateway for Distributed EHR System using gRPC",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# gRPC server configuration from environment variables
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
async def create_patient(patient: PatientCreate):
    """
    Create a new patient record.

    - **patient_id**: Unique patient identifier
    - **name**: Patient's full name
    - **birth_date**: Date of birth (YYYY-MM-DD)
    - **height**: Height in centimeters
    - **weight**: Weight in kilograms
    - **blood_type**: Blood type (A+, A-, B+, B-, AB+, AB-, O+, O-)
    - **diagnosis**: Medical diagnosis
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
        async with GrpcClient(GRPC_HOST, GRPC_PORT) as client:
            result = await client.search_patient_by_id(patient.identity.patientId)
            return PatientResponse(**result)
    except grpc.aio.AioRpcError as e:
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(status_code=400, detail=e.details())
        elif e.code() == grpc.StatusCode.ALREADY_EXISTS:
            raise HTTPException(status_code=409, detail=e.details())
        else:
            raise HTTPException(status_code=500, detail=f"gRPC error: {e.details()}")
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
async def get_patient(patient_uuid: str):
    """
    Retrieve a patient by their UUID.

    - **patient_uuid**: The unique UUID of the patient
    """
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
            raise HTTPException(status_code=500, detail=f"gRPC error: {e.details()}")
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
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return")
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
        raise HTTPException(status_code=500, detail=f"gRPC error: {e.details()}")
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
async def search_patient_by_id(patient_id: str):
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
            raise HTTPException(status_code=500, detail=f"gRPC error: {e.details()}")
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
async def update_patient(patient_uuid: str, patient: PatientUpdate):
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

        async with GrpcClient(GRPC_HOST, GRPC_PORT) as client:
            result = await client.get_patient(patient_uuid)
            return PatientResponse(**result)
    except grpc.aio.AioRpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail=e.details())
        elif e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(status_code=400, detail=e.details())
        else:
            raise HTTPException(status_code=500, detail=f"gRPC error: {e.details()}")
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
async def delete_patient(patient_uuid: str):
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
            raise HTTPException(status_code=500, detail=f"gRPC error: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Error handler for general exceptions
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle uncaught exceptions"""
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )


if __name__ == '__main__':
    import uvicorn

    #TODO: ACTUALLY THIS SERVICE WILL SEND REQUESTS TO A MQ.
    # THIS IS PHASE 1 IMPLEMENTATION DIRECTLY TO GRPC SERVER

    print("=" * 60)
    print("EHR API Gateway - Starting Server")
    print("=" * 60)
    print(f"API Documentation: http://localhost:8080/docs")
    print(f"Alternative Docs: http://localhost:{API_PORT}/redoc")
    print(f"gRPC Backend: {GRPC_HOST}:{GRPC_PORT}")
    print("=" * 60)
    print("")

    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
        log_level="info"
    )


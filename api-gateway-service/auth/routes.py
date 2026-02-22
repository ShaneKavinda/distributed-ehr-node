from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from jose import jwt
import os

router = APIRouter(prefix="/auth", tags=["Auth"])

SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret")
ALGORITHM = "HS256"

# /register endpoint flow:
# # register new patient
'''
forward the request to /register,
send a request to the EHR service (check permission; only doctors can create new patients),
use the UUID from the EHR service to register the new patient in the auth-service set user-status = "PENDING",
navigate to /set-password endpoint, set user-status = "REGISTERED",
Navigate to /login and allow the new user to access the system and their own records in EHR-service,
'''


@router.post("/login")
def login(username: str, password: str):
    # 1. Validate credentials (DB later)
    if username == "doctor1":
        role = "doctor"
        doctor_id = "some-doctor-uuid"
    elif username == "patient1":
        role = "patient"
        patient_id = "some-patient-uuid"
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 2. Issue JWT
    if (role == 'doctor'):
        payload = {
            "doctor_id": doctor_id,
            "role": role,
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
    elif (role == 'patient'):
        payload = {
            "patient_id": patient_id,
            "role": role,
            "exp": datetime.utcnow() + timedelta(hours=1),
        }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": token,
        "role": role,
        "token_type": "bearer",
    }

from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from jose import jwt
import os

router = APIRouter(prefix="/auth", tags=["Auth"])

SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret")
ALGORITHM = "HS256"


@router.post("/login")
def login(username: str, password: str):
    # 1. Validate credentials (DB later)
    if username == "doctor1":
        role = "doctor"
        patient_uuid = None
    elif username == "patient1":
        role = "patient"
        patient_uuid = "some-patient-uuid"
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 2. Issue JWT
    payload = {
        "sub": username,
        "role": role,
        "patient_uuid": patient_uuid,
        "exp": datetime.utcnow() + timedelta(hours=1),
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": token,
        "token_type": "bearer",
    }

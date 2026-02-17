# Distributed EHR Node - System Information

> **Version:** 2.0 - Simplified for Demo  
> **Last Updated:** February 2, 2026

---

## 🎯 Overview

A distributed Electronic Health Record (EHR) system demonstrating microservices architecture with:
- **REST API Gateway** (FastAPI) - External client interface on port 8080
- **gRPC Backend Service** - Business logic and CRUD operations on port 50051
- **MongoDB** - Document database for flexible patient records on port 27017

---

## 🏗️ Architecture

```
Client (Browser/Postman)
    ↓ HTTP/REST (port 8080)
API Gateway (FastAPI)
    ↓ gRPC (port 50051)
CRUD Service (gRPC Server)
    ↓ MongoDB Driver
MongoDB (port 27017)

RabbitMQ (ports 5672, 15672)
    ↕ Message Queue (future inter-service communication)
```

---

## 📦 Services

### API Gateway (`api-gateway-service/`)
- **Technology:** FastAPI, Python 3.9+
- **Port:** 8080
- **Purpose:** REST API for external clients
- **Key Files:**
  - `main.py` - 7 REST endpoints
  - `models.py` - Pydantic validation models
  - `grpc_client.py` - gRPC client

### CRUD Service (`ehr-crud-service/`)
- **Technology:** gRPC, Beanie ODM, Python 3.9+
- **Port:** 50051
- **Purpose:** Business logic and database operations
- **Key Files:**
  - `grpc_server.py` - gRPC server
  - `crud_service.py` - CRUD operations
  - `database.py` - MongoDB connection
  - `models.py` - Database models

### RabbitMQ
- **Technology:** RabbitMQ 3.13 with Management Plugin
- **Ports:** 5672 (AMQP), 15672 (Management UI)
- **Purpose:** Message broker for inter-service communication
- **Access:** http://localhost:15672 (user: `admin`, password: `admin123`)

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| POST | `/patients` | Create patient |
| GET | `/patients/{uuid}` | Get patient by UUID |
| GET | `/patients` | Get all patients (paginated) |
| GET | `/patients/search/{patient_id}` | Search by patientId |
| PUT | `/patients/{uuid}` | Update patient |
| DELETE | `/patients/{uuid}` | Delete patient |

**Access API Docs:** http://localhost:8080/docs

---

## 💾 Data Model

**Simplified patient record with:**
- ✅ Identity (patientId, MRN, nationalId)
- ✅ Demographics (name, DOB, gender)
- ✅ Contacts (address, phone, email)
- ✅ Conditions (diagnoses)
- ✅ Metadata (sourceHospital, version)

**Removed for simplicity:**
- ❌ Encounters
- ❌ Medications
- ❌ Consents
- ❌ Allergies

---

## 🐳 Running with Docker Compose

### Quick Start (Recommended)

```bash
# Start all services (MongoDB, RabbitMQ, gRPC, API Gateway)
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f

# Stop all services
docker compose down
```

**Access Points:**
- API Docs: http://localhost:8080/docs
- RabbitMQ Management UI: http://localhost:15672 (admin/admin123)

### What Docker Compose Does

1. Starts **MongoDB** container (port 27017)
2. Starts **RabbitMQ** container (ports 5672, 15672)
3. Starts **EHR CRUD Service** (port 50051)
4. Starts **API Gateway** (port 8080)
5. Creates isolated Docker network
6. Sets up health checks
7. Configures automatic restarts

### Useful Commands

```bash
# Rebuild and restart
docker compose up -d --build

# View specific service logs
docker compose logs -f api-gateway-service

# Stop and remove volumes (⚠️ deletes data)
docker compose down -v

# Access container shell
docker compose exec api-gateway-service /bin/bash
```

---

## 🔧 Configuration

Each service has its own `.env` file:

**`ehr-crud-service/.env`:**
```bash
MONGODB_URL=mongodb://mongodb:27017
GRPC_HOST=0.0.0.0
GRPC_PORT=50051
```

**`api-gateway-service/.env`:**
```bash
GRPC_HOST=ehr-crud-service
API_HOST=0.0.0.0
API_PORT=8080
```

---

## 🚀 Running Locally (Without Docker)

### Prerequisites
- Python 3.9+
- MongoDB running on localhost:27017

### Steps

**1. Start MongoDB**
```bash
mongod
```

**2. Start CRUD Service**
```bash
cd ehr-crud-service
python grpc_server.py
# Server starts on port 50051
```

**3. Start API Gateway** (in new terminal)
```bash
cd api-gateway-service
python main.py
# Server starts on port 8080
```

**4. Access API**
```
http://localhost:8080/docs
```

**Note:** Update `.env` files to use `localhost` instead of Docker service names.

---

## 📝 Protocol Buffers (pb2 files)

### What are they?

- **`ehr_service_pb2.py`** - Message classes (data structures)
- **`ehr_service_pb2_grpc.py`** - Service stubs (RPC methods)
- **`ehr_service_pb2.pyi`** - Type hints (IDE support)

### How to regenerate?

```bash
cd ehr-crud-service/proto
python -m grpc_tools.protoc -I. --python_out=. --pyi_out=. --grpc_python_out=. ehr_service.proto

cd api-gateway-service/proto
python -m grpc_tools.protoc -I. --python_out=. --pyi_out=. --grpc_python_out=. ehr_service.proto
```

**⚠️ Don't edit generated files manually!**

---

## 🧪 Testing

### Using Swagger UI (Easiest)
1. Open http://localhost:8080/docs
2. Try endpoints interactively

### Using curl
```bash
# Create patient
curl -X POST "http://localhost:8080/patients" \
  -H "Content-Type: application/json" \
  -d '{
    "identity": {"patientId": "P-001", "mrn": "TEST-123"},
    "demographics": {
      "name": {"given": "John", "family": "Doe"},
      "dob": "1990-01-01",
      "deceased": false
    },
    "sourceHospital": "HOSP-A"
  }'

# Get all patients
curl http://localhost:8080/patients
```

---

## 🐛 Troubleshooting

### Docker Compose Issues

**Services won't start:**
```bash
docker compose logs service-name
docker compose down -v
docker compose up -d --build
```

**Port already in use:**
```bash
# Check ports
netstat -ano | findstr :8080
# Stop conflicting service or change port in docker-compose.yml
```

### Local Running Issues

**Can't connect to MongoDB:**
- Ensure MongoDB is running: `mongosh`
- Check connection string in `.env` file

**Can't connect to gRPC:**
- Ensure CRUD service is running on port 50051
- Check `GRPC_HOST` in API Gateway `.env` file

---

## 📚 Documentation Files

- **POSTMAN_ALL_ENDPOINTS.md** - Complete API examples
- **DOCKER_GUIDE.md** - Detailed Docker usage
- **PROTO_FILES_EXPLAINED.md** - Protocol Buffers deep dive

---

## ✨ Key Features

✅ **Microservices architecture** with REST and gRPC  
✅ **Docker Compose** for easy deployment  
✅ **Flexible JSON schema** in MongoDB  
✅ **7 REST endpoints** with auto-generated docs  
✅ **Duplicate patient validation**  
✅ **Health checks** for all services  
✅ **Data persistence** with Docker volumes  

---

## 🎯 Quick Reference

```bash
# Docker (Recommended)
docker compose up -d              # Start
docker compose logs -f            # View logs
docker compose down               # Stop

# Access
http://localhost:8080/docs        # API Documentation
http://localhost:8080             # Health check

# Local
python ehr-crud-service/grpc_server.py    # Start gRPC
python api-gateway-service/main.py        # Start API
```

---

**Ready to start? Run:** `docker compose up -d`
### How to Regenerate

When you modify `ehr_service.proto`, regenerate the Python files:

```bash
# In ehr-crud-service/proto directory:
python -m grpc_tools.protoc -I. --python_out=. --pyi_out=. --grpc_python_out=. ehr_service.proto

# In api-gateway-service/proto directory:
python -m grpc_tools.protoc -I. --python_out=. --pyi_out=. --grpc_python_out=. ehr_service.proto
```

**DO NOT EDIT** generated files manually! Always regenerate from the `.proto` file.

---

## 🚀 Running the System

### Prerequisites

1. **Python 3.9+** installed
2. **MongoDB** running on `localhost:27017`
3. **Dependencies** installed for both services

### Step-by-Step Startup

#### 1. Start MongoDB
```bash
mongod
# MongoDB will run on localhost:27017
```

#### 2. Start EHR CRUD Service (gRPC Server)
```bash
cd ehr-crud-service
python grpc_server.py
```

**Expected Output:**
```
EHR CRUD Service - gRPC Server
==================================================
Database initialized successfully
Starting gRPC server on localhost:50051
gRPC server started successfully
```

#### 3. Start API Gateway Service
```bash
cd api-gateway-service
python main.py
```

**Expected Output:**
```
============================================================
EHR API Gateway - Starting Server
============================================================
API Documentation: http://localhost:8080/docs
Alternative Docs: http://localhost:8080/redoc
gRPC Backend: localhost:50051
============================================================
```

#### 4. Access the API

- **Base URL:** `http://localhost:8080`
- **Swagger UI:** `http://localhost:8080/docs` (Interactive API testing)
- **ReDoc:** `http://localhost:8080/redoc` (Alternative documentation)

---

## 🧪 Testing the System

### Using Swagger UI (Recommended)

1. Open `http://localhost:8080/docs`
2. Click on any endpoint to expand
3. Click "Try it out"
4. Fill in the request body
5. Click "Execute"
6. See the response below

### Using Postman

See `POSTMAN_ALL_ENDPOINTS.md` for comprehensive examples for all 7 endpoints.

**Quick Test - Create Patient:**

**POST** `http://localhost:8080/patients`

```json
{
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
    "deceased": false
  },
  "sourceHospital": "HOSP-A"
}
```

### Using cURL

```bash
# Create a patient
curl -X POST "http://localhost:8080/patients" \
  -H "Content-Type: application/json" \
  -d '{
    "identity": {"patientId": "P-2026-001", "mrn": "HOSP-A-123456"},
    "demographics": {
      "name": {"given": "Jane", "family": "Doe"},
      "dob": "1984-03-12",
      "deceased": false
    },
    "sourceHospital": "HOSP-A"
  }'

# Get all patients
curl "http://localhost:8080/patients"

# Get patient by UUID
curl "http://localhost:8080/patients/{uuid}"

# Search by patientId
curl "http://localhost:8080/patients/search/P-2026-001"

# Update patient (add clinical data)
curl -X PUT "http://localhost:8080/patients/{uuid}" \
  -H "Content-Type: application/json" \
  -d '{
    "conditions": [{
      "id": "cond-001",
      "code": "E11",
      "system": "ICD-10",
      "description": "Type 2 diabetes mellitus",
      "onset": "2020-05-15",
      "status": "active",
      "recordedAt": "2026-02-02T10:00:00Z"
    }]
  }'

# Delete patient
curl -X DELETE "http://localhost:8080/patients/{uuid}"
```

---

## 🔧 Key Technical Features

### 1. Date Serialization/Deserialization

**Problem:** Python `date` objects can't be directly sent through protobuf Struct.

**Solution:**
- **API Gateway:** `serialize_dates()` converts dates to ISO strings before gRPC
- **CRUD Service:** `parse_dates_recursive()` converts ISO strings back to date objects

### 2. List to ListValue Conversion

**Problem:** Python lists of dicts (conditions, allergies) need special handling in protobuf.

**Solution:**
- **CRUD Service:** `list_to_listvalue()` converts Python lists to protobuf ListValue
- **API Gateway:** `MessageToDict()` converts ListValue back to Python lists

### 3. Duplicate Patient Check

**Business Rule:** Each `patientId` must be unique across the system.

**Implementation:**
```python
# In crud_service.py
existing_patient = await Patient.find_one(
    Patient.identity.patientId == patient.identity.patientId
)
if existing_patient:
    raise ValueError(f"Patient with patientId '{patient.identity.patientId}' already exists")
```

**Response:** HTTP 409 Conflict with error message

### 4. Flexible JSON Schema

**Why:** MongoDB's document model allows schema evolution without migrations.

**Benefits:**
- Add new fields without downtime
- Different nodes can have different schema versions
- Supports distributed system evolution

### 5. Protobuf with JSON Struct

**Approach:** Instead of defining every field in `.proto`, we use `google.protobuf.Struct` for flexible JSON.

**Benefits:**
- Easy to add new fields
- No need to recompile proto for minor changes
- Better for demo and rapid iteration

---

## 📊 System Benefits

### 1. Separation of Concerns
- **API Layer:** Handles HTTP, validation, documentation
- **Business Layer:** Implements CRUD logic, rules
- **Data Layer:** Manages MongoDB persistence

### 2. Technology Flexibility
- **External Clients:** Use REST/JSON (easy to integrate)
- **Internal Services:** Use gRPC/Protobuf (fast and efficient)

### 3. Scalability
- Scale API Gateway and CRUD Service independently
- Multiple API Gateway instances → Single CRUD Service
- Can add more CRUD Service nodes for distributed EHR

### 4. Maintainability
- Clear service boundaries
- Type-safe with Pydantic and Protobuf
- Auto-generated API documentation
- Well-structured codebase

### 5. Performance
- **Async/Await:** Non-blocking I/O throughout
- **gRPC:** Binary protocol (faster than REST internally)
- **MongoDB:** Document database optimized for JSON-like data
- **Beanie ODM:** Async MongoDB driver

---

## 🐛 Troubleshooting

### Issue: "Cannot connect to gRPC server"
**Solution:**
1. Check if gRPC server is running: `netstat -an | findstr :50051`
2. Verify MongoDB is running: `mongosh` or check Task Manager
3. Check firewall settings

### Issue: "Cannot find reference 'PatientMessage'"
**Cause:** Proto files not generated or imported correctly

**Solution:**
```bash
cd ehr-crud-service/proto
python -m grpc_tools.protoc -I. --python_out=. --pyi_out=. --grpc_python_out=. ehr_service.proto
```

### Issue: "Conditions and allergies returning empty arrays"
**Cause:** This was a bug that has been fixed.

**Solution:** Make sure you're using the latest version of `grpc_server.py` with `list_to_listvalue()` function.

### Issue: "Duplicate patient error"
**Expected Behavior:** This is a business rule validation.

**Response:** HTTP 409 Conflict - Patient with that `patientId` already exists. Use a different `patientId`.

### Issue: "Date format error"
**Solution:** Use ISO format: `YYYY-MM-DD` for dates, `YYYY-MM-DDTHH:MM:SSZ` for datetimes

---

## 📖 Additional Documentation

- **POSTMAN_ALL_ENDPOINTS.md** - Comprehensive Postman examples for all 7 endpoints
- **SIMPLIFIED_POSTMAN_EXAMPLES.md** - Quick examples with simplified model
- **PROTO_FILES_EXPLAINED.md** - Deep dive into pb2 vs pb2_grpc
- **MIGRATION_GUIDE.md** - Details on data model evolution
- **FIXED_CONDITIONS_ALLERGIES.md** - Technical details on ListValue fix
- **README.md** (in each service) - Service-specific documentation

---

## 🎯 Future Enhancements (Not Yet Implemented)

The following are planned for future versions but not included in this demo:

1. **P2P Service with Raft Consensus** - For distributed node coordination
2. **Authentication & Authorization** - JWT tokens, API keys
3. **Rate Limiting** - Prevent API abuse
4. **Caching Layer** - Redis for frequently accessed data
5. **Monitoring & Metrics** - Prometheus, Grafana
6. **Distributed Tracing** - OpenTelemetry
7. **Event Sourcing** - Track all changes to patient records
8. **Replication** - Multi-node data replication
9. **Docker Containers** - Containerized deployment
10. **CI/CD Pipeline** - Automated testing and deployment

---

## 📝 Summary

### What This System Does

✅ Provides REST API for patient CRUD operations  
✅ Stores patient data in flexible JSON format in MongoDB  
✅ Uses gRPC for efficient internal service communication  
✅ Validates duplicate patient IDs  
✅ Handles complex nested data (conditions, allergies)  
✅ Provides automatic API documentation  
✅ Designed for distributed system architecture  
✅ Simplified for demo purposes  

### Technology Stack

- **Languages:** Python 3.9+
- **API Framework:** FastAPI (async)
- **RPC Framework:** gRPC (async)
- **Database:** MongoDB
- **ODM:** Beanie (async)
- **Validation:** Pydantic
- **Serialization:** Protocol Buffers
- **Documentation:** Swagger UI, ReDoc

### Project Status

🟢 **Production-Ready for Demo**
- All CRUD endpoints working
- Data validation implemented
- Error handling complete
- Documentation comprehensive
- Ready for demonstration

---

**Last Updated:** February 2, 2026  
**Maintained By:** Distributed EHR Team  
**License:** Demo Project

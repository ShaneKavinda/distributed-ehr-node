# Distributed EHR System - Complete Knowledge Base

**A comprehensive guide to understanding, deploying, and testing the distributed Electronic Health Record (EHR) system with Raft consensus on Kubernetes.**

---

## 📚 Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Kubernetes Deployment](#2-kubernetes-deployment)
3. [MongoDB Access](#3-mongodb-access)
4. [Testing & Verification](#4-testing--verification)
5. [Operations & Troubleshooting](#5-operations--troubleshooting)
6. [Advanced Topics](#6-advanced-topics)

---

# 1. System Architecture

## 1.1 High-Level Overview

The system implements a **distributed EHR system** using **Raft consensus algorithm** for strong consistency across multiple nodes. Each hospital operates as an independent Kubernetes namespace with 3-node Raft cluster.

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                      Minikube Cluster                            │
├─────────────────────────────────────────────────────────────────┤
│  Namespace: hospital-h1                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ hospital-0   │  │ hospital-1   │  │ hospital-2   │         │
│  │ (Pod)        │  │ (Pod)        │  │ (Pod)        │         │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤         │
│  │ api-gateway  │  │ api-gateway  │  │ api-gateway  │         │
│  │   :8080      │  │   :8080      │  │   :8080      │         │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤         │
│  │ p2p-raft     │◄─┼─► p2p-raft   │◄─┼─► p2p-raft   │         │
│  │   :7001      │  │   :7001      │  │   :7001      │         │
│  │ [LEADER]     │  │ [FOLLOWER]   │  │ [FOLLOWER]   │         │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤         │
│  │ ehr-crud     │  │ ehr-crud     │  │ ehr-crud     │         │
│  │   :50052     │  │   :50052     │  │   :50052     │         │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤         │
│  │ mongodb      │  │ mongodb      │  │ mongodb      │         │
│  │   :27017     │  │   :27017     │  │   :27017     │         │
│  │ [PVC: 1Gi]   │  │ [PVC: 1Gi]   │  │ [PVC: 1Gi]   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                 │
│  Services:                                                      │
│  • hospital-headless (ClusterIP: None) - Raft discovery        │
│  • hospital-api (NodePort: 30080) - External API access        │
└─────────────────────────────────────────────────────────────────┘
```

### Service Breakdown

| Service | Purpose | Technology | Port |
|---------|---------|------------|------|
| **API Gateway** | REST API for external clients | FastAPI (Python) | 8080 |
| **P2P Raft** | Consensus & replication | Custom Raft (Python) | 7001 |
| **EHR CRUD** | Database operations | gRPC (Python) | 50052 |
| **MongoDB** | Data persistence | MongoDB 7.0 | 27017 |

## 1.2 Request Flow

### Write Operation (Create Patient)

```
Client (POST /patients)
    ↓
NodePort Service (30080) → Any Pod's API Gateway (8080)
    ↓
Authenticate (JWT)
    ↓
P2P Command Client → Submit to Raft (gRPC :7001)
    ↓
Raft Leader
    ├─→ Append to local log
    ├─→ Replicate to Followers (AppendEntries RPC)
    │   └─→ hospital-1.hospital-headless:7001
    │   └─→ hospital-2.hospital-headless:7001
    ↓
Followers acknowledge
    ↓
Leader commits (quorum reached)
    ↓
Commit listeners triggered on ALL nodes
    ↓
EHR Command Applier → CreatePatient (gRPC :50052)
    ↓
EHR CRUD Service → Insert to MongoDB (:27017)
    ↓
Response: Patient created (with UUID)
```

**Timeline:**
- Client → API: ~10ms
- Raft replication: ~50-150ms (network + consensus)
- MongoDB write: ~10-20ms
- **Total:** ~100-200ms

### Read Operation (Get Patient)

```
Client (GET /patients/{uuid})
    ↓
API Gateway (validates JWT)
    ↓
gRPC Client → GetPatient (gRPC :50052)
    ↓
EHR CRUD Service → Query local MongoDB
    ↓
MongoDB → Return document
    ↓
Response: Patient data
```

**Timeline:** ~20-50ms (no Raft consensus needed for reads)

## 1.3 Multi-Container Pod (Sidecar Pattern)

Each pod contains 4 containers sharing:
- ✅ **Network namespace** → `localhost` communication (no network overhead)
- ✅ **Lifecycle** → Start/stop together
- ✅ **Storage** → Shared volumes if needed

### Container Specifications

```yaml
Pod: hospital-0
├── mongodb
│   ├── Image: mongo:7.0
│   ├── Port: 27017
│   ├── Volume: mongo-data (1Gi PersistentVolume)
│   ├── Resources: ~256MB RAM
│   └── Database: ehr_database
│
├── ehr-crud
│   ├── Image: ehr-crud-service:local
│   ├── Port: 50052 (gRPC)
│   ├── Resources: ~128MB RAM
│   └── Connects to: localhost:27017
│
├── p2p-raft
│   ├── Image: p2p-raft-service:local
│   ├── Port: 7001 (gRPC)
│   ├── Resources: ~128MB RAM
│   ├── Env: NODE_ID=hospital-0 (from pod name)
│   │        PEERS=hospital-{0,1,2}.hospital-headless:7001
│   └── Connects to: localhost:50052, peer pods
│
└── api-gateway
    ├── Image: api-gateway-service:local
    ├── Port: 8080 (HTTP REST)
    ├── Resources: ~128MB RAM
    └── Connects to: localhost:50052, localhost:7001

Total per pod: ~640MB RAM
```

## 1.4 DNS Resolution & Service Discovery

### Headless Service

Creates predictable DNS names for Raft peer discovery:

```
Service: hospital-headless (ClusterIP: None)

DNS Names:
- hospital-0.hospital-headless.hospital-h1.svc.cluster.local:7001
- hospital-1.hospital-headless.hospital-h1.svc.cluster.local:7001
- hospital-2.hospital-headless.hospital-h1.svc.cluster.local:7001

Environment Variable (PEERS):
hospital-0=hospital-0.hospital-headless.hospital-h1.svc.cluster.local:7001,
hospital-1=hospital-1.hospital-headless.hospital-h1.svc.cluster.local:7001,
hospital-2=hospital-2.hospital-headless.hospital-h1.svc.cluster.local:7001
```

### NodePort Service

Exposes API to external clients:

```
Service: hospital-api (NodePort)
- External: http://<minikube-ip>:30080
- Internal: hospital-api.hospital-h1.svc.cluster.local:8080
- Targets: All pods' api-gateway containers
```

## 1.5 Raft Consensus States

### Normal Operation (3 nodes)

```
Initial: All nodes start as FOLLOWER
    ↓
Election timeout triggers (2-5 seconds)
    ↓
hospital-0 becomes CANDIDATE
    ├─→ Votes for self (1 vote)
    ├─→ Requests votes from hospital-1 and hospital-2
    ↓
hospital-1 grants vote ✅
hospital-2 grants vote ✅
    ↓
hospital-0 becomes LEADER (quorum: 2/3)
    ↓
Steady state:
- hospital-0: LEADER (accepts writes, sends heartbeats)
- hospital-1: FOLLOWER (replicates, can serve reads)
- hospital-2: FOLLOWER (replicates, can serve reads)
```

### Leader Failure & Recovery

```
hospital-0 crashes ❌
    ↓
hospital-1 and hospital-2 stop receiving heartbeats
    ↓
Election timeout (2-5 seconds)
    ↓
hospital-1 becomes CANDIDATE
    ├─→ Votes for self
    ├─→ Requests vote from hospital-2
    ↓
hospital-2 grants vote ✅
    ↓
hospital-1 becomes new LEADER 👑
    ↓
Meanwhile: Kubernetes recreates hospital-0 (15-30 seconds)
    ↓
hospital-0 comes back online
    ├─→ Discovers hospital-1 is leader
    ├─→ Becomes FOLLOWER
    ├─→ Catches up on missed log entries
    ↓
Cluster restored: 3 nodes operational ✅
```

### Quorum Requirements

| Total Nodes | Quorum Needed | Max Failures | Status |
|-------------|---------------|--------------|--------|
| 1 | 1 | 0 | ⚠️ No fault tolerance |
| 3 | 2 | 1 | ✅ Good for dev/test |
| 5 | 3 | 2 | ✅ Production recommended |
| 7 | 4 | 3 | ✅ High availability |

**Current Setup: 3 nodes (survives 1 failure)**

---

# 2. Kubernetes Deployment

## 2.1 Prerequisites

### Required Tools

1. **Minikube** - Local Kubernetes cluster
   ```powershell
   choco install minikube
   ```

2. **kubectl** - Kubernetes CLI
   ```powershell
   choco install kubernetes-cli
   ```

3. **Docker Desktop** - Container runtime
   - Download from: https://www.docker.com/products/docker-desktop

### Verify Installations

```powershell
minikube version    # Should show v1.x.x
kubectl version --client  # Should show v1.x.x
docker --version    # Should show 20.x.x or higher
```

## 2.2 Start Minikube

```powershell
# Start with sufficient resources for 3-node cluster
minikube start --cpus=4 --memory=8192 --driver=docker

# Enable useful addons
minikube addons enable metrics-server
minikube addons enable dashboard

# Verify running
minikube status
```

**Expected output:**
```
minikube
type: Control Plane
host: Running
kubelet: Running
apiserver: Running
kubeconfig: Configured
```

## 2.3 Configure Docker Environment

**⚠️ CRITICAL STEP** - Allows Minikube to use locally built images:

```powershell
# Get Minikube Docker environment
minikube docker-env

# Apply to current PowerShell session
& minikube -p minikube docker-env --shell powershell | Invoke-Expression

# Verify (you should see Minikube containers)
docker ps
```

**Note:** Run this in every new PowerShell window where you build images!

## 2.4 Build Docker Images

```powershell
# Navigate to project root
cd C:\Users\canba\Desktop\workspace\distributed-ehr-node

# Build all three service images
docker build -t api-gateway-service:local ./api-gateway-service
docker build -t ehr-crud-service:local ./ehr-crud-service
docker build -t p2p-raft-service:local ./p2p-raft-service

# Verify images exist
docker images | Select-String "local"
```

**Expected:**
```
api-gateway-service    local    ...
ehr-crud-service       local    ...
p2p-raft-service       local    ...
```

## 2.5 Deploy to Kubernetes

### Option A: Single Hospital (Recommended for Testing)

```powershell
# Deploy hospital-h1
kubectl apply -k k8s/overlays/hospital-h1

# Watch deployment progress
kubectl get pods -n hospital-h1 -w
```

**Wait for all pods to show `4/4 Running`:**
```
NAME         READY   STATUS    RESTARTS   AGE
hospital-0   4/4     Running   0          2m
hospital-1   4/4     Running   0          2m
hospital-2   4/4     Running   0          2m
```

Press `Ctrl+C` to stop watching.

### Option B: Multiple Hospitals

```powershell
kubectl apply -k k8s/overlays/hospital-h1
kubectl apply -k k8s/overlays/hospital-h2
kubectl apply -k k8s/overlays/hospital-h3

# View all namespaces
kubectl get namespaces
kubectl get pods -A
```

## 2.6 Access the API

### Get Service URL

```powershell
# For hospital-h1
minikube service hospital-api -n hospital-h1 --url
```

**Output:** `http://192.168.49.2:30080` (IP may vary)

### Test API

```powershell
# Open Swagger UI in browser
start http://192.168.49.2:30080/docs

# Or test with PowerShell
Invoke-RestMethod -Uri "http://192.168.49.2:30080/" -Method GET
```

### Alternative: Port Forwarding

```powershell
# Forward pod port to localhost
kubectl port-forward -n hospital-h1 pod/hospital-0 8080:8080

# Access at
start http://localhost:8080/docs
```

## 2.7 View Resources

```powershell
# All resources in namespace
kubectl get all -n hospital-h1

# Pods
kubectl get pods -n hospital-h1

# Services
kubectl get svc -n hospital-h1

# StatefulSet
kubectl get statefulset -n hospital-h1

# PersistentVolumeClaims
kubectl get pvc -n hospital-h1

# Detailed pod info
kubectl describe pod hospital-0 -n hospital-h1
```

## 2.8 View Logs

```powershell
# View specific container logs
kubectl logs -n hospital-h1 hospital-0 -c api-gateway
kubectl logs -n hospital-h1 hospital-0 -c ehr-crud
kubectl logs -n hospital-h1 hospital-0 -c p2p-raft
kubectl logs -n hospital-h1 hospital-0 -c mongodb

# Follow logs in real-time
kubectl logs -n hospital-h1 hospital-0 -c p2p-raft -f

# View last 50 lines
kubectl logs -n hospital-h1 hospital-0 -c p2p-raft --tail=50
```

## 2.9 Kubernetes Dashboard

```powershell
# Open dashboard
minikube dashboard
```

**⚠️ IMPORTANT:** 
- Dashboard defaults to `default` namespace
- Your pods are in `hospital-h1` namespace
- Click namespace dropdown at top and select `hospital-h1`

**What to check:**
- **Workloads → Pods:** 3 pods, each 4/4 Running
- **Workloads → StatefulSets:** hospital (3/3 replicas)
- **Discovery → Services:** hospital-api, hospital-headless
- **Config → Persistent Volumes:** 3 volumes for MongoDB

---

# 3. MongoDB Access

## 3.1 Understanding the Setup

**You have 3 separate MongoDB instances** (not a MongoDB replica set):
- hospital-0 → MongoDB (:27017)
- hospital-1 → MongoDB (:27017)
- hospital-2 → MongoDB (:27017)

**Data replication:** Via Raft consensus (NOT MongoDB replication)

**Database:** `ehr_database`  
**Collection:** `patients`

## 3.2 Method 1: Port Forwarding (Easiest)

### Forward Port

```powershell
# Forward MongoDB from hospital-0 to your machine
kubectl port-forward -n hospital-h1 pod/hospital-0 27017:27017
```

Keep this terminal open!

### Connect with MongoDB Compass (GUI)

1. Download: https://www.mongodb.com/try/download/compass
2. Connection string: `mongodb://localhost:27017/ehr_database`
3. Click "Connect"
4. Browse: `ehr_database` → `patients`

### Connect with mongosh (CLI)

```powershell
# In a NEW terminal
mongosh mongodb://localhost:27017/ehr_database
```

**Commands:**
```javascript
// Show collections
show collections

// Count patients
db.patients.countDocuments()

// Find all patients
db.patients.find().pretty()

// Find specific patient
db.patients.findOne({"identity.patientId": "P-2026-001"})

// Exit
exit
```

## 3.2 Method 2: Direct kubectl exec

```powershell
# Count patients in hospital-0
kubectl exec -n hospital-h1 hospital-0 -c mongodb -- mongosh ehr_database --quiet --eval "db.patients.countDocuments()"

# Get all patient IDs
kubectl exec -n hospital-h1 hospital-0 -c mongodb -- mongosh ehr_database --quiet --eval "db.patients.find({}, {'identity.patientId': 1}).toArray()"

# Interactive shell
kubectl exec -it -n hospital-h1 hospital-0 -c mongodb -- mongosh ehr_database
```

## 3.3 Verify Data Replication

**All 3 nodes should have identical data:**

```powershell
Write-Host "hospital-0:" -ForegroundColor Cyan
kubectl exec -n hospital-h1 hospital-0 -c mongodb -- mongosh ehr_database --quiet --eval "db.patients.countDocuments()"

Write-Host "hospital-1:" -ForegroundColor Cyan
kubectl exec -n hospital-h1 hospital-1 -c mongodb -- mongosh ehr_database --quiet --eval "db.patients.countDocuments()"

Write-Host "hospital-2:" -ForegroundColor Cyan
kubectl exec -n hospital-h1 hospital-2 -c mongodb -- mongosh ehr_database --quiet --eval "db.patients.countDocuments()"
```

**All three should return the same count! ✅**

## 3.4 Connection Strings Reference

| Context | Connection String |
|---------|-------------------|
| Local (with port-forward) | `mongodb://localhost:27017/ehr_database` |
| Same pod | `mongodb://localhost:27017/ehr_database` |
| Same namespace | `mongodb://hospital-0.hospital-headless:27017/ehr_database` |
| Different namespace | `mongodb://hospital-0.hospital-headless.hospital-h1.svc.cluster.local:27017/ehr_database` |

## 3.5 Application Code Examples

### Python (PyMongo)

```python
from pymongo import MongoClient

# With port-forward
client = MongoClient("mongodb://localhost:27017/")
db = client.ehr_database

# Query patients
for patient in db.patients.find():
    print(patient["identity"]["patientId"])
```

### Java (MongoDB Driver - NOT JDBC!)

```java
import com.mongodb.client.*;
import org.bson.Document;

String uri = "mongodb://localhost:27017";
try (MongoClient mongoClient = MongoClients.create(uri)) {
    MongoDatabase database = mongoClient.getDatabase("ehr_database");
    MongoCollection<Document> collection = database.getCollection("patients");
    
    for (Document doc : collection.find()) {
        System.out.println(doc.toJson());
    }
}
```

### Node.js

```javascript
const { MongoClient } = require('mongodb');

const uri = "mongodb://localhost:27017";
const client = new MongoClient(uri);

await client.connect();
const db = client.db('ehr_database');
const patients = await db.collection('patients').find().toArray();
console.log(patients);
```

**⚠️ Important:** MongoDB uses its own drivers, NOT JDBC (which is for SQL databases)

---

# 4. Testing & Verification

## 4.1 Check All Pods Running

```powershell
kubectl get pods -n hospital-h1
```

**Expected:**
```
NAME         READY   STATUS    RESTARTS   AGE
hospital-0   4/4     Running   0          5m
hospital-1   4/4     Running   0          5m
hospital-2   4/4     Running   0          5m
```

## 4.2 Authentication

### Login as Doctor

**Via Swagger UI** (`http://192.168.49.2:30080/docs`):

1. Find **POST /auth/login**
2. Click "Try it out"
3. Enter:
   - Username: `doctor1`
   - Password: `any` (demo mode accepts any password)
4. Click "Execute"
5. Copy the `access_token` from response
6. Click **"Authorize"** button (top right)
7. Paste token and click "Authorize"

**Via PowerShell:**

```powershell
$apiUrl = "http://192.168.49.2:30080"  # Replace with your URL

$response = Invoke-RestMethod -Uri "$apiUrl/auth/login" -Method POST `
    -Body "username=doctor1&password=any" `
    -ContentType "application/x-www-form-urlencoded"

$token = $response.access_token
Write-Host "Token: $token"

# Use in subsequent requests
$headers = @{ "Authorization" = "Bearer $token" }
```

## 4.3 Create Patients (Write Operations)

### Patient 1

```json
{
  "identity": {
    "patientId": "P-2026-001",
    "mrn": "MRN-12345",
    "nationalId": "SSN-123-45-6789"
  },
  "demographics": {
    "name": {
      "given": "John",
      "family": "Doe"
    },
    "dob": "1990-01-15",
    "sexAtBirth": "M",
    "genderIdentity": "Male",
    "deceased": false
  },
  "contacts": {
    "address": "123 Main Street, New York, NY 10001",
    "phone": "+1-555-0100",
    "email": "john.doe@example.com"
  },
  "sourceHospital": "hospital-h1"
}
```

**Via PowerShell:**

```powershell
$patient = @{
    identity = @{
        patientId = "P-2026-001"
        mrn = "MRN-12345"
    }
    demographics = @{
        name = @{
            given = "John"
            family = "Doe"
        }
        dob = "1990-01-15"
        deceased = $false
    }
    sourceHospital = "hospital-h1"
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri "$apiUrl/patients" -Method POST `
    -Headers $headers -Body $patient -ContentType "application/json"
```

**Expected Response:**
```json
{
  "id": "uuid-here",
  "identity": { "patientId": "P-2026-001", ... },
  "version": 1,
  "created_at": "2026-02-17T...",
  ...
}
```

### Create More Patients

Use patient IDs: `P-2026-002`, `P-2026-003`, etc.

## 4.4 Read Operations

```powershell
# Get all patients
Invoke-RestMethod -Uri "$apiUrl/patients" -Headers $headers

# Get patient by UUID
Invoke-RestMethod -Uri "$apiUrl/patients/{uuid}" -Headers $headers

# Search by patient ID
Invoke-RestMethod -Uri "$apiUrl/patients/search/P-2026-001" -Headers $headers
```

## 4.5 Update Operations

```powershell
$update = @{
    contacts = @{
        phone = "+1-555-9999"
        email = "updated@example.com"
    }
} | ConvertTo-Json

Invoke-RestMethod -Uri "$apiUrl/patients/{uuid}" -Method PUT `
    -Headers $headers -Body $update -ContentType "application/json"
```

## 4.6 Delete Operations

```powershell
Invoke-RestMethod -Uri "$apiUrl/patients/{uuid}" -Method DELETE -Headers $headers
```

## 4.7 Verify Raft Consensus

### Check Raft Leader

```powershell
kubectl logs -n hospital-h1 hospital-0 -c p2p-raft --tail=50
kubectl logs -n hospital-h1 hospital-1 -c p2p-raft --tail=50
kubectl logs -n hospital-h1 hospital-2 -c p2p-raft --tail=50
```

**Look for:**
```
👑 ELECTED AS LEADER - Node: hospital-0 | Term: 1
```

OR

```
👤 Following leader: hospital-0 | Term: 1
```

### Verify Data Replication

```powershell
# All 3 MongoDB instances should have same count
kubectl exec -n hospital-h1 hospital-0 -c mongodb -- mongosh ehr_database --quiet --eval "db.patients.countDocuments()"
kubectl exec -n hospital-h1 hospital-1 -c mongodb -- mongosh ehr_database --quiet --eval "db.patients.countDocuments()"
kubectl exec -n hospital-h1 hospital-2 -c mongodb -- mongosh ehr_database --quiet --eval "db.patients.countDocuments()"
```

**✅ All three should return the same number!**

## 4.8 Test Fault Tolerance

### Delete Leader Pod

```powershell
# Delete the leader (example: hospital-0)
kubectl delete pod hospital-0 -n hospital-h1

# Watch automatic recreation
kubectl get pods -n hospital-h1 -w
```

**What happens:**
1. hospital-0 terminates (0-5 seconds)
2. hospital-1 or hospital-2 elects new leader (2-5 seconds)
3. Kubernetes recreates hospital-0 (15-30 seconds)
4. hospital-0 rejoins as follower (5-10 seconds)

**Expected:**
```
hospital-0   4/4     Terminating
hospital-0   0/4     Pending
hospital-0   1/4     Running
hospital-0   2/4     Running
hospital-0   3/4     Running
hospital-0   4/4     Running    ✅
```

### Verify New Leader

```powershell
kubectl logs -n hospital-h1 hospital-1 -c p2p-raft --tail=30
kubectl logs -n hospital-h1 hospital-2 -c p2p-raft --tail=30
```

**Look for:**
```
🗳️  STARTING ELECTION - Node: hospital-1 | Term: 2
✅ Vote granted from hospital-2
👑 ELECTED AS LEADER - Node: hospital-1 | Term: 2
```

### Test During Failure

While pod is being recreated, try creating a patient - it should still work! ✅

## 4.9 Success Criteria

Your system is **fully operational** if:

- ✅ All 3 pods show `4/4 Running`
- ✅ Can authenticate and get JWT token
- ✅ Can create patients via API
- ✅ Can read patients from API
- ✅ All 3 MongoDB instances have identical data
- ✅ Raft leader is elected
- ✅ System survives pod deletion
- ✅ New leader elected automatically
- ✅ No errors in container logs

---

# 5. Operations & Troubleshooting

## 5.1 Common Issues & Solutions

### Issue: Pods Not Starting

**Symptoms:**
```
NAME         READY   STATUS             RESTARTS
hospital-0   0/4     ImagePullBackOff   0
```

**Solution:**
```powershell
# Ensure using Minikube's Docker daemon
& minikube -p minikube docker-env --shell powershell | Invoke-Expression

# Rebuild images
docker build -t api-gateway-service:local ./api-gateway-service
docker build -t ehr-crud-service:local ./ehr-crud-service
docker build -t p2p-raft-service:local ./p2p-raft-service

# Verify images exist
docker images | Select-String "local"

# Redeploy
kubectl delete namespace hospital-h1
kubectl apply -k k8s/overlays/hospital-h1
```

### Issue: Container CrashLoopBackOff

**Symptoms:**
```
NAME         READY   STATUS             RESTARTS
hospital-0   2/4     CrashLoopBackOff   3
```

**Diagnosis:**
```powershell
# Check which container is failing
kubectl get pod hospital-0 -n hospital-h1

# View logs of failing container
kubectl logs hospital-0 -n hospital-h1 -c api-gateway --previous
kubectl logs hospital-0 -n hospital-h1 -c p2p-raft --previous
```

**Common causes:**
- Missing protobuf files → Rebuild images
- MongoDB not ready → Wait longer
- Port conflicts → Check container ports

### Issue: Can't Access API

**Solution 1: Port Forward**
```powershell
kubectl port-forward -n hospital-h1 pod/hospital-0 8080:8080
# Access at http://localhost:8080/docs
```

**Solution 2: Check Service**
```powershell
kubectl get svc -n hospital-h1
minikube service hospital-api -n hospital-h1 --url
```

### Issue: 401 Unauthorized

**Cause:** JWT token not set or expired

**Solution:**
1. Login again to get fresh token
2. Click "Authorize" in Swagger UI
3. Paste new token

### Issue: Data Not Replicated

**Check Raft logs:**
```powershell
kubectl logs -n hospital-h1 hospital-0 -c p2p-raft | Select-String "error|ERROR"
```

**Check network connectivity:**
```powershell
kubectl exec -n hospital-h1 hospital-0 -c p2p-raft -- ping hospital-1.hospital-headless -c 2
```

### Issue: Pod Stuck in Pending

**Check events:**
```powershell
kubectl describe pod hospital-0 -n hospital-h1
```

**Common causes:**
- PersistentVolume not available
- Insufficient resources
- Node selector mismatch

**Solution:**
```powershell
# Check resources
kubectl top nodes

# Check PVs
kubectl get pv
```

## 5.2 Monitoring Commands

### View All Resources

```powershell
# All resources in namespace
kubectl get all -n hospital-h1

# Detailed view
kubectl get pods,svc,statefulset,pvc -n hospital-h1
```

### Watch Events

```powershell
kubectl get events -n hospital-h1 --sort-by='.lastTimestamp'
```

### Resource Usage

```powershell
kubectl top nodes
kubectl top pods -n hospital-h1
```

### Log Aggregation

```powershell
# View logs from all pods
kubectl logs -n hospital-h1 -l app=hospital --all-containers --tail=20
```

## 5.3 Cleanup Operations

### Delete Single Hospital

```powershell
kubectl delete namespace hospital-h1
```

### Delete All Hospitals

```powershell
kubectl delete namespace hospital-h1 hospital-h2 hospital-h3
```

### Stop Minikube

```powershell
minikube stop
```

### Complete Cleanup

```powershell
minikube delete
```

## 5.4 Scaling Operations

### Scale to 5 Replicas

**Edit statefulset.yaml:**
```yaml
spec:
  replicas: 5  # Change from 3
```

**Update PEERS environment:**
```yaml
env:
- name: PEERS
  value: "hospital-0=...:7001,hospital-1=...:7001,...,hospital-4=...:7001"
```

**Redeploy:**
```powershell
kubectl apply -k k8s/overlays/hospital-h1
```

---

# 6. Advanced Topics

## 6.1 Raft Consensus Deep Dive

### Log Structure

```
Index | Term | Command
------|------|------------------
1     | 1    | PATIENT_CREATE
2     | 1    | PATIENT_UPDATE
3     | 2    | PATIENT_DELETE
4     | 2    | PATIENT_CREATE
```

### Leader Election Process

1. **Follower timeout** → Becomes Candidate
2. **Increment term** (e.g., 1 → 2)
3. **Vote for self**
4. **Request votes** from peers
5. **Receive majority** → Become Leader
6. **Send heartbeats** to maintain leadership

### Commit Process

1. Leader receives command
2. Leader appends to local log
3. Leader sends AppendEntries to followers
4. Followers append to their logs and acknowledge
5. Leader commits when majority acknowledge
6. Leader notifies followers of commit
7. All nodes apply committed entry to state machine

## 6.2 Network Topology

```
hospital-h1 (Namespace)
├── hospital-0.hospital-headless:7001
│   ├── Connected to: hospital-1, hospital-2
│   └── Latency: <1ms (same Minikube node)
├── hospital-1.hospital-headless:7001
│   ├── Connected to: hospital-0, hospital-2
│   └── Latency: <1ms
└── hospital-2.hospital-headless:7001
    ├── Connected to: hospital-0, hospital-1
    └── Latency: <1ms
```

## 6.3 Performance Characteristics

| Operation | Latency | Throughput |
|-----------|---------|------------|
| Read (local) | ~20-50ms | High |
| Write (Raft consensus) | ~100-200ms | Medium |
| Leader election | ~2-5 seconds | N/A |
| Pod recovery | ~15-30 seconds | N/A |

## 6.4 Data Consistency Guarantees

- ✅ **Linearizability:** All writes appear in a single, total order
- ✅ **Durability:** Committed writes survive up to f failures (f = (n-1)/2)
- ✅ **Consistency:** All nodes have identical data after convergence
- ⚠️ **Availability:** Requires majority (quorum) for writes

## 6.5 Multi-Hospital Architecture

Each hospital is **completely independent**:

```
Minikube Cluster
├── hospital-h1 (namespace)
│   ├── 3-node Raft cluster
│   ├── Independent patient data
│   └── NodePort: 30080
├── hospital-h2 (namespace)
│   ├── 3-node Raft cluster
│   ├── Independent patient data
│   └── NodePort: 30081
└── hospital-h3 (namespace)
    ├── 3-node Raft cluster
    ├── Independent patient data
    └── NodePort: 30082
```

**No cross-hospital replication** (by design - each hospital owns its data)

---

# 7. Quick Reference

## 7.1 Essential Commands

```powershell
# Start Minikube
minikube start --cpus=4 --memory=8192

# Configure Docker
& minikube -p minikube docker-env --shell powershell | Invoke-Expression

# Build images
docker build -t <service>:local ./<directory>

# Deploy
kubectl apply -k k8s/overlays/hospital-h1

# Get pods
kubectl get pods -n hospital-h1

# Get logs
kubectl logs -n hospital-h1 hospital-0 -c p2p-raft --tail=50

# Port forward
kubectl port-forward -n hospital-h1 pod/hospital-0 8080:8080

# Get API URL
minikube service hospital-api -n hospital-h1 --url

# Dashboard
minikube dashboard

# Delete
kubectl delete namespace hospital-h1
```

## 7.2 Log Symbols Reference

| Symbol | Meaning |
|--------|---------|
| 🚀 | Service startup |
| 👑 | Elected as leader |
| 🗳️ | Starting election |
| ✅ | Success |
| ❌ | Failure |
| 📨 | Command received |
| 📝 | Leader appending |
| 📥 | Follower received |
| 🔄 | Applying committed entry |
| 🏥 | Writing to database |
| 👤 | Following leader |

## 7.3 Port Reference

| Service | Port | Protocol |
|---------|------|----------|
| API Gateway | 8080 | HTTP REST |
| P2P Raft | 7001 | gRPC |
| EHR CRUD | 50052 | gRPC |
| MongoDB | 27017 | MongoDB Wire |
| NodePort (external) | 30080 | HTTP |

## 7.4 URLs

- **Swagger UI:** `http://<minikube-ip>:30080/docs`
- **ReDoc:** `http://<minikube-ip>:30080/redoc`
- **Health:** `http://<minikube-ip>:30080/`
- **Dashboard:** `minikube dashboard`

---

# 8. Summary

## What You've Built

A **production-grade distributed Electronic Health Record system** with:

✅ **Strong Consistency** - Raft consensus ensures all nodes agree  
✅ **Fault Tolerance** - Survives 1 node failure (3-node cluster)  
✅ **High Availability** - Automatic leader election and pod recovery  
✅ **Data Persistence** - PersistentVolumes for MongoDB  
✅ **Service Discovery** - Kubernetes DNS for Raft peers  
✅ **RESTful API** - FastAPI with Swagger documentation  
✅ **Microservices** - 4 containers per pod (sidecar pattern)  
✅ **Authentication** - JWT tokens for secure access  
✅ **Horizontal Scalability** - Deploy multiple independent hospitals  

## Key Technologies

- **Kubernetes** - Container orchestration
- **Raft** - Distributed consensus algorithm
- **MongoDB** - NoSQL database
- **gRPC** - Efficient inter-service communication
- **FastAPI** - Modern Python web framework
- **Docker** - Containerization
- **Minikube** - Local Kubernetes

## Next Steps

1. ✅ Run the full test suite (Section 4)
2. ✅ Experiment with fault tolerance (delete pods)
3. 📚 Study Raft algorithm in depth
4. 🚀 Deploy additional hospital clusters
5. 🔧 Add monitoring (Prometheus + Grafana)
6. 🔐 Implement production authentication
7. 📊 Add observability (tracing, metrics)

---

**Congratulations!** You now have a complete understanding of the distributed EHR system architecture, deployment, and operations! 🎉

**For additional help, see:**
- `POD_RECOVERY_GUIDE.md` - Pod recovery details
- `DASHBOARD_NAMESPACE_GUIDE.md` - Dashboard usage
- `LOGGING_GUIDE.md` - Raft log reference
- `FIX_RACE_CONDITION.md` - API race condition fix

# Complete Testing Guide - Distributed EHR System

## 🎉 Congratulations! Your System is Deployed!

You now have a running 3-node Raft consensus cluster with distributed EHR capabilities.

---

## 📊 Step 1: Verify All Pods are Running

```powershell
kubectl get pods -n hospital-h1
```

**Expected Output:**
```
NAME         READY   STATUS    RESTARTS   AGE
hospital-0   4/4     Running   0          5m
hospital-1   4/4     Running   0          5m
hospital-2   4/4     Running   0          5m
```

All pods should show **4/4 Running**.

### 💡 Viewing in Minikube Dashboard

You can also view pods visually in the Minikube Dashboard:

```powershell
minikube dashboard
```

**⚠️ IMPORTANT:** The dashboard defaults to the `default` namespace, but your pods are in `hospital-h1`.

**To see your pods:**
1. Look for the **namespace selector** at the top of the dashboard
2. Click the dropdown (shows "default")
3. Select **"hospital-h1"**
4. Navigate to **Workloads → Pods**

**What you'll see:**
- 3 pods (hospital-0, hospital-1, hospital-2)
- Each pod has 4 containers
- Can view logs, resource usage, and events

**See `DASHBOARD_NAMESPACE_GUIDE.md` for detailed instructions.**

---

## 🌐 Step 2: Access the API

### Option A: Get Minikube Service URL

```powershell
minikube service hospital-api -n hospital-h1 --url
```

This will output something like: `http://192.168.49.2:30080`

**Save this URL - you'll need it for testing!**

### Option B: Use Port Forwarding (Alternative)

```powershell
kubectl port-forward -n hospital-h1 pod/hospital-0 8080:8080
```

Then access at: `http://localhost:8080`

---

## 📖 Step 3: Open API Documentation

Open your browser to:
- **Minikube URL:** `http://192.168.49.2:30080/docs` (replace with your actual URL)
- **Port Forward:** `http://localhost:8080/docs`

You should see the **Swagger UI** with interactive API documentation.

---

## 🔐 Step 4: Test Authentication System

### 4.1 Login as Doctor

**In Swagger UI:**
1. Find the **POST /auth/login** endpoint
2. Click "Try it out"
3. Enter:
   - `username`: `doctor1`
   - `password`: `any` (any password works in demo mode)
4. Click "Execute"

**Expected Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Copy the `access_token` value!**

### 4.2 Authorize Swagger UI

1. Click the **"Authorize"** button at the top right
2. Paste your token in the "Value" field
3. Click "Authorize"
4. Click "Close"

Now you're authenticated and can use protected endpoints!

---

## 👨‍⚕️ Step 5: Create Patient Records (Test Write Operations)

### 5.1 Create First Patient

**Endpoint:** POST /patients

**Request Body:**
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

**Expected Response:**
```json
{
  "id": "some-uuid-here",
  "identity": {
    "patientId": "P-2026-001",
    ...
  },
  "version": 1,
  "lastUpdated": "2026-02-17T...",
  "created_at": "2026-02-17T...",
  ...
}
```

### 5.2 Create More Patients

Create 2-3 more patients with different data to test the system:

**Patient 2:**
```json
{
  "identity": {
    "patientId": "P-2026-002",
    "mrn": "MRN-67890"
  },
  "demographics": {
    "name": {
      "given": "Jane",
      "family": "Smith"
    },
    "dob": "1985-06-20",
    "sexAtBirth": "F",
    "genderIdentity": "Female",
    "deceased": false
  },
  "contacts": {
    "phone": "+1-555-0200",
    "email": "jane.smith@example.com"
  },
  "sourceHospital": "hospital-h1"
}
```

**Patient 3:**
```json
{
  "identity": {
    "patientId": "P-2026-003",
    "mrn": "MRN-11111"
  },
  "demographics": {
    "name": {
      "given": "Michael",
      "family": "Johnson"
    },
    "dob": "1978-12-05",
    "deceased": false
  },
  "sourceHospital": "hospital-h1"
}
```

---

## 📋 Step 6: Test Read Operations

### 6.1 Get All Patients

**Endpoint:** GET /patients

Click "Execute" to retrieve all patients.

**Expected:** List of all patients you created.

### 6.2 Get Patient by UUID

**Endpoint:** GET /patients/{patient_uuid}

Use the UUID from one of your created patients.

### 6.3 Search by Patient ID

**Endpoint:** GET /patients/search/{patient_id}

Try: `P-2026-001`

---

## ✏️ Step 7: Test Update Operations

### 7.1 Update Patient

**Endpoint:** PUT /patients/{patient_uuid}

**Request Body (Update contacts):**
```json
{
  "contacts": {
    "address": "456 New Address, Los Angeles, CA 90001",
    "phone": "+1-555-9999",
    "email": "john.doe.updated@example.com"
  }
}
```

**Expected:** Patient record updated, version incremented.

---

## 🗑️ Step 8: Test Delete Operation

**Endpoint:** DELETE /patients/{patient_uuid}

Delete one of the test patients.

**Expected Response:**
```json
{
  "message": "Patient deleted successfully",
  "patient_uuid": "..."
}
```

---

## 🔍 Step 9: Verify Raft Consensus (Distributed System Testing)

This is the **most important part** - verifying that Raft consensus is working!

### 9.1 Check Raft Leader

```powershell
# Check logs from all 3 pods to see which is the leader
kubectl logs -n hospital-h1 hospital-0 -c p2p-raft --tail=50
kubectl logs -n hospital-h1 hospital-1 -c p2p-raft --tail=50
kubectl logs -n hospital-h1 hospital-2 -c p2p-raft --tail=50
```

**Expected Log Output:**

You should see startup logs like:
```
================================================================================
🚀 Starting P2P Raft Service - Node: hospital-0
📡 Cluster ID: hospital-h1
🌐 gRPC Port: 50051
👥 Peers: ['hospital-1', 'hospital-2']
⏱️  Election Timeout: 3000ms
💓 Heartbeat Interval: 1000ms
================================================================================
🔧 Initializing Raft transport layer...
🔧 Initializing Raft consensus node...
📋 RaftNode initialized: hospital-0 | Peers: ['hospital-1', 'hospital-2'] | Role: FOLLOWER
🔗 EHR Applier connected to localhost:50052
✅ gRPC server started on port 50051
✅ P2P Raft Service is ready and running!
⏳ Waiting for leader election...
🗳️  STARTING ELECTION - Node: hospital-0 | Term: 1 | LastLogIndex: 0
✅ Vote granted from hospital-1 | Total votes: 2/2
👑 ELECTED AS LEADER - Node: hospital-0 | Term: 1
```

**One node will show "👑 ELECTED AS LEADER", the other two will show "👤 Following leader"**

### 9.1.1 View Real-Time Logs (Better!)

```powershell
# Follow logs in real-time to see Raft in action
kubectl logs -n hospital-h1 hospital-0 -c p2p-raft -f
```

**You should see one node elected as LEADER.**

### 9.2 Verify Data Replication Across All Nodes

Check that the patient data exists in **all 3 MongoDB instances**:

```powershell
# Check MongoDB on hospital-0
kubectl exec -n hospital-h1 hospital-0 -c mongodb -- mongosh ehr_database --quiet --eval "db.patients.countDocuments()"

# Check MongoDB on hospital-1
kubectl exec -n hospital-h1 hospital-1 -c mongodb -- mongosh ehr_database --quiet --eval "db.patients.countDocuments()"

# Check MongoDB on hospital-2
kubectl exec -n hospital-h1 hospital-2 -c mongodb -- mongosh ehr_database --quiet --eval "db.patients.countDocuments()"
```

**All three should return the SAME count!** This proves Raft replication is working.

### 9.3 Verify Patient Data is Identical

```powershell
# Get all patients from each node
kubectl exec -n hospital-h1 hospital-0 -c mongodb -- mongosh ehr_database --quiet --eval "db.patients.find({}, {_id:1, 'identity.patientId':1}).toArray()"

kubectl exec -n hospital-h1 hospital-1 -c mongodb -- mongosh ehr_database --quiet --eval "db.patients.find({}, {_id:1, 'identity.patientId':1}).toArray()"

kubectl exec -n hospital-h1 hospital-2 -c mongodb -- mongosh ehr_database --quiet --eval "db.patients.find({}, {_id:1, 'identity.patientId':1}).toArray()"
```

**All three should return identical results!**

---

## 🚨 Step 10: Test Fault Tolerance (Advanced)

### 10.1 Kill the Leader Pod

First, identify which pod is the leader, then delete it:

```powershell
# Delete hospital-0 (example - delete whichever is leader)
kubectl delete pod hospital-0 -n hospital-h1
```

**What happens:**
1. Pod is terminated
2. Remaining nodes (hospital-1 and hospital-2) detect leader failure
3. New leader is elected within ~2 seconds
4. System continues to work!

### 10.2 Watch Automatic Pod Recreation

**Important:** Kubernetes StatefulSet will **automatically recreate** the deleted pod! You don't need to do anything.

```powershell
# Watch pods in real-time - you'll see the pod go from Terminating → Pending → Running
kubectl get pods -n hospital-h1 -w
```

**Expected sequence:**
```
NAME         READY   STATUS        RESTARTS   AGE
hospital-0   4/4     Terminating   0          10m    ← Shutting down
hospital-1   4/4     Running       0          10m
hospital-2   4/4     Running       0          10m

NAME         READY   STATUS    RESTARTS   AGE
hospital-0   0/4     Pending   0          1s         ← Being recreated
hospital-0   0/4     Init:0/0  0          2s         ← Initializing
hospital-0   0/4     PodInitializing  0    5s        ← Starting containers
hospital-0   1/4     Running   0          10s        ← First container ready
hospital-0   2/4     Running   0          15s        ← Second container ready
hospital-0   3/4     Running   0          20s        ← Third container ready
hospital-0   4/4     Running   0          25s        ← All containers ready! ✅
```

**Press Ctrl+C to stop watching.**

### 10.3 Verify New Leader Elected (During Downtime)

While the deleted pod is being recreated, check which remaining pod became the leader:

```powershell
# Check hospital-1 logs for leader election
kubectl logs -n hospital-h1 hospital-1 -c p2p-raft --tail=50

# Check hospital-2 logs for leader election  
kubectl logs -n hospital-h1 hospital-2 -c p2p-raft --tail=50
```

**Look for these log messages:**
```
🗳️  STARTING ELECTION - Node: hospital-1 | Term: 2 | LastLogIndex: 5
✅ Vote granted from hospital-2 | Total votes: 2/2
👑 ELECTED AS LEADER - Node: hospital-1 | Term: 2
```

### 10.4 Verify Recreated Pod Rejoins Cluster

After hospital-0 is recreated (shows 4/4 Running), check if it rejoined as a follower:

```powershell
# Check hospital-0 logs after it comes back online
kubectl logs -n hospital-h1 hospital-0 -c p2p-raft --tail=50
```

**Expected logs:**
```
🚀 Starting P2P Raft Service - Node: hospital-0
...
👤 Following leader: hospital-1 | Term: 2
📥 Received entries from leader hospital-1
```

### 10.5 Test System Still Works

Try creating another patient - it should work even during the recovery!

**Test during pod recreation:**
1. Delete hospital-0
2. **Immediately** try creating a patient via Swagger UI
3. It should still work! (requests go to hospital-1 or hospital-2)

**This demonstrates:**
- ✅ High availability (no downtime)
- ✅ Automatic leader election (~2 seconds)
- ✅ Automatic pod recreation by Kubernetes
- ✅ Fault tolerance (survives 1 node failure)
- ✅ Self-healing system

### 10.6 What Happens Behind the Scenes?

When you delete a pod from a StatefulSet:

1. **Pod Deletion** (t=0s)
   - Pod receives SIGTERM signal
   - Containers begin graceful shutdown
   - Pod status changes to "Terminating"

2. **Raft Detects Failure** (t=1-3s)
   - Remaining nodes stop receiving heartbeats from deleted node
   - Election timeout triggers on followers
   - New election begins

3. **New Leader Elected** (t=2-5s)
   - One of the remaining nodes becomes candidate
   - Requests votes from peers
   - Achieves quorum (2 out of 3 nodes)
   - Becomes new leader

4. **Kubernetes Recreates Pod** (t=5-30s)
   - StatefulSet controller detects missing pod
   - **Automatically** creates replacement pod with same name (hospital-0)
   - Pod goes through: Pending → Init → Running
   - All 4 containers start up

5. **Pod Rejoins Cluster** (t=30-40s)
   - Raft service starts on recreated pod
   - Discovers current leader (hospital-1 or hospital-2)
   - Becomes follower
   - Receives log entries from leader to catch up

**Result:** Full 3-node cluster restored automatically! ✅

### 10.7 Manual Pod Recreation (If Needed)

**Normally you don't need this** - Kubernetes does it automatically. But if something goes wrong:

```powershell
# Check if StatefulSet is managing the pods
kubectl get statefulset -n hospital-h1

# If pod is stuck, force delete
kubectl delete pod hospital-0 -n hospital-h1 --force --grace-period=0

# Scale down and up (last resort)
kubectl scale statefulset hospital -n hospital-h1 --replicas=2
kubectl scale statefulset hospital -n hospital-h1 --replicas=3
```

### 10.8 Troubleshooting Pod Recreation

**Problem: Pod stuck in "Pending"**
```powershell
# Check events
kubectl describe pod hospital-0 -n hospital-h1

# Common causes:
# - PersistentVolume not available
# - Insufficient resources
# - Image pull errors
```

**Problem: Pod stuck in "CrashLoopBackOff"**
```powershell
# Check logs to see which container is failing
kubectl logs hospital-0 -n hospital-h1 -c api-gateway --previous
kubectl logs hospital-0 -n hospital-h1 -c ehr-crud --previous
kubectl logs hospital-0 -n hospital-h1 -c p2p-raft --previous
kubectl logs hospital-0 -n hospital-h1 -c mongodb --previous
```

**Problem: Pod doesn't recreate at all**
```powershell
# Check StatefulSet status
kubectl get statefulset hospital -n hospital-h1 -o yaml

# Check if StatefulSet is paused or has wrong replicas count
# Should show: replicas: 3
```

---

## 📊 Step 11: Monitor System Health

### 11.1 View All Logs

```powershell
# API Gateway logs
kubectl logs -n hospital-h1 hospital-0 -c api-gateway -f

# Raft consensus logs
kubectl logs -n hospital-h1 hospital-0 -c p2p-raft -f

# Database service logs
kubectl logs -n hospital-h1 hospital-0 -c ehr-crud -f

# MongoDB logs
kubectl logs -n hospital-h1 hospital-0 -c mongodb -f
```

### 11.2 Check Pod Status

```powershell
# Detailed pod information
kubectl describe pod hospital-0 -n hospital-h1

# Resource usage
kubectl top pods -n hospital-h1
```

### 11.3 Monitor Events

```powershell
kubectl get events -n hospital-h1 --sort-by='.lastTimestamp'
```

---

## 🧪 Complete Test Checklist

- [ ] **Authentication**
  - [ ] Login as doctor succeeds
  - [ ] JWT token received
  - [ ] Token works for protected endpoints

- [ ] **CRUD Operations**
  - [ ] Create patient (POST)
  - [ ] Get all patients (GET)
  - [ ] Get patient by UUID (GET)
  - [ ] Search by patient ID (GET)
  - [ ] Update patient (PUT)
  - [ ] Delete patient (DELETE)

- [ ] **Raft Consensus**
  - [ ] Leader elected
  - [ ] Data replicated to all 3 nodes
  - [ ] All nodes have identical data

- [ ] **Fault Tolerance**
  - [ ] System survives pod deletion
  - [ ] New leader elected automatically
  - [ ] System continues to accept requests

- [ ] **Data Persistence**
  - [ ] Patient data persists after pod restart
  - [ ] MongoDB PersistentVolumes working

---

## 📸 Expected Screenshots/Results

### 1. Swagger UI
- Should show all 7 API endpoints
- Should have green "Authorize" button when token is set

### 2. Patient Creation
- Status: 201 Created
- Response includes UUID, version, timestamps

### 3. Data Replication
- All 3 MongoDB instances have same patient count
- All 3 pods show same patient data

### 4. Raft Logs
- One pod shows "elected as leader" or "became leader"
- Followers show "following leader"

---

## 🎯 Success Criteria

Your system is **fully working** if:

✅ All 3 pods are Running (4/4 containers)  
✅ Can create patients via API  
✅ Can read patients from API  
✅ All 3 MongoDB instances have identical data  
✅ Raft leader is elected  
✅ System survives pod deletion  
✅ New leader is elected after failure  
✅ No errors in container logs  

---

## 🐛 Troubleshooting

### Issue: Can't access API
```powershell
# Try port-forward instead
kubectl port-forward -n hospital-h1 pod/hospital-0 8080:8080
```

### Issue: 401 Unauthorized
- Make sure you clicked "Authorize" in Swagger UI
- Check token is copied correctly

### Issue: Patient creation fails
```powershell
# Check Raft service logs
kubectl logs -n hospital-h1 hospital-0 -c p2p-raft

# Check EHR service logs
kubectl logs -n hospital-h1 hospital-0 -c ehr-crud
```

### Issue: Data not replicated
```powershell
# Check network connectivity between pods
kubectl exec -n hospital-h1 hospital-0 -c p2p-raft -- ping hospital-1.hospital-headless -c 2
```

---

## 📚 What You're Testing

This distributed system demonstrates:

1. **Microservices Architecture** - API Gateway, CRUD Service, Raft Service
2. **Raft Consensus Algorithm** - Leader election, log replication
3. **Strong Consistency** - All nodes have identical data
4. **Fault Tolerance** - Survives 1 node failure
5. **gRPC Communication** - Fast inter-service communication
6. **REST API** - External client interface
7. **JWT Authentication** - Secure access control
8. **MongoDB Replication** - Data persistence across nodes
9. **Kubernetes Orchestration** - StatefulSets, Services, Namespaces

---

## 🎓 Demo Script (For Presentation)

1. **Show Architecture**: Open Minikube Dashboard → Show 3 pods running
2. **Show API Docs**: Open Swagger UI → Show 7 endpoints
3. **Authenticate**: Login → Get token → Authorize
4. **Create Patient**: POST /patients → Show success
5. **Verify Replication**: Query MongoDB on all 3 nodes → Show identical data
6. **Show Raft Leader**: Check logs → Identify leader
7. **Test Fault Tolerance**: Delete leader pod → Show new leader elected
8. **Prove Availability**: Create another patient → Show it still works
9. **Show Recovery**: Watch deleted pod restart → System back to 3 nodes

---

## 🚀 Next Steps

After testing, you can:

1. **Deploy more hospitals**: `kubectl apply -k k8s/overlays/hospital-h2`
2. **Add conditions to patients**: Use PUT endpoint with conditions array
3. **Test with Postman**: Import `Distributed-Systems.postman_collection.json`
4. **Monitor with Dashboard**: `minikube dashboard`
5. **Export data**: Use MongoDB export tools
6. **Scale replicas**: Edit statefulset.yaml to use 5 replicas

---

**Happy Testing! 🎉**

Your distributed EHR system is fully operational and ready for demonstration!

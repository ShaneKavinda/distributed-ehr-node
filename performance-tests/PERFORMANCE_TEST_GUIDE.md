# Performance Testing Guide

## Quick Start

This guide will help you run performance tests on the Distributed EHR System to measure throughput, response times, and system capacity.

---

## Prerequisites

### 1. Install Python Dependencies

```powershell
cd performance-tests
pip install -r requirements.txt
```

**Required packages:**
- `locust >= 2.43.3` (load testing framework)
- `faker >= 22.6.0` (realistic test data generation)

### 2. Ensure the System is Running

Make sure your EHR system is deployed in Kubernetes/Minikube:

```powershell
# Check if pods are running
kubectl get pods -n hospital-h1

# You should see pods like: hospital-0, hospital-1, hospital-2
```

---

## Port Forwarding (Required)

Before running tests, you need to expose the API Gateway to your local machine:

```powershell
kubectl port-forward -n hospital-h1 svc/hospital-api 8081:8080
```

**Keep this terminal open** while running tests. The API will be available at `http://localhost:8081`

---

## Running Tests

### Option 1: Web UI (Recommended for Beginners) 🌐

**Best for:** Visual monitoring, experimenting with different loads, real-time graphs

```powershell
cd performance-tests
locust -f locustfile.py --host=http://localhost:8081
```

Then:
1. Open your browser to **http://localhost:8089**
2. Enter test parameters:
   - **Number of users**: `100` (start small, increase gradually)
   - **Spawn rate**: `10` (users added per second)
3. Click **"Start Swarming"**
4. Watch real-time statistics and graphs
5. Click **"Stop"** when done

**Visual Dashboard Features:**
- Live charts showing response times
- Request throughput (req/s)
- Failure rates
- Percentile statistics (50th, 95th, 99th)

---

### Option 2: Headless Mode (Automated Testing) 🤖

**Best for:** Automated tests, CI/CD, generating reports

#### Light Test (10 users, 1 minute)
```powershell
locust -f locustfile.py --host=http://localhost:8081 --users 10 --spawn-rate 2 --run-time 1m --headless
```

#### Medium Test (100 users, 5 minutes)
```powershell
locust -f locustfile.py --host=http://localhost:8081 --users 100 --spawn-rate 10 --run-time 5m --headless --html=report_100users.html --csv=results_100users
```

#### Heavy Load Test (500 users, 10 minutes)
```powershell
locust -f locustfile.py --host=http://localhost:8081 --users 500 --spawn-rate 50 --run-time 10m --headless --html=report_500users.html --csv=results_500users
```

#### Stress Test (1000 users)
```powershell
locust -f locustfile.py --host=http://localhost:8081 --users 1000 --spawn-rate 50 --run-time 10m --headless --html=report_1000users.html --csv=results_1000users
```

#### Extreme Test (Create-Only, 20,000 users)
```powershell
locust -f locustfile.py --user-classes CreateOnlyUser --host=http://localhost:8081 --users 20000 --spawn-rate 100 --run-time 5m --headless --html=report_20k.html --csv=results_20k
```

---

## Understanding the Output

### Terminal Output (Live Statistics)

```
Type     Name                              # reqs      # fails |    Avg     Min     Max    Med | req/s failures/s
--------|--------------------------------|-------|-------------|-------|-------|-------|-------|-------|-----------
POST     /patients                         1250     0(0.00%) |    156      45     678    140 |  4.17    0.00
GET      /patients/{uuid}                   625     0(0.00%) |     71      21     198     65 |  2.08    0.00
GET      /patients/search/{id}              380     0(0.00%) |     67      18     189     61 |  1.27    0.00
PUT      /patients/{uuid}                   380     0(0.00%) |    134      41     456    126 |  1.27    0.00
DELETE   /patients/{uuid}                   120     0(0.00%) |    142      48     398    131 |  0.40    0.00
```

**Key Metrics:**
- **# reqs** - Total requests sent
- **# fails** - Failed requests (lower is better)
- **Avg** - Average response time (milliseconds)
- **Med** - Median response time (50th percentile)
- **req/s** - Throughput (requests per second)

### HTML Report

After running with `--html` flag, open the generated HTML file in your browser:

```powershell
# Open the report
.\report_100users.html
```

**Report includes:**
- Response time charts
- Request distribution
- Failure analysis
- Percentile breakdown (95th, 99th)
- Download/upload throughput

### CSV Files

Generated CSV files for further analysis:
- `results_100users_stats.csv` - Request statistics
- `results_100users_stats_history.csv` - Time-series data
- `results_100users_failures.csv` - Failed requests details

---

## Test Scenarios

### Mixed Workload Test (Default)

Uses `EHRUser` class that simulates realistic usage patterns:

**Task Weights:**
- ⚡ **10x** - Create Patient (most common)
- 🔍 **5x** - Get Patient by UUID
- 🔎 **3x** - Search Patient by ID
- 📋 **2x** - Get All Patients (pagination)
- ✏️ **3x** - Update Patient
- 🗑️ **1x** - Delete Patient (least common)

```powershell
locust -f locustfile.py --host=http://localhost:8081 --users 100 --spawn-rate 10 --run-time 5m --headless
```

### Create-Only Test

Uses `CreateOnlyUser` class that **only creates** patients (for maximum load testing):

```powershell
locust -f locustfile.py --user-classes CreateOnlyUser --host=http://localhost:8081 --users 1000 --spawn-rate 50 --run-time 5m --headless
```

---

## Recommended Testing Sequence

**Step-by-step approach to find your system's limits:**

1. **Baseline** (10 users, 1 min) - Verify everything works
2. **Light Load** (50 users, 3 min) - Check normal operation
3. **Medium Load** (100 users, 5 min) - Realistic usage
4. **Heavy Load** (500 users, 10 min) - Stress test
5. **Breaking Point** (1000+ users) - Find maximum capacity
6. **Spike Test** (sudden jump to 5000 users) - Test resilience

---

## Troubleshooting

### Issue: `AttributeError: 'Events' object has no attribute '__annotations__'`

**Cause:** Locust version incompatible with Python 3.14

**Solution:**
```powershell
pip install --upgrade locust
```

### Issue: Connection Refused / Cannot Connect

**Cause:** Port forwarding not set up or API Gateway not running

**Solution:**
```powershell
# Verify pods are running
kubectl get pods -n hospital-h1

# Port forward the API Gateway
kubectl port-forward -n hospital-h1 svc/hospital-api 8081:8080
```

### Issue: High Failure Rate

**Possible causes:**
1. **503 Raft leader unavailable** - Normal in distributed systems during leader elections
2. **404 Patient not found** - Race conditions (delete before read/update)
3. **500 Internal errors** - Check pod logs:

```powershell
# Check API Gateway logs
kubectl logs -n hospital-h1 hospital-0 -c api-gateway --tail=50

# Check P2P Raft logs
kubectl logs -n hospital-h1 hospital-0 -c p2p-raft --tail=50
```

### Issue: 422 Unprocessable Entity (Login Failed)

**Cause:** Authentication endpoint changed or credentials incorrect

**Solution:** Edit `locustfile.py` line 51 to match your auth endpoint format

---

## Performance Metrics Explained

### Response Time Percentiles

- **50th percentile (Median)**: Half of requests complete faster
- **95th percentile**: 95% of requests complete within this time
- **99th percentile**: 99% of requests complete within this time

**Example:** If 95th percentile is 200ms, then 95% of users experience ≤200ms response time.

### Success Rate

**Acceptable ranges:**
- **99%+** - Excellent
- **95-99%** - Good (some failures expected in distributed systems)
- **90-95%** - Acceptable under heavy load
- **<90%** - Investigate issues

### Throughput (req/s)

Requests per second the system can handle.

**Example targets:**
- Light load: 10-50 req/s
- Medium load: 50-200 req/s
- Heavy load: 200-1000 req/s
- Extreme: 1000+ req/s

---

## Advanced Usage

### Custom Test Duration

```powershell
# Run for specific duration
--run-time 30s   # 30 seconds
--run-time 5m    # 5 minutes
--run-time 2h    # 2 hours
```

### Distributed Load Testing

Run tests from multiple machines:

**Master machine:**
```powershell
locust -f locustfile.py --master --host=http://localhost:8081
```

**Worker machines:**
```powershell
locust -f locustfile.py --worker --master-host=<master-ip>
```

### Export Results to JSON

```powershell
locust -f locustfile.py --host=http://localhost:8081 --users 100 --spawn-rate 10 --run-time 5m --headless --json
```

---

## Quick Reference

| Command Parameter | Description | Example |
|------------------|-------------|---------|
| `-f` | Locust file path | `-f locustfile.py` |
| `--host` | Target host URL | `--host=http://localhost:8081` |
| `-u` / `--users` | Number of concurrent users | `--users 100` |
| `-r` / `--spawn-rate` | Users spawned per second | `--spawn-rate 10` |
| `-t` / `--run-time` | Test duration | `--run-time 5m` |
| `--headless` | Run without web UI | `--headless` |
| `--html` | Generate HTML report | `--html=report.html` |
| `--csv` | Generate CSV results | `--csv=results` |
| `--user-classes` | Specify user class | `--user-classes CreateOnlyUser` |

---

## Example: Complete Test Run

```powershell
# Terminal 1: Port forward (keep running)
kubectl port-forward -n hospital-h1 svc/hospital-api 8081:8080

# Terminal 2: Run test
cd C:\Users\canba\Desktop\workspace\distributed-ehr-node\performance-tests
locust -f locustfile.py --host=http://localhost:8081 --users 200 --spawn-rate 20 --run-time 5m --headless --html=report.html --csv=results

# After test completes, open the report
start report.html
```

---

## Tips for Best Results

✅ **Start small** - Begin with 10-50 users to verify everything works  
✅ **Increase gradually** - Double users each test to find breaking point  
✅ **Monitor pods** - Watch `kubectl get pods` during tests  
✅ **Check logs** - Use `kubectl logs` to investigate failures  
✅ **Run multiple times** - Verify consistent results  
✅ **Save reports** - Keep HTML/CSV reports for comparison  
✅ **Test different scenarios** - Mixed workload vs create-only  

---

## Support

If you encounter issues:
1. Check pod status: `kubectl get pods -n hospital-h1`
2. View logs: `kubectl logs -n hospital-h1 hospital-0 -c api-gateway`
3. Verify port forwarding is active
4. Ensure Python dependencies are installed

**Happy Testing!** 🚀

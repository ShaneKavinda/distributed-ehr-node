"""
Performance Testing for Distributed EHR System
===============================================
This script uses Locust to perform load testing on the EHR API Gateway.

Usage:
    # Install dependencies first
    pip install locust faker

    # Run the test with Web UI
    locust -f locustfile.py --host=http://localhost:8080

    # Run headless (no UI) with 20000 users
    locust -f locustfile.py --host=http://localhost:8080 --users 20000 --spawn-rate 100 --run-time 5m --headless

    # Run with custom parameters
    locust -f locustfile.py --host=http://localhost:8080 --users 1000 --spawn-rate 50 --run-time 2m --headless --html=report.html

KPIs Measured:
- Request throughput (requests/second)
- Response time (avg, min, max, percentiles)
- Success rate
- Failed requests
- Concurrent users handling
"""

import random
import json
from datetime import datetime, timedelta
from locust import HttpUser, task, between, events
from faker import Faker

fake = Faker()

# Store created patient UUIDs and IDs for read/update/delete operations
created_patients = []
patient_id_counter = 0

# Authentication tokens (you can add real tokens here)
DOCTOR_TOKEN = None
PATIENT_TOKEN = None


def get_doctor_token(client):
    """Get or refresh doctor authentication token"""
    global DOCTOR_TOKEN
    if DOCTOR_TOKEN:
        return DOCTOR_TOKEN

    try:
        response = client.post("/auth/login?username=doctor1&password=test")
        if response.status_code == 200:
            DOCTOR_TOKEN = response.json().get("access_token")
            return DOCTOR_TOKEN
    except Exception as e:
        print(f"Failed to get auth token: {e}")

    # Return a dummy token for testing without auth
    return "test-token"


def generate_patient_data():
    """Generate realistic patient data"""
    global patient_id_counter
    patient_id_counter += 1

    birth_date = fake.date_of_birth(minimum_age=0, maximum_age=100)
    sex_choice = random.choice(["male", "female", "other"])

    return {
        "identity": {
            "patientId": f"P-2026-{patient_id_counter:06d}",
            "mrn": f"MRN{random.randint(100000, 999999)}",
            "nationalId": fake.ssn()
        },
        "demographics": {
            "name": {
                "given": fake.first_name(),  # String, not array
                "family": fake.last_name()
            },
            "dob": birth_date.strftime("%Y-%m-%d"),  # Field name is "dob", not "birthDate"
            "sexAtBirth": sex_choice,  # Field name is "sexAtBirth", not "sex"
            "genderIdentity": sex_choice,  # Field name is "genderIdentity", not "gender"
            "deceased": False
        },
        "contacts": {
            "address": f"{fake.street_address()}, {fake.city()}, {fake.state()} {fake.zipcode()}, USA",  # String, not object
            "phone": fake.phone_number(),
            "email": fake.email()
        },
        "sourceHospital": f"Hospital-H{random.randint(1, 5)}"
    }


class EHRUser(HttpUser):
    """
    Simulates a user interacting with the EHR system.
    Tasks are weighted to simulate realistic usage patterns.
    """
    # Wait time between requests (1-3 seconds)
    wait_time = between(1, 3)

    def on_start(self):
        """Called when a user starts"""
        self.token = get_doctor_token(self.client)
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    @task(10)  # Weight: 10 - Most common operation
    def create_patient(self):
        """Create a new patient - PRIMARY KPI TEST"""
        patient_data = generate_patient_data()

        with self.client.post(
            "/patients",
            json=patient_data,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 201:
                try:
                    data = response.json()
                    # API returns 'id' (not 'uuid') and nested 'identity.patientId'
                    patient_uuid = data.get("id")
                    identity = data.get("identity")
                    patient_id = identity.get("patientId") if identity else None

                    if patient_uuid and patient_id:
                        created_patients.append({
                            "uuid": patient_uuid,
                            "patient_id": patient_id
                        })
                        response.success()
                    else:
                        response.failure(f"Patient created but missing ID or patientId. Response: {data}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
                except Exception as e:
                    response.failure(f"Error parsing response: {e}")
            elif response.status_code == 503:
                # Raft leader unavailable - this is expected in distributed systems
                response.failure("503: Raft leader unavailable")
            elif response.status_code == 500:
                # Check if it's a timeout/overload error
                try:
                    error_data = response.json()
                    detail = error_data.get("detail", "")
                    if "DEADLINE_EXCEEDED" in detail or "All pods unavailable" in detail:
                        response.failure("500: System overload - Request timeout (consider increasing timeouts)")
                    else:
                        response.failure(f"500: {detail[:150]}")
                except:
                    response.failure(f"500: {response.text[:150]}")
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(5)  # Weight: 5 - Common read operation
    def get_patient_by_uuid(self):
        """Retrieve a patient by UUID"""
        if not created_patients:
            return

        patient = random.choice(created_patients)
        with self.client.get(
            f"/patients/{patient['uuid']}",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.failure("Patient not found")
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(3)  # Weight: 3 - Search operation
    def search_patient_by_id(self):
        """Search for a patient by patient ID"""
        if not created_patients:
            return

        patient = random.choice(created_patients)
        with self.client.get(
            f"/patients/search/{patient['patient_id']}",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.failure("Patient not found")
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(2)  # Weight: 2 - List all patients (expensive operation)
    def get_all_patients(self):
        """Retrieve all patients with pagination"""
        skip = random.randint(0, 100)
        limit = random.choice([10, 50, 100])

        with self.client.get(
            f"/patients?skip={skip}&limit={limit}",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(3)  # Weight: 3 - Update operation
    def update_patient(self):
        """Update a patient's information"""
        if not created_patients:
            return

        patient = random.choice(created_patients)
        update_data = {
            "contacts": {
                "phone": fake.phone_number(),
                "email": fake.email()
            }
        }

        with self.client.put(
            f"/patients/{patient['uuid']}",
            json=update_data,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.failure("Patient not found")
            elif response.status_code == 503:
                response.failure("Raft leader unavailable")
            else:
                # Capture the actual error message from the response
                try:
                    error_detail = response.json().get("detail", "Unknown error")
                    response.failure(f"Failed with status {response.status_code}: {error_detail}")
                except:
                    response.failure(f"Failed with status {response.status_code}: {response.text[:200]}")

    @task(1)  # Weight: 1 - Least common operation
    def delete_patient(self):
        """Delete a patient (least common)"""
        if len(created_patients) < 10:  # Keep some patients in the system
            return

        patient = created_patients.pop(random.randint(0, len(created_patients) - 1))

        with self.client.delete(
            f"/patients/{patient['uuid']}",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.failure("Patient not found")
            elif response.status_code == 503:
                response.failure("Raft leader unavailable")
            else:
                # Capture the actual error message from the response
                try:
                    error_detail = response.json().get("detail", "Unknown error")
                    response.failure(f"Failed with status {response.status_code}: {error_detail}")
                except:
                    response.failure(f"Failed with status {response.status_code}: {response.text[:200]}")


class CreateOnlyUser(HttpUser):
    """
    User that ONLY creates patients - for testing the specific scenario
    of 20000 users creating patient data simultaneously.

    Usage:
        locust -f locustfile.py --user-classes CreateOnlyUser --host=http://localhost:8080 --users 20000 --spawn-rate 100 --run-time 5m --headless
    """
    wait_time = between(0.1, 0.5)  # Faster rate for stress testing

    def on_start(self):
        """Called when a user starts"""
        self.token = get_doctor_token(self.client)
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    @task
    def create_patient(self):
        """Create a new patient"""
        patient_data = generate_patient_data()

        with self.client.post(
            "/patients",
            json=patient_data,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 201:
                response.success()
            elif response.status_code == 503:
                response.failure("503: Raft leader unavailable")
            elif response.status_code == 500:
                # Check if it's a timeout/overload error
                try:
                    error_data = response.json()
                    detail = error_data.get("detail", "")
                    if "DEADLINE_EXCEEDED" in detail or "All pods unavailable" in detail:
                        response.failure("500: System overload - Request timeout")
                    else:
                        response.failure(f"500: {detail[:150]}")
                except:
                    response.failure(f"500: {response.text[:150]}")
            else:
                response.failure(f"Failed with status {response.status_code}: {response.text[:150]}")


# Event listeners for custom metrics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the test starts"""
    print("\n" + "="*80)
    print("DISTRIBUTED EHR SYSTEM - PERFORMANCE TEST STARTED")
    print("="*80)
    print(f"Target Host: {environment.host}")
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the test stops - print summary"""
    print("\n" + "="*80)
    print("DISTRIBUTED EHR SYSTEM - PERFORMANCE TEST COMPLETED")
    print("="*80)
    print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Patients Created: {len(created_patients)}")
    print("="*80 + "\n")

    # Print statistics
    stats = environment.stats
    print("\n📊 PERFORMANCE KPI SUMMARY:")
    print("-" * 80)

    for stat in stats.entries.values():
        if stat.num_requests > 0:
            print(f"\n🔹 {stat.method} {stat.name}")
            print(f"   Total Requests: {stat.num_requests}")
            print(f"   Failures: {stat.num_failures} ({stat.fail_ratio*100:.2f}%)")
            print(f"   Avg Response Time: {stat.avg_response_time:.2f} ms")
            print(f"   Min Response Time: {stat.min_response_time:.2f} ms")
            print(f"   Max Response Time: {stat.max_response_time:.2f} ms")
            print(f"   Median Response Time: {stat.median_response_time:.2f} ms")
            print(f"   95th Percentile: {stat.get_response_time_percentile(0.95):.2f} ms")
            print(f"   99th Percentile: {stat.get_response_time_percentile(0.99):.2f} ms")
            print(f"   Requests/sec: {stat.total_rps:.2f}")

    print("\n" + "="*80)
    print(f"🎯 Overall Success Rate: {(1 - stats.total.fail_ratio)*100:.2f}%")
    print(f"🎯 Total Throughput: {stats.total.total_rps:.2f} requests/sec")
    print(f"🎯 Average Response Time: {stats.total.avg_response_time:.2f} ms")
    print("="*80 + "\n")

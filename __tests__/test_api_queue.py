import pytest
from fastapi.testclient import TestClient
import os
from pathlib import Path
import uuid
import time

from src.api import app, processing_jobs, active_tasks
import src.api as api_mod

# Test client
client = TestClient(app)

# Test data
TEST_API_KEY = "test_api_key"
TEST_TICKER = "TEST"
TEST_YEAR = 2024
TEST_ORIGIN = f"test_queue_{uuid.uuid4()}"


@pytest.fixture(autouse=True)
def setup_test_env():
    """Setup test environment before each test."""
    # Store original environment variables
    original_env = {}
    for key in [
        "FFS_API_KEY",
        "OPENAI_API_KEY",
        "API_NINJAS_KEY",
        "GOOGLE_DRIVE_ROOT_FOLDER_ID",
        "JOB_QUEUE_BUCKET",
    ]:
        original_env[key] = os.environ.get(key)

    # Set test environment variables
    os.environ["FFS_API_KEY"] = TEST_API_KEY
    os.environ["OPENAI_API_KEY"] = "test_openai_key"
    os.environ["API_NINJAS_KEY"] = "test_ninjas_key"
    os.environ["GOOGLE_DRIVE_ROOT_FOLDER_ID"] = "test_folder_id"
    os.environ["JOB_QUEUE_BUCKET"] = "test-bucket"

    # ensure local queue directory is empty
    qdir = Path("temp/job_queue")
    if qdir.exists():
        for f in qdir.glob("*.json"):
            f.unlink()

    # Clear jobs and tasks before each test
    processing_jobs.clear()
    for task in list(active_tasks.values()):
        task.cancel()
    active_tasks.clear()

    yield

    # Restore original environment variables
    for key, value in original_env.items():
        if value is not None:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)

    # Cleanup after each test
    processing_jobs.clear()
    for task in list(active_tasks.values()):
        task.cancel()
    active_tasks.clear()
    if qdir.exists():
        for f in qdir.glob("*.json"):
            f.unlink()


@pytest.fixture(autouse=True)
def _patch_process(monkeypatch):
    async def _instant(job_id: str, req):
        pass

    monkeypatch.setattr(api_mod, "_process", _instant)
    yield


def test_queue_single_job():
    """Test that a single job is properly queued."""
    response = client.post(
        "/process",
        headers={"X-API-Key": TEST_API_KEY},
        json={"ticker": TEST_TICKER, "year": TEST_YEAR, "point_of_origin": TEST_ORIGIN},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list) and len(data) == 4
    for receipt in data:
        assert receipt["status"] == "queued"
        assert receipt["message"] == "Job queued"
        assert receipt["job_id"] in processing_jobs
        assert processing_jobs[receipt["job_id"]]["status"] in {
            "queued",
            "processing",
            "completed",
        }


def test_queue_multiple_jobs():
    """Test that multiple jobs are properly queued."""
    # Queue 3 jobs
    job_ids = []
    for quarter in [1, 2, 3]:
        response = client.post(
            "/process",
            headers={"X-API-Key": TEST_API_KEY},
            json={
                "ticker": TEST_TICKER,
                "year": TEST_YEAR,
                "quarter": quarter,
                "point_of_origin": TEST_ORIGIN,
            },
        )
        assert response.status_code == 200
        job_ids.append(response.json()["job_id"])

    # Check that all jobs are in processing_jobs
    assert len(processing_jobs) == 3
    for job_id in job_ids:
        assert job_id in processing_jobs
        assert processing_jobs[job_id]["status"] in {
            "queued",
            "processing",
            "completed",
        }


def test_list_all_jobs(monkeypatch):
    """Test that /updates returns jobs with correct metadata and filtering."""
    print("\n=== Starting test_list_all_jobs ===")

    # Clear any existing jobs
    print("\n1. Clearing existing jobs...")
    processing_jobs.clear()
    for task in list(active_tasks.values()):
        task.cancel()
    active_tasks.clear()

    # Queue a test job
    print("\n2. Queueing test job...")
    response = client.post(
        "/process",
        headers={"X-API-Key": TEST_API_KEY},
        json={
            "ticker": TEST_TICKER,
            "year": TEST_YEAR,
            "quarter": 1,
            "point_of_origin": TEST_ORIGIN,
        },
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    print(f"  - Created job: {job_id}")

    monkeypatch.setattr(
        api_mod.job_queue, "list_jobs", lambda: [processing_jobs[job_id]]
    )

    # Wait for GCS operations to complete
    time.sleep(1)

    # Get jobs via /updates
    print("\n3. Fetching jobs via /updates...")
    response = client.get("/updates", headers={"X-API-Key": TEST_API_KEY})
    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "user_requested_jobs" in data
    assert "in_progress_server_tasks" in data

    # Find our test job
    jobs = [job for job in data["user_requested_jobs"] if job["job_id"] == job_id]
    assert len(jobs) == 1, f"Expected to find exactly one job with ID {job_id}"
    job = jobs[0]

    # Verify job metadata
    assert job["status"] in {"queued", "processing", "completed"}
    assert job["point_of_origin"] == TEST_ORIGIN
    assert "time_received" in job
    assert "version" in job
    assert job["version"] == 1

    # Verify job request data
    assert "request" in job
    assert job["request"]["ticker"] == TEST_TICKER
    assert job["request"]["year"] == TEST_YEAR
    assert job["request"]["quarter"] == 1

    print("\n=== test_list_all_jobs completed successfully ===")


def test_job_status_updates(monkeypatch):
    """Test that job status is properly updated."""
    # Queue a job
    response = client.post(
        "/process",
        headers={"X-API-Key": TEST_API_KEY},
        json={"ticker": TEST_TICKER, "year": TEST_YEAR, "point_of_origin": TEST_ORIGIN},
    )
    job_id = response.json()[0]["job_id"]

    monkeypatch.setattr(
        api_mod.job_queue, "list_jobs", lambda: [processing_jobs[job_id]]
    )

    # Check initial status via /updates
    response = client.get("/updates", headers={"X-API-Key": TEST_API_KEY})
    assert response.status_code == 200
    jobs = {j["job_id"]: j for j in response.json()["user_requested_jobs"]}
    assert jobs[job_id]["status"] in {"queued", "processing", "completed"}

    # Manually update status to simulate processing
    processing_jobs[job_id]["status"] = "processing"
    processing_jobs[job_id]["message"] = "Job started"

    # Check updated status via /updates
    response = client.get("/updates", headers={"X-API-Key": TEST_API_KEY})
    assert response.status_code == 200
    jobs = {j["job_id"]: j for j in response.json()["user_requested_jobs"]}
    assert jobs[job_id]["status"] == "processing"
    assert jobs[job_id]["message"] == "Job started"


def test_job_id_format():
    """Test that job IDs are properly formatted."""
    response = client.post(
        "/process",
        headers={"X-API-Key": TEST_API_KEY},
        json={
            "ticker": TEST_TICKER,
            "year": TEST_YEAR,
            "quarter": 1,
            "point_of_origin": TEST_ORIGIN,
        },
    )
    job_id = response.json()["job_id"]

    # Format: TICKER_YEAR_QQUARTER_YYYYMMDD_HHMMSS_micro
    parts = job_id.split("_")
    assert len(parts) == 6  # ← was 5
    assert parts[0] == TEST_TICKER.upper()
    assert parts[1] == str(TEST_YEAR)
    assert parts[2] == "Q1"
    assert len(parts[3]) == 8  # YYYYMMDD
    assert len(parts[4]) == 6  # HHMMSS
    assert len(parts[5]) == 6 and parts[5].isdigit()  # micro-seconds


def test_parallel_processing_starts_all_jobs():
    """Multiple jobs should be tracked immediately."""
    job_ids = []
    for quarter in [1, 2, 3]:
        response = client.post(
            "/process",
            headers={"X-API-Key": TEST_API_KEY},
            json={
                "ticker": TEST_TICKER,
                "year": TEST_YEAR,
                "quarter": quarter,
                "point_of_origin": TEST_ORIGIN,
            },
        )
        job_ids.append(response.json()["job_id"])

    assert len(processing_jobs) == 3
    for jid in job_ids:
        assert jid in processing_jobs


def test_invalid_api_key():
    """Test that invalid API key is rejected."""
    response = client.post(
        "/process",
        headers={"X-API-Key": "invalid_key"},
        json={"ticker": TEST_TICKER, "year": TEST_YEAR},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid API key"


def test_missing_required_fields():
    """Test that missing required fields are rejected."""
    response = client.post(
        "/process",
        headers={"X-API-Key": TEST_API_KEY},
        json={"ticker": TEST_TICKER},  # Missing year
    )
    assert response.status_code == 422  # Validation error


def test_invalid_quarter():
    """Test that invalid quarter values are rejected."""
    response = client.post(
        "/process",
        headers={"X-API-Key": TEST_API_KEY},
        json={
            "ticker": TEST_TICKER,
            "year": TEST_YEAR,
            "quarter": 5,
        },  # Invalid quarter
    )
    assert response.status_code == 422  # Validation error


def test_full_year_splits_into_four_jobs():
    """Request without quarter should create four jobs."""
    response = client.post(
        "/process",
        headers={"X-API-Key": TEST_API_KEY},
        json={"ticker": TEST_TICKER, "year": TEST_YEAR, "point_of_origin": TEST_ORIGIN},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list) and len(data) == 4
    ids = [d["job_id"] for d in data]
    assert len(ids) == len(set(ids))
    for jid in ids:
        assert jid in processing_jobs
        assert processing_jobs[jid]["status"] in {"queued", "processing", "completed"}


def test_updates_removes_deleted_jobs(monkeypatch):
    """Jobs deleted from GCS should not be returned."""
    job_id = "STALE_JOB"
    processing_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "request": {"ticker": TEST_TICKER, "year": TEST_YEAR, "quarter": 1},
        "point_of_origin": TEST_ORIGIN,
        "version": 1,
    }

    monkeypatch.setattr(api_mod.job_queue, "list_jobs", lambda: [])

    response = client.get("/updates", headers={"X-API-Key": TEST_API_KEY})
    assert response.status_code == 200
    jobs = {j["job_id"] for j in response.json()["user_requested_jobs"]}
    assert job_id not in jobs
    assert job_id not in processing_jobs

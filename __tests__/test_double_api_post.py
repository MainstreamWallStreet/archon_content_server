"""
Regression test – make sure /process doesn't "stay open" on a second POST
while the first job is still queued/processing, and that each request
gets its own unique job_id.
"""

import time
from fastapi.testclient import TestClient
import pytest
from pathlib import Path
import os
import uuid
from google.cloud import storage
from google.api_core import exceptions

from src.api import app, processing_jobs, active_tasks
import src.api as api_mod  # for monkey-patching


# ──────────────────
# constants
# ──────────────────
API_KEY = "test_api_key"
PAYLOAD = {
    "ticker": "AAPL",
    "year": 2023,
    "quarter": 1,
    "point_of_origin": "test_double_post",
}
HEADERS = {"X-API-Key": API_KEY}
MAX_LATENCY = 10.0  # seconds – allow for GCS latency


def create_test_bucket():
    """Create a unique test bucket for this test run."""
    storage_client = storage.Client()
    bucket_name = f"raven-test-{os.getpid()}-{uuid.uuid4().hex[:8]}"

    try:
        storage_client.create_bucket(bucket_name, location="us-central1")
        print(f"Created test bucket: {bucket_name}")
        return bucket_name
    except exceptions.Conflict:
        # If bucket already exists (unlikely with UUID), try again
        return create_test_bucket()


def delete_test_bucket(bucket_name):
    """Delete the test bucket and all its contents."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)

        # Delete all blobs first
        blobs = list(storage_client.list_blobs(bucket_name))
        for blob in blobs:
            blob.delete()

        # Then delete the bucket
        bucket.delete()
        print(f"Deleted test bucket: {bucket_name}")
    except Exception as e:
        print(f"Warning: Could not delete test bucket {bucket_name}: {e}")


# ──────────────────
# env + queue cleanup
# ──────────────────
@pytest.fixture(autouse=True)
def _env_and_cleanup(monkeypatch):
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
    monkeypatch.setenv("FFS_API_KEY", API_KEY)
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("API_NINJAS_KEY", "dummy")
    monkeypatch.setenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "dummy")

    # Create a unique test bucket for this test run
    test_bucket = create_test_bucket()
    monkeypatch.setenv("JOB_QUEUE_BUCKET", test_bucket)

    # ensure clean slate
    processing_jobs.clear()
    qdir = Path("temp/job_queue")
    if qdir.exists():
        for f in qdir.glob("*.json"):
            f.unlink()
    for t in list(active_tasks.values()):
        t.cancel()
    active_tasks.clear()

    yield

    # Restore original environment variables
    for key, value in original_env.items():
        if value is not None:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)

    processing_jobs.clear()
    if qdir.exists():
        for f in qdir.glob("*.json"):
            f.unlink()
    for t in list(active_tasks.values()):
        t.cancel()
    active_tasks.clear()

    # Delete the test bucket
    delete_test_bucket(test_bucket)


# ──────────────────
# stub out heavy worker
# ──────────────────
@pytest.fixture(autouse=True)
def _patch_process(monkeypatch):
    async def _instant_success(job_id: str, req):
        processing_jobs[job_id]["status"] = "completed"
        processing_jobs[job_id]["message"] = "Done (stubbed)"

    monkeypatch.setattr(api_mod, "_process", _instant_success)
    yield


# ──────────────────
# the regression test
# ──────────────────
def test_two_quick_posts_dont_block():
    client = TestClient(app)

    start = time.perf_counter()

    # 1️⃣ first request
    r1 = client.post("/process", json=PAYLOAD, headers=HEADERS)
    assert r1.status_code == 200
    id1 = r1.json()["job_id"]

    # 2️⃣ immediate second request
    r2 = client.post("/process", json=PAYLOAD, headers=HEADERS)
    assert r2.status_code == 200
    id2 = r2.json()["job_id"]

    # endpoint latency must remain low
    elapsed = time.perf_counter() - start
    assert elapsed < MAX_LATENCY, f"/process took {elapsed:.3f}s (> {MAX_LATENCY}s)"

    # both requests must enqueue one unique job each
    assert id1 != id2, "job_id collision – IDs must be unique"
    assert id1 in processing_jobs and id2 in processing_jobs
    assert processing_jobs[id1]["status"] in {"queued", "processing", "completed"}
    assert processing_jobs[id2]["status"] in {"queued", "processing", "completed"}


def test_three_quick_posts_dont_block():
    client = TestClient(app)

    start = time.perf_counter()

    ids = []
    for _ in range(3):
        r = client.post("/process", json=PAYLOAD, headers=HEADERS)
        assert r.status_code == 200
        ids.append(r.json()["job_id"])

    elapsed = time.perf_counter() - start
    assert elapsed < MAX_LATENCY, f"/process took {elapsed:.3f}s (> {MAX_LATENCY}s)"

    assert len(ids) == len(set(ids))
    for jid in ids:
        assert jid in processing_jobs
        assert processing_jobs[jid]["status"] in {"queued", "processing", "completed"}

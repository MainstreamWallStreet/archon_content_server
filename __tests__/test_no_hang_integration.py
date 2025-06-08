"""
End-to-end regression: every /process request must respond promptly
even while a long-running job is in progress.

Prereqs:
  * pytest-timeout
  * httpx      – more convenient async client than requests
"""

import threading
import httpx
import pytest
from src.api import app
from fastapi.testclient import TestClient
from pathlib import Path
import os
import uuid
from google.cloud import storage
from google.api_core import exceptions

API_KEY = "test_api_key"
HEADERS = {"X-API-Key": API_KEY}
PAYLOAD = {
    "ticker": "AAPL",
    "year": 2023,
    "quarter": 1,
    "point_of_origin": "test_no_hang",
}
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


@pytest.fixture(autouse=True)
def _minimal_env(monkeypatch):
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

    qdir = Path("temp/job_queue")
    if qdir.exists():
        for f in qdir.glob("*.json"):
            f.unlink()

    yield

    # Restore original environment variables
    for key, value in original_env.items():
        if value is not None:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)

    # Delete the test bucket
    delete_test_bucket(test_bucket)


def _post_sync(client: TestClient, results: list[str]):
    """Helper run in a thread so we can join(timeout=…)"""
    r = client.post("/process", json=PAYLOAD, headers=HEADERS, timeout=MAX_LATENCY)
    results.append(r)


@pytest.mark.timeout(MAX_LATENCY + 0.2)  # extra head-room per-test
def test_process_never_hangs_under_load():
    client = TestClient(app)

    # 1️⃣ Kick off a first job (this may start the long, blocking _process)
    r1 = client.post("/process", json=PAYLOAD, headers=HEADERS)
    assert r1.status_code == 200

    # 2️⃣ Immediately issue a second request in a background thread
    results: list[httpx.Response] = []
    t = threading.Thread(target=_post_sync, args=(client, results), daemon=True)
    t.start()
    t.join(timeout=MAX_LATENCY)  # -> Fail if handler blocks the event loop

    # If we're still here, the request returned (thread joined)
    assert results, "Second request never returned (hang)"
    assert results[0].status_code == 200, results[0].text

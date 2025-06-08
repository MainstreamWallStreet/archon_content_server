import asyncio
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import os
import uuid
from unittest.mock import MagicMock, patch
from google.cloud import storage
from google.api_core import exceptions

from src.api import app, task_queue, processing_jobs, active_tasks
import src.api as api_mod

API_KEY = "test_api_key"
HEADERS = {"X-API-Key": API_KEY}
PAYLOAD = {
    "ticker": "AAPL",
    "year": 2024,
    "quarter": 1,
    "point_of_origin": f"test_many_jobs_{uuid.uuid4()}",
}


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
def _env(monkeypatch):
    """Minimal environment and cleanup."""
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
    monkeypatch.setenv("JOB_QUEUE_BUCKET", "test-bucket")
    monkeypatch.setattr(api_mod, "MAX_CONCURRENT_JOBS", 10, raising=False)

    processing_jobs.clear()
    qdir = Path("temp/job_queue")
    if qdir.exists():
        for f in qdir.glob("*.json"):
            f.unlink()
    # Cancel any existing worker tasks and clear globals to ensure a clean state
    for t in list(active_tasks.values()):
        t.cancel()
    active_tasks.clear()

    # Drain any pending items in the global task queue so we start fresh
    try:
        while True:
            task_queue.get_nowait()
            task_queue.task_done()
    except asyncio.QueueEmpty:
        pass

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

    # Drain the queue again to restore pristine state for following tests
    try:
        while True:
            task_queue.get_nowait()
            task_queue.task_done()
    except asyncio.QueueEmpty:
        pass


@pytest.fixture(autouse=True)
def _patch_process(monkeypatch):
    async def _stub(job_id: str, _req):
        """Quick stub that marks the job done without touching the queue.

        The real queue bookkeeping (``task_queue.task_done``) is handled by
        the job worker in ``src.api._job_worker``. Calling it here as well
        causes a mismatch between ``put``/``task_done`` calls and makes
        ``task_queue.join`` block forever. We therefore only update the
        in-memory job state and return immediately.
        """
        print(f"stub processing {job_id}")
        await asyncio.sleep(0.01)
        processing_jobs[job_id]["status"] = "completed"
        processing_jobs[job_id]["message"] = "Done (stubbed)"

    monkeypatch.setattr(api_mod, "_process", _stub)
    yield


async def _wait_for_completion(expected: int, timeout: float = 10.0):
    """Poll ``processing_jobs`` until the expected number are completed.

    Relying on the internal implementation details of ``asyncio.Queue`` is
    brittle (attributes may change between Python versions).  Instead we watch
    the high-level state that the application tracks for us.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        if len(processing_jobs) == expected and all(
            j["status"] == "completed" for j in processing_jobs.values()
        ):
            return
        if asyncio.get_event_loop().time() >= deadline:
            raise TimeoutError(
                f"Timed out waiting for {expected} completed jobs. Currently have {len(processing_jobs)} total; "
                f"completed={sum(1 for j in processing_jobs.values() if j['status']=='completed')}"
            )
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_many_jobs_complete():
    # Mock the GCS client
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.exists.return_value = True

    # Mock the blob operations
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_blob.exists.return_value = False  # Simulate new job creation

    # Mock the job queue
    mock_job_queue = MagicMock()
    mock_job_queue.create_job.return_value = {
        "status": "queued",
        "message": "Job queued",
    }
    mock_job_queue.update_job.return_value = None
    mock_job_queue.list_jobs.return_value = []

    with patch("google.cloud.storage.Client", return_value=mock_client), patch(
        "src.api.job_queue", mock_job_queue
    ), TestClient(app) as client:
        print("worker tasks:", len(api_mod.worker_tasks))

        # Submit 50 jobs, each with a unique point_of_origin
        responses = []
        for i in range(50):
            payload = dict(PAYLOAD)
            payload["point_of_origin"] = f"test_many_jobs_{i}_{uuid.uuid4()}"
            response = client.post("/process", json=payload, headers=HEADERS)
            responses.append(response)

        # Verify all responses
        for r in responses:
            assert r.status_code == 200

        # Wait for all jobs to complete with timeout
        await _wait_for_completion(expected=50)

        # Verify final state
        assert len(processing_jobs) == 50
        assert all(m["status"] == "completed" for m in processing_jobs.values())

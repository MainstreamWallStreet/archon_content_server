import pytest
from unittest.mock import Mock, patch
from google.cloud.exceptions import GoogleCloudError

from src.gcs_job_queue import GcsJobQueue


@pytest.fixture
def mock_storage_client():
    with patch("google.cloud.storage.Client") as mock_client:
        mock_bucket = Mock()
        mock_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.exists.return_value = True
        yield mock_client


@pytest.fixture
def job_queue(mock_storage_client):
    return GcsJobQueue("test-bucket")


def test_create_job_saves_to_gcs(job_queue, mock_storage_client):
    """Test that job creation is synchronous with GCS save."""
    # Arrange
    job_id = "TEST_2020_Q1_123456"
    request = {"ticker": "TEST", "year": 2020, "quarter": 1}
    point_of_origin = "test_origin"

    # Act
    job = job_queue.create_job(job_id, request, point_of_origin)

    # Assert
    mock_bucket = mock_storage_client.return_value.bucket.return_value
    mock_bucket.blob.assert_called_once()
    mock_blob = mock_bucket.blob.return_value
    mock_blob.upload_from_string.assert_called_once()

    # Verify job data
    assert job["job_id"] == job_id
    assert job["status"] == "queued"
    assert job["version"] == 1
    assert job["point_of_origin"] == point_of_origin
    assert job["transcript_url"] is None
    assert job["transcript_date"] is None


def test_create_job_handles_gcs_error(job_queue, mock_storage_client):
    """Test that GCS errors during job creation are properly handled."""
    # Arrange
    mock_bucket = mock_storage_client.return_value.bucket.return_value
    mock_blob = mock_bucket.blob.return_value
    mock_blob.upload_from_string.side_effect = GoogleCloudError("Test error")

    # Act & Assert
    with pytest.raises(RuntimeError) as exc_info:
        job_queue.create_job("TEST_2020_Q1_123456", {}, "test_origin")
    assert "Failed to save job" in str(exc_info.value)


def test_list_jobs_handles_missing_gcs_files(job_queue, mock_storage_client):
    """Test that listing jobs handles missing GCS files gracefully."""
    # Arrange
    mock_bucket = mock_storage_client.return_value.bucket.return_value
    mock_blob = mock_bucket.blob.return_value
    mock_blob.exists.return_value = False

    # Act
    jobs = job_queue.list_jobs()

    # Assert
    assert jobs == []


def test_update_job_ensures_version(job_queue, mock_storage_client):
    """Test that job updates ensure version field is present."""
    # Arrange
    job_id = "TEST_2020_Q1_123456"
    mock_bucket = mock_storage_client.return_value.bucket.return_value
    mock_blob = mock_bucket.blob.return_value
    mock_blob.download_as_text.return_value = '{"job_id": "TEST_2020_Q1_123456"}'

    # Act
    job_queue.update_job(job_id, status="processing")

    # Assert
    mock_blob.upload_from_string.assert_called_once()
    uploaded_data = mock_blob.upload_from_string.call_args[0][0]
    assert '"version": 1' in uploaded_data


def test_race_condition_handling(job_queue, mock_storage_client):
    """Test that the job queue handles race conditions between memory and GCS."""
    # Arrange
    job_id = "TEST_2020_Q1_123456"
    mock_bucket = mock_storage_client.return_value.bucket.return_value
    mock_blob = mock_bucket.blob.return_value

    # Simulate job in memory but not in GCS
    mock_blob.exists.return_value = False

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        job_queue.update_job(job_id, status="processing")
    assert "Job not found" in str(exc_info.value)

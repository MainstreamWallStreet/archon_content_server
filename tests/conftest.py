"""
Test configuration and fixtures for FastAPI template.
"""

import asyncio
import json
import os
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from google.cloud import storage

from src.api import app
from src.config import get_setting
from src.database import DataStore
from src.gcs_store import GcsStore
from src.models import Item, ItemCreate, ItemUpdate


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_client() -> TestClient:
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def mock_gcs_client() -> MagicMock:
    """Mock Google Cloud Storage client."""
    with patch("src.gcs_store.storage.Client") as mock_client:
        # Mock bucket
        mock_bucket = MagicMock()
        mock_bucket.exists.return_value = True
        mock_client.return_value.bucket.return_value = mock_bucket
        
        yield mock_client


@pytest.fixture
def mock_data_store(mock_gcs_client: MagicMock) -> GcsStore:
    """Create a mock data store for testing."""
    return GcsStore("test-bucket")


@pytest.fixture
def sample_item() -> Item:
    """Create a sample item for testing."""
    return Item(
        id="test-item-1",
        name="Test Item",
        description="A test item",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z"
    )


@pytest.fixture
def sample_item_create() -> ItemCreate:
    """Create a sample item creation request for testing."""
    return ItemCreate(
        name="New Test Item",
        description="A new test item"
    )


@pytest.fixture
def sample_item_update() -> ItemUpdate:
    """Create a sample item update request for testing."""
    return ItemUpdate(
        name="Updated Test Item",
        description="An updated test item"
    )


@pytest.fixture
def mock_secret_manager() -> MagicMock:
    """Mock Google Secret Manager client."""
    with patch("src.config.secretmanager.SecretManagerServiceClient") as mock_client:
        mock_response = MagicMock()
        mock_response.payload.data.decode.return_value = "test-secret"
        mock_client.return_value.access_secret_version.return_value = mock_response
        
        yield mock_client


@pytest.fixture
def mock_scheduler() -> MagicMock:
    """Mock background scheduler."""
    with patch("src.scheduler.BackgroundScheduler") as mock_scheduler:
        mock_instance = MagicMock()
        mock_scheduler.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def api_key_header() -> dict:
    """Return API key header for authenticated requests."""
    return {"X-API-Key": "test-api-key"}


@pytest.fixture
def invalid_api_key_header() -> dict:
    """Return invalid API key header for testing authentication."""
    return {"X-API-Key": "invalid-key"}


@pytest.fixture
def mock_env_vars() -> None:
    """Set up mock environment variables for testing."""
    test_env = {
        "APP_NAME": "test-app",
        "API_KEY": "test-api-key",
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "STORAGE_BUCKET": "test-bucket",
        "ENV": "test"
    }
    
    with patch.dict(os.environ, test_env):
        yield


@pytest.fixture
def mock_gcs_bucket_data() -> dict:
    """Mock GCS bucket data for testing."""
    return {
        "items": [
            {
                "id": "item-1",
                "name": "Test Item 1",
                "description": "First test item",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": "item-2", 
                "name": "Test Item 2",
                "description": "Second test item",
                "created_at": "2024-01-02T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z"
            }
        ]
    }


@pytest.fixture
def mock_gcs_blob() -> MagicMock:
    """Mock GCS blob for testing."""
    mock_blob = MagicMock()
    mock_blob.exists.return_value = True
    mock_blob.download_as_text.return_value = json.dumps({"test": "data"})
    return mock_blob


@pytest.fixture
def mock_gcs_bucket(mock_gcs_blob: MagicMock) -> MagicMock:
    """Mock GCS bucket for testing."""
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_gcs_blob
    mock_bucket.exists.return_value = True
    return mock_bucket


@pytest.fixture
def mock_storage_client(mock_gcs_bucket: MagicMock) -> MagicMock:
    """Mock storage client for testing."""
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_gcs_bucket
    return mock_client 
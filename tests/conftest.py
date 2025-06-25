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

from src.api import app
from src.config import get_setting
from src.database import DataStore
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
def sample_item() -> Item:
    """Create a sample item for testing."""
    return Item(
        id="test-item-1",
        name="Test Item",
        description="A test item",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )


@pytest.fixture
def sample_item_create() -> ItemCreate:
    """Create a sample item creation request for testing."""
    return ItemCreate(name="New Test Item", description="A new test item")


@pytest.fixture
def sample_item_update() -> ItemUpdate:
    """Create a sample item update request for testing."""
    return ItemUpdate(name="Updated Test Item", description="An updated test item")


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


@pytest.fixture(autouse=True)
def test_env():
    """Set up test environment variables."""
    with patch.dict(
        os.environ,
        {
            "ARCHON_API_KEY": "test-api-key",
        },
    ):
        yield

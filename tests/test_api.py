"""
Tests for FastAPI endpoints.
"""

import json
from typing import List
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.models import (
    Item,
    ItemCreate,
    ItemUpdate,
)


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_endpoint(self, test_client: TestClient, api_key_header: dict):
        """Test root endpoint returns health status."""
        with patch("src.api.get_setting", return_value="test-api-key"):
            response = test_client.get("/", headers=api_key_header)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "message" in data

    def test_health_endpoint(self, test_client: TestClient):
        """Test health endpoint returns detailed status."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data


class TestAuthentication:
    """Test API key authentication."""

    def test_authenticated_endpoint_with_valid_key(
        self, test_client: TestClient, api_key_header: dict
    ):
        """Test authenticated endpoint with valid API key."""
        with patch("src.api.get_setting", return_value="test-api-key"):
            response = test_client.get("/items", headers=api_key_header)
            # Should not return 401 (Unauthorized)
            assert response.status_code != 401

    def test_authenticated_endpoint_without_key(self, test_client: TestClient):
        """Test authenticated endpoint without API key."""
        response = test_client.get("/items")
        assert response.status_code == 403  # FastAPI returns 403 if header is missing
        data = response.json()
        assert "detail" in data

    def test_authenticated_endpoint_with_invalid_key(
        self, test_client: TestClient, invalid_api_key_header: dict
    ):
        """Test authenticated endpoint with invalid API key."""
        with patch("src.api.get_setting", return_value="test-api-key"):
            response = test_client.get("/items", headers=invalid_api_key_header)
            assert response.status_code == 401
            data = response.json()
            assert "detail" in data

    def test_unauthenticated_endpoint(self, test_client: TestClient):
        """Test unauthenticated endpoint (health check)."""
        response = test_client.get("/health")
        assert response.status_code == 200


class TestItemsEndpoints:
    """Test items CRUD endpoints."""

    def test_list_items_empty(self, test_client: TestClient, api_key_header: dict):
        """Test listing items when none exist."""
        with patch("src.api.get_setting", return_value="test-api-key"):
            with patch("src.api.data_store") as mock_store:
                mock_store.list_items.return_value = []

                response = test_client.get("/items", headers=api_key_header)
                assert response.status_code == 200
                data = response.json()
                assert data["items"] == []
                assert data["total"] == 0

    def test_list_items_with_data(self, test_client: TestClient, api_key_header: dict):
        """Test listing items with existing data."""
        sample_items = [
            Item(
                id="item-1",
                name="Test Item 1",
                description="First item",
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            ),
            Item(
                id="item-2",
                name="Test Item 2",
                description="Second item",
                created_at="2024-01-02T00:00:00Z",
                updated_at="2024-01-02T00:00:00Z",
            ),
        ]

        with patch("src.api.get_setting", return_value="test-api-key"):
            with patch("src.api.data_store") as mock_store:
                mock_store.list_items.return_value = sample_items

                response = test_client.get("/items", headers=api_key_header)
                assert response.status_code == 200
                data = response.json()
                assert len(data["items"]) == 2
                assert data["total"] == 2
                assert data["items"][0]["id"] == "item-1"
                assert data["items"][1]["id"] == "item-2"

    def test_list_items_store_error(
        self, test_client: TestClient, api_key_header: dict
    ):
        """Test listing items when store raises error."""
        with patch("src.api.get_setting", return_value="test-api-key"):
            with patch("src.api.data_store") as mock_store:
                mock_store.list_items.side_effect = RuntimeError("Store error")

                response = test_client.get("/items", headers=api_key_header)
                assert response.status_code == 500
                data = response.json()
                assert "detail" in data

    def test_get_item_exists(self, test_client: TestClient, api_key_header: dict):
        """Test getting an existing item."""
        sample_item = Item(
            id="item-1",
            name="Test Item",
            description="A test item",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        with patch("src.api.get_setting", return_value="test-api-key"):
            with patch("src.api.data_store") as mock_store:
                mock_store.get_item.return_value = sample_item

                response = test_client.get("/items/item-1", headers=api_key_header)
                assert response.status_code == 200
                data = response.json()
                assert data["id"] == "item-1"
                assert data["name"] == "Test Item"

    def test_get_item_not_exists(self, test_client: TestClient, api_key_header: dict):
        """Test getting a non-existent item."""
        with patch("src.api.get_setting", return_value="test-api-key"):
            with patch("src.api.data_store") as mock_store:
                mock_store.get_item.return_value = None

                response = test_client.get(
                    "/items/non-existent", headers=api_key_header
                )
                assert response.status_code == 404
                data = response.json()
                assert "detail" in data

    def test_create_item_success(self, test_client: TestClient, api_key_header: dict):
        """Test creating a new item."""
        item_data = {"name": "New Item", "description": "A new item"}

        created_item = Item(
            id="new-item-id",
            name="New Item",
            description="A new item",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        with patch("src.api.get_setting", return_value="test-api-key"):
            with patch("src.api.data_store") as mock_store:
                mock_store.create_item.return_value = created_item

                response = test_client.post(
                    "/items", headers=api_key_header, json=item_data
                )
                assert response.status_code == 201
                data = response.json()
                assert data["id"] == "new-item-id"
                assert data["name"] == "New Item"

                # Verify the store was called with correct data
                mock_store.create_item.assert_called_once()
                call_args = mock_store.create_item.call_args[0][0]
                assert call_args.name == "New Item"
                assert call_args.description == "A new item"

    def test_create_item_invalid_data(
        self, test_client: TestClient, api_key_header: dict
    ):
        """Test creating item with invalid data."""
        invalid_data = {"description": "Missing name"}

        with patch("src.api.get_setting", return_value="test-api-key"):
            response = test_client.post(
                "/items", headers=api_key_header, json=invalid_data
            )
            assert response.status_code == 422  # Validation error

    def test_create_item_already_exists(
        self, test_client: TestClient, api_key_header: dict
    ):
        """Test creating item that already exists."""
        item_data = {"name": "Existing Item", "description": "An existing item"}

        with patch("src.api.get_setting", return_value="test-api-key"):
            with patch("src.api.data_store") as mock_store:
                mock_store.create_item.side_effect = ValueError("Item already exists")

                response = test_client.post(
                    "/items", headers=api_key_header, json=item_data
                )
                assert response.status_code == 409  # Conflict
                data = response.json()
                assert "detail" in data

    def test_update_item_success(self, test_client: TestClient, api_key_header: dict):
        """Test updating an existing item."""
        item_data = {"name": "Updated Item", "description": "An updated item"}

        updated_item = Item(
            id="item-1",
            name="Updated Item",
            description="An updated item",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-02T00:00:00Z",
        )

        with patch("src.api.get_setting", return_value="test-api-key"):
            with patch("src.api.data_store") as mock_store:
                mock_store.update_item.return_value = updated_item

                response = test_client.put(
                    "/items/item-1", headers=api_key_header, json=item_data
                )
                assert response.status_code == 200
                data = response.json()
                assert data["name"] == "Updated Item"
                assert data["description"] == "An updated item"

    def test_update_item_not_exists(
        self, test_client: TestClient, api_key_header: dict
    ):
        """Test updating a non-existent item."""
        item_data = {"name": "Updated Item"}

        with patch("src.api.get_setting", return_value="test-api-key"):
            with patch("src.api.data_store") as mock_store:
                mock_store.update_item.side_effect = ValueError("Item not found")

                response = test_client.put(
                    "/items/non-existent", headers=api_key_header, json=item_data
                )
                assert response.status_code == 404
                data = response.json()
                assert "detail" in data

    def test_delete_item_success(self, test_client: TestClient, api_key_header: dict):
        """Test deleting an existing item."""
        with patch("src.api.get_setting", return_value="test-api-key"):
            with patch("src.api.data_store") as mock_store:
                mock_store.delete_item.return_value = None

                response = test_client.delete("/items/item-1", headers=api_key_header)
                assert response.status_code == 204

                # Verify the store was called
                mock_store.delete_item.assert_called_once_with("item-1")

    def test_delete_item_not_exists(
        self, test_client: TestClient, api_key_header: dict
    ):
        """Test deleting a non-existent item."""
        with patch("src.api.get_setting", return_value="test-api-key"):
            with patch("src.api.data_store") as mock_store:
                mock_store.delete_item.side_effect = ValueError("Item not found")

                response = test_client.delete(
                    "/items/non-existent", headers=api_key_header
                )
                assert response.status_code == 404
                data = response.json()
                assert "detail" in data


class TestAdminEndpoints:
    """Test admin endpoints."""

    def test_run_scheduler_success(self, test_client: TestClient, api_key_header: dict):
        """Test running background scheduler."""
        with patch("src.api.get_setting", return_value="test-api-key"):
            with patch("src.api.scheduler") as mock_scheduler:

                async def mock_run_tasks():
                    return {"tasks_run": 2}

                mock_scheduler.run_tasks = mock_run_tasks

                response = test_client.post(
                    "/admin/tasks/run-scheduler", headers=api_key_header
                )
                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Background tasks completed"
                assert data["tasks_run"] == 2

    def test_run_scheduler_error(self, test_client: TestClient, api_key_header: dict):
        """Test running scheduler with error."""
        with patch("src.api.get_setting", return_value="test-api-key"):
            with patch("src.api.scheduler") as mock_scheduler:
                mock_scheduler.run_tasks.side_effect = RuntimeError("Scheduler error")

                response = test_client.post(
                    "/admin/tasks/run-scheduler", headers=api_key_header
                )
                assert response.status_code == 500
                data = response.json()
                assert "detail" in data


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_internal_server_error(self, test_client: TestClient, api_key_header: dict):
        """Test handling of internal server errors."""
        with patch("src.api.get_setting", return_value="test-api-key"):
            with patch("src.api.data_store") as mock_store:
                mock_store.list_items.side_effect = Exception("Unexpected error")

                response = test_client.get("/items", headers=api_key_header)
                assert response.status_code == 500
                data = response.json()
                assert "detail" in data

    def test_validation_error(self, test_client: TestClient, api_key_header: dict):
        """Test handling of validation errors."""
        invalid_data = {
            "name": "",  # Empty name should fail validation
            "description": "Test description",
        }

        with patch("src.api.get_setting", return_value="test-api-key"):
            response = test_client.post(
                "/items", headers=api_key_header, json=invalid_data
            )
            assert response.status_code == 422
            data = response.json()
            assert "detail" in data

    def test_method_not_allowed(self, test_client: TestClient, api_key_header: dict):
        """Test handling of unsupported HTTP methods."""
        with patch("src.api.get_setting", return_value="test-api-key"):
            response = test_client.patch("/items/item-1", headers=api_key_header)
            assert response.status_code == 405  # Method Not Allowed

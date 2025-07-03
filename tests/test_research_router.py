"""Tests for the research router."""

import pytest
from fastapi.testclient import TestClient
import os
from dotenv import load_dotenv
from unittest.mock import patch, MagicMock
from fastapi import FastAPI

# Remove the local mock app creation - use conftest.py fixtures instead
# mock_app = FastAPI()

# @mock_app.post("/build-context")
# def build_context_mock():
#     return {
#         "result": "Citi's ROE is depressed by high capital requirements and low net interest margins.",
#         "metadata": {"mocked": True}
#     }

# @pytest.fixture
# def client():
#     """Create a test client using the mock app."""
#     return TestClient(mock_app)


def test_research_endpoint_exists(test_client):
    """Test that the research endpoint exists."""
    # Test that the endpoint is registered by checking the OpenAPI schema
    response = test_client.get("/openapi.json")
    assert response.status_code == 200
    
    # Check that the research endpoint is documented in the OpenAPI schema
    openapi_schema = response.json()
    paths = openapi_schema.get("paths", {})
    assert "/execute-research" in paths


def test_research_endpoint_requires_auth(test_client):
    """Test that the research endpoint requires authentication."""
    response = test_client.post(
        "/execute-research",
        json={"query": "test query"}
    )
    # Should return 401 for unauthorized access
    assert response.status_code == 401


def test_research_endpoint_accepts_valid_request(test_client):
    """Test that the research endpoint accepts valid requests."""
    # This test requires a valid API key, so we'll just test the endpoint structure
    # In a real test environment, you'd set up proper authentication
    
    # Test with a mock API key (this will likely fail, but we're testing structure)
    response = test_client.post(
        "/execute-research",
        headers={"X-API-Key": "test-key"},
        json={"query": "test query"}
    )
    
    # The response should be either 401/403 (invalid key) or 500 (flow execution error)
    # but not 422 (validation error) which would indicate the endpoint structure is wrong
    assert response.status_code != 422


def test_research_endpoint_validation(test_client):
    """Test that the research endpoint validates input."""
    # Use the test API key from conftest.py
    test_api_key = "test-api-key"
    
    # Test missing query
    response = test_client.post(
        "/execute-research",
        headers={"X-API-Key": test_api_key},
        json={}
    )
    # Should return 422 for validation error
    assert response.status_code == 422
    
    # Test empty query
    response = test_client.post(
        "/execute-research",
        headers={"X-API-Key": test_api_key},
        json={"query": ""}
    )
    # Should return 422 for validation error
    assert response.status_code == 422


def test_build_context_endpoint_exists(test_client):
    """Test that the build-context endpoint exists."""
    # Test that the endpoint is registered by checking the OpenAPI schema
    response = test_client.get("/openapi.json")
    assert response.status_code == 200
    
    # Check that the build-context endpoint is documented in the OpenAPI schema
    openapi_schema = response.json()
    paths = openapi_schema.get("paths", {})
    assert "/build-context" in paths


def test_build_context_endpoint_requires_auth(test_client):
    """Test that the build-context endpoint requires authentication."""
    response = test_client.post(
        "/build-context",
        json={"query": "Test query"},
        headers={"X-API-Key": "test-key"}
    )
    # Should return 401 for unauthorized access
    assert response.status_code == 401


def test_build_context_endpoint_accepts_valid_request(test_client):
    """Test that the build-context endpoint accepts valid requests."""
    # This test requires a valid API key, so we'll just test the endpoint structure
    # In a real test environment, you'd set up proper authentication
    
    # Test with a mock API key (this will likely fail, but we're testing structure)
    response = test_client.post(
        "/build-context",
        json={"query": "Test query"},
        headers={"X-API-Key": "test-key"}
    )
    
    # The response should be either 401/403 (invalid key) or 500 (flow execution error)
    # but not 422 (validation error) which would indicate the endpoint structure is wrong
    assert response.status_code != 422


def test_build_context_endpoint_validation(test_client):
    """Test that the build-context endpoint validates input."""
    # Use the test API key from conftest.py
    test_api_key = "test-api-key"
    
    # Test missing query
    response = test_client.post(
        "/build-context",
        json={"query": ""},
        headers={"X-API-Key": test_api_key}
    )
    # Should return 422 for validation error
    assert response.status_code == 422
    
    # Test empty query
    response = test_client.post(
        "/build-context",
        json={"query": ""},
        headers={"X-API-Key": test_api_key}
    )
    # Should return 422 for validation error
    assert response.status_code == 422


def test_build_context_returns_final_output(test_client):
    """Test that the build-context endpoint returns the final output from the TextOutput node (mocked)."""
    # Since we're using a mock app, we don't need to patch the real function
    # The mock app already returns the expected response
    response = test_client.post(
        "/build-context",
        json={"query": "What factors depress Citi's ROE?"},
        headers={"X-API-Key": "test-api-key"},  # Use the correct test API key
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result"].strip() != ""
    assert "Citi" in data["result"] or "ROE" in data["result"] 
"""Tests for the Generic VID Response router."""

import pytest
from fastapi.testclient import TestClient


def test_generic_vid_endpoint_exists(test_client: TestClient):
    """Test that the generic VID endpoint exists in the OpenAPI schema."""
    response = test_client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json().get("paths", {})
    assert "/execute-generic-vid" in paths


def test_generic_vid_endpoint_requires_auth(test_client: TestClient):
    """Ensure the generic VID endpoint enforces API-key authentication."""
    response = test_client.post(
        "/execute-generic-vid",
        json={"query": "Explain NIM differences"},
    )
    assert response.status_code == 401  # Unauthorized


def test_generic_vid_endpoint_accepts_valid_request(test_client: TestClient):
    """Endpoint should accept structurally valid requests (auth may still fail)."""
    response = test_client.post(
        "/execute-generic-vid",
        headers={"X-API-Key": "test-key"},
        json={"query": "Explain NIM differences"},
    )
    # Expect anything *except* a validation error (422)
    assert response.status_code != 422


def test_generic_vid_endpoint_validation(test_client: TestClient):
    """Validate request body requirements for the generic VID endpoint."""
    api_key_header = {"X-API-Key": "test-api-key"}

    # Missing query
    resp = test_client.post("/execute-generic-vid", headers=api_key_header, json={})
    assert resp.status_code == 422

    # Empty query
    resp = test_client.post(
        "/execute-generic-vid", headers=api_key_header, json={"query": ""}
    )
    assert resp.status_code == 422


def test_generic_vid_endpoint_returns_result(test_client: TestClient):
    """Smoke-test: endpoint returns non-empty result when given a valid request."""
    resp = test_client.post(
        "/execute-generic-vid",
        headers={"X-API-Key": "test-api-key"},
        json={"query": "How does NIM differ between banks?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"].strip() != "" 
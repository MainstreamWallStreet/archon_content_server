"""Tests for the research endpoint."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from src.api import app

client = TestClient(app)


class TestResearchEndpoint:
    """Test cases for the research endpoint."""

    def test_research_endpoint_missing_env_vars(self):
        """Test that the endpoint returns 503 when environment variables are missing."""
        with patch("src.api.get_setting", side_effect=RuntimeError("Missing config")):
            response = client.post(
                "/research",
                json={"query": "test query", "flow_id": "test-flow-id"},
                headers={"X-API-Key": "test-key"},
            )
            assert response.status_code == 503
            assert "ARCHON_API_KEY not configured" in response.json()["detail"]

    @patch("httpx.AsyncClient")
    def test_research_endpoint_success(self, mock_client_class):
        """Test successful research request."""
        # Mock the async client
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock the response with LangFlow structure
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "outputs": [
                {
                    "outputs": [
                        {
                            "results": {
                                "text": {
                                    "text": "This is the final answer from LangFlow"
                                }
                            }
                        }
                    ]
                }
            ]
        }
        mock_client.post.return_value = mock_response

        with patch("src.api.get_setting") as mock_get_setting:
            mock_get_setting.side_effect = lambda key, default=None: {
                "LANGFLOW_API_KEY": "test-api-key",
                "LANGFLOW_SERVER_URL": "http://test-server:7860/api/v1/run/",
                "ARCHON_API_KEY": "test-key",
            }.get(key, default)

            response = client.post(
                "/research",
                json={"query": "test query", "flow_id": "test-flow-id"},
                headers={"X-API-Key": "test-key"},
            )

            assert response.status_code == 200
            assert response.json() == {
                "result": "This is the final answer from LangFlow"
            }

    @patch("httpx.AsyncClient")
    def test_research_endpoint_http_error(self, mock_client_class):
        """Test research request with HTTP error."""
        # Mock the async client
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock the response with HTTP error
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "HTTP Error",
            request=MagicMock(),
            response=MagicMock(status_code=500, text="Internal Server Error"),
        )
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.post.return_value = mock_response

        with patch("src.api.get_setting") as mock_get_setting:
            mock_get_setting.side_effect = lambda key, default=None: {
                "LANGFLOW_API_KEY": "test-api-key",
                "LANGFLOW_SERVER_URL": "http://test-server:7860/api/v1/run/",
                "ARCHON_API_KEY": "test-key",
            }.get(key, default)

            response = client.post(
                "/research",
                json={"query": "test query", "flow_id": "test-flow-id"},
                headers={"X-API-Key": "test-key"},
            )

            assert response.status_code == 500
            assert "Internal Server Error" in response.json()["detail"]

    def test_research_endpoint_invalid_request(self):
        """Test research endpoint with invalid request body."""
        response = client.post(
            "/research",
            json={
                "query": "test query"
                # Missing flow_id
            },
        )
        assert response.status_code == 422  # Validation error

    @patch("httpx.AsyncClient")
    def test_research_endpoint_text_response(self, mock_client_class):
        """Test research endpoint with text response (non-JSON)."""
        # Mock the async client
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock the response with text
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Plain text response"
        mock_client.post.return_value = mock_response

        with patch("src.api.get_setting") as mock_get_setting:
            mock_get_setting.side_effect = lambda key, default=None: {
                "LANGFLOW_API_KEY": "test-api-key",
                "LANGFLOW_SERVER_URL": "http://test-server:7860/api/v1/run/",
                "ARCHON_API_KEY": "test-key",
            }.get(key, default)

            response = client.post(
                "/research",
                json={"query": "test query", "flow_id": "test-flow-id"},
                headers={"X-API-Key": "test-key"},
            )

            assert response.status_code == 200
            assert response.json() == {"result": "Plain text response"}

    @patch("httpx.AsyncClient")
    def test_research_endpoint_complex_langflow_response(self, mock_client_class):
        """Test research endpoint with complex LangFlow response structure."""
        # Mock the async client
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock the response with the actual LangFlow structure from the test
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "session_id": "af41bf0f-6ffb-4591-a276-8ae5f296da51",
            "outputs": [
                {
                    "inputs": {"input_value": "test query"},
                    "outputs": [
                        {
                            "results": {
                                "text": {
                                    "text": "How We Think About Risk\n\n1. The working definition...",
                                    "data": {
                                        "text": "How We Think About Risk\n\n1. The working definition..."
                                    },
                                }
                            }
                        }
                    ],
                }
            ],
        }
        mock_client.post.return_value = mock_response

        with patch("src.api.get_setting") as mock_get_setting:
            mock_get_setting.side_effect = lambda key, default=None: {
                "LANGFLOW_API_KEY": "test-api-key",
                "LANGFLOW_SERVER_URL": "http://test-server:7860/api/v1/run/",
                "ARCHON_API_KEY": "test-key",
            }.get(key, default)

            response = client.post(
                "/research",
                json={"query": "test query", "flow_id": "test-flow-id"},
                headers={"X-API-Key": "test-key"},
            )

            assert response.status_code == 200
            result = response.json()["result"]
            assert "How We Think About Risk" in result
            assert "working definition" in result

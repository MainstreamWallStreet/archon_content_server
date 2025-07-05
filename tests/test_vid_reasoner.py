"""Tests for the vid-reasoner endpoint."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from src.api import app

client = TestClient(app)


class TestVidReasonerEndpoint:
    """Test cases for the vid-reasoner endpoint."""

    def test_vid_reasoner_endpoint_missing_env_vars(self):
        """Test that the endpoint returns 503 when environment variables are missing."""
        with patch("src.api.get_setting", side_effect=RuntimeError("Missing config")):
            response = client.post(
                "/vid-reasoner",
                json={"input_value": "hello world!"},
                headers={"X-API-Key": "test-key"},
            )
            assert response.status_code == 503
            assert "ARCHON_API_KEY not configured" in response.json()["detail"]

    @patch("httpx.AsyncClient")
    def test_vid_reasoner_endpoint_success(self, mock_client_class):
        """Test successful vid-reasoner request."""
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
                                    "text": "This is the video reasoning result from LangFlow"
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
                "LANGFLOW_SERVER_URL": "https://langflow-455624753981.us-central1.run.app/api/v1/run/",
                "ARCHON_API_KEY": "test-key",
            }.get(key, default)

            response = client.post(
                "/vid-reasoner",
                json={
                    "input_value": "hello world!",
                    "output_type": "text",
                    "input_type": "text",
                },
                headers={"X-API-Key": "test-key"},
            )

            assert response.status_code == 200
            assert response.json() == {
                "result": "This is the video reasoning result from LangFlow"
            }

    @patch("httpx.AsyncClient")
    def test_vid_reasoner_endpoint_http_error(self, mock_client_class):
        """Test vid-reasoner request with HTTP error."""
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
                "LANGFLOW_SERVER_URL": "https://langflow-455624753981.us-central1.run.app/api/v1/run/",
                "ARCHON_API_KEY": "test-key",
            }.get(key, default)

            response = client.post(
                "/vid-reasoner",
                json={"input_value": "hello world!"},
                headers={"X-API-Key": "test-key"},
            )

            assert response.status_code == 500
            assert "Internal Server Error" in response.json()["detail"]

    def test_vid_reasoner_endpoint_invalid_request(self):
        """Test vid-reasoner endpoint with invalid request body."""
        response = client.post(
            "/vid-reasoner",
            json={
                # Missing input_value
                "output_type": "text"
            },
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 401  # Unauthorized due to missing required field
        assert "Invalid API key" in response.json()["detail"]

    @patch("httpx.AsyncClient")
    def test_vid_reasoner_endpoint_text_response(self, mock_client_class):
        """Test vid-reasoner endpoint with text response (non-JSON)."""
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
                "LANGFLOW_SERVER_URL": "https://langflow-455624753981.us-central1.run.app/api/v1/run/",
                "ARCHON_API_KEY": "test-key",
            }.get(key, default)

            response = client.post(
                "/vid-reasoner",
                json={"input_value": "hello world!"},
                headers={"X-API-Key": "test-key"},
            )

            assert response.status_code == 200
            assert response.json() == {"result": "Plain text response"}

    @patch("httpx.AsyncClient")
    def test_vid_reasoner_endpoint_complex_langflow_response(self, mock_client_class):
        """Test vid-reasoner endpoint with complex LangFlow response structure."""
        # Mock the async client
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock the response with the actual LangFlow structure
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "session_id": "59ef78ef-195b-4534-9b38-21527c2c90d4",
            "outputs": [
                {
                    "inputs": {"input_value": "hello world!"},
                    "outputs": [
                        {
                            "results": {
                                "text": {
                                    "text": "Video reasoning analysis result",
                                    "data": {"text": "Video reasoning analysis result"},
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
                "LANGFLOW_SERVER_URL": "https://langflow-455624753981.us-central1.run.app/api/v1/run/",
                "ARCHON_API_KEY": "test-key",
            }.get(key, default)

            response = client.post(
                "/vid-reasoner",
                json={"input_value": "hello world!"},
                headers={"X-API-Key": "test-key"},
            )

            assert response.status_code == 200
            result = response.json()["result"]
            assert "Video reasoning analysis result" in result

    def test_vid_reasoner_endpoint_default_values(self):
        """Test vid-reasoner endpoint with default output_type and input_type values."""
        with patch("httpx.AsyncClient") as mock_client_class:
            # Mock the async client
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock the response
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {
                "outputs": [
                    {
                        "outputs": [
                            {
                                "results": {
                                    "text": {"text": "Default values test result"}
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
                    "LANGFLOW_SERVER_URL": "https://langflow-455624753981.us-central1.run.app/api/v1/run/",
                    "ARCHON_API_KEY": "test-key",
                }.get(key, default)

                response = client.post(
                    "/vid-reasoner",
                    json={
                        "input_value": "test input"
                        # output_type and input_type should default to "text"
                    },
                    headers={"X-API-Key": "test-key"},
                )

                assert response.status_code == 200
                assert response.json() == {"result": "Default values test result"}

    @patch("httpx.AsyncClient")
    def test_vid_reasoner_endpoint_correct_flow_id(self, mock_client_class):
        """Test that the vid-reasoner endpoint uses the correct flow ID."""
        # Mock the async client
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock the response
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "outputs": [
                {"outputs": [{"results": {"text": {"text": "Flow ID test result"}}}]}
            ]
        }
        mock_client.post.return_value = mock_response

        with patch("src.api.get_setting") as mock_get_setting:
            mock_get_setting.side_effect = lambda key, default=None: {
                "LANGFLOW_API_KEY": "test-api-key",
                "LANGFLOW_SERVER_URL": "https://langflow-455624753981.us-central1.run.app/api/v1/run/",
                "ARCHON_API_KEY": "test-key",
            }.get(key, default)

            response = client.post(
                "/vid-reasoner",
                json={"input_value": "test input"},
                headers={"X-API-Key": "test-key"},
            )

            # Verify that the correct flow ID was used in the URL
            expected_url = "https://langflow-455624753981.us-central1.run.app/api/v1/run/59ef78ef-195b-4534-9b38-21527c2c90d4"
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == expected_url

            assert response.status_code == 200

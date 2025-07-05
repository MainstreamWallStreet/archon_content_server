"""Tests for the spreadsheet API endpoints."""

import pytest
import tempfile
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.api import app

client = TestClient(app)


class TestSpreadsheetEndpoints:
    """Test cases for spreadsheet endpoints."""

    @patch("src.api.PlanGenerator")
    @patch("src.api.build_from_plan")
    @patch("src.api.get_setting")
    def test_generate_spreadsheet_success(self, mock_get_setting, mock_build, mock_generator_class):
        """Test successful spreadsheet generation."""
        # Mock the plan generator
        mock_generator = MagicMock()
        mock_generator_class.return_value = mock_generator
        mock_generator.generate.return_value = {"workbook": {"filename": "test.xlsx"}}
        
        # Mock the API key setting
        mock_get_setting.return_value = "test-key"

        # Create a temporary file that actually exists
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_file.write(b"fake excel content")
            tmp_file_path = tmp_file.name

        # Mock the build function to return the actual file path
        mock_build.return_value = Path(tmp_file_path)

        try:
            response = client.post(
                "/spreadsheet/build",
                json={"objective": "Model FY-2024 revenue", "data": "Revenue: 100M"},
                headers={"X-API-Key": "test-key"}
            )

            assert response.status_code == 200
            assert (
                response.headers["content-type"]
                == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    @patch("src.api.PlanGenerator")
    @patch("src.api.get_setting")
    def test_generate_spreadsheet_missing_api_key(self, mock_get_setting, mock_generator_class):
        """Test spreadsheet generation with missing OpenAI API key."""
        # Mock the generator to raise RuntimeError (missing API key)
        mock_generator = MagicMock()
        mock_generator_class.return_value = mock_generator
        mock_generator.generate.side_effect = RuntimeError("OPENAI_API_KEY is required")
        
        # Mock the API key setting
        mock_get_setting.return_value = "test-key"

        response = client.post(
            "/spreadsheet/build",
            json={"objective": "Model FY-2024 revenue", "data": "Revenue: 100M"},
            headers={"X-API-Key": "test-key"}
        )

        assert response.status_code == 503
        assert "OPENAI_API_KEY is required" in response.json()["detail"]

    @patch("src.api.PlanGenerator")
    @patch("src.api.get_setting")
    def test_generate_plan_success(self, mock_get_setting, mock_generator_class):
        """Test successful plan generation."""
        # Mock the plan generator
        mock_generator = MagicMock()
        mock_generator_class.return_value = mock_generator
        expected_plan = {
            "workbook": {"filename": "test.xlsx"},
            "worksheet": {"name": "Model", "columns": []},
        }
        mock_generator.generate.return_value = expected_plan
        
        # Mock the API key setting
        mock_get_setting.return_value = "test-key"

        response = client.post(
            "/spreadsheet/plan",
            json={"objective": "Model FY-2024 revenue", "data": "Revenue: 100M"},
            headers={"X-API-Key": "test-key"}
        )

        assert response.status_code == 200
        assert response.json() == expected_plan

    @patch("src.api.PlanGenerator")
    @patch("src.api.get_setting")
    def test_generate_plan_missing_api_key(self, mock_get_setting, mock_generator_class):
        """Test plan generation with missing OpenAI API key."""
        # Mock the generator to raise RuntimeError (missing API key)
        mock_generator = MagicMock()
        mock_generator_class.return_value = mock_generator
        mock_generator.generate.side_effect = RuntimeError("OPENAI_API_KEY is required")
        
        # Mock the API key setting
        mock_get_setting.return_value = "test-key"

        response = client.post(
            "/spreadsheet/plan",
            json={"objective": "Model FY-2024 revenue", "data": "Revenue: 100M"},
            headers={"X-API-Key": "test-key"}
        )

        assert response.status_code == 503
        assert "OPENAI_API_KEY is required" in response.json()["detail"]

    def test_spreadsheet_endpoint_invalid_request(self):
        """Test spreadsheet endpoint with invalid request body."""
        response = client.post(
            "/spreadsheet/build",
            json={
                # Missing objective
                "data": "Revenue: 100M"
            },
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 401  # Unauthorized due to missing or invalid API key

    def test_plan_endpoint_invalid_request(self):
        """Test plan endpoint with invalid request body."""
        response = client.post(
            "/spreadsheet/plan",
            json={
                # Missing objective
                "data": "Revenue: 100M"
            },
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 401  # Unauthorized due to missing or invalid API key

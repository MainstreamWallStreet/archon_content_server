"""
Tests for configuration management.
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from src.config import get_setting


class TestGetSetting:
    """Test get_setting function."""

    def test_get_setting_from_env(self):
        """Test getting setting from environment variable."""
        with patch.dict(os.environ, {"TEST_KEY": "test-value"}):
            result = get_setting("TEST_KEY")
            assert result == "test-value"

    def test_get_setting_with_default(self):
        """Test getting setting with default value."""
        result = get_setting("NONEXISTENT_KEY", default="default-value")
        assert result == "default-value"

    def test_get_setting_missing_no_default(self):
        """Test getting setting that doesn't exist without default."""
        with pytest.raises(
            RuntimeError, match="Missing required setting: NONEXISTENT_KEY"
        ):
            get_setting("NONEXISTENT_KEY")

    def test_get_setting_from_secret_manager(self):
        """Test getting setting from Secret Manager."""
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}):
            with patch("src.config._sm_client") as mock_client:
                mock_response = MagicMock()
                mock_response.payload.data.decode.return_value = "secret-value"
                mock_client.return_value.access_secret_version.return_value = (
                    mock_response
                )

                result = get_setting("TEST_SECRET")
                assert result == "secret-value"

                # Verify Secret Manager was called with correct path
                mock_client.return_value.access_secret_version.assert_called_once_with(
                    name="projects/test-project/secrets/test-secret/versions/latest"
                )

    def test_get_setting_from_secret_manager_custom_secret_id(self):
        """Test getting setting from Secret Manager with custom secret ID."""
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}):
            with patch("src.config._sm_client") as mock_client:
                mock_response = MagicMock()
                mock_response.payload.data.decode.return_value = "secret-value"
                mock_client.return_value.access_secret_version.return_value = (
                    mock_response
                )

                result = get_setting("TEST_KEY", secret_id="custom-secret-name")
                assert result == "secret-value"

                # Verify Secret Manager was called with custom secret ID
                mock_client.return_value.access_secret_version.assert_called_once_with(
                    name="projects/test-project/secrets/custom-secret-name/versions/latest"
                )

    def test_get_setting_from_secret_manager_custom_version(self):
        """Test getting setting from Secret Manager with custom version."""
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}):
            with patch("src.config._sm_client") as mock_client:
                mock_response = MagicMock()
                mock_response.payload.data.decode.return_value = "secret-value"
                mock_client.return_value.access_secret_version.return_value = (
                    mock_response
                )

                result = get_setting("TEST_KEY", version="v1")
                assert result == "secret-value"

                # Verify Secret Manager was called with custom version
                mock_client.return_value.access_secret_version.assert_called_once_with(
                    name="projects/test-project/secrets/test-key/versions/v1"
                )

    def test_get_setting_secret_manager_fallback_to_default(self):
        """Test Secret Manager failure falls back to default."""
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}):
            with patch("src.config._sm_client") as mock_client:
                mock_client.return_value.access_secret_version.side_effect = Exception(
                    "Secret not found"
                )

                result = get_setting("TEST_KEY", default="fallback-value")
                assert result == "fallback-value"

    def test_get_setting_secret_manager_fallback_to_error(self):
        """Test Secret Manager failure raises error when no default."""
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}):
            with patch("src.config._sm_client") as mock_client:
                mock_client.return_value.access_secret_version.side_effect = Exception(
                    "Secret not found"
                )

                with pytest.raises(
                    RuntimeError, match="Missing required setting: TEST_KEY"
                ):
                    get_setting("TEST_KEY")

    def test_get_setting_env_takes_precedence(self):
        """Test environment variable takes precedence over Secret Manager."""
        with patch.dict(
            os.environ,
            {"GOOGLE_CLOUD_PROJECT": "test-project", "TEST_KEY": "env-value"},
        ):
            with patch("src.config._sm_client") as mock_client:
                mock_response = MagicMock()
                mock_response.payload.data.decode.return_value = "secret-value"
                mock_client.return_value.access_secret_version.return_value = (
                    mock_response
                )

                result = get_setting("TEST_KEY")
                assert result == "env-value"

                # Verify Secret Manager was not called
                mock_client.return_value.access_secret_version.assert_not_called()

    def test_get_setting_gcp_project_from_gcp_project_env(self):
        """Test getting GCP project from GOOGLE_CLOUD_PROJECT environment variable."""
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}):
            with patch("src.config._sm_client") as mock_client:
                mock_response = MagicMock()
                mock_response.payload.data.decode.return_value = "secret-value"
                mock_client.return_value.access_secret_version.return_value = (
                    mock_response
                )

                result = get_setting("TEST_KEY")
                assert result == "secret-value"

                # Verify Secret Manager was called with correct project
                mock_client.return_value.access_secret_version.assert_called_once_with(
                    name="projects/test-project/secrets/test-key/versions/latest"
                )

    def test_get_setting_no_gcp_project(self):
        """Test behavior when no GCP project is set."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.config._sm_client") as mock_client:
                result = get_setting("TEST_KEY", default="default-value")
                assert result == "default-value"

                # Verify Secret Manager was not called
                mock_client.return_value.access_secret_version.assert_not_called()

    def test_get_setting_key_name_conversion(self):
        """Test that key names are converted to kebab-case for Secret Manager."""
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}):
            with patch("src.config._sm_client") as mock_client:
                mock_response = MagicMock()
                mock_response.payload.data.decode.return_value = "secret-value"
                mock_client.return_value.access_secret_version.return_value = (
                    mock_response
                )

                result = get_setting("MY_TEST_KEY")
                assert result == "secret-value"

                # Verify Secret Manager was called with kebab-case secret name
                mock_client.return_value.access_secret_version.assert_called_once_with(
                    name="projects/test-project/secrets/my-test-key/versions/latest"
                )

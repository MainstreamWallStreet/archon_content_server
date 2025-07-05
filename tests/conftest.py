"""
Pytest configuration and fixtures for FastAPI template tests.
"""

import os
import pytest

# Set test environment variables
os.environ["ARCHON_API_KEY"] = "test-api-key"
os.environ["LANGFLOW_SERVER_URL"] = "http://test-server:7860/api/v1/run/"
os.environ["LANGFLOW_API_KEY"] = "test-langflow-key"
os.environ["OPENAI_API_KEY"] = "test-openai-key"


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    from src.api import app

    return TestClient(app)


@pytest.fixture
def sample_research_request():
    """Sample research request data."""
    return {
        "query": "Explain quantum computing in simple terms.",
        "flow_id": "af41bf0f-6ffb-4591-a276-8ae5f296da51",
    }


@pytest.fixture
def sample_spreadsheet_request():
    """Sample spreadsheet request data."""
    return {
        "objective": "Model FY-2024 revenue break-even analysis",
        "data": "Revenue: 763.9M, Fixed Costs: 45M, Variable Cost %: 12%",
    }


@pytest.fixture
def mock_langflow_response():
    """Mock LangFlow response structure."""
    return {
        "session_id": "test-session",
        "outputs": [
            {
                "inputs": {"input_value": "test query"},
                "outputs": [
                    {
                        "results": {
                            "text": {
                                "text": "This is the final answer from LangFlow",
                                "data": {
                                    "text": "This is the final answer from LangFlow"
                                },
                            }
                        }
                    }
                ],
            }
        ],
    }

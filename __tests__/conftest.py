import os
import sys
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import pytest

# Patch google libraries
for mod in [
    "google",
    "google.cloud",
    "google.cloud.storage",
    "google.cloud.exceptions",
]:
    sys.modules.setdefault(mod, MagicMock())

sys.modules["google.cloud.exceptions"].GoogleCloudError = Exception

# Minimal env vars
os.environ.setdefault("BANSHEE_DATA_BUCKET", "bucket")
os.environ.setdefault("EARNINGS_BUCKET", "calls-b")
os.environ.setdefault("EMAIL_QUEUE_BUCKET", "email-b")
os.environ["BANSHEE_API_KEY"] = "secret"
os.environ.setdefault("RAVEN_URL", "https://filing-fetcher-api-455624753981.us-central1.run.app")

from src.banshee_api import app, validate_key  # noqa: E402

# Add this global override for all tests
def always_valid_key():
    return True
app.dependency_overrides[validate_key] = always_valid_key

@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c

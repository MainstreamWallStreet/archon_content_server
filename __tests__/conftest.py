import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure Google modules exist so patching works without real dependencies
for mod in [
    "google",
    "google.cloud",
    "google.cloud.storage",
    "google.cloud.exceptions",
    "google.oauth2",
    "google.oauth2.credentials",
    "google.api_core",
    "google.api_core.exceptions",
    "googleapiclient",
    "googleapiclient.errors",
    "googleapiclient.http",
    "googleapiclient.discovery",
]:
    sys.modules.setdefault(mod, MagicMock())

# Minimal exception classes used by the code
sys.modules["google.cloud.exceptions"].GoogleCloudError = Exception


class _HttpError(Exception):
    def __init__(self, resp, content=b"", uri=None):
        super().__init__(resp, content, uri)
        self.resp = resp
        self.content = content
        self.uri = uri


sys.modules["googleapiclient.errors"].HttpError = _HttpError
sys.modules["googleapiclient.http"].MediaIoBaseUpload = MagicMock

# Provide default environment so src.api imports cleanly
os.environ.setdefault("FFS_API_KEY", "test")
os.environ.setdefault("OPENAI_API_KEY", "dummy")
os.environ.setdefault("API_NINJAS_KEY", "dummy")
os.environ.setdefault("GOOGLE_DRIVE_ROOT_FOLDER_ID", "dummy")
os.environ.setdefault("JOB_QUEUE_BUCKET", "test-bucket")
os.environ.setdefault("STORAGE_EMULATOR_HOST", "http://localhost:4443")
os.environ.setdefault("QUARTERLY_FILING_DATA_VERSION", "1")
os.environ.setdefault("TRANSCRIPT_DATA_VERSION", "1")

# Mock GCS client at module level
mock_client = MagicMock()
mock_bucket = MagicMock()
mock_blob = MagicMock()

mock_client.bucket.return_value = mock_bucket
mock_bucket.blob.return_value = mock_blob
mock_bucket.exists.return_value = True
mock_blob.exists.return_value = False
mock_blob.download_as_text.return_value = "{}"

# Apply patch at import time so src.api sees the mock
patcher = patch("google.cloud.storage.Client", return_value=mock_client)
patcher.start()

pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(scope="session", autouse=True)
def _mock_gcs():
    """Ensure the storage client patch is active for all tests."""
    yield
    patcher.stop()

import pytest
from unittest.mock import MagicMock

import src.api as api_mod
from src.api import ProcessingRequest, processing_jobs


@pytest.fixture(autouse=True)
def _patch_services(monkeypatch):
    monkeypatch.setattr(
        api_mod, "get_or_create_company_folder", lambda *a, **k: "folder"
    )
    monkeypatch.setattr(api_mod, "get_or_create_year_folder", lambda *a, **k: "year")
    monkeypatch.setattr(api_mod, "process_quarter", lambda *a, **k: None)
    monkeypatch.setattr(api_mod, "save_transcript_to_drive", lambda **k: None)
    monkeypatch.setattr(api_mod, "build", lambda *a, **k: MagicMock())
    monkeypatch.setattr(
        api_mod.Credentials,
        "from_authorized_user_info",
        lambda *a, **k: MagicMock(),
    )
    yield


def _run_job(token: str | None) -> dict:
    job_id = "TEST_JOB"
    processing_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "request": {},
        "version": 1,
    }
    req = ProcessingRequest(
        ticker="AAPL",
        year=2023,
        quarter=1,
        include_transcript=False,
        point_of_origin="test",
    )
    monkeypatch = pytest.MonkeyPatch()
    if token is None:
        monkeypatch.delenv("TOKEN", raising=False)
    else:
        monkeypatch.setenv("TOKEN", token)
    try:
        api_mod._run_job_sync(job_id, req)
    finally:
        monkeypatch.undo()
    result = processing_jobs.pop(job_id)
    return result


def test_invalid_token_sets_failed_status():
    job = _run_job("{bad_json}")
    assert job["status"] == "failed"
    assert "Invalid TOKEN" in job["message"]


def test_missing_token_sets_failed_status():
    job = _run_job(None)
    assert job["status"] == "failed"
    assert "Missing required setting: TOKEN" in job["message"]


def test_token_with_extra_data_is_parsed():
    token = '{"foo": "bar"} trailing'
    job = _run_job(token)
    assert job["status"] == "completed"

import json
from unittest.mock import MagicMock

import src.api as api_mod
from src.api import ProcessingRequest, processing_jobs


def test_filing_failure_marks_job_failed(monkeypatch):
    monkeypatch.setattr(
        api_mod, "get_or_create_company_folder", lambda *a, **k: "folder"
    )
    monkeypatch.setattr(api_mod, "get_or_create_year_folder", lambda *a, **k: "year")
    monkeypatch.setattr(api_mod, "save_transcript_to_drive", lambda **k: None)
    monkeypatch.setattr(api_mod, "build", lambda *a, **k: MagicMock())
    monkeypatch.setattr(
        api_mod.Credentials, "from_authorized_user_info", lambda *a, **k: MagicMock()
    )

    def fail_process(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(api_mod, "process_quarter", fail_process)

    job_id = "JOB2"
    processing_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "request": {},
        "version": 1,
    }

    req = ProcessingRequest(
        ticker="AAPL",
        year=2024,
        quarter=1,
        include_transcript=True,
        point_of_origin="test",
    )

    monkeypatch.setenv("TOKEN", json.dumps({}))

    api_mod._run_job_sync(job_id, req)
    job = processing_jobs.pop(job_id)

    assert job["status"] == "failed"
    assert "Filing processing failed" in job["message"]

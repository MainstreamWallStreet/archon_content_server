import json
from unittest.mock import MagicMock

import src.api as api_mod
from src.api import ProcessingRequest, processing_jobs


def test_transcript_and_filing_both_processed(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(
        api_mod, "get_or_create_company_folder", lambda *a, **k: "folder"
    )
    monkeypatch.setattr(api_mod, "get_or_create_year_folder", lambda *a, **k: "year")
    monkeypatch.setattr(api_mod, "build", lambda *a, **k: MagicMock())
    monkeypatch.setattr(
        api_mod.Credentials, "from_authorized_user_info", lambda *a, **k: MagicMock()
    )

    def fake_transcript(**kwargs):
        calls.append("transcript")
        return "tid"

    def fake_process(*args, **kwargs):
        calls.append("filing")
        return "furl"

    monkeypatch.setattr(api_mod, "save_transcript_to_drive", fake_transcript)
    monkeypatch.setattr(api_mod, "process_quarter", fake_process)

    job_id = "JOB1"
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
    processing_jobs.pop(job_id)

    assert calls == ["transcript", "filing"]

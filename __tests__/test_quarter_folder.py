import json
from unittest.mock import MagicMock

import src.api as api_mod
from src.api import ProcessingRequest, processing_jobs


def test_run_job_creates_quarter_folder(monkeypatch):
    called = []
    monkeypatch.setattr(api_mod, "get_or_create_company_folder", lambda *a, **k: "comp")
    monkeypatch.setattr(api_mod, "get_or_create_year_folder", lambda *a, **k: "year")

    def fake_get_quarter(drive, year_id, q):
        called.append(q)
        return "q"

    monkeypatch.setattr(api_mod, "get_or_create_quarter_folder", fake_get_quarter)
    monkeypatch.setattr(api_mod, "build", lambda *a, **k: MagicMock())
    monkeypatch.setattr(
        api_mod.Credentials, "from_authorized_user_info", lambda *a, **k: MagicMock()
    )
    monkeypatch.setattr(api_mod, "save_transcript_to_drive", lambda **k: "tid")
    monkeypatch.setattr(api_mod, "process_quarter", lambda *a, **k: "furl")

    job_id = "J1"
    processing_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "request": {},
        "version": 1,
    }

    req = ProcessingRequest(
        ticker="AAPL",
        year=2024,
        quarter=2,
        include_transcript=True,
        point_of_origin="t",
    )
    monkeypatch.setenv("TOKEN", json.dumps({}))

    api_mod._run_job_sync(job_id, req)
    processing_jobs.pop(job_id)

    assert called == [2, 2]

from unittest.mock import MagicMock

import src.transcript_helper as th


def test_save_transcript_inserts_version_and_title(monkeypatch):
    docs = MagicMock()
    docs.documents().create.return_value.execute.return_value = {"documentId": "ID"}
    drive = MagicMock()
    drive.files().update.return_value.execute.return_value = None

    captured = []
    monkeypatch.setattr(th, "insert_paragraph", lambda *a, **k: captured.append(a[2]))
    monkeypatch.setattr(th, "_safe_request", lambda fn, **kw: fn())
    monkeypatch.setattr(
        th, "_fetch_transcript", lambda **kw: {"transcript": "T", "date": "D"}
    )
    monkeypatch.setenv("TRANSCRIPT_DATA_VERSION", "2")

    doc_id = th.save_transcript_to_drive(
        docs_service=docs,
        drive_service=drive,
        quarter_folder_id="Q",
        ticker="TEST",
        year=2024,
        quarter=1,
    )

    assert doc_id == "ID"
    assert captured[0] == "data_version = 2"
    assert captured[1].startswith("TEST 2024 Q1 - TRANSCRIPT")

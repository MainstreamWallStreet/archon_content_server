#!/usr/bin/env python3
"""
transcript_helper.py – Fetches and uploads earnings call transcripts

• Uses API Ninjas to retrieve quarterly earnings transcripts
• Saves the transcript to Google Docs under the company's Drive folder
• Called from edgar_cli after folder creation, before Q/K processing
"""

from __future__ import annotations

import logging
import os
import requests
import textwrap
from typing import Any, Dict

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from src.gdrive.gdrive_helper import insert_paragraph, _safe_request
from src.config import get_setting
from src import progress

log = logging.getLogger("transcript_helper")

# ───────────────────────── API Ninjas helpers ──────────────────────────

ENDPOINT = "https://api.api-ninjas.com/v1/earningstranscript"


def _fetch_transcript(
    *, ticker: str, year: int, quarter: int, api_key: str
) -> Dict[str, Any] | None:
    """Fetch earnings call transcript JSON. Return None if not found or failed."""
    params = {"ticker": ticker.upper(), "year": year, "quarter": quarter}
    try:
        r = requests.get(
            ENDPOINT,
            params=params,
            timeout=30,
            headers={"X-Api-Key": api_key, "User-Agent": "Raven/1.0"},
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
    except requests.RequestException as e:
        log.warning(
            "Transcript fetch failed for %s %d Q%d: %s",
            ticker.upper(),
            year,
            quarter,
            e,
        )
        return None
    return r.json()


# ───────────────────────── Drive upload logic ──────────────────────────


def save_transcript_to_drive(
    *,
    docs_service: Resource,
    drive_service: Resource,
    quarter_folder_id: str,
    ticker: str,
    year: int,
    quarter: int,
    api_key: str | None = None,
    job_id: str | None = None,
    job_queue: Any | None = None,
) -> str | None:
    """Fetch transcript and stream it to a Google Doc inside the quarter folder."""
    api_key = api_key or os.getenv("API_NINJAS_KEY")
    if not api_key:
        log.warning("API_NINJAS_KEY not set – skipping transcript fetch")
        return None

    progress.report("fetch_transcript")
    data = _fetch_transcript(ticker=ticker, year=year, quarter=quarter, api_key=api_key)
    if not data:
        log.info("No transcript found for %s %d Q%d", ticker.upper(), year, quarter)
        return None

    title = f"{ticker.upper()} {year} Q{quarter} - TRANSCRIPT"
    try:
        progress.report("create_transcript_doc")
        doc_id = _safe_request(
            lambda: docs_service.documents().create(body={"title": title}).execute(),
            label="create_doc",
        )["documentId"]
        _safe_request(
            lambda: drive_service.files()
            .update(fileId=doc_id, addParents=quarter_folder_id, removeParents="root")
            .execute(),
            label="move_doc",
        )
        version = get_setting("TRANSCRIPT_DATA_VERSION", default="1")
        insert_paragraph(docs_service, doc_id, f"data_version = {version}")

        # Save URL immediately after document creation
        doc_url = f"https://docs.google.com/document/d/{doc_id}"
        log.info("Transcript document created: %s", doc_url)

        # Store the document link in job metadata if job_id and job_queue are provided
        if job_id and job_queue:
            job_queue.update_job(
                job_id, transcript_url=doc_url, transcript_date=data.get("date", "N/A")
            )

        progress.report("write_header")
        insert_paragraph(
            docs_service,
            doc_id,
            f"{title}\nDate: {data.get('date', 'N/A')}",
            bold=True,
            heading="HEADING_1",
        )

        for para in textwrap.wrap(
            data.get("transcript", ""),
            width=2000,
            break_long_words=False,
            replace_whitespace=False,
        ):
            progress.report("write_para")
            insert_paragraph(docs_service, doc_id, para.strip() + "\n")

        log.info("Transcript content saved to: %s", doc_url)
        return doc_id

    except HttpError as e:
        log.warning("Google Docs error while saving transcript: %s", e)
        return None

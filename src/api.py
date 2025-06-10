#!/usr/bin/env python3
"""FastAPI application for Banshee – Automated Earnings Call Tracking System.

Banshee continuously monitors a global watchlist of ticker symbols, automatically
fetching upcoming earnings calls from API Ninjas, scheduling email alerts via SendGrid,
and orchestrating transcript processing through the Raven API.

The system operates through scheduled Cloud Tasks and maintains state in Google
Cloud Storage, providing a complete earnings call monitoring solution for
portfolio managers and financial analysts.

Jobs are placed onto a global :class:`asyncio.Queue` (named ``task_queue``)
and processed by up to ``MAX_CONCURRENT_JOBS`` background workers.  This
centralises all external API calls so rate limiting and retries happen in one
place.  A streaming endpoint exposes the current queue for easy monitoring by
client applications.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from contextlib import asynccontextmanager
import threading
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pydantic import BaseModel, field_validator

from src.config import get_setting  # centralised secret helper
from src.edgar_cli import process_quarter
from src.transcript_helper import save_transcript_to_drive
from src import progress
from src.edgar_cli import (
    get_or_create_company_folder,
    get_or_create_year_folder,
    get_or_create_quarter_folder,
)
from src.gcs_job_queue import GcsJobQueue
import logging
import traceback

MAX_CONCURRENT_JOBS = int(get_setting("MAX_CONCURRENT_JOBS", default="4"))

log = logging.getLogger("worker")

# ────────────────────────────
# 🔐  Auth
# ────────────────────────────
AUTH_HEADER_NAME = "X-API-Key"
AUTH_TOKEN_KEY = "BANSHEE_API_KEY"

api_key_header = APIKeyHeader(name=AUTH_HEADER_NAME, auto_error=True)


async def validate_api_key(api_key_header: str = Security(api_key_header)) -> str:
    expected = get_setting(AUTH_TOKEN_KEY)
    if not expected:
        raise HTTPException(500, f"{AUTH_TOKEN_KEY} not configured")
    if api_key_header != expected:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key_header


# ────────────────────────────
# 🚀  FastAPI application
# ────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background workers on startup and clean up on shutdown."""
    global worker_tasks, status_task
    if not worker_tasks:
        for idx in range(MAX_CONCURRENT_JOBS):
            t = asyncio.create_task(_job_worker(), name=f"worker-{idx}")
            worker_tasks.append(t)

    # restore pending jobs from storage
    for job in job_queue.list_jobs():
        processing_jobs[job["job_id"]] = job
        if job["status"] == "queued":
            # Use the origin from the job if available, otherwise use "api"
            job["request"]["origin"] = job.get("origin", "api")
            req = ProcessingRequest(**job["request"])
            await task_queue.put((job["job_id"], req))
    progress.set_message_callback(job_queue.append_log)
    if status_task is None:
        status_task = asyncio.create_task(_status_printer(), name="status_printer")

    yield

    # Cleanup on shutdown
    for task in worker_tasks:
        task.cancel()
    await asyncio.gather(*worker_tasks, return_exceptions=True)
    worker_tasks.clear()
    if status_task:
        status_task.cancel()
        await asyncio.gather(status_task, return_exceptions=True)
        status_task = None


app = FastAPI(
    title="Banshee API",
    description="""**Banshee - Automated Earnings Call Tracking & Alert System**

Banshee continuously monitors upcoming earnings conference calls for every ticker in a global watchlist, automatically scheduling alerts and orchestrating transcript processing through the Raven service.

## 🎯 Core Mission

Banshee tracks earnings calls across your entire portfolio, ensuring you never miss important corporate communications by providing:
- **Automated watchlist management** for ticker symbols
- **Proactive email alerts** (7 days before + day of earnings)
- **Intelligent transcript processing** via integration with Raven API
- **Rate limit monitoring** and admin notifications

## 🔄 Automated Workflows

### 1️⃣ **Daily Watchlist Sync** 
*Triggered: 05:00 EST daily via Cloud Scheduler*
- Fetches upcoming earnings from API Ninjas for all watchlist tickers
- Persists call schedules to `gs://banshee-data/earnings_queue/`
- Automatically schedules email reminder workflows

### 2️⃣ **Smart Email Alerts**
*Triggered: Immediately after watchlist sync*
- **-7 Days @ 09:00 EST**: "AAPL earnings call in 1 week (Jul 30)"
- **Day-of @ 06:00 EST**: "AAPL earnings call today at 2:00 PM"
- Uses Cloud Tasks → SendGrid for reliable delivery

### 3️⃣ **Transcript Processing**
*Triggered: Every 30 minutes on call dates*
- Monitors for published SEC transcripts/audio
- Automatically calls Raven API for transcript processing
- Handles authentication and job tracking

### 4️⃣ **Completion Notifications**
*Triggered: Raven success callbacks*
- Confirms transcript capture via email
- Updates call status to `transcript_saved`
- Provides direct links to processed documents

### 5️⃣ **Rate Limit Protection**
*Triggered: After each API call*
- Logs all API Ninjas requests to `gs://banshee-data/api_calls/`
- Sends admin alerts at ≥50,000 monthly requests
- Prevents quota overruns and service disruptions

## 📊 Data Architecture

**GCS Storage Layout:**
```
gs://banshee-data/
├── watchlist/           # Ticker management
│   ├── AAPL.json       # Per-ticker metadata
│   └── MSFT.json
├── earnings_queue/      # Scheduled calls
│   └── AAPL/2025-07-30.json
├── api_calls/2025-06.csv # Rate limiting log
└── tmp/                 # Processing workspace
```

**Call Status Flow:**
`scheduled` → `reminded-7d` → `reminded-day` → `sent_to_raven` → `transcript_saved`

## 🔌 API Endpoints

### Watchlist Management
- **GET /watchlist**: List all tracked tickers
- **POST /watchlist**: Add ticker to monitoring
- **DELETE /watchlist/{ticker}**: Remove ticker

### Earnings Queue
- **GET /earnings/upcoming**: View scheduled calls
- **GET /earnings/{ticker}**: Ticker-specific schedule
- **PATCH /earnings/{ticker}/{date}**: Update call status

### Automation Tasks
- **POST /tasks/daily-sync**: Manual watchlist sync
- **POST /tasks/intraday**: Check for new transcripts
- **GET /tasks/status**: Task execution history

### Monitoring
- **GET /stats/api-usage**: Current month's API call stats
- **GET /health**: Service health + integration status

## 🔐 Security & Integration

**Authentication:** API key via `X-API-Key` header (managed by Archon proxy)

**External Services:**
- **API Ninjas**: Earnings calendar data (`/v1/earningscalendar`)
- **Raven API**: Transcript processing (shared API key in Secret Manager)
- **SendGrid**: Email delivery (API key, from email, recipient list)

## 📱 Email Alert Examples

```
"📊 AAPL earnings call in 7 days (Jul 30 @ 2:00 PM EST)"
"🚨 AAPL earnings call TODAY at 2:00 PM EST"
"✅ AAPL Q2 transcript processed: [link]"
"⚠️ API usage at 48K/50K limit"
```

## ⚡ Built for Scale

- **Cloud Scheduler**: Reliable cron execution
- **Cloud Tasks**: Fault-tolerant email delivery  
- **Secret Manager**: Secure credential storage
- **GCS**: Durable state management with versioning
- **Terraform**: Infrastructure as code

Perfect for portfolio managers, analysts, and anyone who needs systematic earnings call coverage.
""",
    version="1.0.0",
    lifespan=lifespan,
)


# ────────────────────────────
# 📦  Models
# ────────────────────────────
class ProcessingRequest(BaseModel):
    ticker: str
    year: int
    quarter: Optional[int] = None
    include_transcript: bool = True
    point_of_origin: str  # Required field to track which service initiated the request

    @field_validator("quarter")
    @classmethod
    def _qtr(cls, v):
        if v is not None and not 1 <= v <= 4:
            raise ValueError("Quarter must be 1–4")
        return v

    @field_validator("point_of_origin")
    @classmethod
    def _validate_origin(cls, v):
        if not v or not v.strip():
            raise ValueError("point_of_origin is required")
        return v.strip()


class ProcessingResponse(BaseModel):
    job_id: str
    status: str
    message: str
    version: int = 1  # Add version field with default value


class JobReceipt(BaseModel):
    job_id: str
    status: str
    message: str
    queued_jobs: int
    running_job: Optional[str]
    version: int = 1  # Add version field with default value


# ────────────────────────────
# 🗃️  State & queue
# ────────────────────────────
processing_jobs: Dict[str, Dict] = {}
active_tasks: Dict[str, asyncio.Task] = {}
job_states: Dict[str, Dict[str, Any]] = {}

# Persistent GCS-backed queue
try:
    job_queue = GcsJobQueue(get_setting("JOB_QUEUE_BUCKET"))
except (ValueError, RuntimeError) as e:
    log.error("Failed to initialize GCS job queue: %s", e)
    raise RuntimeError(
        "Failed to initialize GCS job queue. Please check your GCS configuration."
    ) from e

# Cache to store company folder IDs to avoid creating duplicates when
# multiple jobs for the same ticker run concurrently
_folder_cache: Dict[str, str] = {}
_year_folder_cache: Dict[tuple[str, int], str] = {}
_quarter_folder_cache: Dict[tuple[str, int], str] = {}
_folder_lock = threading.Lock()

# global asyncio queue for job execution
task_queue: asyncio.Queue[tuple[str, "ProcessingRequest"]] = asyncio.Queue()
worker_tasks: list[asyncio.Task] = []
status_task: asyncio.Task | None = None


# ────────────────────────────
# 🛠️  Helpers
# ────────────────────────────
def generate_job_id(ticker: str, year: int, qtr: Optional[int]) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")  # micro-seconds
    return f"{ticker.upper()}_{year}_{f'Q{qtr}_' if qtr else ''}{ts}"


# ────────────────────────────
# 🔧  Task helpers
# ────────────────────────────
async def _task_wrapper(job_id: str, req: ProcessingRequest):
    """Run a job with retries."""
    job_states[job_id] = {"phase": "starting"}
    processing_jobs[job_id]["status"] = "processing"
    processing_jobs[job_id]["message"] = "Job started"
    job_queue.update_job(
        job_id,
        status="processing",
        message="Job started",
        time_started=datetime.utcnow().isoformat(),
    )
    attempts = 0
    last_exc: Exception | None = None
    while attempts < 3:
        try:
            job_states[job_id]["phase"] = "processing"
            await _process(job_id, req)
            last_exc = None
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            log.error("Job %s attempt %d failed: %s", job_id, attempts + 1, exc)
            await asyncio.sleep(2**attempts)
            attempts += 1
    if last_exc:
        processing_jobs[job_id]["status"] = "failed"
        processing_jobs[job_id]["message"] = f"{type(last_exc).__name__}: {last_exc}"
        job_states[job_id]["phase"] = f"error: {last_exc}"
        job_queue.update_job(
            job_id,
            status="failed",
            message=f"{type(last_exc).__name__}: {last_exc}",
            time_completed=datetime.utcnow().isoformat(),
        )
    else:
        processing_jobs[job_id]["status"] = "completed"
        processing_jobs[job_id]["message"] = "Job completed"
        job_states[job_id]["phase"] = "complete"
        job_queue.update_job(
            job_id,
            status="completed",
            message="Job completed",
            time_completed=datetime.utcnow().isoformat(),
        )
        active_tasks.pop(job_id, None)


async def _job_worker() -> None:
    """Background task that processes queued jobs from ``task_queue``."""
    while True:
        job_id, req = await task_queue.get()
        task = asyncio.create_task(_task_wrapper(job_id, req), name=f"job-{job_id}")
        active_tasks[job_id] = task
        try:
            await task
        finally:
            task_queue.task_done()


async def _status_printer() -> None:
    """Periodically print a grid of job phases to the console."""
    while True:
        rows = [
            (jid, state.get("phase", "unknown")) for jid, state in job_states.items()
        ]
        if rows:
            print("\nJob Progress")
            for jid, phase in rows:
                print(f"{jid:<20} {phase}")
            print(flush=True)
        for jid, state in job_states.items():
            if state.get("phase") == "complete" and not state.get("notified"):
                t_url = state.get("transcript_url", "n/a")
                f_url = state.get("filing_url", "n/a")
                print(f"{jid} complete🎉 {t_url} {f_url}", flush=True)
                state["notified"] = True
        await asyncio.sleep(10)


# ────────────────────────────
# 🚚  Heavy lifting (threaded)
# ────────────────────────────
def _parse_token(raw: str) -> dict:
    """Parse ``TOKEN`` JSON and tolerate trailing characters."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        decoder = json.JSONDecoder()
        try:
            data, _ = decoder.raw_decode(raw)
            return data
        except json.JSONDecodeError:
            raise RuntimeError(f"Invalid TOKEN value: {exc}") from exc


def _run_job_sync(job_id: str, req: ProcessingRequest) -> None:
    """
    Synchronous part of the workload – executed in a background thread so the
    event-loop stays free.
    """
    progress.bind_job(job_id)
    if job_id not in job_states:
        job_states[job_id] = {"phase": "starting"}
    try:
        creds_json = get_setting("TOKEN")
        if not creds_json:
            raise RuntimeError("TOKEN not configured")

        creds_data = _parse_token(creds_json)

        creds = Credentials.from_authorized_user_info(
            creds_data,
            scopes=[
                "https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/drive.file",
            ],
        )

        drive = build("drive", "v3", credentials=creds)
        docs = build("docs", "v1", credentials=creds)

        folder_id = get_or_create_company_folder(drive, req.ticker)
        year_folder_id = get_or_create_year_folder(drive, folder_id, req.year)

        for qtr in [req.quarter] if req.quarter else [1, 2, 3, 4]:
            if req.include_transcript:
                progress.report(f"fetch_transcript_Q{qtr}")
                job_states[job_id]["phase"] = "get_transcript"
                try:
                    q_folder_id = get_or_create_quarter_folder(
                        drive, year_folder_id, qtr
                    )
                    doc_id = save_transcript_to_drive(
                        docs_service=docs,
                        drive_service=drive,
                        quarter_folder_id=q_folder_id,
                        ticker=req.ticker,
                        year=req.year,
                        quarter=qtr,
                        job_id=job_id,
                        job_queue=job_queue,
                    )
                    if doc_id:
                        t_url = f"https://docs.google.com/document/d/{doc_id}"
                        job_states[job_id]["transcript_url"] = t_url
                    else:
                        job_states[job_id]["transcript_error"] = "not found"
                except Exception as exc:  # noqa: BLE001 - keep server alive
                    log.error("Transcript Q%d failed: %s", qtr, exc)
                    # Re-raise the exception to crash the server
                    raise RuntimeError(
                        f"Transcript processing failed: {str(exc)}"
                    ) from exc
            progress.report(f"process_Q{qtr}")
            job_states[job_id]["phase"] = "get_10qk"
            try:
                q_folder_id = get_or_create_quarter_folder(drive, year_folder_id, qtr)
                f_url = process_quarter(
                    req.ticker,
                    req.year,
                    qtr,
                    drive,
                    q_folder_id,
                    job_queue=job_queue,
                    job_id=job_id,
                )
                job_states[job_id]["filing_url"] = f_url
                job_states[job_id]["phase"] = "complete"
            except Exception as exc:  # noqa: BLE001 - keep server alive
                log.error("Quarter %d failed: %s", qtr, exc)
                raise RuntimeError(f"Filing processing failed: {str(exc)}") from exc

        processing_jobs[job_id]["status"] = "completed"
        job_states[job_id]["phase"] = "complete"
    except Exception as exc:
        # ----- new robust logging -----
        tb = traceback.format_exc()
        log.error("Job %s crashed:\n%s", job_id, tb)
        processing_jobs[job_id]["status"] = "failed"
        processing_jobs[job_id]["message"] = f"{type(exc).__name__}: {exc}"
        job_states[job_id]["phase"] = f"error: {exc}"
    finally:
        progress.clear_job()


async def _process(job_id: str, req: ProcessingRequest):
    """
    Thin async wrapper that off-loads the blocking work to a thread,
    allowing multiple jobs to run in parallel while keeping FastAPI
    responsive.
    """
    await asyncio.to_thread(_run_job_sync, job_id, req)


# ────────────────────────────
# 🌐  API endpoints
# ────────────────────────────


@app.post("/process", response_model=Union[JobReceipt, List[JobReceipt]])
async def process_filing(req: ProcessingRequest, _: str = Depends(validate_api_key)):
    """Queue a new job for processing SEC filings and/or earnings call transcripts.

    Required fields:
    - ticker: Company stock symbol
    - year: Year to process
    - point_of_origin: Service initiating the request (e.g., "web_ui", "queue_aapl_jobs")

    Optional fields:
    - quarter: Specific quarter to process (1-4). If not provided, all quarters will be processed.
    - include_transcript: Whether to fetch and process earnings call transcript (default: true)

    Returns:
    - For single quarter requests: A JobReceipt with job details
    - For all quarters: A list of JobReceipts, one for each quarter
    """
    # basic config sanity-check
    for key in ("OPENAI_API_KEY", "API_NINJAS_KEY"):
        if req.include_transcript or key == "OPENAI_API_KEY":
            if not get_setting(key):
                raise HTTPException(500, f"{key} not configured")

    if req.quarter is None:
        receipts: List[JobReceipt] = []
        for qtr in (1, 2, 3, 4):
            sub_id = generate_job_id(req.ticker, req.year, qtr)
            sub_req = ProcessingRequest(
                ticker=req.ticker,
                year=req.year,
                quarter=qtr,
                include_transcript=req.include_transcript,
                point_of_origin=req.point_of_origin,
            )
            processing_jobs[sub_id] = job_queue.create_job(
                sub_id, sub_req.model_dump(), req.point_of_origin
            )
            await task_queue.put((sub_id, sub_req))
            receipts.append(
                JobReceipt(
                    job_id=sub_id,
                    status="queued",
                    message="Job queued",
                    queued_jobs=sum(
                        1 for m in processing_jobs.values() if m["status"] == "queued"
                    ),
                    running_job=next(
                        (
                            j
                            for j, m in processing_jobs.items()
                            if m["status"] == "processing"
                        ),
                        None,
                    ),
                )
            )
        return receipts

    job_id = generate_job_id(req.ticker, req.year, req.quarter)
    processing_jobs[job_id] = job_queue.create_job(
        job_id, req.model_dump(), req.point_of_origin
    )

    await task_queue.put((job_id, req))

    queued = sum(1 for m in processing_jobs.values() if m["status"] == "queued")
    running = next(
        (j for j, m in processing_jobs.items() if m["status"] == "processing"), None
    )

    return JobReceipt(
        job_id=job_id,
        status="queued",
        message="Job queued",
        queued_jobs=queued,
        running_job=running,
    )


@app.get("/updates")
async def get_updates(_: str = Depends(validate_api_key)):
    """Return all jobs from GCS and active tasks in one payload."""
    try:
        # Get all jobs from GCS
        log.info("Fetching jobs from GCS bucket: %s", job_queue.bucket_name)
        gcs_jobs = job_queue.list_jobs()
        log.info("Successfully retrieved %d jobs from GCS", len(gcs_jobs))

        # Create a map of all jobs, with in-memory jobs taking precedence
        all_jobs = {job["job_id"]: job for job in gcs_jobs}

        # Remove stale jobs that were deleted from GCS
        gcs_job_ids = set(all_jobs)
        for jid in list(processing_jobs.keys()):
            if jid not in gcs_job_ids and jid not in active_tasks:
                processing_jobs.pop(jid, None)

        # Update with in-memory jobs, ensuring they take precedence
        for job_id, job in processing_jobs.items():
            all_jobs[job_id] = job

        user_requested_jobs = [
            {
                "job_id": jid,
                "status": meta["status"],
                "message": meta.get("message", ""),
                "request": meta.get("request"),
                "start_time": meta.get("time_started"),
                "time_received": meta.get("time_received"),
                "time_completed": meta.get("time_completed"),
                "log": meta.get("log", []),
                "transcript_url": meta.get("transcript_url"),
                "transcript_date": meta.get("transcript_date"),
                "point_of_origin": meta.get("point_of_origin", "unknown"),
                "version": meta.get("version", 1),
            }
            for jid, meta in all_jobs.items()
        ]

        in_progress_server_tasks = [
            {
                "job_id": jid,
                "status": all_jobs.get(jid, {}).get("status", "unknown"),
                "task": progress.job_tasks.get(jid, task.get_name()),
            }
            for jid, task in list(active_tasks.items())
        ]

        return {
            "user_requested_jobs": user_requested_jobs,
            "in_progress_server_tasks": in_progress_server_tasks,
        }
    except RuntimeError as e:
        error_msg = f"Failed to fetch jobs from GCS: {str(e)}"
        log.error(error_msg)
        # Log additional context
        log.error("GCS Bucket: %s", job_queue.bucket_name)
        log.error("Active tasks count: %d", len(active_tasks))
        log.error("Processing jobs count: %d", len(processing_jobs))

        # Create a detailed error response
        error_detail = {
            "error": "GCS_OPERATION_FAILED",
            "message": error_msg,
            "context": {
                "bucket": job_queue.bucket_name,
                "active_tasks": len(active_tasks),
                "processing_jobs": len(processing_jobs),
                "timestamp": datetime.utcnow().isoformat(),
            },
        }
        raise HTTPException(status_code=503, detail=error_detail)
    except Exception as e:
        error_msg = f"Unexpected error in /updates: {str(e)}"
        log.error(error_msg, exc_info=True)
        error_detail = {
            "error": "INTERNAL_SERVER_ERROR",
            "message": error_msg,
            "type": type(e).__name__,
            "timestamp": datetime.utcnow().isoformat(),
        }
        raise HTTPException(status_code=500, detail=error_detail)


@app.get("/health")
async def health():
    return {"status": "healthy"}

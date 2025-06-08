#!/usr/bin/env python3
"""
edgar_cli.py – Raven "v9.1"
• Parallel LLM with Semaphore and RateLimiter
• Thread-pool Drive writes with per-thread logging
• Robust against missing/invalid {"relevant": …} keys from the LLM
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import atexit
import concurrent.futures
import asyncio
import os
import threading
from pathlib import Path
from typing import List, Dict, Any, Mapping

import bs4
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.transcript_helper import save_transcript_to_drive
from src.sec_filing import fetch_html_asset
from src.parser.ixbrl_parser import clean_ixbrl_html
from src.gdrive.gdrive_helper import (
    insert_paragraph,
    insert_html_table,
    _safe_request,
)
from src.llm_reasoner import Reasoner
from src.config import get_setting
from src import progress

# ─────────────────────────────── env / paths ───────────────────────────────
load_dotenv()

SAVE_JSON = True
# Default to 'dummy' so tests can import without env vars
ROOT_FOLDER_ID = get_setting("GOOGLE_DRIVE_ROOT_FOLDER_ID", default="dummy")
TEMP_DIR = Path(__file__).parent.parent / "temp"
TEMP_DIR.mkdir(exist_ok=True)
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

GDRIVE_MAX = 1  # executor threads
_executor: concurrent.futures.ThreadPoolExecutor | None = None
_pending: List[concurrent.futures.Future] = []
files_to_cleanup: List[Path] = []

# Cache company folders when processing multiple quarters concurrently
_folder_cache: Dict[str, str] = {}
_year_folder_cache: Dict[tuple[str, int], str] = {}
_quarter_folder_cache: Dict[tuple[str, int], str] = {}
_folder_lock = threading.Lock()

# ─────────────────────────── thread-local Google clients ───────────────────
_tls = threading.local()


def _thread_docs():
    if not hasattr(_tls, "docs"):
        creds = Credentials.from_authorized_user_info(
            json.loads(get_setting("TOKEN")),
            scopes=[
                "https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/drive.file",
            ],
        )
        _tls.docs = build("docs", "v1", credentials=creds)
    return _tls.docs


def _thread_drive():
    if not hasattr(_tls, "drive"):
        creds = Credentials.from_authorized_user_info(
            json.loads(get_setting("TOKEN")),
            scopes=[
                "https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/drive.file",
            ],
        )
        _tls.drive = build("drive", "v3", credentials=creds)
    return _tls.drive


def _exec_init():
    global _executor
    if _executor is None:
        _executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=GDRIVE_MAX, thread_name_prefix="gdocs"
        )
        atexit.register(_executor.shutdown, wait=True, cancel_futures=False)
    return _executor


# ----------------------------- logging helpers -----------------------------
def enqueue_write(fn, *args, **kwargs):
    fut = _exec_init().submit(fn, *args, **kwargs)
    _pending.append(fut)


def flush_writes():
    if _pending:
        concurrent.futures.wait(_pending)
        _pending.clear()


# ───────────────────────────── gDrive helpers ──────────────────────────────
def get_or_create_company_folder(drive_service, ticker: str) -> str:
    ticker_up = ticker.upper()

    with _folder_lock:
        cached = _folder_cache.get(ticker_up)
        if cached:
            return cached

        q = (
            f"name = '{ticker_up}' and mimeType='application/vnd.google-apps.folder' "
            f"and '{ROOT_FOLDER_ID}' in parents and trashed=false"
        )
        items = (
            drive_service.files()
            .list(q=q, spaces="drive", fields="files(id)", pageSize=1)
            .execute()
            .get("files", [])
        )
        if items:
            folder_id = items[0]["id"]
        else:
            meta = {
                "name": ticker_up,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [ROOT_FOLDER_ID],
            }
            folder_id = _safe_request(
                lambda: drive_service.files().create(body=meta, fields="id").execute(),
                label="create_folder",
            )["id"]
            print(f"📁 Created company folder {ticker_up}")

        _folder_cache[ticker_up] = folder_id

    return folder_id


def get_or_create_year_folder(drive_service, company_folder_id: str, year: int) -> str:
    """Return the Drive folder ID for ``year`` under ``company_folder_id``."""
    with _folder_lock:
        key = (company_folder_id, year)
        cached = _year_folder_cache.get(key)
        if cached:
            return cached

        q = (
            f"name = '{year}' and mimeType='application/vnd.google-apps.folder' "
            f"and '{company_folder_id}' in parents and trashed=false"
        )
        items = (
            drive_service.files()
            .list(q=q, spaces="drive", fields="files(id)", pageSize=1)
            .execute()
            .get("files", [])
        )
        if items:
            folder_id = items[0]["id"]
        else:
            meta = {
                "name": str(year),
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [company_folder_id],
            }
            folder_id = _safe_request(
                lambda: drive_service.files().create(body=meta, fields="id").execute(),
                label="create_year_folder",
            )["id"]
            print(f"📁 Created year folder {year}")

        _year_folder_cache[key] = folder_id

    return folder_id


def get_or_create_quarter_folder(
    drive_service, year_folder_id: str, quarter: int
) -> str:
    """Return the Drive folder ID for ``quarter`` under ``year_folder_id``."""
    with _folder_lock:
        key = (year_folder_id, quarter)
        cached = _quarter_folder_cache.get(key)
        if cached:
            return cached

        q = (
            f"name = 'Q{quarter}' and mimeType='application/vnd.google-apps.folder' "
            f"and '{year_folder_id}' in parents and trashed=false"
        )
        items = (
            drive_service.files()
            .list(q=q, spaces="drive", fields="files(id)", pageSize=1)
            .execute()
            .get("files", [])
        )
        if items:
            folder_id = items[0]["id"]
        else:
            meta = {
                "name": f"Q{quarter}",
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [year_folder_id],
            }
            folder_id = _safe_request(
                lambda: drive_service.files().create(body=meta, fields="id").execute(),
                label="create_quarter_folder",
            )["id"]
            print(f"📁 Created quarter folder Q{quarter}")

        _quarter_folder_cache[key] = folder_id

    return folder_id


# ───────────────────────────────── utils ───────────────────────────────────
def _table_grid(tbl) -> List[List[str]]:
    return [
        [
            td.get_text(" ", strip=True)
            for td in tr.find_all(["td", "th"], recursive=False)
        ]
        or [""]
        for tr in tbl.find_all("tr")
    ]


def _chunk_repr(node) -> str:
    if node.name == "table":
        g = _table_grid(node)
        return "TABLE:\n" + "\n".join(" | ".join(r) for r in g[:3])
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True))[:300]


def _tbljson_to_grid(tbl_json: Dict[str, Any]) -> List[List[str]]:
    """Convert LLM table JSON to a 2-D grid (list of rows).

    The LLM may omit the "rows" key or produce malformed types. We coerce
    everything to strings to ensure downstream table insertion never
    crashes.
    """
    headers = tbl_json.get("headers") or []
    rows = tbl_json.get("rows") or []

    if not isinstance(headers, list):
        headers = [str(headers)]

    if not isinstance(rows, list):
        # If rows is a dict / str, wrap it in a single-row table
        rows = [rows]

    grid: List[List[str]] = []
    if headers:
        grid.append([str(c) for c in headers])

    for r in rows:
        if isinstance(r, list):
            grid.append([str(c) for c in r])
        elif isinstance(r, Mapping):
            if headers:
                grid.append([str(r.get(h, "")) for h in headers])
            else:
                grid.append([str(v) for _, v in sorted(r.items())])
        else:
            grid.append([str(r)])

    return grid


def _gather_chunks(root) -> List[bs4.Tag]:
    """Return top-level text and table nodes, skipping wrappers with tables."""
    return [
        n
        for n in root.descendants
        if (name := getattr(n, "name", None)) in {"p", "div", "table"}
        and (name == "table" or not n.find("table"))
    ]


# ─────────────────────── Drive-write wrappers with logging ─────────────────
def _log_prefix(label: str) -> str:
    t = threading.current_thread()
    return f"[{t.name}/{t.ident}] {label}"


def _insert_paragraph_logged(label, docs_svc, doc_id, text, **kw):
    if docs_svc is None:
        docs_svc = _thread_docs()
    print(f"{_log_prefix(label)} START insert_paragraph")
    try:
        insert_paragraph(docs_svc, doc_id, text, **kw)
        print(f"{_log_prefix(label)} END insert_paragraph")
    except Exception as e:
        print(f"{_log_prefix(label)} FAIL insert_paragraph: {e}")
        raise


def _insert_html_table_logged(label, docs_svc, doc_id, grid, *, drive=None, **kw):
    if docs_svc is None:
        docs_svc = _thread_docs()
    if drive is None:
        drive = _thread_drive()
    print(f"{_log_prefix(label)} START insert_html_table")
    try:
        insert_html_table(docs_svc, doc_id, grid, drive=drive, **kw)
        print(f"{_log_prefix(label)} END insert_html_table")
    except Exception as e:
        print(f"{_log_prefix(label)} FAIL insert_html_table: {e}")
        raise


# ───────────────────────────── LLM async pipeline ──────────────────────────
async def _analyse_chunks(
    chunks: List[bs4.Tag],
    R: Reasoner,
    workers: int,
    *,
    docs_service,
    drive_service,
    doc_id: str,
    title: str,
    fa_tables: List[dict],
):
    sem = asyncio.Semaphore(workers)

    async def handle(idx: int, node: bs4.Tag):
        async with sem:
            before = [_chunk_repr(chunks[j]) for j in range(max(0, idx - 5), idx)]
            after = [
                _chunk_repr(chunks[j])
                for j in range(idx + 1, min(len(chunks), idx + 6))
            ]

            # ---------- paragraph ----------
            if node.name in {"p", "div"} and not node.find("table"):
                txt = re.sub(r"\s+", " ", node.get_text(" ", strip=True))
                meta = await R.para_relevant_async(txt, before, after)
                rel = meta.get("relevant", "no").lower()
                why = meta.get("why", "(no reason)")
                print(f"[task-{idx}] PARA rel={rel}  why={why[:60]}", flush=True)

                if rel.startswith("y"):
                    enqueue_write(
                        _insert_paragraph_logged,
                        f"P{idx}",
                        docs_service,
                        doc_id,
                        txt + "\n",
                    )

            # ---------- table ----------
            else:
                raw_grid = _table_grid(node)
                excerpt = "\n".join(" | ".join(r) for r in raw_grid[:3])
                det = await R.table_relevant_async(excerpt, before, after)
                rel = det.get("relevant", "no").lower()
                why = det.get("why", "(no reason)")
                print(f"[task-{idx}] TABLE rel={rel}  why={why}", flush=True)

                if rel.startswith("y"):
                    rows_txt = "\n".join(" | ".join(r) for r in raw_grid[:40])
                    tbl_json = await R.table_format_async(rows_txt)

                    if tbl_json and tbl_json.get("headers"):
                        grid = _tbljson_to_grid(tbl_json)
                        hdr_rows = 1 if tbl_json.get("headers") else 0
                        raw_units = tbl_json.get("units", "")
                        if isinstance(raw_units, str):
                            units = raw_units.strip()
                        else:
                            # Fallback: try to serialize non-string units to text
                            try:
                                units = json.dumps(raw_units)
                            except Exception:
                                units = str(raw_units)

                        if units:
                            enqueue_write(
                                _insert_paragraph_logged,
                                f"T{idx}_units",
                                docs_service,
                                doc_id,
                                f"Units: {units}",
                                italic=True,
                                bold=True,
                            )

                        enqueue_write(
                            _insert_html_table_logged,
                            f"T{idx}",
                            docs_service,
                            doc_id,
                            grid,
                            merges=[],
                            header_rows=hdr_rows,
                            drive=drive_service,
                            folder_id=None,
                            csv_title=f"{title}_table{idx}",
                        )
                        enqueue_write(
                            _insert_paragraph_logged,
                            f"T{idx}_sp",
                            docs_service,
                            doc_id,
                            "",
                        )
                        fa_tables.append(tbl_json)

    await asyncio.gather(
        *(asyncio.create_task(handle(i, n)) for i, n in enumerate(chunks))
    )


# ───────────────────────────── HTML → Docs main ────────────────────────────
def process_html(html: str, title: str, folder_id: str) -> tuple[list[dict], str]:
    soup = bs4.BeautifulSoup(html, "html.parser")
    root = soup.body or soup
    chunks = _gather_chunks(root)

    creds = Credentials.from_authorized_user_info(
        json.loads(get_setting("TOKEN")),
        scopes=[
            "https://www.googleapis.com/auth/documents",
            "https://www.googleapis.com/auth/drive.file",
        ],
    )
    docs = build("docs", "v1", credentials=creds)
    drive = build("drive", "v3", credentials=creds)

    doc_id = _safe_request(
        lambda: docs.documents().create(body={"title": title}).execute(),
        label="create_doc",
    )["documentId"]
    _safe_request(
        lambda: drive.files()
        .update(fileId=doc_id, addParents=folder_id, removeParents="root")
        .execute(),
        label="move_doc",
    )
    version = get_setting("QUARTERLY_FILING_DATA_VERSION", default="1")
    insert_paragraph(docs, doc_id, f"data_version = {version}")
    insert_paragraph(docs, doc_id, title, bold=True, heading="HEADING_1")
    doc_url = f"https://docs.google.com/document/d/{doc_id}"
    print("📝 Google Doc:", doc_url)

    R = Reasoner()
    workers = int(os.getenv("LLM_WORKERS", "8"))
    fa_tables: List[dict] = []

    asyncio.run(
        _analyse_chunks(
            chunks,
            R,
            workers,
            docs_service=docs,
            drive_service=drive,
            doc_id=doc_id,
            title=title,
            fa_tables=fa_tables,
        )
    )

    flush_writes()
    print("\n──────── cost summary ────────")
    print(R.cost_summary())
    return fa_tables, doc_url


# ───────────────────────────── quarter wrapper ─────────────────────────────
def process_quarter(
    ticker: str,
    year: int,
    quarter: int,
    drive_service,
    quarter_folder_id: str,
    *,
    job_queue: Any | None = None,
    job_id: str | None = None,
) -> str:
    """Process a single quarter's filing and return the Google Doc URL."""
    progress.report(f"quarter_{quarter}")
    print(f"\n📊 Processing {ticker.upper()} {year} Q{quarter}")
    asset = fetch_html_asset(ticker, year, quarter)

    tmp = TEMP_DIR / f"{ticker.lower()}_{year}_Q{quarter}.html"
    tmp.write_text(asset["path"].read_text(encoding="utf-8", errors="ignore"))
    files_to_cleanup.append(tmp)

    html = (
        clean_ixbrl_html(tmp.read_text())
        if asset["kind"] == "ixbrl"
        else tmp.read_text()
    )
    # Determine form type for document title
    form_type = asset.get("form", "").replace("-", "").upper() or (
        "10Q" if "10q" in tmp.name.lower() else "10K"
    )
    doc_title = f"{ticker.upper()} {year} Q{quarter} - {form_type}"
    tables, doc_url = process_html(
        html,
        doc_title,
        quarter_folder_id,
    )

    if tables and SAVE_JSON:
        out = TEMP_DIR / f"{ticker.lower()}_{year}_Q{quarter}_tables.json"
        out.write_text(json.dumps(tables, indent=2))
        files_to_cleanup.append(out)
        print("💾 JSON saved to", out)
    if job_queue and job_id:
        job_queue.update_job(job_id, filing_url=doc_url)
    return doc_url


# ───────────────────────────── CLI entrypoint ─────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--quarter", type=int, choices=[1, 2, 3, 4])
    args = ap.parse_args()

    creds = Credentials.from_authorized_user_info(
        json.loads(get_setting("TOKEN")),
        scopes=[
            "https://www.googleapis.com/auth/documents",
            "https://www.googleapis.com/auth/drive.file",
        ],
    )
    drive = build("drive", "v3", credentials=creds)
    company_folder_id = get_or_create_company_folder(drive, args.ticker)
    year_folder_id = get_or_create_year_folder(drive, company_folder_id, args.year)

    quarters = [args.quarter] if args.quarter else [1, 2, 3, 4]
    for q in quarters:
        try:
            save_transcript_to_drive(
                docs_service=build("docs", "v1", credentials=creds),
                drive_service=drive,
                quarter_folder_id=get_or_create_quarter_folder(
                    drive, year_folder_id, q
                ),
                ticker=args.ticker,
                year=args.year,
                quarter=q,
            )
        except Exception as e:  # noqa: BLE001 - broad catch for CLI robustness
            print(f"Transcript Q{q} failed: {e}", flush=True)

        try:
            q_folder = get_or_create_quarter_folder(drive, year_folder_id, q)
            process_quarter(args.ticker, args.year, q, drive, q_folder)
        except Exception as e:  # noqa: BLE001
            print(f"Quarter {q} failed: {e}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted ❌")
        sys.exit(130)

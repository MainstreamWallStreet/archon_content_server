#!/usr/bin/env python3
"""
Google‑Docs helper – handles paragraph insertion, table rendering (incl. rowspan/colspan),
and falls back to Drive‑hosted CSVs for extremely wide tables.
"""

from __future__ import annotations

import csv
import io
import random
import ssl
import time
from typing import Any, Callable, List, Optional, Tuple

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from src import progress

BACKOFF_CEILING = 60


def _backoff_sleep(attempt: int, *, ceiling: float = BACKOFF_CEILING) -> float:
    """Return exponential backoff duration capped by ``ceiling``."""
    delay = min(2**attempt, ceiling) + random.random()
    time.sleep(delay)
    return delay


# ───────────────────────── internal helpers ────────────────────────────


def _safe_batch_update(
    docs, doc_id: str, requests: List[dict], *, label: str = "", max_retries: int = 20
):
    """Robust wrapper around Docs batchUpdate – handles 429/5xx with exponential back‑off."""
    last: Optional[Exception] = None  # keep last failure for logging
    for attempt in range(max_retries):
        try:
            return (
                docs.documents()
                .batchUpdate(documentId=doc_id, body={"requests": requests})
                .execute()
            )
        except HttpError as e:
            # Retry on 429 (Rate Limit), 500 (Internal Server Error), 503 (Service Unavailable)
            # and other 5xx server-side errors.
            if e.resp.status not in {429, 500, 503} and not (
                500 <= e.resp.status < 600
            ):
                raise
            last = e
            delay = _backoff_sleep(attempt)
            print(
                f"[GDriveRetry/{label}] HttpError (status {e.resp.status}) on attempt {attempt + 1}/{max_retries}. Retrying in {delay:.2f}s...",
                flush=True,
            )
        except ssl.SSLError as e:
            last = e
            delay = _backoff_sleep(attempt)
            print(
                f"[GDriveRetry/{label}] SSLError on attempt {attempt + 1}/{max_retries}. Retrying in {delay:.2f}s... Error: {e}",
                flush=True,
            )
        except Exception as e:
            # Catch any other unexpected error during the API call and retry if it seems transient
            # For now, we will be cautious and re-raise immediately for unknown errors.
            # In the future, specific transient errors (e.g., socket errors) could be added here.
            print(
                f"[GDriveRetry/{label}] Unexpected error on attempt {attempt + 1}/{max_retries}: {e}. Re-raising.",
                flush=True,
            )
            raise

    print(
        f"[GDriveRetry/{label}] All {max_retries} retry attempts failed. Last error: {last}",
        flush=True,
    )
    raise last  # type: ignore


def _safe_request(
    fn: Callable[[], Any], *, label: str = "", max_retries: int = 10
) -> Any:
    """Execute ``fn`` with retries and exponential backoff."""
    last: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            return fn()
        except HttpError as e:
            if e.resp.status not in {429, 500, 503} and not (
                500 <= e.resp.status < 600
            ):
                raise
            last = e
            delay = _backoff_sleep(attempt)
            print(
                f"[GDriveRetry/{label}] HttpError (status {e.resp.status}) on attempt {attempt + 1}/{max_retries}. Retrying in {delay:.2f}s...",
                flush=True,
            )
        except ssl.SSLError as e:
            last = e
            delay = _backoff_sleep(attempt)
            print(
                f"[GDriveRetry/{label}] SSLError on attempt {attempt + 1}/{max_retries}. Retrying in {delay:.2f}s... Error: {e}",
                flush=True,
            )
    print(
        f"[GDriveRetry/{label}] All {max_retries} attempts failed. Last error: {last}",
        flush=True,
    )
    raise last  # type: ignore


def end_index(docs, doc_id: str) -> int:
    body = (
        docs.documents()
        .get(documentId=doc_id, fields="body.content(endIndex)")
        .execute()
    )
    return body["body"]["content"][-1]["endIndex"]  # type: ignore


# ───────────────────────── paragraph helpers ───────────────────────────


def insert_paragraph(
    docs,
    doc_id: str,
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    heading: str | None = None,
) -> None:
    progress.report("paragraph")
    idx = end_index(docs, doc_id) - 1
    reqs: List[dict] = [
        {"insertText": {"location": {"index": idx}, "text": text + "\n"}}
    ]

    style = {k: v for k, v in {"bold": bold, "italic": italic}.items() if v}
    if style:
        reqs.append(
            {
                "updateTextStyle": {
                    "range": {"startIndex": idx, "endIndex": idx + len(text)},
                    "textStyle": style,
                    "fields": ",".join(style.keys()),
                }
            }
        )
    if heading:
        reqs.append(
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": idx, "endIndex": idx + len(text)},
                    "paragraphStyle": {"namedStyleType": heading},
                    "fields": "namedStyleType",
                }
            }
        )
    _safe_batch_update(docs, doc_id, reqs, label="insert_paragraph")


# ───────────────────────── CSV fallback (wide tables) ──────────────────


def _upload_csv_and_link(
    rows: List[List[str]],
    docs,
    drive,
    doc_id: str,
    *,
    folder_id: str,
    title: str,
) -> None:
    progress.report("csv")
    buf = io.StringIO(newline="")
    csv.writer(buf).writerows(rows)
    media = MediaIoBaseUpload(io.BytesIO(buf.getvalue().encode()), mimetype="text/csv")
    file_meta = {"name": title, "mimeType": "text/csv", "parents": [folder_id]}
    link = (
        drive.files()
        .create(body=file_meta, media_body=media, fields="webViewLink")
        .execute()["webViewLink"]
    )

    idx = end_index(docs, doc_id) - 1
    _safe_batch_update(
        docs,
        doc_id,
        [
            {"insertText": {"location": {"index": idx}, "text": f"📈 {title}\n"}},
            {
                "updateTextStyle": {
                    "range": {"startIndex": idx, "endIndex": idx + len(title) + 2},
                    "textStyle": {"bold": True, "link": {"url": link}},
                    "fields": "bold,link.url",
                }
            },
        ],
        label="insert_csv_link",
    )


# ───────────────────────── table helper (fixed) ────────────────────────


def insert_html_table(
    docs,
    doc_id: str,
    grid: List[List[str]],
    merges: List[Tuple[int, int, int, int]],
    *,
    header_rows: int = 0,
    drive=None,
    folder_id: str | None = None,
    csv_title: str | None = None,
) -> None:
    progress.report("table")
    if not grid or not grid[0]:
        print("⚠️  Skipping table insertion – grid is empty or malformed")
        return

    # Ensure all rows are same length
    cols = max(len(row) for row in grid)
    for row in grid:
        row += [""] * (cols - len(row))

    rows = len(grid)
    if (cols > 20 or rows * cols > 400) and drive and folder_id and csv_title:
        _upload_csv_and_link(
            grid, docs, drive, doc_id, folder_id=folder_id, title=csv_title
        )
        return

    # Insert shell
    cursor = end_index(docs, doc_id) - 1
    _safe_batch_update(
        docs,
        doc_id,
        [
            {
                "insertTable": {
                    "rows": rows,
                    "columns": cols,
                    "location": {"index": cursor},
                }
            }
        ],
        label="insert_table_shell",
    )

    doc = docs.documents().get(documentId=doc_id).execute()
    for blk in reversed(doc["body"]["content"]):
        if "table" in blk:
            table_block = blk
            break
    else:
        raise RuntimeError("Inserted table not found – Docs API changed?")

    table = table_block["table"]
    tbl_start = table_block["startIndex"]

    # Populate each cell
    text_reqs: List[dict] = []
    for r in range(rows):
        for c in range(cols):
            cell_start = table["tableRows"][r]["tableCells"][c]["content"][0][
                "startIndex"
            ]
            txt = grid[r][c] or " "
            text_reqs.append(
                {"insertText": {"location": {"index": cell_start}, "text": txt}}
            )
            if r < header_rows and txt.strip():
                text_reqs.append(
                    {
                        "updateTextStyle": {
                            "range": {
                                "startIndex": cell_start,
                                "endIndex": cell_start + len(txt),
                            },
                            "textStyle": {"bold": True},
                            "fields": "bold",
                        }
                    }
                )

    text_reqs.sort(
        key=lambda req: (
            req["insertText"]["location"]["index"] if "insertText" in req else 0
        ),
        reverse=True,
    )
    _safe_batch_update(docs, doc_id, text_reqs, label="populate_table_cells")

    if merges:
        merge_reqs = [
            {
                "mergeTableCells": {
                    "tableRange": {
                        "tableCellLocation": {
                            "tableStartLocation": {"index": tbl_start},
                            "rowIndex": r0,
                            "columnIndex": c0,
                        },
                        "rowSpan": r1 - r0 + 1,
                        "columnSpan": c1 - c0 + 1,
                    }
                }
            }
            for r0, c0, r1, c1 in merges
        ]
        _safe_batch_update(docs, doc_id, merge_reqs, label="merge_table_cells")

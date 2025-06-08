#!/usr/bin/env python3
"""
save_as_csv_to_gdrive.py
========================
Helper for **save_sec_docs.py**

Whenever we meet a table that is *too wide* for Google Docs (more than
20 columns **OR** more than ~400 cells), we call
`upload_csv_and_insert_link()` instead of dumping raw Markdown.  The helper

1. Converts the list‑of‑lists **rows** to CSV text.
2. Uploads it to the *same* Drive folder that holds the SEC doc (mimetype
   `text/csv`).
3. Inserts a one‑line paragraph in the Google Doc with a hyperlink to the
   uploaded CSV.

Usage inside `_stream_to_doc` (pseudo code):

```python
from src.gdrive.save_as_csv_to_gdrive import upload_csv_and_insert_link
...
if too_wide:
    upload_csv_and_insert_link(rows, docs, doc_id, drive, quarter_id,
                               base_title=f"{ticker}_{year}_Q{quarter}_table{table_count+1}")
```
"""
from __future__ import annotations

import csv
import io
import logging
from typing import List

from googleapiclient.http import MediaIoBaseUpload

log = logging.getLogger("save_csv")

# ---------------------------------------------------------------------------
# core helper
# ---------------------------------------------------------------------------


def upload_csv_and_insert_link(
    rows: List[List[str]],
    docs,
    drive,
    doc_id: str,
    *,
    parent_folder_id: str,
    csv_title: str,
    bold_link: bool = False,
) -> str:
    """
    1.  Serialises **rows** to CSV and uploads it to Drive.
    2.  Inserts a one‑line paragraph at the *end* of `doc_id`
        containing a hyperlink to the uploaded file.

    Returns
    -------
    str
        The Drive “webViewLink” for the new CSV (handy for logging).
    """
    # 1️⃣ CSV → bytes ------------------------------------------------------
    buf = io.StringIO(newline="")
    csv.writer(buf).writerows(rows)
    payload = buf.getvalue().encode("utf‑8")

    # 2️⃣ upload -----------------------------------------------------------
    media = MediaIoBaseUpload(io.BytesIO(payload), mimetype="text/csv", resumable=False)
    meta = {
        "name": csv_title,
        "mimeType": "text/csv",
        "parents": [parent_folder_id],
    }
    file_obj = (
        drive.files()
        .create(body=meta, media_body=media, fields="id, webViewLink")
        .execute()
    )
    web_link: str = file_obj["webViewLink"]

    # 3️⃣ link paragraph ---------------------------------------------------
    from src.gdrive import gdrive_helper as gdh  # avoid import cycle

    idx = gdh.end_index(docs, doc_id) - 1
    text = f"📈 Wide table saved as CSV → {csv_title}"

    requests = [
        {"insertText": {"location": {"index": idx}, "text": text + "\n"}},
        {
            "updateTextStyle": {
                "range": {"startIndex": idx, "endIndex": idx + len(text)},
                "textStyle": {
                    "link": {"url": web_link},
                    **({"bold": True} if bold_link else {}),
                },
                "fields": "link.url" + (",bold" if bold_link else ""),
            }
        },
    ]
    gdh._safe_batch_update(docs, doc_id, requests, label="insert_csv_link")
    log.info("CSV uploaded (%s) and linked -> %s", csv_title, web_link)

    return web_link

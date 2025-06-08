"""
sec_filing.py
=============
Locate the correct 10‑Q / 10‑K for (ticker, year, quarter) and download the
cleanest HTML we can find.

Public API
----------
fetch_html_asset(ticker:str, year:int, quarter:int) -> dict
    Returns {"kind": <ixbrl|summary|primary>, "path": pathlib.Path}
"""

from __future__ import annotations
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import requests
from sec_edgar_api import EdgarClient

# ----------------------------------------------------------------------
# Configuration & polite HTTP
# ----------------------------------------------------------------------
UA = "Raven Research contact@raven.ai"

_session, _last_req = requests.Session(), 0.0
_session.headers.update({"User-Agent": UA})

# Create temp directory if it doesn't exist
TEMP_DIR = Path(__file__).parent.parent / "temp"
TEMP_DIR.mkdir(exist_ok=True)


def _get(url: str) -> requests.Response:
    """SEC rate‑limit helper (≤ 1 request / second)."""
    global _last_req
    wait = 1.01 - (time.time() - _last_req)
    if wait > 0:
        time.sleep(wait)
    _last_req = time.time()
    r = _session.get(url, timeout=30)
    r.raise_for_status()
    return r


# ----------------------------------------------------------------------
# Core helpers
# ----------------------------------------------------------------------
def _cik(ticker: str) -> str:
    """Convert ticker → zero‑padded 10‑digit CIK."""
    for v in _get("https://www.sec.gov/files/company_tickers.json").json().values():
        if v["ticker"] == ticker.upper():
            return f"{int(v['cik_str']):010d}"
    raise ValueError(f"CIK not found for {ticker.upper()}")


def _recent_filings(cik: str) -> List[Dict]:
    """Recent 10‑Q / 10‑K rows (JSON list)."""
    recent = EdgarClient(user_agent=UA).get_submissions(cik=cik)["filings"]["recent"]
    rows: List[Dict] = []
    for i, form in enumerate(recent["form"]):
        if form not in {"10-Q", "10-K"}:
            continue
        filed = (
            recent.get("reportDate", [None])[i]
            or recent.get("periodOfReport", [None])[i]
            or recent["filingDate"][i]
        )
        rows.append(
            dict(
                form=form,
                year=datetime.fromisoformat(filed).year,
                date=filed,
                accession=recent["accessionNumber"][i],
                primary=recent["primaryDocument"][i],
            )
        )
    return rows


def _calendar_quarter(iso_date: str) -> int:
    """Return calendar quarter (1‑4) from YYYY‑MM‑DD string."""
    month = int(iso_date[5:7])
    return (month - 1) // 3 + 1


def _walk_index(idx: Dict, base_url: str) -> Iterable[str]:
    """Yield every file path in the filing (recursive)."""
    for item in idx.get("directory", {}).get("item", []):
        name = item["name"]
        if item["type"] == "dir":
            yield from (
                f"{name}/{p}"
                for p in _walk_index(
                    _get(f"{base_url}/{name}/index.json").json(),
                    f"{base_url}/{name}",
                )
            )
        else:
            yield name


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
def fetch_html_asset(ticker: str, year: int, quarter: int) -> Dict:
    """
    Download the *best HTML* artefact for the requested filing.

    Returns
    -------
    dict
        kind : "ixbrl" | "summary" | "primary"
        path : pathlib.Path to the downloaded HTML
        form : "10-Q" | "10-K"
    """
    cik = _cik(ticker)
    rows = _recent_filings(cik)

    # 1️⃣ prefer the 10‑Q that matches calendar quarter
    target = next(
        (
            r
            for r in rows
            if r["form"] == "10-Q"
            and r["year"] == year
            and _calendar_quarter(r["date"]) == quarter
        ),
        None,
    )

    # 2️⃣ otherwise, fall back to the latest 10‑K that fiscal year
    if not target:
        target = max(
            (r for r in rows if r["form"] == "10-K" and r["year"] == year),
            key=lambda r: r["date"],
            default=None,
        )

    if not target:
        raise RuntimeError("No matching filing found")

    base = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{int(cik)}/{target['accession'].replace('-', '')}"
    )
    files = list(_walk_index(_get(f"{base}/index.json").json(), base))

    # Inline XBRL primary HTML (cleanest if present)
    ix = next(
        (
            f
            for f in files
            if f.lower().endswith((".htm", ".html")) and "xbrl" in f.lower()
        ),
        None,
    )
    if ix:
        p = TEMP_DIR / f"{ticker}_{year}_Q{quarter}.ix.html"
        p.write_bytes(_get(f"{base}/{ix}").content)
        return {"kind": "ixbrl", "path": p, "form": target["form"]}

    # FilingSummary bundle (rendered HTML)
    if "FilingSummary.xml" in files:
        root = ET.fromstring(_get(f"{base}/FilingSummary.xml").content)
        html_file = root.findtext(".//Report/HtmlFile")
        if html_file:
            p = TEMP_DIR / f"{ticker}_{year}_Q{quarter}.summary.html"
            p.write_bytes(_get(f"{base}/{html_file}").content)
            return {"kind": "summary", "path": p, "form": target["form"]}

    # The SEC "primary" document (fallback)
    prim = target["primary"]
    if prim.lower().endswith((".htm", ".html")):
        p = TEMP_DIR / f"{ticker}_{year}_Q{quarter}.primary.html"
        p.write_bytes(_get(f"{base}/{prim}").content)
        return {"kind": "primary", "path": p, "form": target["form"]}

    raise RuntimeError("Filing contains no HTML we can parse")

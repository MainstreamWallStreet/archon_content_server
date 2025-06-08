#!/usr/bin/env python3
"""
ixbrl_parser.py  –  strip <ix:*> tags from Inline XBRL HTML
"""

from __future__ import annotations
from bs4 import BeautifulSoup

IX_PREFIX = ("ix:", "ixt:", "ixbrl", "ix-nonnumeric", "ix-numeric")


def clean_ixbrl_html(raw: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for t in soup.find_all(lambda n: any(n.name.startswith(p) for p in IX_PREFIX)):
        t.unwrap()
    for bad in soup.find_all(["script", "link"]):
        bad.decompose()
    return str(soup)

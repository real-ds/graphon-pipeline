"""Parses the Atom XML that the arxiv API returns. Pure/deterministic — arxiv's
feed already gives structured fields, so this does NOT go through the LLM
orchestrator (no ambiguity to resolve, and it'd be wasteful to spend LLM budget
on already-structured data).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Iterator

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def parse_arxiv_feed(xml_text: str) -> Iterator[dict]:
    root = ET.fromstring(xml_text)
    for entry in root.findall("atom:entry", _NS):
        arxiv_id = entry.findtext("atom:id", default="", namespaces=_NS)
        title = (entry.findtext("atom:title", default="", namespaces=_NS) or "").strip()
        published = entry.findtext("atom:published", default="", namespaces=_NS)
        authors = [
            (a.findtext("atom:name", default="", namespaces=_NS) or "").strip()
            for a in entry.findall("atom:author", _NS)
        ]

        pdf_url = None
        for link in entry.findall("atom:link", _NS):
            if link.get("title") == "pdf" or link.get("type") == "application/pdf":
                pdf_url = link.get("href")
                break

        published_date = None
        if published:
            try:
                published_date = datetime.fromisoformat(published.replace("Z", "+00:00"))
            except ValueError:
                published_date = None

        yield {
            "title": title,
            "authors": authors,
            "paper_url": arxiv_id or pdf_url,
            "github_url": None,  # resolved separately — see github_stars.py
            "github_stars": None,
            "published_date": published_date or datetime.now(timezone.utc),
        }

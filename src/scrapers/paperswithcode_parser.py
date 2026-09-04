"""Parses Papers with Code HTML pages into structured paper records.

Unlike arxiv's API (which returns structured XML), PWC pages are HTML.
This parser extracts: title, arxiv URL, github URL, and published date.
This is a deterministic parser — it does NOT go through the LLM orchestrator
since the content is already structured enough to extract with CSS selectors.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterator, Optional

from selectolax.parser import HTMLParser

from ..freshness.date_normalizer import normalize_date

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_pwc_page(html_text: str) -> Iterator[dict]:
    """Parse a single PWC paper detail HTML page into a paper dict.

    Yields one dict per page with keys: title, paper_url, github_url, github_stars,
    published_date, authors.
    """
    parser = HTMLParser(html_text)
    text = parser.body.text() if parser.body else ""

    title = _extract_title(parser)
    arxiv_url = _extract_arxiv_url(text)
    github_url = _extract_github_url(parser)
    published_date = _extract_date(text)

    yield {
        "title": title or "",
        "paper_url": arxiv_url or "",
        "github_url": github_url,
        "github_stars": None,
        "published_date": published_date or datetime.now(timezone.utc),
        "authors": [],
    }


def _extract_title(parser: HTMLParser) -> str:
    h1 = parser.css_first("h1")
    if h1:
        raw = h1.text().strip()
        return re.sub(r"\s+", " ", raw)
    title_tag = parser.css_first("title")
    if title_tag:
        return title_tag.text().split("|")[0].strip()
    return ""


def _extract_arxiv_url(text: str) -> Optional[str]:
    m = re.search(r"arxiv\.org/abs/([\w.\-]+)", text)
    if m:
        return f"https://arxiv.org/abs/{m.group(1)}"
    m = re.search(r"\b(\d{4}\.\d{4,5})\b", text)
    if m:
        return f"https://arxiv.org/abs/{m.group(1)}"
    return None


def _extract_github_url(parser: HTMLParser) -> Optional[str]:
    for a in parser.css("a"):
        href = a.attrs.get("href", "")
        if "github.com/" in href:
            if any(x in href for x in ["/issues", "/pull", "/tree/", "/blob/"]):
                continue
            return href.rstrip("/")
    return None


def _extract_date(text: str) -> Optional[datetime]:
    date_match = re.search(
        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
        text,
    )
    if date_match:
        day, month_str, year = date_match.groups()
        month = _MONTHS.get(month_str.lower())
        if month:
            try:
                dt = datetime(int(year), month, int(day), tzinfo=timezone.utc)
                return dt
            except ValueError:
                pass

    parsed = normalize_date(text[:500])
    if parsed:
        return parsed

    return None

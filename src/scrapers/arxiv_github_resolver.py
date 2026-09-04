"""Fetch arxiv abstract pages and extract GitHub repository links.

This is the bridge between arxiv and GitHub for the dynamic-metrics requirement.
The arxiv API itself doesn't include paper code links, so we hit the abstract
HTML page (e.g. https://arxiv.org/abs/2401.12345) and extract any github.com
URLs that appear in the metadata.
"""
from __future__ import annotations

import asyncio
import re
from typing import Optional

import aiohttp

from ..config import settings
from ..logger import get_logger
from .rate_limiter import DomainRateLimiter

logger = get_logger(__name__)

ARXIV_ABSTRACT_URL = "https://arxiv.org/abs/"
TIMEOUT = aiohttp.ClientTimeout(total=30, connect=15)
_REQUEST_DELAY = 1.0  # arxiv is also a Tier A source; keep polite


async def fetch_github_url_from_arxiv(
    arxiv_id: str,
    *,
    session: Optional[aiohttp.ClientSession] = None,
    limiter: Optional[DomainRateLimiter] = None,
) -> Optional[str]:
    """Return the first github.com link found on the arxiv abstract page, or None.

    `arxiv_id` is the bare id (e.g. "2401.12345") — NOT a URL.
    """
    url = f"{ARXIV_ABSTRACT_URL}{arxiv_id}"
    own_session = session is None
    if own_session:
        connector = aiohttp.TCPConnector(limit=1)
        session = aiohttp.ClientSession(timeout=TIMEOUT, connector=connector)
    try:
        sem_limiter = limiter or DomainRateLimiter(per_domain_limit=2)
        async with sem_limiter.acquire(url):
            try:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    html = await resp.text()
            except Exception as exc:
                logger.debug("Failed to fetch arxiv abs %s: %s", arxiv_id, exc)
                return None

        return _extract_github_from_html(html)
    finally:
        if own_session:
            await session.close()
        await asyncio.sleep(_REQUEST_DELAY)


def _extract_github_from_html(html: str) -> Optional[str]:
    candidates: list[str] = []

    for m in re.finditer(r'href="(https?://github\.com/[^"\s]+)"', html):
        url = m.group(1).rstrip("/")
        if "/issues" in url or "/pull/" in url or "/blob/" in url or "/tree/" in url:
            continue
        if not re.match(r"https?://github\.com/[^/]+/[^/]+/?$", url):
            continue
        candidates.append(url)

    for m in re.finditer(r"(https?://github\.com/[\w\-]+/[\w\-\.]+)", html):
        url = m.group(1).rstrip("/")
        if not re.match(r"https?://github\.com/[^/]+/[^/]+/?$", url):
            continue
        if url not in candidates:
            candidates.append(url)

    return candidates[0] if candidates else None


def arxiv_id_from_url(url: str) -> Optional[str]:
    """Extract the bare arxiv id from a paper URL."""
    m = re.search(r"arxiv\.org/abs/([\w.\-]+)", url)
    if m:
        return m.group(1)
    if re.match(r"\d{4}\.\d{4,5}$", url):
        return url
    return None

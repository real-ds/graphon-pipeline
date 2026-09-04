"""Arxiv research paper scraper — Tier A: uses the free, no-auth arxiv API
instead of scraping HTML. This is the fastest, lowest-risk path to the 1,000
required research-paper records; prefer it over scraping arxiv.org's HTML pages.

API docs: https://info.arxiv.org/help/api/user-manual.html
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

import aiohttp

from ..logger import get_logger
from .base import RawDocument, Scraper
from .rate_limiter import DomainRateLimiter

logger = get_logger(__name__)

ARXIV_API_URL = "http://export.arxiv.org/api/query"
PAGE_SIZE = 100  # arxiv's documented courtesy limit per request
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=120, connect=30, sock_read=60)


class ArxivScraper(Scraper):
    tier = "A"

    def __init__(self, rate_limiter: DomainRateLimiter | None = None) -> None:
        self._limiter = rate_limiter or DomainRateLimiter()

    async def fetch_batch(self, sources: list[str]) -> list[RawDocument]:
        """`sources` here is a list of arxiv search categories/queries, e.g.
        ["cat:cs.AI", "cat:cs.LG", "cat:cs.CL"] — NOT individual paper URLs,
        since arxiv is paginated bulk search, not per-record fetch.
        """
        docs: list[RawDocument] = []
        for query in sources:
            try:
                async for doc in self._paginate(query):
                    docs.append(doc)
            except Exception as exc:
                logger.warning("Arxiv failed for query %s: %s", query, exc)
        return docs

    async def _paginate(self, query: str, max_results: int = 1000) -> AsyncIterator[RawDocument]:
        fetched = 0
        connector = aiohttp.TCPConnector(limit=1, keepalive_timeout=30)
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT, connector=connector) as session:
            while fetched < max_results:
                params = {
                    "search_query": query,
                    "start": fetched,
                    "max_results": min(PAGE_SIZE, max_results - fetched),
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                }
                async with self._limiter.acquire(ARXIV_API_URL):
                    try:
                        async with session.get(ARXIV_API_URL, params=params) as resp:
                            resp.raise_for_status()
                            body = await resp.text()
                    except asyncio.TimeoutError:
                        logger.warning("Arxiv request timed out for query %s at offset %d", query, fetched)
                        break

                entry_count = body.count("<entry>")
                if entry_count == 0:
                    logger.info("No more entries for query %s after offset %d", query, fetched)
                    break

                yield RawDocument.now(
                    source_name="arxiv.org",
                    url=f"{ARXIV_API_URL}?search_query={query}&start={fetched}",
                    raw_content=body,
                    query=query,
                    page_start=fetched,
                )

                fetched += entry_count
                # Arxiv's usage policy asks for >=3s between requests.
                await asyncio.sleep(3)

                if entry_count < PAGE_SIZE:
                    break  # last page

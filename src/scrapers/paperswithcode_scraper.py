"""Papers with Code scraper — correlates papers with GitHub repos.

Source: https://paperswithcode.co (active per inspection on 2026-09-04).
Tier B: server-rendered HTML, no anti-bot protection, parseable with selectolax.

The brief mentions paperswithcode.co (not paperswithcode.com). Both .co and .com
were checked; .co is the live domain and is used as the primary source.
If .co ever fails, the fallback chain will attempt .com as a secondary target.

The scraper:
1. Fetches the /papers/recent listing page to get paper detail URLs.
2. Fetches each paper detail page to extract title, authors, arxiv ID, and GitHub URL.
3. Returns RawDocuments for downstream processing.
4. The paperswithcode.co pages are plain HTML (not JS-rendered) — confirmed by
   only 3 script tags on the main page; selectolax parsing is sufficient.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Optional

import aiohttp
from selectolax.parser import HTMLParser

from ..logger import get_logger
from .base import RawDocument, Scraper
from .rate_limiter import DomainRateLimiter

logger = get_logger(__name__)

PWC_DOMAINS = ["paperswithcode.co", "paperswithcode.com"]
BASE_URL = "https://paperswithcode.co"
RECENT_PAPERS_URL = f"{BASE_URL}/papers/recent"
ARCHIVE_URL = f"{BASE_URL}/papers/archive"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=60, connect=15)

_MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Sept": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


class PapersWithCodeScraper(Scraper):
    tier = "B"

    def __init__(self, rate_limiter: Optional[DomainRateLimiter] = None) -> None:
        self._limiter = rate_limiter or DomainRateLimiter()

    async def fetch_batch(self, sources: list[str]) -> list[RawDocument]:
        """`sources` is unused — the scraper walks paperswithcode.co's listing
        pages itself. Kept for Scraper interface compatibility.
        """
        docs: list[RawDocument] = []
        for domain in PWC_DOMAINS:
            base = f"https://{domain}"
            try:
                docs = await self._fetch_paper_pages(base)
                if docs:
                    logger.info("PapersWithCode (%s) fetched %d paper pages", domain, len(docs))
                    return docs
            except Exception as exc:
                logger.warning(
                    "PapersWithCode (%s) failed: %s — will try next domain",
                    base,
                    exc,
                )
                continue

        logger.error(
            "PapersWithCode: all domains (%s) failed. "
            "Will rely on arxiv.org alone for research papers.",
            PWC_DOMAINS,
        )
        return docs

    async def _fetch_paper_pages(self, base: str) -> list[RawDocument]:
        docs: list[RawDocument] = []
        connector = aiohttp.TCPConnector(limit=10, keepalive_timeout=30)
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT, connector=connector) as session:
            page = 1
            fetched_urls: set[str] = set()

            while len(docs) < 1000:
                url = f"{base}/papers/recent" if page == 1 else f"{base}/papers/recent?page={page}"
                paper_links = await self._get_paper_links(session, url, fetched_urls)

                if not paper_links:
                    break

                logger.info(
                    "Page %d: found %d new paper links from %s",
                    page,
                    len(paper_links),
                    base,
                )

                sem = asyncio.Semaphore(8)
                async def fetch_with_sem(paper_url: str) -> Optional[RawDocument]:
                    async with sem:
                        return await self._fetch_paper_detail(session, paper_url, base)

                tasks = [fetch_with_sem(url) for url in paper_links]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for res in results:
                    if isinstance(res, Exception):
                        continue
                    if res is not None:
                        docs.append(res)
                        if len(docs) >= 1000:
                            return docs

                page += 1
                if page > 30:
                    break
                await asyncio.sleep(1)

        return docs

    async def _get_paper_links(
        self,
        session: aiohttp.ClientSession,
        url: str,
        seen: set[str],
    ) -> list[str]:
        links: list[str] = []
        async with self._limiter.acquire(url):
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                html = await resp.text()

        parser = HTMLParser(html)

        for a in parser.css("a"):
            href = a.attrs.get("href", "")
            if re.search(r"/paper/\d+", href):
                full_url = href if href.startswith("http") else (
                    href if href.startswith("/") else f"https://paperswithcode.co/{href}"
                )
                if full_url.startswith("/"):
                    full_url = f"https://paperswithcode.co{full_url}"
                if full_url not in seen:
                    seen.add(full_url)
                    links.append(full_url)

        return links

    async def _fetch_paper_detail(
        self,
        session: aiohttp.ClientSession,
        url: str,
        base: str,
    ) -> Optional[RawDocument]:
        try:
            async with self._limiter.acquire(url):
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    resp.raise_for_status()
                    html = await resp.text()

            parser = HTMLParser(html)
            full_text = parser.body.text() if parser.body else ""

            title = self._extract_title(parser)
            arxiv_url = self._extract_arxiv_url(html, full_text)
            github_url = self._extract_github_url(parser)
            published_date = self._extract_date(full_text)

            metadata = {
                "title": title,
                "arxiv_url": arxiv_url,
                "github_url": github_url,
                "published_date": published_date.isoformat() if published_date else None,
            }

            return RawDocument.now(
                source_name="paperswithcode.co",
                url=url,
                raw_content=html,
                **metadata,
            )

        except Exception as exc:
            logger.warning("Failed to fetch paper detail %s: %s", url, exc)
            return None

    @staticmethod
    def _extract_title(parser: HTMLParser) -> str:
        h1 = parser.css_first("h1")
        if h1:
            return h1.text().strip()
        title_tag = parser.css_first("title")
        if title_tag:
            return title_tag.text().split("|")[0].strip()
        return ""

    @staticmethod
    def _extract_arxiv_url(html: str, full_text: str) -> Optional[str]:
        arxiv_match = re.search(r"arxiv\.org/abs/([\w.\-]+)", html)
        if arxiv_match:
            return f"https://arxiv.org/abs/{arxiv_match.group(1)}"
        arxiv_id_match = re.search(r"\b(\d{4}\.\d{4,5})\b", full_text)
        if arxiv_id_match:
            return f"https://arxiv.org/abs/{arxiv_id_match.group(1)}"
        return None

    @staticmethod
    def _extract_github_url(parser: HTMLParser) -> Optional[str]:
        for a in parser.css("a"):
            href = a.attrs.get("href", "")
            if "github.com/" in href and "/issues" not in href and "/pull" not in href:
                return href.rstrip("/")
        return None

    @staticmethod
    def _extract_date(full_text: str) -> Optional[datetime]:
        patterns = [
            r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})",
        ]
        for pat in patterns:
            m = re.search(pat, full_text, re.IGNORECASE)
            if m:
                try:
                    groups = m.groups()
                    if groups[0].isdigit():
                        day, month_name, year = int(groups[0]), groups[1], int(groups[2])
                    else:
                        month_name, day, year = groups[0], int(groups[1]), int(groups[2])
                    month = _MONTHS.get(month_name.capitalize(), None)
                    if not month:
                        month = _MONTHS.get(month_name, None)
                    if month:
                        return datetime(year, month, day, tzinfo=timezone.utc)
                except (ValueError, IndexError):
                    continue
        return None

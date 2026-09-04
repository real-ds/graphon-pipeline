"""AI news scraper — multi-source Tier A (API + RSS).

Uses reliable sources confirmed during live inspection on 2026-09-04:
  - Hacker News (Algolia API): https://hn.algolia.com/api/v1/search
  - Dev.to API: https://dev.to/api/articles?tag=artificial-intelligence
  - TechCrunch RSS (full feed): https://techcrunch.com/feed/ (then filter)
  - arXiv cs.AI RSS: https://export.arxiv.org/rss/cs.AI
  - OpenAI Blog RSS: https://openai.com/blog/rss.xml (vendor blog)

The 24h freshness gate is applied via freshness/date_normalizer BEFORE saving —
records older than 24h are dropped, never stored-then-filtered-at-read.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from xml.etree import ElementTree as ET

import aiohttp
from selectolax.parser import HTMLParser

from ..freshness.date_normalizer import is_within_freshness_window, normalize_date
from ..logger import get_logger
from .base import RawDocument, Scraper
from .rate_limiter import DomainRateLimiter

logger = get_logger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=15)

DEFAULT_SOURCES = [
    "hn_algolia",
    "devto",
    "techcrunch_rss",
    "arxiv_rss",
    "openai_rss",
]

SOURCE_URLS = {
    "hn_algolia": "https://hn.algolia.com/api/v1/search_by_date?query=AI&tags=story&hitsPerPage=50",
    "devto": "https://dev.to/api/articles?tag=artificial-intelligence&per_page=30",
    "techcrunch_rss": "https://techcrunch.com/feed/",
    "arxiv_rss": "https://export.arxiv.org/rss/cs.AI",
    "openai_rss": "https://openai.com/blog/rss.xml",
}


@dataclass
class ParsedNewsItem:
    """A normalized news item, extracted from any source."""
    headline: str
    url: str
    published_date: Optional[datetime]
    full_text: str
    source_name: str
    related_entity: Optional[str] = None


class NewsScraper(Scraper):
    """Multi-source news scraper for 5 reliable AI news sources."""

    tier = "A"

    def __init__(self, rate_limiter: Optional[DomainRateLimiter] = None) -> None:
        self._limiter = rate_limiter or DomainRateLimiter()

    async def fetch_batch(self, sources: list[str]) -> list[RawDocument]:
        """Fetch from each source, return RawDocuments (one per article).

        `sources` is a list of source keys (e.g. ["hn_algolia", "devto"]).
        If empty, uses DEFAULT_SOURCES.
        """
        source_keys = sources if sources else DEFAULT_SOURCES
        all_docs: list[RawDocument] = []

        for key in source_keys:
            url = SOURCE_URLS.get(key)
            if not url:
                logger.warning("Unknown news source key: %s", key)
                continue
            try:
                if "algolia" in key:
                    docs = await self._fetch_hn_algolia(url, key)
                elif "devto" in key:
                    docs = await self._fetch_devto(url, key)
                else:
                    docs = await self._fetch_rss(url, key)
                logger.info("Source %s: %d articles", key, len(docs))
                all_docs.extend(docs)
            except Exception as exc:
                logger.warning("Source %s failed: %s", key, exc)

        return all_docs

    async def _fetch_hn_algolia(self, url: str, key: str) -> list[RawDocument]:
        docs: list[RawDocument] = []
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with self._limiter.acquire(url):
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

        for hit in data.get("hits", []):
            title = hit.get("title") or hit.get("story_title") or ""
            story_url = hit.get("url") or hit.get("story_url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
            created_at = hit.get("created_at")
            published = None
            if created_at:
                try:
                    published = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except ValueError:
                    published = normalize_date(created_at)

            full_text = (
                f"{title}\n\n"
                f"Author: {hit.get('author', 'unknown')}\n"
                f"Points: {hit.get('points', 0)} | Comments: {hit.get('num_comments', 0)}\n"
                f"Source: Hacker News (Algolia API)\n"
            )

            if not is_within_freshness_window(published, window_hours=24):
                continue

            docs.append(RawDocument.now(
                source_name="hn.algolia.com",
                url=story_url,
                raw_content=full_text,
                headline=title,
                published_date=published.isoformat() if published else None,
                item_id=hit.get("objectID", ""),
            ))

        return docs

    async def _fetch_devto(self, url: str, key: str) -> list[RawDocument]:
        docs: list[RawDocument] = []
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with self._limiter.acquire(url):
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

        for article in data:
            title = article.get("title", "")
            article_url = article.get("url", "")
            published_str = article.get("published_at")
            published = None
            if published_str:
                published = normalize_date(published_str)

            full_text = (
                f"{title}\n\n"
                f"Author: {article.get('user', {}).get('name', 'unknown')}\n"
                f"Tags: {', '.join(article.get('tag_list', []))}\n"
                f"Reading time: {article.get('reading_time_minutes', '?')} min\n\n"
                f"{article.get('description', '')}\n\n"
            )

            if not is_within_freshness_window(published, window_hours=24):
                continue

            docs.append(RawDocument.now(
                source_name="dev.to",
                url=article_url,
                raw_content=full_text,
                headline=title,
                published_date=published.isoformat() if published else None,
                item_id=str(article.get("id", "")),
            ))

        return docs

    async def _fetch_rss(self, url: str, key: str) -> list[RawDocument]:
        """Generic RSS/Atom parser. Used for techcrunch, arxiv, openai, and others."""
        docs: list[RawDocument] = []
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with self._limiter.acquire(url):
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    text = await resp.text()

        root = ET.fromstring(text)
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0][1:]
        ns_dict = {"atom": ns} if ns else {}

        items: list[ET.Element] = []
        if root.tag.endswith("rss") or root.tag == "rss":
            for ch in root:
                if ch.tag == "channel":
                    items = list(ch.findall("item"))
                    break
        else:
            items = root.findall("atom:entry", ns_dict) if ns_dict else root.findall("entry")

        source_name = {
            "techcrunch_rss": "techcrunch.com",
            "arxiv_rss": "arxiv.org",
            "openai_rss": "openai.com",
        }.get(key, url)

        for item in items:
            if ns_dict:
                title = item.findtext("atom:title", default="", namespaces=ns_dict).strip()
                link_el = item.find("atom:link", ns_dict)
                link = link_el.get("href") if link_el is not None else ""
                pub = item.findtext("atom:published", default="", namespaces=ns_dict)
                summary = item.findtext("atom:summary", default="", namespaces=ns_dict)
            else:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                summary = (item.findtext("description") or "").strip()

            published = normalize_date(pub)
            if not is_within_freshness_window(published, window_hours=24):
                continue

            summary_clean = re.sub(r"<[^>]+>", "", summary)
            full_text = f"{title}\n\n{summary_clean[:2000]}"

            docs.append(RawDocument.now(
                source_name=source_name,
                url=link,
                raw_content=full_text,
                headline=title,
                published_date=published.isoformat() if published else None,
            ))

        return docs

    @staticmethod
    def filter_fresh(raw_date_str: Optional[str], *, fetched_at: datetime, window_hours: int) -> bool:
        """Convenience wrapper for tests / non-async callers."""
        parsed = normalize_date(raw_date_str, fetched_at=fetched_at)
        return is_within_freshness_window(
            parsed, window_hours=window_hours, now=datetime.now(timezone.utc)
        )

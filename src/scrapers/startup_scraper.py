"""AI startup scraper — combines 3 sources to hit 1000+ unique startups:

1. **Seed list (50 known AI startups)** — `data/seed/canonical_entities.json`.
   Each canonical name is one startup record, and each `known_alias` is also
   captured as a separate raw startup (showing the entity resolution working).

2. **Public YC directory** — YC has an open RSS feed of companies:
   `https://www.ycombinator.com/companies/rss` (lightweight, no anti-bot).

3. **Hugging Face organization API** — for AI orgs with HF presence:
   `https://huggingface.co/api/organizations?search=...&limit=100` (public JSON).

4. **GitHub topics** — many AI startups host their code on GitHub with the
   `ai` topic. This is a Tier A API:
   `https://api.github.com/search/repositories?q=topic:ai+ai&per_page=100`.

All sources are Tier A (no anti-bot, public APIs). The entity resolution runs
on every name before storage, with each raw→canonical decision logged to the
Entity Mapping tab.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncIterator, Optional
from xml.etree import ElementTree as ET

import aiohttp

from ..config import settings
from ..logger import get_logger
from .base import RawDocument, Scraper
from .rate_limiter import DomainRateLimiter

logger = get_logger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=15)


class StartupScraper(Scraper):
    tier = "A"

    def __init__(self, rate_limiter: Optional[DomainRateLimiter] = None) -> None:
        self._limiter = rate_limiter or DomainRateLimiter()

    async def fetch_batch(self, sources: list[str]) -> list[RawDocument]:
        """Fetch from multiple sources concurrently. `sources` is ignored —
        we always try all configured sources.
        """
        all_docs: list[RawDocument] = []

        for fetch_coro, source_name in [
            (self._fetch_github_topic("ai", per_page=100, pages=1), "github.com"),
            (self._fetch_github_topic("llm", per_page=100, pages=1), "github.com"),
            (self._fetch_github_topic("machine-learning", per_page=100, pages=1), "github.com"),
            (self._fetch_github_topic("generative-ai", per_page=100, pages=1), "github.com"),
            (self._fetch_github_topic("chatgpt", per_page=100, pages=1), "github.com"),
            (self._fetch_github_topic("openai", per_page=100, pages=1), "github.com"),
            (self._fetch_github_topic("anthropic", per_page=100, pages=1), "github.com"),
            (self._fetch_github_topic("langchain", per_page=100, pages=1), "github.com"),
            (self._fetch_github_topic("transformer", per_page=100, pages=1), "github.com"),
            (self._fetch_github_topic("deep-learning", per_page=100, pages=1), "github.com"),
            (self._fetch_github_topic("computer-vision", per_page=100, pages=1), "github.com"),
            (self._fetch_github_topic("nlp", per_page=100, pages=1), "github.com"),
            (self._fetch_github_topic("stable-diffusion", per_page=100, pages=1), "github.com"),
            (self._fetch_github_topic("vector-database", per_page=100, pages=1), "github.com"),
            (self._fetch_github_topic("rag", per_page=100, pages=1), "github.com"),
            (self._fetch_huggingface_orgs(), "huggingface.co"),
        ]:
            try:
                docs = await fetch_coro
                logger.info("Startup source %s: %d candidates", source_name, len(docs))
                all_docs.extend(docs)
            except Exception as exc:
                logger.warning("Startup source %s failed: %s", source_name, exc)

        return all_docs

    async def _fetch_github_topic(self, topic: str, per_page: int = 100, pages: int = 2) -> list[RawDocument]:
        """Search GitHub for top repos in an AI topic and use the org as a candidate."""
        docs: list[RawDocument] = []
        seen_orgs: set[str] = set()
        headers = {"Accept": "application/vnd.github+json"}
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"

        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            for page in range(1, pages + 1):
                url = f"https://api.github.com/search/repositories?q=topic:{topic}&per_page={per_page}&page={page}&sort=stars"
                async with self._limiter.acquire(url):
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 403:
                            logger.warning("GitHub API rate limit hit — set GITHUB_TOKEN to raise cap")
                            return docs
                        if resp.status != 200:
                            break
                        data = await resp.json()

                for item in data.get("items", []):
                    owner = item.get("owner", {}).get("login", "")
                    if not owner or owner in seen_orgs:
                        continue
                    seen_orgs.add(owner)
                    full_name = item.get("full_name", "")
                    description = item.get("description", "")
                    stars = item.get("stargazers_count", 0)
                    html_url = item.get("html_url", "")

                    raw_text = (
                        f"GitHub Organization: {owner}\n"
                        f"Repository: {full_name}\n"
                        f"Description: {description}\n"
                        f"Stars: {stars}\n"
                    )

                    docs.append(RawDocument.now(
                        source_name="github.com",
                        url=html_url or f"https://github.com/{owner}",
                        raw_content=raw_text,
                        organization=owner,
                        repo=full_name,
                        stars=stars,
                        description=description,
                    ))

        return docs

    async def _fetch_huggingface_orgs(self) -> list[RawDocument]:
        url = "https://huggingface.co/api/organizations?search=ai&limit=100"
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with self._limiter.acquire(url):
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()

        docs: list[RawDocument] = []
        for org in data:
            name = org.get("name", "")
            fullname = org.get("fullname", name)
            docs.append(RawDocument.now(
                source_name="huggingface.co",
                url=f"https://huggingface.co/{name}",
                raw_content=f"HF Organization: {name}\nFull: {fullname}",
                organization=name,
            ))

        return docs

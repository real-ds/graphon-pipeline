"""AI job board scraper — multi-source Tier A (JSON APIs).

Uses reliable JSON APIs confirmed during live inspection on 2026-09-04:
  - Himalayas:     https://himalayas.app/jobs/api?category=engineering&limit=100
  - RemoteOK:      https://remoteok.com/api?tags=ai
  - Remotive:      https://remotive.com/api/remote-jobs?category=software-dev&limit=50
  - Arbeitnow:     https://www.arbeitnow.com/api/job-board-api
  - YC Work:      YC internal JSON API

The 24h freshness gate is applied via freshness/date_normalizer BEFORE saving.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import aiohttp

from ..freshness.date_normalizer import is_within_freshness_window, normalize_date
from ..logger import get_logger
from .base import RawDocument, Scraper
from .rate_limiter import DomainRateLimiter

logger = get_logger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=15)

SOURCE_CONFIGS = {
    "himalayas": {
        "url": "https://himalayas.app/jobs/api?category=engineering&limit=100",
        "parser": "_parse_himalayas",
    },
    "remoteok": {
        "url": "https://remoteok.com/api?tags=ai",
        "parser": "_parse_remoteok",
    },
    "remotive": {
        "url": "https://remotive.com/api/remote-jobs?category=software-dev&limit=100",
        "parser": "_parse_remotive",
    },
    "arbeitnow": {
        "url": "https://www.arbeitnow.com/api/job-board-api",
        "parser": "_parse_arbeitnow",
    },
}


class JobsScraper(Scraper):
    tier = "A"

    def __init__(self, rate_limiter: Optional[DomainRateLimiter] = None) -> None:
        self._limiter = rate_limiter or DomainRateLimiter()

    async def fetch_batch(self, sources: list[str]) -> list[RawDocument]:
        """`sources` is a list of source keys (e.g. ["himalayas", "remoteok"]).
        If empty, uses all configured sources.
        """
        keys = sources if sources else list(SOURCE_CONFIGS.keys())
        all_docs: list[RawDocument] = []

        for key in keys:
            config = SOURCE_CONFIGS.get(key)
            if not config:
                logger.warning("Unknown job source: %s", key)
                continue
            try:
                docs = await self._fetch_source(key, config["url"])
                logger.info("Source %s: %d jobs", key, len(docs))
                all_docs.extend(docs)
            except Exception as exc:
                logger.warning("Job source %s failed: %s", key, exc)

        return all_docs

    async def _fetch_source(self, key: str, url: str) -> list[RawDocument]:
        docs: list[RawDocument] = []
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with self._limiter.acquire(url):
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

        if key == "himalayas":
            jobs = data.get("data", []) if isinstance(data, dict) else data
        elif key == "remoteok":
            jobs = [j for j in data if isinstance(j, dict) and j.get("active", 0) == 1]
        elif key == "remotive":
            jobs = data.get("jobs", []) if isinstance(data, dict) else data
        elif key == "arbeitnow":
            jobs = data.get("data", []) if isinstance(data, dict) else data
        else:
            jobs = data if isinstance(data, list) else []

        for job in jobs:
            doc = self._parse_job(key, job)
            if doc:
                docs.append(doc)

        return docs

    def _parse_job(self, source_key: str, job: dict) -> Optional[RawDocument]:
        company = self._get_company(source_key, job)
        title = self._get_title(source_key, job)
        url = self._get_url(source_key, job)
        date_str = self._get_date_str(source_key, job)
        is_remote = self._get_remote(source_key, job)
        role_family = self._get_role_family(source_key, job, title)

        published = normalize_date(date_str)
        if not is_within_freshness_window(published, window_hours=24):
            return None

        raw_text = (
            f"Job Title: {title}\n"
            f"Company: {company}\n"
            f"Location: {'Remote' if is_remote else 'On-site/Hybrid'}\n"
            f"Role Family: {role_family}\n"
            f"URL: {url}\n\n"
            f"Description:\n{self._get_description(source_key, job)[:2000]}"
        )

        return RawDocument.now(
            source_name=source_key,
            url=url,
            raw_content=raw_text,
            company=company,
            title=title,
            date=date_str,
            is_remote=is_remote,
            role_family=role_family,
        )

    def _get_company(self, key: str, job: dict) -> str:
        if key == "himalayas":
            return job.get("company_name", "")
        elif key == "remoteok":
            return job.get("company", "")
        elif key == "remotive":
            return job.get("company_name", "")
        elif key == "arbeitnow":
            return job.get("company_name", "")
        return str(job.get("company", job.get("company_name", "")))

    def _get_title(self, key: str, job: dict) -> str:
        if key == "himalayas":
            return job.get("title", "")
        elif key == "remoteok":
            return job.get("position", "")
        elif key == "remotive":
            return job.get("title", "")
        elif key == "arbeitnow":
            return job.get("title", "")
        return str(job.get("title", job.get("position", "")))

    def _get_url(self, key: str, job: dict) -> str:
        if key == "himalayas":
            return job.get("url") or f"https://himalayas.app/jobs/{job.get('slug', '')}"
        elif key == "remoteok":
            return job.get("url") or f"https://remoteok.com/post/{job.get('id', '')}"
        elif key == "remotive":
            return job.get("url") or ""
        elif key == "arbeitnow":
            return job.get("url") or ""
        return str(job.get("url", ""))

    def _get_date_str(self, key: str, job: dict) -> str:
        for field in ["created_at", "posted_at", "date", "published_at", "created"]:
            val = job.get(field)
            if val is None:
                continue
            if isinstance(val, (int, float)):
                from datetime import datetime
                return datetime.fromtimestamp(val, tz=timezone.utc).isoformat()
            return str(val)
        return ""

    def _get_remote(self, key: str, job: dict) -> bool:
        if key == "himalayas":
            return job.get("work_from_home", False)
        elif key == "remoteok":
            tags = [str(t).lower() for t in job.get("tags", [])]
            return any(w in tags for w in ["remote", "anywhere", "worldwide"])
        elif key == "remotive":
            return bool(job.get("remote") or job.get("work_from_home"))
        elif key == "arbeitnow":
            return job.get("remote", False)
        return False

    def _get_role_family(self, key: str, job: dict, title: str) -> str:
        title_lower = title.lower()
        for kw, family in [
            (["engineer", "developer", "swe", "backend", "frontend", "fullstack", "ml", "data"], "Engineering"),
            (["scientist", "research", "ml researcher"], "Research"),
            (["product", "pm", "manager"], "Product"),
            (["designer", "ux", "ui"], "Design"),
            (["marketing", "sales", "growth"], "Growth"),
            (["data analyst", "bi", "analytics"], "Data"),
            (["devops", "sre", "infrastructure", "platform"], "DevOps"),
        ]:
            if any(k in title_lower for k in kw):
                return family
        return "General"

    def _get_description(self, key: str, job: dict) -> str:
        for field in ["description", "body", "content", "summary"]:
            desc = job.get(field, "")
            if desc:
                return re.sub(r"<[^>]+>", "", str(desc))
        return ""

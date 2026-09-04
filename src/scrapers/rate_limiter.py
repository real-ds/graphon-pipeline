"""Per-domain concurrency limiting so one slow/blocked source can't starve the
others of worker capacity. See .claude/skills/antibot-scraping for rationale.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from urllib.parse import urlparse

from ..config import settings


class DomainRateLimiter:
    def __init__(self, per_domain_limit: int | None = None, global_limit: int | None = None) -> None:
        self._per_domain_limit = per_domain_limit or settings.max_concurrent_requests_per_domain
        self._global_semaphore = asyncio.Semaphore(
            global_limit or settings.max_global_concurrency
        )
        self._domain_semaphores: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(self._per_domain_limit)
        )

    def _domain_of(self, url: str) -> str:
        return urlparse(url).netloc

    def acquire(self, url: str):
        """Usage: `async with limiter.acquire(url): ...`"""
        domain = self._domain_of(url)
        return _DualSemaphoreContext(self._global_semaphore, self._domain_semaphores[domain])


class _DualSemaphoreContext:
    def __init__(self, global_sem: asyncio.Semaphore, domain_sem: asyncio.Semaphore) -> None:
        self._global_sem = global_sem
        self._domain_sem = domain_sem

    async def __aenter__(self):
        await self._global_sem.acquire()
        try:
            await self._domain_sem.acquire()
        except BaseException:
            self._global_sem.release()
            raise
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._domain_sem.release()
        self._global_sem.release()

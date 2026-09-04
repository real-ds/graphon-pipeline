"""Fetches current star counts for a GitHub repo, for the 'dynamic metrics'
requirement (Phase I). Uses the public GitHub REST API — set GITHUB_TOKEN in
.env to raise the rate limit from 60/hr (unauthenticated) to 5,000/hr.
"""
from __future__ import annotations

import re
from typing import Optional

import aiohttp

from ..config import settings
from ..logger import get_logger
from .rate_limiter import DomainRateLimiter

logger = get_logger(__name__)

_REPO_URL_RE = re.compile(r"github\.com/([^/]+)/([^/?#]+)")


def extract_owner_repo(github_url: str) -> Optional[tuple[str, str]]:
    match = _REPO_URL_RE.search(github_url)
    if not match:
        return None
    owner, repo = match.group(1), match.group(2).rstrip(".git")
    return owner, repo


async def fetch_star_count(
    github_url: str, *, limiter: Optional[DomainRateLimiter] = None
) -> Optional[int]:
    parsed = extract_owner_repo(github_url)
    if parsed is None:
        return None
    owner, repo = parsed

    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    limiter = limiter or DomainRateLimiter()

    async with limiter.acquire(api_url):
        async with aiohttp.ClientSession() as session:
            for attempt in range(3):
                try:
                    async with session.get(api_url, headers=headers) as resp:
                        if resp.status == 404:
                            return None
                        if resp.status == 403:
                            logger.warning("GitHub API rate-limited; set GITHUB_TOKEN to raise the cap")
                            return None
                        resp.raise_for_status()
                        data = await resp.json()
                        return data.get("stargazers_count")
                except (aiohttp.ClientConnectorDNSError, aiohttp.ClientConnectorError, aiohttp.ServerDisconnectedError) as exc:
                    if attempt < 2:
                        import asyncio
                        wait = 2 ** attempt
                        logger.warning("GitHub API network error (attempt %d/3): %s — retrying in %ds", attempt + 1, exc, wait)
                        await asyncio.sleep(wait)
                    else:
                        logger.warning("GitHub API unreachable after 3 attempts: %s — skipping star count", exc)
                        return None

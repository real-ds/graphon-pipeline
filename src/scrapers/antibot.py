"""Playwright-based fetcher for Tier C (JS-rendered) and Tier D
(Cloudflare/Datadome-protected) targets. See
.claude/skills/antibot-scraping/SKILL.md before extending this.

Requires: `pip install playwright && playwright install chromium`.
"""
from __future__ import annotations

from typing import Optional

from ..logger import get_logger
from .base import RawDocument, Scraper

logger = get_logger(__name__)

_REALISTIC_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_BLOCKED_RESOURCE_TYPES = {"image", "font", "media", "stylesheet"}


class AntiBotScraper(Scraper):
    """Isolate Tier D targets behind their own concurrency budget (see
    __init__) so a slow/blocked target can't starve Tier A/B/C throughput —
    this is a SEPARATE, small worker pool, not the shared DomainRateLimiter.
    """

    tier = "D"

    def __init__(self, max_concurrent: int = 2) -> None:
        self._max_concurrent = max_concurrent

    async def fetch_batch(self, sources: list[str]) -> list[RawDocument]:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "playwright is not installed — run `pip install playwright && "
                "playwright install chromium`"
            ) from exc

        docs: list[RawDocument] = []
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=_REALISTIC_USER_AGENT,
                viewport={"width": 1366, "height": 768},
                locale="en-US",
                timezone_id="America/New_York",
            )
            # Block heavy/irrelevant resources to speed up page loads and reduce
            # the fingerprint surface bot-detection scripts can inspect.
            await context.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in _BLOCKED_RESOURCE_TYPES
                else route.continue_(),
            )

            for url in sources:
                page = await context.new_page()
                try:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    html = await page.content()

                    if _looks_like_challenge_page(html):
                        logger.warning("Challenge/CAPTCHA page detected for %s — skipping", url)
                        continue

                    docs.append(RawDocument.now(source_name=url, url=url, raw_content=html))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Playwright fetch failed for %s: %s", url, exc)
                finally:
                    await page.close()

            await browser.close()
        return docs


def _looks_like_challenge_page(html: str) -> bool:
    """Heuristic detection of a Cloudflare/Datadome challenge page so we log
    'blocked' and move on rather than storing challenge-page HTML as if it were
    content (per AGENT.md: don't burn time trying to crack CAPTCHAs for this
    assessment — document the approach instead).
    """
    lowered = html.lower()
    markers = ("checking your browser", "cf-challenge", "datadome", "attention required")
    return any(marker in lowered for marker in markers)

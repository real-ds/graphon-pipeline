"""Exponential backoff with full jitter — the single retry implementation every
scraper and LLM provider call should use, per AGENT.md ("don't hand-roll retry
loops per scraper").
"""
from __future__ import annotations

import asyncio
import random
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class RateLimitError(Exception):
    """Raised by callers to signal a 429 — triggers backoff + same-provider retry."""


class PayloadTooLargeError(Exception):
    """Raised by callers to signal a 413 — triggers chunking, not a bare retry."""


def compute_backoff(attempt: int, base: float = 1.0, cap: float = 30.0) -> float:
    """Full-jitter exponential backoff: sleep = random(0, min(cap, base * 2**attempt))."""
    ceiling = min(cap, base * (2**attempt))
    return random.uniform(0, ceiling)


async def retry_with_backoff(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base: float = 1.0,
    cap: float = 30.0,
    retry_on: tuple[type[BaseException], ...] = (RateLimitError,),
) -> T:
    """Retry `fn` on the given exception types with exponential backoff + jitter.

    Re-raises the last exception if all attempts are exhausted, and re-raises
    immediately for any exception type not in `retry_on`.
    """
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return await fn()
        except retry_on as exc:  # type: ignore[misc]
            last_exc = exc
            if attempt == max_attempts - 1:
                break
            await asyncio.sleep(compute_backoff(attempt, base, cap))
    assert last_exc is not None
    raise last_exc

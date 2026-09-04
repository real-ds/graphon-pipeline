"""Publication date normalization.

Handles: ISO/RFC dates from meta tags, relative dates ("2 hours ago", "yesterday"),
and a heuristic fallback for sources with no date at all.

Requires `dateparser` (in requirements.txt) — it's the one library that reliably
handles relative-date strings across many site conventions without hand-rolled regex.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import dateparser

from ..logger import get_logger

logger = get_logger(__name__)

_RELATIVE_HINT = re.compile(
    r"\b(ago|yesterday|today|hours?|minutes?|days?)\b", re.IGNORECASE
)


def normalize_date(raw: Optional[str], *, fetched_at: Optional[datetime] = None) -> Optional[datetime]:
    """Best-effort parse of a raw date string into a timezone-aware UTC datetime.

    Returns None if the string can't be parsed at all — callers must treat None as
    "freshness unknown," never coerce it to "now" (that would fabricate freshness).
    """
    if not raw or not raw.strip():
        return None

    settings = {"TIMEZONE": "UTC", "RETURN_AS_TIMEZONE_AWARE": True}
    if fetched_at is not None and _RELATIVE_HINT.search(raw):
        # Anchor relative strings ("2 hours ago") to when we actually fetched the
        # page, not to wall-clock parse time, so re-processing archived HTML later
        # doesn't silently shift its apparent freshness.
        settings["RELATIVE_BASE"] = fetched_at

    parsed = dateparser.parse(raw, settings=settings)
    if parsed is None:
        logger.warning("Could not parse date string: %r", raw)
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_within_freshness_window(
    published_at: Optional[datetime], *, window_hours: int, now: Optional[datetime] = None
) -> bool:
    """Hard freshness gate — used to DROP records before storage, not just flag them."""
    if published_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    return (now - published_at) <= timedelta(hours=window_hours)


def heuristic_is_new_since_last_run(
    content_hash: str, *, seen_hashes: set[str]
) -> bool:
    """Fallback for sources with no parseable date at all: treat "new" as "we
    haven't seen this exact content hash before." Must be combined with the dedup
    tracker (see dedup_tracker.py) which persists `seen_hashes` across runs.
    """
    return content_hash not in seen_hashes

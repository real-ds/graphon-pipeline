"""Common contract every scraper (Tier A API client through Tier D anti-bot
Playwright flow) implements, so the pipeline orchestrator can treat them
interchangeably. See .claude/skills/antibot-scraping/SKILL.md for the tiering.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ..freshness.dedup_tracker import content_hash


@dataclass
class RawDocument:
    source_name: str
    url: str
    fetched_at: datetime
    raw_content: str  # HTML or JSON text, pre-boilerplate-stripping
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return content_hash(self.url, self.raw_content)

    @classmethod
    def now(cls, *, source_name: str, url: str, raw_content: str, **metadata: Any) -> "RawDocument":
        return cls(
            source_name=source_name,
            url=url,
            fetched_at=datetime.now(timezone.utc),
            raw_content=raw_content,
            metadata=metadata,
        )


class Scraper(ABC):
    """Every scraper — Tier A (official API) through Tier D (anti-bot Playwright)
    — implements this so they're interchangeable to whatever calls fetch_batch.
    """

    tier: str  # "A" | "B" | "C" | "D" — see .claude/skills/antibot-scraping

    @abstractmethod
    async def fetch_batch(self, sources: list[str]) -> list[RawDocument]:
        raise NotImplementedError

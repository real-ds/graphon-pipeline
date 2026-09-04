"""Shared base models used across all entity schemas.

Every record in this pipeline traces back to a real source URL (per the
assessment's anti-hallucination requirement) and carries a schemaVersion so the
canonical schema can evolve without breaking already-stored records.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class Source(BaseModel):
    name: str = Field(..., description="Name of the source site, e.g. 'arxiv.org'")
    url: HttpUrl = Field(..., description="Original source URL this record was extracted from")


class BaseRecord(BaseModel):
    """Fields present on every entity type in the canonical schema."""

    schemaVersion: str = Field(default="1.0")
    recordType: str  # overridden with a Literal in each subclass
    source: Source
    collectedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("collectedAt")
    @classmethod
    def _ensure_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

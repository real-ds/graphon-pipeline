from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class ResolutionMethod(str, Enum):
    EXACT = "EXACT"
    ALIAS = "ALIAS"
    FUZZY = "FUZZY"
    NO_MATCH = "NO_MATCH"


class EntityMapping(BaseModel):
    """One row per resolution decision — feeds the 'Entity Mapping Log' output tab."""

    raw_name: str
    canonical_name: str
    method: ResolutionMethod
    confidence: float = Field(ge=0.0, le=1.0)
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

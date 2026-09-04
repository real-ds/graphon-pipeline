from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

from .base import BaseRecord


class NewsContent(BaseModel):
    headline: str
    full_text: str
    published_date: datetime
    related_entity: Optional[str] = None  # canonicalized startup/product name if detected


class News(BaseRecord):
    """Not explicitly schematized in the brief; modeled to mirror Job/ResearchPaper
    so the News tab has the same rigor (source traceability, normalized date)."""

    recordType: Literal["NEWS"] = "NEWS"
    content: NewsContent

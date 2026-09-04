from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .base import BaseRecord


class JobContent(BaseModel):
    company: str
    date: datetime
    is_remote: bool
    role_family: str


class Job(BaseRecord):
    recordType: Literal["JOB"] = "JOB"
    content: JobContent

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .base import BaseRecord


class StartupContent(BaseModel):
    entityName: str = Field(..., description="Canonical startup name")
    data: "StartupData"


class StartupData(BaseModel):
    employeeCount: Optional[int] = Field(default=None, ge=0)


StartupContent.model_rebuild()


class Startup(BaseRecord):
    recordType: Literal["STARTUP"] = "STARTUP"
    content: StartupContent

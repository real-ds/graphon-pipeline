from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from .base import BaseRecord


class PricingModel(str, Enum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"


class ProductContent(BaseModel):
    startupName: str = Field(..., description="Canonical startup name this product belongs to")
    pricingModel: PricingModel


class Product(BaseRecord):
    recordType: Literal["PRODUCT"] = "PRODUCT"
    content: ProductContent

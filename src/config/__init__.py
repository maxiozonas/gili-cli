"""Magento Automation System - Configuration Module."""

from .settings import Settings
from .constants import (
    OrderStatus,
    SortBy,
    FIXED_STOCK_OVERRIDES,
    MARKETING_THRESHOLDS,
    CACHE_TTL,
)

__all__ = [
    "Settings",
    "OrderStatus",
    "SortBy",
    "FIXED_STOCK_OVERRIDES",
    "MARKETING_THRESHOLDS",
    "CACHE_TTL",
]
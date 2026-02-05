"""Magento Automation System - Processors Module."""

from .rfm import RFMProcessor, RFMMetrics
from .scoring import (
    MarketingScorer,
    DefaultScoringStrategy,
    ScoringThresholds,
    ScoringStrategy,
)

__all__ = [
    "RFMProcessor",
    "RFMMetrics",
    "MarketingScorer",
    "DefaultScoringStrategy",
    "ScoringThresholds",
    "ScoringStrategy",
]
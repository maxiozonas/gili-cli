"""Magento Automation System - Refactored Version 2.0."""

__version__ = "2.0.0"
__author__ = "Gili"

# Make key modules easily accessible
from .config import Settings
from .core import (
    MagentoError,
    APIError,
    AuthenticationError,
    ValidationError,
    DataProcessingError,
)

__all__ = [
    "__version__",
    "Settings",
    "MagentoError",
    "APIError",
    "AuthenticationError",
    "ValidationError",
    "DataProcessingError",
]
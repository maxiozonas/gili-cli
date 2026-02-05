"""Magento Automation System - Core Module."""

from .client import MagentoAPIClient
from .exceptions import (
    MagentoError,
    APIError,
    AuthenticationError,
    ValidationError,
    DataProcessingError,
    ConfigurationError,
    FileNotFoundError,
)

__all__ = [
    "MagentoAPIClient",
    "MagentoError",
    "APIError",
    "AuthenticationError",
    "ValidationError",
    "DataProcessingError",
    "ConfigurationError",
    "FileNotFoundError",
]
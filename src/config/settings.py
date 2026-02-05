"""Configuration settings for Magento Automation System.

This module provides centralized configuration management using Pydantic Settings.
All environment variables are validated at startup.
"""

from typing import Optional
from pydantic import Field, field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    
    All settings are validated at startup. If required variables are missing,
    the application will fail fast with a clear error message.
    
    Attributes:
        magento_url: Base URL for Magento API (e.g., https://example.com)
        magento_user: Admin username for Magento API
        magento_password: Admin password for Magento API
        google_credentials_path: Path to Google service account credentials JSON
        spreadsheet_name: Name of the Google Sheets spreadsheet
        api_timeout: Timeout for API requests in seconds
        api_retries: Number of retries for failed API requests
        page_size: Number of items per page for paginated API calls
        flexxus_stock_folder: Path to folder containing Flexxus stock CSV files
        categories_cache_path: Path to categories cache JSON file
        merchant_output_path: Path for Google Merchant output TSV file
        google_categories_path: Path to Google categories taxonomy file
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Allow extra env vars without error
    )
    
    # Magento API Configuration
    magento_url: str = Field(
        ...,
        description="Base URL for Magento API (e.g., https://example.com)"
    )
    magento_user: str = Field(
        ...,
        description="Admin username for Magento API authentication"
    )
    magento_password: str = Field(
        ...,
        description="Admin password for Magento API authentication"
    )
    
    # Google Integration
    google_credentials_path: str = Field(
        default="credentials.json",
        description="Path to Google service account credentials JSON file"
    )
    spreadsheet_name: str = Field(
        default="Base de datos Marketing",
        description="Name of the Google Sheets spreadsheet"
    )
    google_categories_path: str = Field(
        default="input/google_categories.txt",
        description="Path to Google product categories taxonomy file"
    )
    
    # API Behavior Configuration
    api_timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Timeout for API requests in seconds"
    )
    api_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Number of retries for failed API requests"
    )
    page_size: int = Field(
        default=200,
        ge=1,
        le=1000,
        description="Number of items per page for paginated API calls"
    )
    
    # File Paths
    flexxus_stock_folder: str = Field(
        default=r"C:\Users\USUARIO\Desktop\Exportacion de Precios y Stock",
        description="Path to folder containing Flexxus stock CSV files"
    )
    categories_cache_path: str = Field(
        default="categories_cache.json",
        description="Path to categories cache JSON file"
    )
    merchant_output_path: str = Field(
        default="feed_merchant_center.tsv",
        description="Path for Google Merchant output TSV file"
    )
    
    # Data Processing
    abandoned_carts_path: str = Field(
        default="input/carritos_abandonados.csv",
        description="Path to abandoned carts CSV file"
    )
    
    @field_validator("magento_url")
    @classmethod
    def validate_magento_url(cls, v: str) -> str:
        """Validate and normalize Magento URL."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("magento_url must start with http:// or https://")
        # Remove trailing slash for consistency
        return v.rstrip("/")
    
    @field_validator("magento_user", "magento_password")
    @classmethod
    def validate_not_empty(cls, v: str, info: ValidationInfo) -> str:
        """Validate that required string fields are not empty."""
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        return v.strip()


# Global settings instance - lazy loaded
def get_settings() -> Settings:
    """Get or create settings instance.
    
    This function creates a singleton pattern for settings,
    ensuring they are loaded only once and reused.
    
    Returns:
        Settings instance with validated configuration
        
    Raises:
        ValidationError: If required environment variables are missing or invalid
    """
    return Settings()

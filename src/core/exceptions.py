"""Custom exceptions for Magento Automation System.

This module defines the exception hierarchy used throughout the application.
All exceptions inherit from MagentoError for easy catching.
"""

from typing import Optional, Dict, Any


class MagentoError(Exception):
    """Base exception for all Magento Automation errors.
    
    This is the parent class for all custom exceptions in the application.
    Catching this exception will catch all application-specific errors.
    
    Attributes:
        message: Human-readable error description
        details: Additional error context (optional)
    """
    
    def __init__(
        self, 
        message: str, 
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize exception with message and optional details.
        
        Args:
            message: Human-readable error description
            details: Dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class APIError(MagentoError):
    """Error related to API communication.
    
    Raised when there are issues connecting to or communicating with
    external APIs (Magento, Google Sheets, etc.).
    
    Attributes:
        status_code: HTTP status code if applicable
        endpoint: API endpoint that failed
    """
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        endpoint: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize API error with context.
        
        Args:
            message: Error description
            status_code: HTTP status code if available
            endpoint: API endpoint that was called
            details: Additional error details
        """
        super().__init__(message, details)
        self.status_code = status_code
        self.endpoint = endpoint


class AuthenticationError(APIError):
    """Error during authentication.
    
    Raised when authentication fails or credentials are invalid.
    This could be for Magento API, Google Sheets, or any other service.
    """
    
    def __init__(
        self,
        message: str = "Authentication failed",
        service: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize authentication error.
        
        Args:
            message: Error description
            service: Name of the service that failed auth (e.g., "Magento", "Google")
            details: Additional error details
        """
        super().__init__(message, details=details)
        self.service = service


class ValidationError(MagentoError):
    """Error in data validation.
    
    Raised when data does not meet expected format or constraints.
    This includes invalid CSV files, missing required fields, etc.
    
    Attributes:
        field: Name of the field that failed validation
        value: The invalid value
    """
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize validation error.
        
        Args:
            message: Error description
            field: Name of the invalid field
            value: The value that failed validation
            details: Additional error details
        """
        super().__init__(message, details)
        self.field = field
        self.value = value


class DataProcessingError(MagentoError):
    """Error during data processing.
    
    Raised when there are issues processing data, such as
    DataFrame operations, calculations, or transformations.
    """
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize data processing error.
        
        Args:
            message: Error description
            operation: Name of the operation that failed
            details: Additional error details
        """
        super().__init__(message, details)
        self.operation = operation


class ConfigurationError(MagentoError):
    """Error in application configuration.
    
    Raised when required configuration is missing or invalid.
    This includes missing environment variables, invalid file paths, etc.
    """
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize configuration error.
        
        Args:
            message: Error description
            config_key: Name of the configuration key that failed
            details: Additional error details
        """
        super().__init__(message, details)
        self.config_key = config_key


class FileNotFoundError(MagentoError):
    """Error when a required file is not found.
    
    This is different from Python's built-in FileNotFoundError
    as it provides more context about what the file is for.
    """
    
    def __init__(
        self,
        filepath: str,
        file_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize file not found error.
        
        Args:
            filepath: Path to the file that was not found
            file_type: Description of what the file is (e.g., "credentials", "input data")
            details: Additional error details
        """
        message = f"File not found: {filepath}"
        if file_type:
            message = f"{file_type} file not found: {filepath}"
        super().__init__(message, details)
        self.filepath = filepath
        self.file_type = file_type

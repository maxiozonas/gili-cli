"""Utility functions for data processing and transformation.

This module provides common utility functions used across the application
for data normalization, cleaning, and transformation.
"""

import re
from typing import Any, Dict, Optional, Union
from datetime import datetime

import pandas as pd


def clean_category(category_string: Union[str, None]) -> str:
    """Extract the last category from a full category path.
    
    Magento categories are stored as comma-separated paths.
    This function extracts the most specific category.
    
    Args:
        category_string: Full category path (e.g., "Root/Category/SubCategory")
        
    Returns:
        Last category name or "Sin Categoria"
        
    Examples:
        >>> clean_category("Root/Electricidad/Cables")
        'Cables'
        >>> clean_category(None)
        'Sin Categoria'
    """
    if pd.isna(category_string):
        return 'Sin Categoria'
    
    parts = str(category_string).split(',')
    last_part = parts[-1].split('/')[-1].strip()
    
    return last_part if last_part else 'Sin Categoria'


def format_date_to_dmy(date_value: Union[datetime, str, None]) -> str:
    """Format a date to DD/MM/YYYY format.
    
    Args:
        date_value: Date to format
        
    Returns:
        Formatted date string or 'N/A'
        
    Examples:
        >>> format_date_to_dmy(datetime(2024, 1, 15))
        '15/01/2024'
        >>> format_date_to_dmy(None)
        'N/A'
    """
    if pd.isna(date_value) or date_value is None:
        return 'N/A'
    
    if isinstance(date_value, str):
        try:
            date_value = pd.to_datetime(date_value)
        except:
            return 'N/A'
    
    return date_value.strftime('%d/%m/%Y')


def format_to_comma_decimal(value: Union[float, int, None]) -> str:
    """Format a number with comma as decimal separator.
    
    Argentine format: 1234.56 -> "1.234,56"
    
    Args:
        value: Number to format
        
    Returns:
        Formatted string with comma decimal
        
    Examples:
        >>> format_to_comma_decimal(1234.56)
        '1.234,56'
        >>> format_to_comma_decimal(None)
        '0,00'
    """
    if pd.isna(value) or value is None:
        return '0,00'
    
    # Format with 2 decimals and replace
    formatted = f"{float(value):,.2f}"
    # Replace thousand separator and decimal point
    formatted = formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
    
    return formatted


def normalize_sku(sku: Union[str, float, None]) -> str:
    """Normalize SKU by removing spaces and padding with zeros.
    
    This function handles various SKU formats and normalizes them to
    a standard 5-digit zero-padded format.
    
    Args:
        sku: SKU value (string, number, or None)
        
    Returns:
        Normalized SKU string (e.g., "01234")
        
    Examples:
        >>> normalize_sku("123")
        '00123'
        >>> normalize_sku(" 12 34 ")
        '01234'
        >>> normalize_sku(None)
        ''
    """
    if pd.isna(sku):
        return ""
    
    sku_str = str(sku).strip().replace(" ", "")
    
    # Remove any non-numeric characters if SKU is numeric
    if sku_str.isdigit():
        return sku_str.zfill(5)
    
    return sku_str


def get_custom_attribute(product: Dict[str, Any], attribute_code: str) -> str:
    """Extract a custom attribute value from a Magento product.
    
    Magento products store custom attributes in a list of dictionaries.
    This helper extracts the value for a specific attribute code.
    
    Args:
        product: Product dictionary from Magento API
        attribute_code: The attribute code to look for (e.g., "brand", "description")
        
    Returns:
        The attribute value or empty string if not found
        
    Example:
        >>> product = {
        ...     "custom_attributes": [
        ...         {"attribute_code": "brand", "value": "Nike"},
        ...         {"attribute_code": "color", "value": "Red"}
        ...     ]
        ... }
        >>> get_custom_attribute(product, "brand")
        'Nike'
        >>> get_custom_attribute(product, "size")
        ''
    """
    custom_attrs = product.get("custom_attributes", [])
    
    if isinstance(custom_attrs, list):
        for attr in custom_attrs:
            if attr.get("attribute_code") == attribute_code:
                return str(attr.get("value", ""))
    
    return ""


def parse_comma_decimal(value: Union[str, float, None]) -> float:
    """Parse a number with comma as decimal separator.
    
    Handles Argentine number format where thousands are separated by dots
    and decimals by commas (e.g., "1.234,56" -> 1234.56).
    
    Args:
        value: String or number to parse
        
    Returns:
        Parsed float value (0.0 if parsing fails)
        
    Examples:
        >>> parse_comma_decimal("1.234,56")
        1234.56
        >>> parse_comma_decimal("0,00")
        0.0
        >>> parse_comma_decimal(1234.56)
        1234.56
        >>> parse_comma_decimal(None)
        0.0
    """
    if pd.isna(value) or value == "":
        return 0.0
    
    # If already a number, return it
    if isinstance(value, (int, float)):
        return float(value)
    
    value_str = str(value).strip()
    
    # Try direct conversion first
    try:
        return float(value_str)
    except ValueError:
        pass
    
    # Remove dots (thousand separators) and replace comma with dot
    value_str = value_str.replace(".", "").replace(",", ".")
    
    try:
        return float(value_str)
    except ValueError:
        return 0.0


def format_currency(value: float, symbol: str = "$") -> str:
    """Format a number as currency string.
    
    Args:
        value: Number to format
        symbol: Currency symbol (default: $)
        
    Returns:
        Formatted currency string
        
    Examples:
        >>> format_currency(1234.56)
        '$1,234.56'
        >>> format_currency(1000000)
        '$1,000,000.00'
    """
    return f"{symbol}{value:,.2f}"


def clean_email(email: Union[str, None]) -> str:
    """Clean and normalize email address.
    
    Args:
        email: Email string to clean
        
    Returns:
        Lowercase, stripped email or empty string
        
    Examples:
        >>> clean_email("  User@Example.COM  ")
        'user@example.com'
        >>> clean_email(None)
        ''
    """
    if pd.isna(email) or not email:
        return ""
    
    return str(email).strip().lower()


def parse_date(date_value: Union[str, datetime, None]) -> Optional[datetime]:
    """Parse a date string or value to datetime object.
    
    Args:
        date_value: Date string or datetime object
        
    Returns:
        Parsed datetime or None if parsing fails
    """
    if pd.isna(date_value) or not date_value:
        return None
    
    if isinstance(date_value, datetime):
        return date_value
    
    try:
        return pd.to_datetime(date_value)
    except (ValueError, TypeError):
        return None


def clean_text(text: Union[str, None]) -> str:
    """Clean text by removing extra whitespace and special characters.
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text
    """
    if pd.isna(text) or not text:
        return ""
    
    # Remove extra whitespace and normalize
    text = str(text).strip()
    text = re.sub(r'\s+', ' ', text)
    
    return text


def batch_items(items: list, batch_size: int):
    """Split a list into batches of specified size.
    
    Args:
        items: List to batch
        batch_size: Size of each batch
        
    Yields:
        Batches of the list
        
    Example:
        >>> list(batch_items([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4], [5]]
    """
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero.
    
    Args:
        numerator: Number to divide
        denominator: Number to divide by
        default: Value to return if division by zero
        
    Returns:
        Division result or default value
        
    Examples:
        >>> safe_divide(10, 2)
        5.0
        >>> safe_divide(10, 0)
        0.0
        >>> safe_divide(10, 0, default=float('inf'))
        inf
    """
    if denominator == 0:
        return default
    
    return numerator / denominator

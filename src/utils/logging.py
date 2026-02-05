"""Structured logging configuration for Magento Automation System.

This module provides centralized logging setup using structlog for structured
logging. All technical logs go to a file (logs/app.log), keeping the console
clean for user-friendly output via Rich.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog
from rich.console import Console


def setup_file_logging(
    log_file: str = "logs/app.log",
    level: str = "INFO"
) -> str:
    """Configure logging to write to a single log file.
    
    This function sets up file-only logging. Technical logs go to the file,
    while user-facing messages should use console.print() from Rich.
    
    Args:
        log_file: Path to the log file (default: logs/app.log)
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        
    Returns:
        Path to the log file created
    """
    # Ensure log directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure file handler
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(getattr(logging, level.upper()))
    
    # Simple formatter for text-based logs
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = []  # Clear existing handlers
    root_logger.addHandler(file_handler)
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Configure structlog to use stdlib logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    return str(log_path.absolute())


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured structlog logger (writes to file)
    """
    return structlog.get_logger(name)

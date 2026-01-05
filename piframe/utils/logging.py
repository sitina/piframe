"""
Centralized logging setup for PiFrame application.
Replaces scattered print() statements with structured logging.
"""

import logging
import sys
from typing import Optional
from pathlib import Path


def setup_logging(
    log_file: str = "piframe.log",
    log_level: str = "INFO",
    enable_console: bool = True,
    log_format: Optional[str] = None
) -> None:
    """
    Set up centralized logging for the application.
    
    Args:
        log_file: Path to the log file
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_console: Whether to also log to console
        log_format: Custom log format string
    """
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Clear any existing handlers
    logger = logging.getLogger()
    logger.handlers.clear()
    
    # Set root logger level
    logger.setLevel(numeric_level)
    
    # Create formatters
    formatter = logging.Formatter(log_format)
    
    # File handler
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, IOError) as e:
        print(f"Warning: Could not set up file logging to {log_file}: {e}")
    
    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Set specific loggers to appropriate levels
    # Reduce noise from external libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('google').setLevel(logging.WARNING)
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    
    logger.info("Logging initialized")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Usually __name__ from the calling module
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class LoggerMixin:
    """
    Mixin class to add logging capabilities to other classes.
    Provides a self.logger attribute.
    """
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger instance for this class."""
        return get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")


def log_performance(func):
    """
    Decorator to log function execution time.
    Useful for monitoring performance of slow operations.
    """
    import time
    
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        func_name = f"{func.__qualname__}"
        
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func_name} executed in {execution_time:.3f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func_name} failed after {execution_time:.3f} seconds: {str(e)}")
            raise
    
    return wrapper
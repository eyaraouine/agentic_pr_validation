# Logger Configuration Utility

import logging
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from pythonjsonlogger import jsonlogger

from src.config.settings import Settings

# Get settings
settings = Settings()

# Logger cache to avoid recreating loggers
_loggers: Dict[str, logging.Logger] = {}


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields"""

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        """Add custom fields to log record"""
        super().add_fields(log_record, record, message_dict)

        # Add timestamp
        log_record['timestamp'] = datetime.utcnow().isoformat()

        # Add log level name
        log_record['level'] = record.levelname

        # Add module and function info
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno

        # Add environment
        log_record['environment'] = settings.ENVIRONMENT

        # Add custom fields if present
        if hasattr(record, 'extra_fields'):
            log_record.update(record.extra_fields)


class ContextFilter(logging.Filter):
    """Filter to add context information to log records"""

    def __init__(self, context: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.context = context or {}

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to log record"""
        for key, value in self.context.items():
            setattr(record, key, value)
        return True


def setup_logger(name: str, context: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """
    Set up a logger with the specified name and context

    Args:
        name: Logger name (usually module name)
        context: Additional context to include in all logs

    Returns:
        Configured logger instance
    """
    # Check cache first
    if name in _loggers and not context:
        return _loggers[name]

    # Create logger
    logger = logging.getLogger(name)

    # Set level from settings
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    logger.handlers = []

    # Console handler (JSON format for production, readable for development)
    console_handler = logging.StreamHandler(sys.stdout)

    if settings.ENVIRONMENT == "production":
        # JSON format for production
        json_formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            json_ensure_ascii=False
        )
        console_handler.setFormatter(json_formatter)
    else:
        # Human-readable format for development
        formatter = logging.Formatter(
            settings.LOG_FORMAT,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    # File handler if configured
    if settings.LOG_FILE:
        try:
            # Create log directory if it doesn't exist
            log_path = Path(settings.LOG_FILE)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # Create file handler
            file_handler = logging.FileHandler(settings.LOG_FILE)

            # Always use JSON format for file logs
            json_formatter = CustomJsonFormatter(
                '%(timestamp)s %(level)s %(name)s %(message)s',
                json_ensure_ascii=False
            )
            file_handler.setFormatter(json_formatter)

            logger.addHandler(file_handler)
        except Exception as e:
            logger.error(f"Failed to set up file logging: {str(e)}")

    # Add context filter if provided
    if context:
        context_filter = ContextFilter(context)
        logger.addFilter(context_filter)

    # Cache logger if no context
    if not context:
        _loggers[name] = logger

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger or create a new one

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return setup_logger(name)


def log_exception(logger: logging.Logger, exception: Exception, context: Optional[Dict[str, Any]] = None):
    """
    Log an exception with full stack trace

    Args:
        logger: Logger instance
        exception: Exception to log
        context: Additional context information
    """
    extra = {
        'exception_type': type(exception).__name__,
        'exception_message': str(exception),
        'extra_fields': context or {}
    }

    logger.error(
        f"Exception occurred: {type(exception).__name__}: {str(exception)}",
        exc_info=True,
        extra=extra
    )


def log_performance(logger: logging.Logger, operation: str, duration: float, context: Optional[Dict[str, Any]] = None):
    """
    Log performance metrics

    Args:
        logger: Logger instance
        operation: Operation name
        duration: Duration in seconds
        context: Additional context information
    """
    extra = {
        'operation': operation,
        'duration_seconds': duration,
        'duration_ms': round(duration * 1000, 2),
        'extra_fields': context or {}
    }

    logger.info(
        f"Performance: {operation} completed in {round(duration * 1000, 2)}ms",
        extra=extra
    )


def log_validation_result(logger: logging.Logger, pr_id: str, result: Dict[str, Any]):
    """
    Log validation result with structured data

    Args:
        logger: Logger instance
        pr_id: Pull request ID
        result: Validation result dictionary
    """
    extra = {
        'pr_id': pr_id,
        'production_ready': result.get('production_ready', False),
        'critical_issues': result.get('critical_issues_count', 0),
        'total_issues': result.get('statistics', {}).get('failed_checkpoints', 0),
        'technologies': result.get('technologies_detected', []),
        'duration': result.get('validation_duration', 0),
        'extra_fields': {
            'validation_id': result.get('validation_id'),
            'risk_level': result.get('risk_level', 'UNKNOWN')
        }
    }

    status = "PASSED" if result.get('production_ready') else "FAILED"
    logger.info(
        f"Validation {status} for PR {pr_id}: {extra['critical_issues']} critical issues",
        extra=extra
    )


class LogContext:
    """Context manager for temporary logging context"""

    def __init__(self, logger: logging.Logger, **kwargs):
        self.logger = logger
        self.context = kwargs
        self.original_filters = []

    def __enter__(self):
        """Add context filter"""
        context_filter = ContextFilter(self.context)
        self.logger.addFilter(context_filter)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Remove context filter"""
        # Remove the last filter (our context filter)
        if self.logger.filters:
            self.logger.removeFilter(self.logger.filters[-1])


# Convenience function for structured logging
def log_structured(logger: logging.Logger, level: str, message: str, **kwargs):
    """
    Log a structured message with additional fields

    Args:
        logger: Logger instance
        level: Log level (info, warning, error, etc.)
        message: Log message
        **kwargs: Additional fields to include in the log
    """
    extra = {'extra_fields': kwargs}
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message, extra=extra)
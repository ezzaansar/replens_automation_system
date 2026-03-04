"""
Centralized logging configuration for the Replens Automation System.

Replaces the duplicated logging.basicConfig() calls in each phase module.

Usage:
    # Call once at application startup (e.g. in main.py or a phase entry point):
    from src.utils.logger import setup_logging
    setup_logging()

    # Then in every module, just use the standard pattern:
    import logging
    logger = logging.getLogger(__name__)
"""

import logging
import sys
from pathlib import Path

from src.config import settings

_logging_configured = False


def setup_logging(log_file: str = None, level: str = None) -> None:
    """
    Configure the root logger with file and console handlers.

    Safe to call multiple times — subsequent calls are no-ops.

    Args:
        log_file: Override log file path (defaults to settings.log_file)
        level: Override log level (defaults to settings.log_level)
    """
    global _logging_configured
    if _logging_configured:
        return

    log_file = log_file or settings.log_file
    level = level or settings.log_level

    # Ensure log directory exists
    log_dir = Path(log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    _logging_configured = True


def setup_logger(name: str, log_file: str = None, level: str = None) -> logging.Logger:
    """
    Create and configure a logger instance.

    Kept for backward compatibility. Prefer calling ``setup_logging()`` once
    at startup and then using ``logging.getLogger(__name__)`` in each module.

    Args:
        name: Logger name (typically __name__)
        log_file: Override log file path (defaults to settings.log_file)
        level: Override log level (defaults to settings.log_level)

    Returns:
        Configured logger
    """
    setup_logging(log_file=log_file, level=level)
    return logging.getLogger(name)

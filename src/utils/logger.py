"""
Centralized logging configuration for the Replens Automation System.

Replaces the duplicated logging.basicConfig() calls in each phase module.
"""

import logging
import sys
from pathlib import Path

from src.config import settings


def setup_logger(name: str, log_file: str = None, level: str = None) -> logging.Logger:
    """
    Create and configure a logger instance.

    Args:
        name: Logger name (typically __name__)
        log_file: Override log file path (defaults to settings.log_file)
        level: Override log level (defaults to settings.log_level)

    Returns:
        Configured logger
    """
    log_file = log_file or settings.log_file
    level = level or settings.log_level

    # Ensure log directory exists
    log_dir = Path(log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid adding duplicate handlers on repeated calls
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

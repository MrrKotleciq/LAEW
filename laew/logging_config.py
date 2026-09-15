"""Application-level logging configuration (Milestone 11: Phase 3).

Provides a single, idempotent entry point for app-wide logging using only the
standard library. The tool logger (``laew.tools``, ADR-016) keeps its own
handlers; ``configure_logging`` never mutates child loggers.

Usage::

    configure_logging(level=logging.INFO, log_file="runtime/laew.log")
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

# Rotate at 1 MiB per file, keep 3 backups.
_MAX_BYTES = 1_048_576
_BACKUP_COUNT = 3


def configure_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    Configure the app-level ``laew`` logger.

    Args:
        level: Logging level for handlers (e.g. ``logging.DEBUG``).
        log_file: Optional path for a rotating file handler. The file (and any
            parent) does not need to exist; ``RotatingFileHandler`` creates it.

    Returns:
        The configured ``laew`` logger.

    Notes:
        Repeated calls are safe: handlers are only added once per type, so the
        console and file handlers are never duplicated. The ``laew.tools``
        logger (structured tool logging) is left untouched.
    """
    logger = logging.getLogger("laew")
    logger.setLevel(level)

    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(level)
        console.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(console)

    if log_file and not any(
        isinstance(h, RotatingFileHandler) for h in logger.handlers
    ):
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(file_handler)

    # Keep app logs out of the root logger's handlers; child loggers such as
    # laew.tools already own their output.
    logger.propagate = False

    return logger
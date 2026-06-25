"""Centralized logging configuration for pykrx-mcp.

Logs always go to stderr (stdout is reserved for the MCP protocol).
Optionally, setting the ``LOG_FILE`` environment variable also writes logs
to a rotating file for later debugging.

Environment variables:
    LOG_LEVEL: Logging level (DEBUG/INFO/WARNING/ERROR). Default: INFO.
    LOG_FILE:  Path to a log file. If unset, file logging is disabled.
    LOG_MAX_BYTES: Max size per log file before rotation. Default: 10 MB.
    LOG_BACKUP_COUNT: Number of rotated files to keep. Default: 5.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def configure_logging() -> logging.Logger:
    """Configure root logging from environment variables.

    Returns:
        The configured root logger.
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(_LOG_FORMAT)

    handlers: list[logging.Handler] = []

    # Always log to stderr (stdout is the MCP protocol channel).
    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setFormatter(formatter)
    handlers.append(stderr_handler)

    # Optionally log to a rotating file when LOG_FILE is set.
    log_file = os.getenv("LOG_FILE")
    if log_file:
        log_path = os.path.abspath(os.path.expanduser(log_file))
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        max_bytes = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
        backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    # force=True so repeated calls (e.g. server + rest_api in one process)
    # don't stack duplicate handlers.
    logging.basicConfig(level=level, handlers=handlers, force=True)

    root = logging.getLogger()
    if log_file:
        root.info("File logging enabled at %s (level=%s)", log_path, level_name)
    return root

"""
temporal_kg.utils.logger
~~~~~~~~~~~~~~~~~~~~~~~~
Provides a factory function `get_logger(name)` that returns a Python
`logging.Logger` configured once per process from settings.yaml.

Usage
-----
    from src.utils.logger import get_logger

    log = get_logger(__name__)
    log.info("Article ingested", extra={"article_id": 42})
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

# Import settings lazily to avoid circular imports at module level
_configured = False


def _configure_root_logger() -> None:
    """
    Run once per process. Attaches a StreamHandler + optional
    RotatingFileHandler to the root logger using values from settings.
    """
    global _configured
    if _configured:
        return

    # Late import to break potential circular dependency
    from src.utils.config import settings  # noqa: PLC0415

    level_name: str = settings("logging.level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = settings(
        "logging.format",
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    datefmt = settings("logging.date_format", "%Y-%m-%d %H:%M:%S")
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    root = logging.getLogger()
    root.setLevel(level)

    # ── Console handler ───────────────────────────────────────────────────────
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        console.setLevel(level)
        root.addHandler(console)

    # ── Rotating file handler ─────────────────────────────────────────────────
    if settings("logging.log_to_file", False):
        log_file = settings.abs_path("logging.log_file")
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file),
            maxBytes=settings("logging.max_bytes", 10_485_760),
            backupCount=settings("logging.backup_count", 5),
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root.addHandler(file_handler)

    # Silence noisy third-party loggers
    for noisy in ("urllib3", "httpx", "httpcore", "neo4j"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger, configuring the root logger on first call.

    Parameters
    ----------
    name : str
        Typically ``__name__`` of the calling module.

    Returns
    -------
    logging.Logger
    """
    _configure_root_logger()
    return logging.getLogger(name)

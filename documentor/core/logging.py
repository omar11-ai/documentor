"""Logging configuration for DocuMentor."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.logging import RichHandler
from rich.console import Console

from documentor.core.config import get_config


_console: Optional[Console] = None
_loggers: dict[str, logging.Logger] = {}


def get_console() -> Console:
    """Get or create global Rich console."""
    global _console
    if _console is None:
        _console = Console(stderr=True)
    return _console


def setup_logging(level: str = "INFO", log_file: Optional[Path] = None) -> None:
    """Configure logging for the application."""
    config = get_config()

    # Determine log level
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create handlers
    handlers: list[logging.Handler] = [
        RichHandler(
            console=get_console(),
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True,
        )
    ]

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers,
        force=True,
    )

    # Set specific logger levels
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("ollama").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance."""
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)
    return _loggers[name]
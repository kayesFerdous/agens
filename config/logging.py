# config/logging.py — production-grade centralized logging configuration
"""
Centralized logging configuration for production Python projects.

Usage:
    from config.logging import setup_logging, get_logger

    setup_logging()                          # call once at app entry point
    logger = get_logger(__name__)            # use anywhere in the project
"""

from __future__ import annotations

import logging
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# ANSI colour codes — used only when writing to a real terminal (TTY)
# ---------------------------------------------------------------------------

class _Colour:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREY   = "\033[38;5;245m"
    CYAN   = "\033[36m"
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    RED    = "\033[31m"
    BRIGHT_RED = "\033[1;31m"

_LEVEL_COLOURS: dict[int, str] = {
    logging.DEBUG:    _Colour.GREY,
    logging.INFO:     _Colour.GREEN,
    logging.WARNING:  _Colour.YELLOW,
    logging.ERROR:    _Colour.RED,
    logging.CRITICAL: _Colour.BRIGHT_RED,
}


# ---------------------------------------------------------------------------
# Custom formatter
# ---------------------------------------------------------------------------

class _ColourFormatter(logging.Formatter):
    """
    Human-friendly formatter for terminal output.

    Produces lines like:
        2025-01-15 12:34:56  INFO      myapp.server  Started on port 8080
        2025-01-15 12:34:57  WARNING   myapp.db      Slow query detected (1.4 s)

    Colours are applied only when the stream is a real TTY so that log files
    and piped output stay clean.
    """

    _FMT = (
        "{grey}{asctime}{reset}  "
        "{level_colour}{bold}{levelname:<9}{reset} "
        "{cyan}{name:<30}{reset} "
        "{message}"
    )

    _PLAIN_FMT = "{asctime}  {levelname:<9} {name:<30} {message}"

    def __init__(self, use_colours: bool = True) -> None:
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S")
        self._use_colours = use_colours

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        # Let the base class populate exc_text, stack_info, etc.
        super().format(record)

        if self._use_colours:
            level_colour = _LEVEL_COLOURS.get(record.levelno, "")
            line = self._FMT.format(
                grey=_Colour.GREY,
                cyan=_Colour.CYAN,
                bold=_Colour.BOLD,
                reset=_Colour.RESET,
                level_colour=level_colour,
                asctime=self.formatTime(record, self.datefmt),
                levelname=record.levelname,
                name=record.name,
                message=record.getMessage(),
            )
        else:
            line = self._PLAIN_FMT.format(
                asctime=self.formatTime(record, self.datefmt),
                levelname=record.levelname,
                name=record.name,
                message=record.getMessage(),
            )

        # Append exception / stack info when present
        if record.exc_text:
            line += f"\n{record.exc_text}"
        if record.stack_info:
            line += f"\n{self.formatStack(record.stack_info)}"

        return line


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

#: Tracks whether setup_logging() has already run so repeated imports of this
#: module in tests or sub-packages never add duplicate handlers.
_configured: bool = False


def setup_logging(
    level: int | str = logging.INFO,
    *,
    force: bool = False,
) -> None:
    """Configure the root logger for the whole application.

    Call this **once** at the application entry point (``main.py``,
    ``app/__init__.py``, CLI entry, etc.).  Every subsequent call is a no-op
    unless *force* is ``True``.

    Args:
        level:  Log level for the root logger.  Accepts an ``int``
                (``logging.DEBUG``) or a string (``"DEBUG"``).
                Defaults to ``logging.INFO``.
        force:  Re-apply configuration even if already set up.  Useful in
                tests that need a specific level.

    Example::

        from config.logging import setup_logging
        setup_logging(level="DEBUG")
    """
    global _configured  # noqa: PLW0603

    if _configured and not force:
        return

    # Normalise string levels ("DEBUG" → 10)
    if isinstance(level, str):
        level = logging.getLevelName(level.upper())

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any handlers that were added before our setup (e.g. by a library
    # that calls logging.basicConfig at import time).
    root.handlers.clear()

    # Decide whether the terminal supports ANSI escape codes.
    is_tty: bool = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(_ColourFormatter(use_colours=is_tty))
    root.addHandler(handler)

    # Silence chatty third-party libraries at WARNING by default so they
    # don't drown out your application logs.  Add more as needed.
    _silence("urllib3", "httpx", "asyncio", level=logging.WARNING)

    _configured = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a module-level logger that participates in the logging hierarchy.

    Prefer calling this at the **top of each module** so every log record
    carries the correct ``name`` (dotted package path).

    Args:
        name: Logger name — pass ``__name__`` from the calling module.
              Defaults to the root logger when omitted.

    Returns:
        A :class:`logging.Logger` instance.

    Example::

        from config.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Service started")
    """
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _silence(*logger_names: str, level: int = logging.WARNING) -> None:
    """Set a minimum level on noisy third-party loggers.

    Args:
        *logger_names: One or more logger names to quieten.
        level:         The minimum level to allow through (default WARNING).
    """
    for name in logger_names:
        logging.getLogger(name).setLevel(level)
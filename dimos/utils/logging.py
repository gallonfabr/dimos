"""Logging utilities for dimos.

Provides a consistent logging interface across the dimos package,
with support for structured logging and configurable log levels.
"""

import logging
import os
import sys
from typing import Optional


# Default log format
# Personal note: added %(filename)s:%(lineno)d to make it easier to trace
# where log messages originate during debugging sessions.
_DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
_DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Track whether the root logger has been configured
_configured = False


def configure_logging(
    level: Optional[str] = None,
    fmt: str = _DEFAULT_FORMAT,
    date_fmt: str = _DEFAULT_DATE_FORMAT,
    stream=sys.stdout,
) -> None:
    """Configure the root dimos logger.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Defaults to the DIMOS_LOG_LEVEL env var, or INFO.
        fmt: Log message format string.
        date_fmt: Date/time format string.
        stream: Output stream for the handler. Defaults to stdout.
    """
    global _configured

    if level is None:
        level = os.environ.get("DIMOS_LOG_LEVEL", "INFO").upper()

    numeric_level = getattr(logging, level, logging.INFO)

    root_logger = logging.getLogger("dimos")
    root_logger.setLevel(numeric_level)

    # Avoid adding duplicate handlers on repeated calls
    if not root_logger.handlers:
        handler = logging.StreamHandler(stream)
        handler.setLevel(numeric_level)
        formatter = logging.Formatter(fmt=fmt, datefmt=date_fmt)
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # Prevent propagation to the root Python logger
    root_logger.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the dimos namespace.

    Ensures the root dimos logger is configured before returning
    the requested child logger.

    Args:
        name: Dotted module/component name, e.g. ``"agent.planner"``.
              The returned logger will be ``dimos.<name>``.

    Returns:
        A :class:`logging.Logger` instance.

    Example::

        from dimos.utils.logging import get_logger

        log = get_logger(__name__)
        log.info("Component initialised")
    """
    if not _configured:
        configure_logging()

    # Strip leading "dimos." if the caller already passed the full path
    if name.startswith("dimos."):
        full_name = name
    else:
        full_name = f"dimos.{name}"

    return logging.getLogger(full_name)

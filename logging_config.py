"""
AgentForge — Structured Logging (v0.7)
=======================================
Replaces ad-hoc print() calls with proper log levels and format.
Supports: console (colored) + file output, log rotation.

Usage:
  from logging_config import get_logger
  log = get_logger(__name__)
  log.info("Pipeline started")
  log.warning("Retry required")
  log.error("API failure", exc_info=True)
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional

# ── Singleton state ──
_log_initialized = False
_log_file_path: Optional[str] = None

# ── ANSI color map for log levels ──
_LEVEL_COLORS = {
    "DEBUG":    "\033[36m",    # CYAN
    "INFO":     "\033[32m",    # GREEN
    "WARNING":  "\033[33m",    # YELLOW
    "ERROR":    "\033[91m",    # BRIGHT RED
    "CRITICAL": "\033[41m\033[97m",  # WHITE on RED bg
}
_RESET = "\033[0m"
_DIM = "\033[2m"


class _ColoredFormatter(logging.Formatter):
    """Formatter that adds ANSI colors to console log output."""

    def format(self, record: logging.LogRecord) -> str:
        # Create a copy to avoid mutating the original
        levelname = record.levelname
        color = _LEVEL_COLORS.get(levelname, "")

        # Check if ANSI is disabled
        if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
            color = ""
            reset = ""
            dim = ""
        else:
            reset = _RESET
            dim = _DIM

        # Format: [HH:MM:SS] LEVEL  module — message
        timestamp = datetime.now().strftime("%H:%M:%S")
        module = record.name.replace("__main__", "forge").split(".")[-1]

        msg = record.getMessage()
        if record.exc_info and record.exc_info[1]:
            msg = f"{msg} — {record.exc_info[1]}"

        return (
            f"{dim}{timestamp}{reset} "
            f"{color}{levelname:<8s}{reset} "
            f"{dim}{module:<16s}{reset} "
            f"{msg}"
        )


def init_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    log_dir: str = "logs",
) -> None:
    """
    Initialize the logging system. Call once at application startup.

    Args:
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to a log file. If None, auto-generates one in log_dir.
        log_dir: Directory for auto-generated log files.
    """
    global _log_initialized, _log_file_path

    if _log_initialized:
        return

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any existing handlers (avoid duplicates on re-init)
    root.handlers.clear()

    # ── Console handler (colored) ──
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(_ColoredFormatter())
    root.addHandler(console)

    # ── File handler (plain text) ──
    if log_file:
        file_path = log_file
    else:
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        file_path = os.path.join(log_dir, f"agentforge-{ts}.log")

    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # File always gets DEBUG level
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)-20s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(file_handler)
    _log_file_path = file_path
    _log_initialized = True

    # Log the startup
    log = logging.getLogger("forge")
    log.info("Logging initialized (console: %s, file: %s)", logging.getLevelName(level), file_path)


def get_logger(name: str = "forge") -> logging.Logger:
    """Get a logger instance. Auto-initializes with defaults if not yet initialized."""
    if not _log_initialized:
        init_logging()
    return logging.getLogger(name)


def get_log_file() -> Optional[str]:
    """Return the path to the current log file, if any."""
    return _log_file_path

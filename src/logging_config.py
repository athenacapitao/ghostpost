"""Production logging configuration for GhostPost.

Sets up JSON file logging with rotation, colored console output,
and separate concern-based log files (app, error, security).
"""

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5

COLORS = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[32m",      # green
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[1;31m",  # bold red
}
RESET = "\033[0m"


class JsonFormatter(logging.Formatter):
    """One JSON object per line with structured fields."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["exception_type"] = record.exc_info[0].__name__
            entry["exception_message"] = str(record.exc_info[1])
            entry["traceback"] = traceback.format_exception(*record.exc_info)
        return json.dumps(entry, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable format with ANSI colors when stderr is a TTY."""

    def __init__(self):
        super().__init__()
        self._use_color = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        level = record.levelname.ljust(8)
        if self._use_color:
            color = COLORS.get(record.levelname, "")
            level = f"{color}{level}{RESET}"
        msg = record.getMessage()
        base = f"[{ts}] {level} {record.name} | {msg}"
        if record.exc_info and record.exc_info[0] is not None:
            base += "\n" + "".join(traceback.format_exception(*record.exc_info))
        return base


class _SecurityFilter(logging.Filter):
    """Only allow records from ghostpost.security.* loggers."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name.startswith("ghostpost.security")


def setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> None:
    """Configure logging for the entire application.

    - Console handler on stderr (human-readable, colored)
    - app.log — all ghostpost + uvicorn logs (JSON, rotated)
    - error.log — ERROR+ only (JSON, rotated)
    - security.log — ghostpost.security.* only (JSON, rotated)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    os.makedirs(log_dir, exist_ok=True)
    json_fmt = JsonFormatter()
    console_fmt = ConsoleFormatter()

    # Root logger — capture everything
    root = logging.getLogger()
    root.setLevel(level)
    # Clear any existing handlers (e.g. from basicConfig)
    root.handlers.clear()

    # Console handler (stderr)
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(console_fmt)
    root.addHandler(console)

    # app.log — all logs
    app_handler = RotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
    )
    app_handler.setLevel(level)
    app_handler.setFormatter(json_fmt)
    root.addHandler(app_handler)

    # error.log — ERROR+ only
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, "error.log"),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_fmt)
    root.addHandler(error_handler)

    # security.log — ghostpost.security.* only
    security_handler = RotatingFileHandler(
        os.path.join(log_dir, "security.log"),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
    )
    security_handler.setLevel(level)
    security_handler.setFormatter(json_fmt)
    security_handler.addFilter(_SecurityFilter())
    root.addHandler(security_handler)

    # Hijack uvicorn loggers to use our handlers
    for uvi_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvi_logger = logging.getLogger(uvi_name)
        uvi_logger.handlers.clear()
        uvi_logger.propagate = True

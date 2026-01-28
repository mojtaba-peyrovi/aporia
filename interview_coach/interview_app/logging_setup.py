from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


_CONFIGURED = False


class _DefaultFieldsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "session_id"):
            record.session_id = "-"
        if not hasattr(record, "event_name"):
            record.event_name = "-"
        return True


def setup_logging(log_dir: Path | None = None, level: int = logging.INFO) -> None:
    """Configure application logging (idempotent).

    This sets up the *root* logger with two handlers:

    - A rotating file handler writing to ``app.log`` (2 MB max per file, 5 backups, UTF-8).
    - A stream handler writing to stderr/stdout (depending on the runtime).

    Both handlers share the same formatter and attach a filter that ensures every log record
    has ``session_id`` and ``event_name`` attributes (defaulting to ``"-"``) so log formatting
    never fails when those fields are missing.

    By default, logs are written to ``<project>/logs/app.log`` where ``<project>`` is the
    ``interview_coach`` directory (derived from this module's location). Repeated calls are
    a no-op to avoid adding duplicate handlers.

    Args:
        log_dir: Directory to place log files in. If not provided, defaults to
            ``interview_coach/logs``.
        level: Logging level to apply to the root logger and both handlers.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    base_dir = Path(__file__).resolve().parents[1]
    log_dir = log_dir or (base_dir / "logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s session_id=%(session_id)s event_name=%(event_name)s",
    )

    file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    file_handler.addFilter(_DefaultFieldsFilter())
    root.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(fmt)
    stream_handler.addFilter(_DefaultFieldsFilter())
    root.addHandler(stream_handler)

    _CONFIGURED = True


class _ContextAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("session_id", self.extra.get("session_id", "-"))
        extra.setdefault("event_name", self.extra.get("event_name", "-"))
        return msg, kwargs


def get_logger(session_id: str | None = None) -> logging.LoggerAdapter:
    return _ContextAdapter(logging.getLogger("interview_app"), {"session_id": session_id or "-"})

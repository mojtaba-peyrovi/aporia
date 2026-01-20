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

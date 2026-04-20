"""Structured logging setup. Writes human-readable logs to stdout and an
audit-grade JSON line log to ``<log_dir>/audit.log``.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
from pathlib import Path
from typing import Any

from billionaire.config import get_settings


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extras = getattr(record, "extra_data", None)
        if isinstance(extras, dict):
            payload.update(extras)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging() -> None:
    """Idempotent logging setup. Safe to call multiple times."""
    settings = get_settings()
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    if getattr(root, "_billionaire_configured", False):
        return

    root.setLevel(settings.log_level)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%H:%M:%S")
    )
    root.addHandler(console)

    audit_path = log_dir / "audit.log"
    audit_handler = logging.handlers.RotatingFileHandler(
        audit_path, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )
    audit_handler.setFormatter(_JsonFormatter())
    root.addHandler(audit_handler)

    root._billionaire_configured = True  # type: ignore[attr-defined]


def audit(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit an INFO-level structured audit log entry."""
    logger.info(event, extra={"extra_data": {"event": event, **fields}})

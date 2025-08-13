"""Project-wide structured JSON logging with correlation IDs and audit trail.

Usage:
- from infra.logging import get_logger, set_correlation_id, AuditLogger, audit
- logger = get_logger(__name__)
- logger.info("message", extra={"key": "value"})
- with new_correlation_id(): ...

Every log includes: timestamp, level, message, logger, module, func, line,
correlation_id, and any provided extra fields.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Optional

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    cid = _correlation_id.get()
    if not cid:
        cid = uuid.uuid4().hex
        _correlation_id.set(cid)
    return cid


def set_correlation_id(value: str) -> None:
    _correlation_id.set(value)


@contextmanager
def new_correlation_id(value: Optional[str] = None) -> Any:
    token = None
    try:
        value = value or uuid.uuid4().hex
        token = _correlation_id.set(value)
        yield value
    finally:
        if token is not None:
            _correlation_id.reset(token)


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON with correlation id."""

    def format(self, record: logging.LogRecord) -> str:
        # Base fields
        payload: Dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "correlation_id": getattr(record, "correlation_id", None) or get_correlation_id(),
        }

        # Merge any structured extras (exclude standard attributes)
        standard = set(vars(logging.LogRecord("x", 0, "x", 0, "", (), None)).keys())
        for k, v in record.__dict__.items():
            if k not in standard and k not in payload and k != "args":
                payload[k] = v

        # If exception info present, include concise info
        if record.exc_info:
            etype = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            payload["exception"] = {"type": etype, "message": str(record.msg)}

        return json.dumps(payload, separators=(",", ":"))


_configured = False


def _configure_root_logger() -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Avoid duplicate handlers if reloaded by Streamlit
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)
    else:
        # Replace formatters to ensure JSON output
        for h in root.handlers:
            if isinstance(h, logging.StreamHandler):
                h.setFormatter(JsonFormatter())
    _configured = True


def get_logger(name: str | None = None) -> logging.Logger:
    _configure_root_logger()
    logger = logging.getLogger(name if name else "app")
    # Ensure our logs propagate to root to use JSON handler
    logger.propagate = True
    return logger


class AuditLogger:
    """Minimal audit logger for trades and domain events."""

    def __init__(self, base: Optional[logging.Logger] = None):
        self._logger = base or get_logger("audit")

    def trade(
        self,
        action: str,
        *,
        ticker: str,
        shares: float,
        price: float,
        status: str = "success",
        reason: Optional[str] = None,
        **extra: Any,
    ) -> None:
        payload = {
            "event": "trade",
            "action": action,
            "ticker": ticker,
            "shares": shares,
            "price": price,
            "status": status,
        }
        if reason:
            payload["reason"] = reason
        payload.update(extra)
        self._logger.info("trade", extra=payload)

    def event(self, name: str, **attrs: Any) -> None:
        payload = {"event": name}
        payload.update(attrs)
        self._logger.info(name, extra=payload)


# Singleton audit logger
_audit_logger = AuditLogger(get_logger("audit"))

audit: AuditLogger = _audit_logger

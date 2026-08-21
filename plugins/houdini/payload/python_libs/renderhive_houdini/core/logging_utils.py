"""Production logging with token redaction and rotating files."""

from __future__ import absolute_import

import json
import logging
import logging.handlers
import os
import re
import threading

from renderhive_houdini.core.paths import runtime_logs_dir

_LOGGER = None
_LOCK = threading.Lock()
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*(?:token|bearer)?\s*)[^\s,;]+"),
    re.compile(r"(?i)(api[_ -]?token\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(x-session-token\s*[:=]\s*)[^\s,;]+"),
)


def redact(value):
    if value is None:
        return value
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if str(key).lower() in ("token", "authorization", "api_token", "password", "secret"):
                result[key] = "***REDACTED***" if item else ""
            else:
                result[key] = redact(item)
        return result
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda match: match.group(1) + "***REDACTED***", text)
    return text


class _RedactingFilter(logging.Filter):
    def filter(self, record):
        record.msg = redact(record.msg)
        if record.args:
            record.args = tuple(redact(item) for item in record.args)
        return True


def get_logger(name="renderhive_houdini"):
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER.getChild(name) if name != "renderhive_houdini" else _LOGGER
    with _LOCK:
        if _LOGGER is not None:
            return _LOGGER.getChild(name) if name != "renderhive_houdini" else _LOGGER
        logger = logging.getLogger("renderhive_houdini")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if not logger.handlers:
            path = os.path.join(runtime_logs_dir(), "renderhive_houdini.log")
            handler = logging.handlers.RotatingFileHandler(
                path,
                maxBytes=2 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            ))
            handler.addFilter(_RedactingFilter())
            logger.addHandler(handler)
        _LOGGER = logger
    return _LOGGER.getChild(name) if name != "renderhive_houdini" else _LOGGER


def log_json(logger, level, event, payload=None):
    data = {"event": str(event), "data": redact(payload or {})}
    getattr(logger, level, logger.info)(json.dumps(data, sort_keys=True, default=str))

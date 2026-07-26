from __future__ import absolute_import

import logging
import os
import re
from logging.handlers import RotatingFileHandler

from api.version import PLUGIN_VERSION


_LOGGERS = {}
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*token\s+)[^\s,;]+"),
    re.compile(r"(?i)(x-session-token\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(api[_ -]?token\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(\"token\"\s*:\s*\")[^\"]+(\")"),
)


def local_data_root():
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return os.path.join(root, "RenderHive")
    return os.path.join(os.path.expanduser("~"), ".renderhive")


def runtime_log_folder():
    folder = os.path.join(local_data_root(), "logs", "runtime")
    if not os.path.isdir(folder):
        os.makedirs(folder)
    return folder


def redact_text(value):
    text = str(value or "")
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            text = pattern.sub(r"\1***REDACTED***\2", text)
        else:
            text = pattern.sub(r"\1***REDACTED***", text)
    return text


class _RedactionFilter(logging.Filter):
    def filter(self, record):
        try:
            record.msg = redact_text(record.msg)
            if record.args:
                record.args = tuple(redact_text(item) for item in record.args)
        except Exception:
            pass
        return True


def get_logger(name="renderhive"):
    key = str(name or "renderhive")
    existing = _LOGGERS.get(key)
    if existing is not None:
        return existing

    logger = logging.getLogger("RenderHive.{}".format(key))
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        path = os.path.join(runtime_log_folder(), "renderhive_maya.log")
        handler = RotatingFileHandler(
            path,
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        ))
        handler.addFilter(_RedactionFilter())
        logger.addHandler(handler)

    logger.info("Logger ready for RenderHive Maya v%s", PLUGIN_VERSION)
    _LOGGERS[key] = logger
    return logger


def log_exception(logger, message):
    try:
        logger.exception(redact_text(message))
    except Exception:
        pass

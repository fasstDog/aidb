"""stdlib logging + python-json-logger. 禁止记录密码 / DSN / Connection.config。"""

from __future__ import annotations

import logging
import os
import re
import sys
import threading
from collections.abc import Mapping
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from pythonjsonlogger.json import JsonFormatter

LOGGER_NAME = "aidb"
DEFAULT_DATA_ROOT = Path("/var/lib/aidb")
LOG_FILENAME = "aidb.log"
_MAX_BYTES = 2 * 1024 * 1024
_BACKUP_COUNT = 5
_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_REDACTED = "[redacted]"

# 允许出现在 extra 里的字段；其余丢弃。不含 statement / config / password / dsn。
ALLOWED_FIELDS = frozenset(
    {
        "event",
        "source_id",
        "engine",
        "kind",
        "language",
        "tool",
        "code",
        "error_code",
        "version",
        "bind",
        "port",
        "ok",
        "status",
    }
)

_SECRET_KEYS = frozenset(
    {
        "password",
        "passwd",
        "dsn",
        "config",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "access_token",
        "refresh_token",
        "private_key",
        "credential",
        "credentials",
        "connection_string",
        "secret_key",
        "client_secret",
        "auth",
        "statement",
        "sql",
        "query",
        "payload",
        "handle",
    }
)

_SECRET_KEY_SUBSTR = (
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "dsn",
)

_RESERVED_RECORD_KEYS = frozenset(logging.makeLogRecord({}).__dict__.keys()) | {
    "asctime",
    "message",
    "taskName",
}

_KV_SECRET = re.compile(
    r'(?i)("?(?:password|passwd|dsn|config|secret|token|api[_-]?key|authorization|'
    r'access_token|refresh_token|private_key|connection_string|client_secret|statement)"?'
    r"\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|\S+)"
)
_URI_PASSWORD = re.compile(r"(?i)(\w+://[^:/?#\s]+:)([^@/?#\s]+)(@)")

_lock = threading.Lock()
_configured_root: Path | None = None


def _is_secret_key(name: str) -> bool:
    n = name.casefold()
    if n in _SECRET_KEYS:
        return True
    return any(part in n for part in _SECRET_KEY_SUBSTR)


def _looks_like_config(value: Any) -> bool:
    """Connection.config 或长得像它的 mapping / 带 .config 的对象。"""

    if isinstance(value, Mapping):
        keys = {str(k).casefold() for k in value}
        if keys & _SECRET_KEYS:
            return True
        if "host" in keys and ("user" in keys or "password" in keys or "dbname" in keys):
            return True
    config = getattr(value, "config", None)
    if isinstance(config, Mapping):
        return True
    return False


def _redact_text(text: str) -> str:
    text = _URI_PASSWORD.sub(rf"\1{_REDACTED}\3", text)
    return _KV_SECRET.sub(rf'\1"{_REDACTED}"', text)


def _safe_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if key not in ALLOWED_FIELDS:
            continue
        if _is_secret_key(key) or _looks_like_config(value):
            continue
        out[key] = value
    return out


class RedactFilter(logging.Filter):
    """丢掉 extra 里的密钥键；消息里的 password=/dsn=/config 替换为 [redacted]。"""

    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__):
            if key in _RESERVED_RECORD_KEYS and key not in {"msg", "args"}:
                continue
            if _is_secret_key(key):
                if key not in _RESERVED_RECORD_KEYS:
                    delattr(record, key)
                else:
                    setattr(record, key, _REDACTED)
                continue
            value = record.__dict__.get(key)
            if _looks_like_config(value):
                if key in _RESERVED_RECORD_KEYS:
                    setattr(record, key, _REDACTED)
                else:
                    delattr(record, key)
        if isinstance(record.msg, str):
            record.msg = _redact_text(record.msg)
        elif isinstance(record.msg, Mapping) or _looks_like_config(record.msg):
            record.msg = _REDACTED
        if record.args:
            if isinstance(record.args, Mapping):
                record.args = {k: (_REDACTED if _is_secret_key(str(k)) or _looks_like_config(v) else v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    _REDACTED if _looks_like_config(a) or (isinstance(a, str) and _KV_SECRET.search(a)) else a
                    for a in record.args
                )
        return True


def _formatter() -> JsonFormatter:
    return JsonFormatter(_FORMAT, json_ensure_ascii=False)


def _resolve_data_root(data_root: Path | str | None) -> Path:
    if data_root is not None:
        return Path(data_root)
    raw = os.environ.get("AIDB_DATA")
    if raw:
        return Path(raw)
    return DEFAULT_DATA_ROOT


def _clear_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        if isinstance(handler, logging.FileHandler):
            try:
                handler.close()
            except OSError:
                pass


def log_path(data_root: Path | str | None = None) -> Path:
    return _resolve_data_root(data_root) / "logs" / LOG_FILENAME


def configure_logging(
    data_root: Path | str | None = None,
    bind: str | None = None,
    port: int | None = None,
    *,
    force: bool = False,
) -> logging.Logger:
    """幂等：同一 data_root 不重复加 handler。bind/port 仅占位，启动事件走 log_event。"""

    del bind, port
    root = _resolve_data_root(data_root)
    logger = logging.getLogger(LOGGER_NAME)
    global _configured_root
    with _lock:
        if not force and _configured_root == root and logger.handlers:
            return logger
        _clear_handlers(logger)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        redact = RedactFilter()
        formatter = _formatter()

        stderr = logging.StreamHandler(sys.stderr)
        stderr.setLevel(logging.INFO)
        stderr.addFilter(redact)
        stderr.setFormatter(formatter)
        logger.addHandler(stderr)

        log_dir = root / "logs"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler: logging.Handler = RotatingFileHandler(
                log_dir / LOG_FILENAME,
                maxBytes=_MAX_BYTES,
                backupCount=_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.INFO)
            file_handler.addFilter(redact)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError:
            pass
        _configured_root = root
        return logger


def log_event(event: str, **fields: Any) -> None:
    """只把安全字段写入 extra；event 作为 message。"""

    extra = _safe_fields(fields)
    extra["event"] = event
    logging.getLogger(LOGGER_NAME).info(event, extra=extra)


__all__ = [
    "ALLOWED_FIELDS",
    "LOGGER_NAME",
    "RedactFilter",
    "configure_logging",
    "log_event",
    "log_path",
]

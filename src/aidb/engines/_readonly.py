"""sqlglot 只读判定与单元格序列化。仅适配器使用，不进核心。"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from aidb.errors import AidbError

EngineFailKind = Literal["connect", "timeout", "syntax", "other"]

_KIND_MESSAGE: dict[str, str] = {
    "connect": "连不上",
    "timeout": "超时",
    "syntax": "语法错误",
    "other": "执行失败",
}

_MYSQL_CONNECT = frozenset({2002, 2003, 2006, 2013, 1045, 1049, 1129})
_MYSQL_TIMEOUT = frozenset({3024, 1969, 1317})
_MYSQL_SYNTAX = frozenset({1064, 1146, 1054, 1060, 1109})


def classify_engine_failure(exc: BaseException | None) -> EngineFailKind:
    """从驱动异常归类。只看类型/错误码/关键词，不把原文塞进返回值。"""

    if exc is None:
        return "other"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, (ConnectionError, BrokenPipeError, OSError)) and not isinstance(
        exc, TimeoutError
    ):
        if isinstance(exc, (ConnectionError, ConnectionRefusedError, ConnectionResetError)):
            return "connect"
        if isinstance(exc, OSError) and getattr(exc, "errno", None) in {111, 61, 113, 101}:
            return "connect"
    if isinstance(exc, ImportError):
        return "connect"

    name = type(exc).__name__.casefold()
    pgcode = str(getattr(exc, "pgcode", None) or getattr(exc, "sqlstate", None) or "").upper()
    mysql_errno: int | None = None
    args = getattr(exc, "args", ())
    if args and isinstance(args[0], int):
        mysql_errno = args[0]

    if pgcode == "57014" or mysql_errno in _MYSQL_TIMEOUT:
        return "timeout"
    if any(k in name for k in ("timeout", "canceled", "cancelled", "querycanceled")):
        return "timeout"

    if pgcode.startswith("08") or pgcode in {"28P01", "28000"}:
        return "connect"
    if mysql_errno in _MYSQL_CONNECT:
        return "connect"
    if any(k in name for k in ("interfaceerror",)):
        return "connect"

    if pgcode.startswith("42") or mysql_errno in _MYSQL_SYNTAX:
        return "syntax"
    if "programmingerror" in name or "syntaxerror" in name:
        return "syntax"

    text = str(exc).casefold()
    if any(
        k in text
        for k in (
            "timeout",
            "timed out",
            "canceling statement",
            "cancelling statement",
            "query canceled",
            "max_execution_time",
            "max_statement_time",
        )
    ):
        return "timeout"
    if any(
        k in text
        for k in (
            "could not connect",
            "connection refused",
            "can't connect",
            "cant connect",
            "lost connection",
            "server closed",
            "password authentication",
            "access denied",
            "name or service not known",
        )
    ):
        return "connect"
    if any(
        k in text
        for k in (
            "syntax error",
            "undefined table",
            "undefined column",
            "unknown column",
            "unknown table",
            "does not exist",
        )
    ):
        return "syntax"
    if "operationalerror" in name:
        return "connect"
    return "other"


def engine_error(engine: str, op: str, exc: BaseException | None = None) -> AidbError:
    """结构化 engine_error。details 只有 engine/kind/op，不含语句、密码、DSN。"""

    kind = classify_engine_failure(exc)
    return AidbError(
        "engine_error",
        _KIND_MESSAGE[kind],
        {"engine": engine, "kind": kind, "op": op},
    )


def is_readonly_sql(sql: str, dialect: str) -> bool:
    """单条 SELECT/UNION 等只读语句为 True；解析失败或含写操作为 False。"""

    if not sql or not str(sql).strip():
        return False
    try:
        import sqlglot
        from sqlglot import exp
    except ImportError:
        return False
    allowed_root = (
        exp.Select,
        exp.Union,
        exp.Except,
        exp.Intersect,
        exp.Values,
    )
    forbidden = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Merge,
        exp.Create,
        exp.Drop,
        exp.Alter,
        exp.Command,
        exp.TruncateTable,
        exp.Grant,
        exp.Set,
        exp.Lock,
        exp.Into,
    )
    try:
        trees = sqlglot.parse(sql, dialect=dialect)
    except Exception:
        return False
    if not trees or len(trees) != 1 or trees[0] is None:
        return False
    tree = trees[0]
    if not isinstance(tree, allowed_root):
        return False
    for cls in forbidden:
        if tree.find(cls):
            return False
    return True


def jsonable_cell(value: Any, *, max_len: int = 4096) -> Any:
    """查询结果单元格转可序列化值；过长字符串截断。"""

    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) > max_len:
            return value[:max_len] + "…"
        return value
    if isinstance(value, (bytes, memoryview, bytearray)):
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    return str(value)

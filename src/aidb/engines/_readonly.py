"""sqlglot 只读判定与单元格序列化。仅适配器使用，不进核心。"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from aidb.errors import AidbError


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


def engine_error(engine: str, op: str) -> AidbError:
    return AidbError("engine_error", f"{op}失败", {"engine": engine})

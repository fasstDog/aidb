"""AIDB 统一错误。核心与适配器均抛 AidbError，不泄漏驱动异常给 MCP 工具层。"""

from __future__ import annotations

from typing import Any, NoReturn

KIND_NOT_ENABLED = "kind_not_enabled"
ENGINE_NOT_IMPLEMENTED = "engine_not_implemented"
LANGUAGE_MISMATCH = "language_mismatch"
NOT_READONLY = "not_readonly"
CATALOG_PAGE_REQUIRED = "catalog_page_required"
SOURCE_NOT_FOUND = "source_not_found"
CONCURRENCY_LIMIT = "concurrency_limit"
OVERLAY_NOT_FOUND = "overlay_not_found"
INVALID_PATH = "invalid_path"
ENGINE_ERROR = "engine_error"
MISSING_STATEMENT = "missing_statement"

DEFAULT_MESSAGES: dict[str, str] = {
    KIND_NOT_ENABLED: "该数据源类型尚未启用",
    ENGINE_NOT_IMPLEMENTED: "该引擎尚未实现",
    LANGUAGE_MISMATCH: "查询语言与数据源类型不匹配",
    NOT_READONLY: "语句不是只读查询",
    CATALOG_PAGE_REQUIRED: "目录查询必须分页",
    SOURCE_NOT_FOUND: "数据源不存在",
    CONCURRENCY_LIMIT: "并发执行已达上限",
    OVERLAY_NOT_FOUND: "覆盖层版本不存在",
    INVALID_PATH: "非法路径",
    ENGINE_ERROR: "执行失败",
    MISSING_STATEMENT: "需要 statement（别名 sql / query）",
}


class AidbError(Exception):
    """可序列化给 MCP / 配置台的业务错误。"""

    code: str
    message: str
    details: dict[str, Any]

    def __init__(
        self,
        code: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message if message is not None else DEFAULT_MESSAGES.get(code, code)
        self.details = details if details is not None else {}
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """MCP 工具层结构化错误：code + message + details，不含堆栈。"""

        return {"code": self.code, "message": self.message, "details": self.details}


def raise_kind_not_enabled(kind: str) -> NoReturn:
    """未启用的 kind（document/kv/search 等）必须走这个口子，不得落到关系型执行。"""

    raise AidbError(
        KIND_NOT_ENABLED,
        DEFAULT_MESSAGES[KIND_NOT_ENABLED],
        {"kind": kind},
    )

"""引擎适配器抽象。新增引擎 = 新文件 + register()。sqlglot 只存在于适配器实现中。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from aidb.models.catalog import Column, QueryResult
from aidb.models.connection import Family


class FormField(BaseModel):
    """配置表单字段。"""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    type: Literal["string", "int", "password", "text"]
    required: bool = False
    default: Any = None
    secret: bool = False


class FormSchema(BaseModel):
    """引擎连接配置表单。"""

    model_config = ConfigDict(extra="forbid")

    fields: list[FormField] = Field(default_factory=list)


class EngineLabels(BaseModel):
    """引擎目录层级标签（命名空间 / 集合 / 字段）。"""

    model_config = ConfigDict(extra="forbid")

    namespace: str
    collection: str
    field: str


class UiMeta(BaseModel):
    """引擎在配置台的展示元数据。"""

    model_config = ConfigDict(extra="forbid")

    visible: bool = True
    label: str = ""  # 画廊显示名；空则回退为 adapter.id


class EngineAdapter(ABC):
    """二级注册表条目。id + aliases 由 engines.registry 索引。"""

    id: str
    aliases: Sequence[str] = ()
    family: Family
    ui: UiMeta
    form_schema: FormSchema
    labels: EngineLabels

    @abstractmethod
    def connect(self, config: Mapping[str, Any]) -> Any:
        """打开不透明句柄。config 即 Connection.config，仅适配器解读键。"""

    @abstractmethod
    def ping(self, handle: Any) -> None:
        """探活。"""

    @abstractmethod
    def list_schemas(self, handle: Any) -> list[str]:
        """列出 namespace（schema/库）。"""

    @abstractmethod
    def list_tables(self, handle: Any, schema: str) -> list[str]:
        """列出 collection（表/集合）。"""

    @abstractmethod
    def list_columns(self, handle: Any, schema: str, table: str) -> list[Column]:
        """列出字段。"""

    @abstractmethod
    def list_fks(self, handle: Any, schema: str, table: str) -> list[dict[str, Any]]:
        """外键，结构保持通用 dict。"""

    @abstractmethod
    def sample_values(
        self,
        handle: Any,
        schema: str,
        table: str,
        column: str,
        *,
        enabled: bool = False,
        limit: int = 5,
    ) -> list[Any]:
        """样本值。默认 enabled=False（PII 风险）。"""

    @abstractmethod
    def quote_ident(self, name: str) -> str:
        """按本引擎规则引用标识符。"""

    @abstractmethod
    def dialect_prompt(self) -> str:
        """给宿主 Agent 的方言提示：分页、日期、字符串比较、标识符。"""

    @abstractmethod
    def limit_clause(self, n: int) -> str:
        """分页片段。各引擎自己写；核心不得自行拼接。"""

    @abstractmethod
    def is_readonly(self, sql: str) -> bool:
        """只读判定在适配器上，不在 MCP 工具层。"""

    @abstractmethod
    def execute_readonly(
        self,
        handle: Any,
        sql: str,
        *,
        timeout_s: float,
        max_rows: int,
    ) -> QueryResult:
        """执行只读语句并截断行数。驱动 import 只允许出现在本引擎文件。"""

    @abstractmethod
    def close(self, handle: Any) -> None:
        """释放句柄。"""

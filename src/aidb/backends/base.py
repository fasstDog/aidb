"""查询后端：按 kind 分发。生成 SQL/NL 是宿主 Agent 的事，这里只执行。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from aidb.models.catalog import CatalogPage, CatalogQuery, QueryResult, ReadonlyPayload
from aidb.models.connection import Connection, Kind


class QueryBackend(ABC):
    """一级注册表：按 kind（relational/document/kv/search/graph）。

    不变量：
    - 后端不生成查询语句；宿主 Agent 生成，本层只执行只读语句。
    - 不得按引擎名分支；关系型内部再经 EngineAdapter 注册表分发。
    - 未启用的 kind 必须是 UnsupportedBackend，不得落到关系型。
    - config 不透明，本层不得解析连接键。
    - introspect_catalog 必须分页。
    """

    kind: Kind

    @abstractmethod
    def ping(self, source: Connection) -> None:
        """探活。失败抛 AidbError。"""

    @abstractmethod
    def introspect_catalog(self, source: Connection, query: CatalogQuery) -> CatalogPage:
        """分页目录。overlays HEAD 由 MCP 存储层组装，不在此后端内读取。"""

    @abstractmethod
    def execute_native(self, source: Connection, payload: ReadonlyPayload) -> QueryResult:
        """执行只读原生语句。关系型仅接受 language=sql。"""

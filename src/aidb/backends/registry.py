"""一级注册表：QueryBackend by kind。

builtin() 为 document/kv/search/graph 挂 UnsupportedBackend。
relational 由 MCP 核心通过 register_relational 注入，本模块不注册。
未知 kind 返回 UnsupportedBackend，绝不回落到 SQL。
"""

from __future__ import annotations

from aidb.backends.base import QueryBackend
from aidb.backends.unsupported import UnsupportedBackend
from aidb.models.connection import Kind

_UNIMPLEMENTED_KINDS: tuple[Kind, ...] = ("document", "kv", "search", "graph")


class BackendRegistry:
    """按 kind 取 QueryBackend。禁止按引擎名分支。"""

    def __init__(self) -> None:
        self._backends: dict[str, QueryBackend] = {}

    def register(self, backend: QueryBackend) -> None:
        self._backends[str(backend.kind)] = backend

    def register_relational(self, backend: QueryBackend) -> None:
        """MCP 核心注入 RelationalBackend 实现的钩子。"""

        self.register(backend)

    def get(self, kind: str) -> QueryBackend:
        found = self._backends.get(kind)
        if found is not None:
            return found
        return UnsupportedBackend(kind)

    @classmethod
    def builtin(cls) -> BackendRegistry:
        registry = cls()
        for kind in _UNIMPLEMENTED_KINDS:
            registry.register(UnsupportedBackend(kind))
        return registry

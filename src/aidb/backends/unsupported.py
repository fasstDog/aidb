"""未启用 kind 的空嘴。document/kv/search 现在就必须挂上，禁止静默落到 SQL。"""

from __future__ import annotations

from aidb.backends.base import QueryBackend
from aidb.errors import raise_kind_not_enabled
from aidb.models.catalog import CatalogPage, CatalogQuery, QueryResult, ReadonlyPayload
from aidb.models.connection import Connection, Kind


class UnsupportedBackend(QueryBackend):
    """每个未实现 kind 的必填占位。所有方法抛 KIND_NOT_ENABLED。"""

    def __init__(self, kind: Kind | str) -> None:
        self.kind = kind  # type: ignore[assignment]

    def ping(self, source: Connection) -> None:
        raise_kind_not_enabled(str(self.kind))

    def introspect_catalog(self, source: Connection, query: CatalogQuery) -> CatalogPage:
        raise_kind_not_enabled(str(self.kind))

    def execute_native(self, source: Connection, payload: ReadonlyPayload) -> QueryResult:
        raise_kind_not_enabled(str(self.kind))

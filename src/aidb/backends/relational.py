"""关系型 QueryBackend 骨架。一律经引擎注册表取适配器，禁止按引擎名分支。"""

from __future__ import annotations

from aidb.backends.base import QueryBackend
from aidb.engines.registry import get as get_engine_adapter
from aidb.errors import (
    CATALOG_PAGE_REQUIRED,
    LANGUAGE_MISMATCH,
    NOT_READONLY,
    AidbError,
)
from aidb.models.catalog import (
    CatalogLabels,
    CatalogNode,
    CatalogPage,
    CatalogQuery,
    QueryResult,
    ReadonlyPayload,
)
from aidb.models.connection import Connection

_DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_MAX_ROWS = 500
_MAX_PAGE = 100


def _page_names(
    names: list[str],
    cursor: str | None,
    limit: int,
) -> tuple[list[str], str | None]:
    start = 0
    if cursor:
        try:
            start = max(0, int(cursor))
        except ValueError:
            start = 0
    end = start + limit
    sliced = names[start:end]
    next_cursor = str(end) if end < len(names) else None
    return sliced, next_cursor


def _filter_q(names: list[str], q: str | None) -> list[str]:
    if not q:
        return names
    needle = q.casefold()
    return [n for n in names if needle in n.casefold()]


class RelationalBackend(QueryBackend):
    """kind=relational。列表/分页语法全部委托 EngineAdapter，本文件不写方言。

    overlays HEAD 不在此读取：MCP catalog 组装层附加 overlays=... 。
    本骨架返回 overlays=None。
    """

    kind = "relational"

    def _adapter_and_handle(self, source: Connection):
        adapter = get_engine_adapter(source.engine)
        handle = adapter.connect(source.config)
        return adapter, handle

    def ping(self, source: Connection) -> None:
        adapter, handle = self._adapter_and_handle(source)
        try:
            adapter.ping(handle)
        finally:
            adapter.close(handle)

    def introspect_catalog(self, source: Connection, query: CatalogQuery) -> CatalogPage:
        if query.limit <= 0:
            raise AidbError(
                CATALOG_PAGE_REQUIRED,
                "目录查询必须分页",
                {"limit": query.limit},
            )
        limit = query.limit if query.limit <= _MAX_PAGE else _MAX_PAGE
        adapter, handle = self._adapter_and_handle(source)
        try:
            labels = CatalogLabels(
                namespace_label=adapter.labels.namespace,
                collection_label=adapter.labels.collection,
                field_label=adapter.labels.field,
            )
            items: list[CatalogNode] = []
            next_cursor: str | None = None

            if query.namespace is not None and query.collection is not None:
                columns = adapter.list_columns(handle, query.namespace, query.collection)
                if query.include_sample_values:
                    for col in columns:
                        col.samples = adapter.sample_values(
                            handle,
                            query.namespace,
                            query.collection,
                            col.name,
                            enabled=True,
                        )
                fks = adapter.list_fks(handle, query.namespace, query.collection)
                items.append(
                    CatalogNode(
                        namespace=query.namespace,
                        collection=query.collection,
                        columns=columns,
                        labels=labels,
                        fks=fks,
                    )
                )
            elif query.namespace is not None:
                tables = _filter_q(adapter.list_tables(handle, query.namespace), query.q)
                page, next_cursor = _page_names(tables, query.cursor, limit)
                items = [
                    CatalogNode(namespace=query.namespace, collection=name, labels=labels)
                    for name in page
                ]
            else:
                schemas = _filter_q(adapter.list_schemas(handle), query.q)
                page, next_cursor = _page_names(schemas, query.cursor, limit)
                items = [
                    CatalogNode(namespace=name, collection=None, labels=labels)
                    for name in page
                ]

            # overlays=None：MCP catalog 组装层负责附加 HEAD。
            return CatalogPage(
                source_id=query.source_id,
                items=items,
                overlays=None,
                dialect_prompt=adapter.dialect_prompt(),
                next_cursor=next_cursor,
                labels=labels,
            )
        finally:
            adapter.close(handle)

    def execute_native(self, source: Connection, payload: ReadonlyPayload) -> QueryResult:
        if payload.language != "sql":
            raise AidbError(
                LANGUAGE_MISMATCH,
                "关系型数据源仅接受 sql",
                {"language": payload.language, "expected": "sql"},
            )
        adapter, handle = self._adapter_and_handle(source)
        try:
            if not adapter.is_readonly(payload.statement):
                raise AidbError(
                    NOT_READONLY,
                    "语句不是只读查询",
                    {"source_id": payload.source_id},
                )
            return adapter.execute_readonly(
                handle,
                payload.statement,
                timeout_s=_DEFAULT_TIMEOUT_S,
                max_rows=_DEFAULT_MAX_ROWS,
            )
        finally:
            adapter.close(handle)

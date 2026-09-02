"""MCP 业务层：list_sources / search_catalog / execute_readonly。不生成 SQL。"""

from __future__ import annotations

import os
import threading
from typing import Any

from pydantic import ValidationError

from aidb.backends.registry import BackendRegistry
from aidb.catalog.assemble import assemble_catalog
from aidb.errors import CATALOG_PAGE_REQUIRED, CONCURRENCY_LIMIT, LANGUAGE_MISMATCH, AidbError
from aidb.models.catalog import CatalogPage, CatalogQuery, QueryResult, ReadonlyPayload
from aidb.store.connections import ConnectionStore
from aidb.store.overlays import OverlayStore

_DEFAULT_CONCURRENCY = 4


def _concurrency_cap(value: int | None) -> int:
    if value is not None:
        return max(1, value)
    raw = os.environ.get("AIDB_MAX_CONCURRENCY", str(_DEFAULT_CONCURRENCY))
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_CONCURRENCY


class AidbService:
    """配置台与 MCP 共用的只读执行服务。"""

    def __init__(
        self,
        connections: ConnectionStore,
        overlays: OverlayStore,
        backends: BackendRegistry,
        max_concurrency: int | None = None,
    ) -> None:
        self.connections = connections
        self.overlays = overlays
        self.backends = backends
        self.max_concurrency = _concurrency_cap(max_concurrency)
        self._sem = threading.BoundedSemaphore(self.max_concurrency)

    def list_sources(self) -> dict[str, Any]:
        from aidb import SERVER_VERSION

        return {
            "server_version": SERVER_VERSION,
            "sources": self.connections.public_meta(),
        }

    def search_catalog(
        self,
        source_id: str,
        q: str | None = None,
        namespace: str | None = None,
        collection: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
        include_sample_values: bool = False,
    ) -> CatalogPage:
        source = self.connections.require(source_id)
        try:
            query = CatalogQuery(
                source_id=source_id,
                q=q,
                namespace=namespace,
                collection=collection,
                cursor=cursor,
                limit=limit,
                include_sample_values=include_sample_values,
            )
        except ValidationError as exc:
            raise AidbError(
                CATALOG_PAGE_REQUIRED,
                details={"source_id": source_id},
            ) from exc
        return assemble_catalog(source, query, self.backends, self.overlays)

    def execute_readonly(self, source_id: str, language: str, statement: str) -> QueryResult:
        source = self.connections.require(source_id)
        try:
            payload = ReadonlyPayload(source_id=source_id, language=language, statement=statement)  # type: ignore[arg-type]
        except ValidationError as exc:
            raise AidbError(
                LANGUAGE_MISMATCH,
                details={"language": language},
            ) from exc
        backend = self.backends.get(source.kind)
        acquired = self._sem.acquire(blocking=False)
        if not acquired:
            raise AidbError(
                CONCURRENCY_LIMIT,
                details={"limit": self.max_concurrency},
            )
        try:
            return backend.execute_native(source, payload)
        finally:
            self._sem.release()

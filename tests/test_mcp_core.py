"""catalog 组装、未启用 kind、execute_readonly、MCP 工具名。"""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from aidb.backends.base import QueryBackend
from aidb.backends.registry import BackendRegistry
from aidb.errors import (
    KIND_NOT_ENABLED,
    LANGUAGE_MISMATCH,
    SOURCE_NOT_FOUND,
    AidbError,
)
from aidb.mcp.server import create_mcp_server
from aidb.mcp.service import AidbService
from aidb.models.catalog import (
    CatalogItem,
    CatalogLabels,
    CatalogPage,
    CatalogQuery,
    QueryResult,
    ReadonlyPayload,
)
from aidb.models.connection import Connection
from aidb.models.overlay import CollectionOverlay, OverlayRef, SourceOverlay
from aidb.runtime import build_runtime
from aidb.store.connections import ConnectionStore
from aidb.store.overlays import OverlayStore
from tests.fakes import ensure_fake_adapter



class FakeQueryBackend(QueryBackend):
    """测试用后端：不连真实库，分页由 CatalogQuery.limit/cursor 驱动。"""

    kind = "relational"

    def ping(self, source: Connection) -> None:
        return None

    def introspect_catalog(self, source: Connection, query: CatalogQuery) -> CatalogPage:
        labels = CatalogLabels(namespace_label="schema", collection_label="表", field_label="列")
        names = ["orders", "users", "items", "payments"]
        if query.q:
            names = [n for n in names if query.q.casefold() in n.casefold()]
        start = 0
        if query.cursor:
            try:
                start = max(0, int(query.cursor))
            except ValueError:
                start = 0
        sliced = names[start : start + query.limit]
        next_cursor = str(start + query.limit) if start + query.limit < len(names) else None
        items = [
            CatalogItem(namespace=query.namespace or "public", collection=n, labels=labels)
            for n in sliced
        ]
        return CatalogPage(
            source_id=source.id,
            items=items,
            overlays=None,
            dialect_prompt="use limit",
            next_cursor=next_cursor,
            labels=labels,
        )

    def execute_native(self, source: Connection, payload: ReadonlyPayload) -> QueryResult:
        if payload.language != "sql":
            raise AidbError(LANGUAGE_MISMATCH, details={"language": payload.language})
        return QueryResult(columns=["id"], rows=[[1]], truncated=False, row_count_capped=1)


def _rel(source_id: str = "src1") -> Connection:
    return Connection(
        id=source_id,
        name="订单库",
        kind="relational",
        engine="fake",
        family="postgres",
        config={"password": "s3cret-token-xyz", "host": "db.internal"},
    )


class TestMcpCore(unittest.TestCase):
    def setUp(self) -> None:
        ensure_fake_adapter()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.svc = build_runtime(self.root, load=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_list_sources_no_secrets(self) -> None:
        self.svc.connections.put(_rel())
        payload = self.svc.list_sources()
        blob = json.dumps(payload)
        self.assertNotIn("s3cret-token-xyz", blob)
        self.assertNotIn("password", blob)
        self.assertNotIn("config", blob)
        self.assertNotIn("db.internal", blob)
        self.assertEqual(payload["sources"][0]["id"], "src1")
        self.assertIn("server_version", payload)

    def test_search_catalog_pagination(self) -> None:
        self.svc.connections.put(_rel())
        page = self.svc.search_catalog("src1", namespace="public", limit=2)
        names = [i.collection for i in page.items]
        self.assertEqual(names, ["orders", "users"])
        self.assertEqual(page.next_cursor, "2")
        self.assertIsNotNone(page.overlays)
        page2 = self.svc.search_catalog("src1", namespace="public", cursor="2", limit=2)
        names2 = [i.collection for i in page2.items]
        self.assertEqual(names2, ["items", "payments"])
        self.assertIsNone(page2.next_cursor)

    def test_search_catalog_assembles_overlay_head(self) -> None:
        self.svc.connections.put(_rel())
        self.svc.overlays.write_head(
            OverlayRef(source_id="src1"),
            SourceOverlay(description="源说明", query_rules="只用已发布状态"),
        )
        self.svc.overlays.write_head(
            OverlayRef(source_id="src1", namespace="public", collection="orders"),
            CollectionOverlay(description="订单表", fields={"id": "主键补丁"}),
        )
        page = self.svc.search_catalog(
            "src1",
            namespace="public",
            collection="orders",
        )
        assert page.overlays is not None
        self.assertTrue(page.overlays.patched)
        self.assertEqual(page.overlays.source.description, "源说明")
        self.assertEqual(page.overlays.collection.description, "订单表")
        self.assertEqual(page.overlays.fields["id"], "主键补丁")
        dumped = page.to_json_dict()
        self.assertEqual(dumped["overlays"]["source"]["description"], "源说明")
        self.assertEqual(dumped["dialect_prompt"], "pagination: limit n; identifiers: unquoted")
        self.assertEqual(dumped["columns"][0]["comment"], "主键")

    def test_search_catalog_uses_head_not_history(self) -> None:
        self.svc.connections.put(_rel())
        ref = OverlayRef(source_id="src1")
        self.svc.overlays.write_head(ref, SourceOverlay(description="old"))
        self.svc.overlays.write_head(ref, SourceOverlay(description="HEAD-only"))
        page = self.svc.search_catalog("src1", limit=2)
        assert page.overlays is not None
        self.assertEqual(page.overlays.source.description, "HEAD-only")

    def test_unimplemented_kinds(self) -> None:
        for kind, engine, family in (
            ("document", "mongodb", "document"),
            ("kv", "redis", "kv"),
            ("search", "elasticsearch", "search"),
        ):
            cid = f"{kind}1"
            self.svc.connections.put(
                Connection(
                    id=cid,
                    name=kind,
                    kind=kind,
                    engine=engine,
                    family=family,
                    config={"password": "nope"},
                )
            )
            with self.assertRaises(AidbError) as ctx:
                self.svc.search_catalog(cid)
            self.assertEqual(ctx.exception.code, KIND_NOT_ENABLED)
            self.assertEqual(ctx.exception.message, "该数据源类型尚未启用")
            with self.assertRaises(AidbError) as ctx2:
                self.svc.execute_readonly(cid, "sql", "SELECT 1")
            self.assertEqual(ctx2.exception.code, KIND_NOT_ENABLED)
            self.assertEqual(ctx2.exception.message, "该数据源类型尚未启用")

    def test_execute_readonly_language_mismatch(self) -> None:
        self.svc.connections.put(_rel())
        with self.assertRaises(AidbError) as ctx:
            self.svc.execute_readonly("src1", "mql", "db.x.find()")
        self.assertEqual(ctx.exception.code, LANGUAGE_MISMATCH)

    def test_execute_readonly_sql_ok(self) -> None:
        self.svc.connections.put(_rel())
        result = self.svc.execute_readonly("src1", "sql", "SELECT 1")
        self.assertEqual(result.columns, ["id"])
        self.assertEqual(result.rows, [[1]])

    def test_missing_source(self) -> None:
        with self.assertRaises(AidbError) as ctx:
            self.svc.search_catalog("missing")
        self.assertEqual(ctx.exception.code, SOURCE_NOT_FOUND)

    def test_mcp_tool_names_exact(self) -> None:
        server = create_mcp_server(self.svc)
        tools = asyncio.run(server.list_tools())
        names = sorted(t.name for t in tools)
        self.assertEqual(names, ["execute_readonly", "list_sources", "search_catalog"])
        self.assertNotIn("ask_readonly", names)
        self.assertFalse(any("patch" in n or "write" in n for n in names))

    def test_mcp_tools_map_aidb_error(self) -> None:
        server = create_mcp_server(self.svc)
        result = asyncio.run(server.call_tool("search_catalog", {"source_id": "missing"}))
        text = ""
        if hasattr(result, "structured_content") and result.structured_content:
            text = json.dumps(result.structured_content)
        elif hasattr(result, "content") and result.content:
            text = result.content[0].text
        elif isinstance(result, dict):
            text = json.dumps(result)
        else:
            text = str(result)
        self.assertIn("source_not_found", text)

    def test_attach_same_process_no_second_port(self) -> None:
        from starlette.applications import Starlette
        from starlette.testclient import TestClient

        from aidb.mcp.server import attach

        try:
            from fastapi import FastAPI

            app = FastAPI()
        except ImportError:
            app = Starlette()
        attach(app)
        mounted = [getattr(r, "path", "") for r in app.routes]
        self.assertTrue(any(str(p).startswith("/mcp") for p in mounted), mounted)
        # TestClient 是进程内 ASGI，不 bind 端口；进入上下文会跑 session_manager lifespan。
        with TestClient(app) as client:
            self.assertIs(client.app, app)
            self.assertFalse(hasattr(app, "server"))

    def test_fake_query_backend_pagination(self) -> None:
        registry = BackendRegistry()
        registry.register_relational(FakeQueryBackend())
        svc = AidbService(
            connections=ConnectionStore(self.root),
            overlays=OverlayStore(self.root),
            backends=registry,
        )
        svc.connections.put(_rel())
        page = svc.search_catalog("src1", limit=2)
        self.assertEqual([i.collection for i in page.items], ["orders", "users"])
        self.assertEqual(page.next_cursor, "2")
        page2 = svc.search_catalog("src1", cursor="2", limit=2)
        self.assertEqual([i.collection for i in page2.items], ["items", "payments"])
        self.assertIsNone(page2.next_cursor)

def _call_payload(result: object) -> dict:
    if isinstance(result, dict):
        return result
    if isinstance(result, tuple) and result:
        for part in result:
            if isinstance(part, dict) and ("code" in part or "columns" in part or "rows" in part):
                return part
            if hasattr(part, "structured_content") and isinstance(part.structured_content, dict):
                return part.structured_content
    sc = getattr(result, "structured_content", None)
    if isinstance(sc, dict):
        return sc
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        return data
    content = getattr(result, "content", None)
    if content:
        raw = getattr(content[0], "text", None)
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
    raise AssertionError(f"unparsed tool result: {type(result)!r} {result!r}")


class BoomBackend(QueryBackend):
    kind = "relational"

    def ping(self, source: Connection) -> None:
        return None

    def introspect_catalog(self, source: Connection, query: CatalogQuery) -> CatalogPage:
        raise RuntimeError("boom catalog SELECT 1")

    def execute_native(self, source: Connection, payload: ReadonlyPayload) -> QueryResult:
        raise RuntimeError("boom execute SELECT secret FROM x")


class TestExecuteReadonlyHostCompat(unittest.TestCase):
    def setUp(self) -> None:
        ensure_fake_adapter()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.svc = build_runtime(self.root, load=True)
        self.svc.connections.put(_rel())
        self.server = create_mcp_server(self.svc)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _exec(self, arguments: dict) -> dict:
        return _call_payload(asyncio.run(self.server.call_tool("execute_readonly", arguments)))

    def test_execute_readonly_sql_alias(self) -> None:
        payload = self._exec({"source_id": "src1", "language": "sql", "sql": "SELECT 1"})
        self.assertEqual(payload.get("columns"), ["id"])
        self.assertEqual(payload.get("rows"), [[1]])
        self.assertNotIn("code", payload)

    def test_execute_readonly_query_alias(self) -> None:
        payload = self._exec({"source_id": "src1", "query": "SELECT 1"})
        self.assertEqual(payload.get("rows"), [[1]])

    def test_execute_readonly_statement_canonical(self) -> None:
        payload = self._exec({"source_id": "src1", "statement": "SELECT 1"})
        self.assertEqual(payload.get("rows"), [[1]])

    def test_execute_readonly_missing_body(self) -> None:
        payload = self._exec({"source_id": "src1", "language": "sql"})
        self.assertEqual(payload.get("code"), "missing_statement")
        self.assertIn("statement", payload.get("message", ""))

    def test_uncaught_exception_is_structured_engine_error(self) -> None:
        boom = BoomBackend()
        registry = BackendRegistry()
        registry.register_relational(boom)
        svc = AidbService(
            connections=ConnectionStore(self.root),
            overlays=OverlayStore(self.root),
            backends=registry,
        )
        svc.connections.put(_rel())
        server = create_mcp_server(svc)
        payload = _call_payload(
            asyncio.run(
                server.call_tool(
                    "execute_readonly",
                    {"source_id": "src1", "sql": "SELECT secret FROM x"},
                )
            )
        )
        self.assertEqual(payload.get("code"), "engine_error")
        blob = json.dumps(payload)
        self.assertNotIn("SELECT secret", blob)
        self.assertNotIn("RuntimeError", blob)
        self.assertNotIn("s3cret-token-xyz", blob)


"""AIDB 配置台 FastAPI 应用。引擎下拉只走 visible_for_ui()。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from aidb.backends.registry import BackendRegistry
from aidb.backends.relational import RelationalBackend
from aidb.engines import load_engines
from aidb.engines.registry import get as get_adapter
from aidb.engines.registry import visible_for_ui
from aidb import SERVER_VERSION
from aidb.errors import CATALOG_PAGE_REQUIRED, INVALID_PATH, AidbError
from aidb.logsetup import configure_logging, log_event
from aidb.models.catalog import CatalogQuery, OverlayHead
from aidb.models.overlay import CollectionOverlay, OverlayRef, SourceOverlay
from aidb.store.bundle import export_bundle, import_bundle
from aidb.store.connections import ConnectionStore
from aidb.store.overlays import OverlayStore, default_data_root
from aidb.web.connections import ConnectionRepo
from aidb.web.overlays import OverlayRepo
from aidb.web.settings import Settings
from aidb.web.util import (
    overlay_body_patched,
    prune_auto_versions,
    read_patched,
    redact_connection,
    secret_keys_for_engine,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
AUTHOR = "web"


@dataclass
class AppCtx:
    root: Path
    connections: ConnectionStore
    overlays: OverlayStore
    overlay_repo: OverlayRepo
    backends: BackendRegistry
    repo: ConnectionRepo
    token: str | None
    auto_keep: int


class ConnectionIn(BaseModel):
    id: str | None = None
    name: str
    engine: str
    config: dict[str, Any] = Field(default_factory=dict)


class SourceOverlayIn(BaseModel):
    description: str | None = None
    query_rules: str | None = None


class CollectionOverlayIn(BaseModel):
    description: str | None = None
    fields: dict[str, str] = Field(default_factory=dict)


class LabelIn(BaseModel):
    label: str


class ExportIn(BaseModel):
    include_history: bool = True


def _error_body(exc: AidbError) -> dict[str, Any]:
    return {"code": exc.code, "message": exc.message, "details": exc.details}


def _aidb_response(exc: AidbError, status: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status, content=_error_body(exc))


def _clean_secrets(engine: str, config: dict[str, Any]) -> dict[str, Any]:
    secrets = secret_keys_for_engine(engine)
    cleaned = dict(config)
    for key in secrets:
        value = cleaned.get(key)
        if value in ("***",):
            cleaned[key] = ""
    return cleaned


def _record_payload(rec: Any | None, *, current: bool = False) -> dict[str, Any]:
    if rec is None:
        return {"meta": None, "body": {}, "patched": False, "current": current}
    return {
        "meta": rec.meta.model_dump(mode="json"),
        "body": rec.body.model_dump(mode="json"),
        "patched": overlay_body_patched(rec.body),
        "current": current,
        "id": rec.meta.id,
        "kind": rec.meta.kind,
        "label": rec.meta.label,
        "author": rec.meta.author,
        "created_at": rec.meta.created_at.isoformat() if rec.meta.created_at else None,
        "parent_id": rec.meta.parent_id,
    }


def _source_ref(source_id: str) -> OverlayRef:
    return OverlayRef(source_id=source_id)


def _collection_ref(source_id: str, namespace: str, collection: str) -> OverlayRef:
    return OverlayRef(source_id=source_id, namespace=namespace, collection=collection)


def _write_overlay(ctx: AppCtx, ref: OverlayRef, body: SourceOverlay | CollectionOverlay) -> dict[str, Any]:
    rec = ctx.overlays.write_head(ref, body, author=AUTHOR, kind="auto")
    prune_auto_versions(ctx.overlays, ref, ctx.auto_keep)
    return _record_payload(rec, current=True)


def _list_overlay_versions(ctx: AppCtx, ref: OverlayRef) -> dict[str, Any]:
    head = ctx.overlays.read_head(ref)
    head_id = head.meta.id if head is not None else None
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    archived = list(reversed(ctx.overlays.list_versions(ref)))
    for meta in archived:
        items.append(
            {
                "id": meta.id,
                "kind": meta.kind,
                "label": meta.label,
                "author": meta.author,
                "created_at": meta.created_at.isoformat() if meta.created_at else None,
                "parent_id": meta.parent_id,
                "current": bool(head_id and meta.id == head_id),
                "meta": meta.model_dump(mode="json"),
            }
        )
        seen.add(meta.id)
    return {"versions": items, "current": next((i for i in items if i.get("current")), items[0] if items else None)}


def _resolve_vid(ctx: AppCtx, ref: OverlayRef, token: str) -> str:
    if token in {"HEAD", "head", "current"}:
        rec = ctx.overlays.read_head(ref)
        if rec is None:
            raise AidbError(INVALID_PATH, "没有 HEAD 版本", {"ref": ref.model_dump()})
        return rec.meta.id
    return token


def _serialize_engine(adapter: Any) -> dict[str, Any]:
    return {
        "id": adapter.id,
        "aliases": list(adapter.aliases),
        "family": adapter.family,
        "labels": adapter.labels.model_dump(mode="json"),
        "form_schema": adapter.form_schema.model_dump(mode="json"),
        "ui": adapter.ui.model_dump(mode="json"),
    }


def _catalog_payload(page: Any, overlays: OverlayStore) -> dict[str, Any]:
    source_ref = OverlayRef(source_id=page.source_id)
    source_rec = overlays.read_head(source_ref)
    source_body = source_rec.body if source_rec is not None and isinstance(source_rec.body, SourceOverlay) else None

    collection_body: CollectionOverlay | None = None
    if len(page.items) == 1:
        node = page.items[0]
        if node.namespace is not None and node.collection is not None:
            coll_rec = overlays.read_head(
                OverlayRef(
                    source_id=page.source_id,
                    namespace=node.namespace,
                    collection=node.collection,
                )
            )
            if coll_rec is not None and isinstance(coll_rec.body, CollectionOverlay):
                collection_body = coll_rec.body

    fields = dict(collection_body.fields) if collection_body is not None else {}
    patched = overlay_body_patched(source_body) if source_body is not None else False
    if collection_body is not None:
        patched = patched or overlay_body_patched(collection_body)

    page.overlays = OverlayHead(
        source=source_body,
        collection=collection_body,
        fields=fields,
        patched=patched,
    )
    payload = page.to_json_dict()
    payload["patched"] = patched
    items_out: list[dict[str, Any]] = []
    for node in page.items:
        item = {
            "namespace": node.namespace,
            "collection": node.collection,
            "columns": [
                {"name": col.name, "type": col.type, "comment": col.comment}
                for col in node.columns
            ],
            "fks": node.fks,
            "patched": False,
        }
        if node.namespace and node.collection:
            item["patched"] = read_patched(
                overlays,
                OverlayRef(
                    source_id=page.source_id,
                    namespace=node.namespace,
                    collection=node.collection,
                ),
            )
        items_out.append(item)
    payload["items"] = items_out
    payload["source_patched"] = overlay_body_patched(source_body) if source_body is not None else False
    return payload


def _maybe_attach_mcp(app: FastAPI) -> None:
    try:
        from aidb.mcp.server import attach as attach_mcp
        attach_mcp(app)
    except ImportError:
        pass


def create_app(root: Path | str | None = None, *, token: str | None = None) -> FastAPI:
    """装配配置台：load_engines + BackendRegistry + 同一 data root 上的两个 Store。"""

    load_engines()
    if root is not None:
        data_root = Path(root)
        data_root.mkdir(parents=True, exist_ok=True)
        keep = 50
        raw_keep = os.environ.get("AIDB_OVERLAY_AUTO_KEEP")
        if raw_keep:
            try:
                keep = max(1, int(raw_keep))
            except ValueError:
                keep = 50
        tok = token if token is not None else (os.environ.get("AIDB_TOKEN") or None)
    else:
        settings = Settings.from_env()
        data_root = settings.data_dir
        keep = settings.overlay_auto_keep
        tok = token if token is not None else settings.token
        if tok is None:
            tok = os.environ.get("AIDB_TOKEN") or None

    backends = BackendRegistry.builtin()
    backends.register_relational(RelationalBackend())
    connections = ConnectionStore(data_root)
    overlay_repo = OverlayRepo(data_root, auto_keep=keep)
    overlays = overlay_repo.store
    ctx = AppCtx(
        root=data_root,
        connections=connections,
        overlays=overlays,
        overlay_repo=overlay_repo,
        backends=backends,
        repo=ConnectionRepo(data_root),
        token=tok or None,
        auto_keep=keep,
    )

    bind = os.environ.get("AIDB_BIND", "127.0.0.1")
    try:
        port = int(os.environ.get("AIDB_PORT", "8787"))
    except ValueError:
        port = 8787
    configure_logging(data_root=data_root, bind=bind, port=port)
    log_event("process_start", version=SERVER_VERSION, bind=bind, port=port)

    app = FastAPI(title="AIDB 配置台", docs_url=None, redoc_url=None)
    app.state.ctx = ctx
    app.state.aidb = ctx

    @app.middleware("http")
    async def _auth(request: Request, call_next):  # noqa: ANN001
        expected = ctx.token
        if not expected:
            return await call_next(request)
        if not request.url.path.startswith("/api"):
            return await call_next(request)
        header = request.headers.get("authorization") or ""
        bearer = header[7:].strip() if header.lower().startswith("bearer ") else ""
        xtoken = request.headers.get("x-aidb-token") or ""
        if bearer != expected and xtoken != expected:
            return JSONResponse(
                status_code=401,
                content={"code": "unauthorized", "message": "需要认证", "details": {}},
            )
        return await call_next(request)

    @app.exception_handler(AidbError)
    async def _aidb_error(_request: Request, exc: AidbError) -> JSONResponse:
        return _aidb_response(exc)

    @app.exception_handler(RequestValidationError)
    async def _valid_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        if request.url.path.startswith("/api"):
            return JSONResponse(
                status_code=400,
                content={
                    "code": INVALID_PATH,
                    "message": "请求无效",
                    "details": {"errors": exc.errors()},
                },
            )
        return await request_validation_exception_handler(request, exc)

    def _ctx() -> AppCtx:
        return ctx

    @app.get("/api/engines")
    def api_engines() -> list[dict[str, Any]]:
        # dropdown: visible_for_ui() only
        return [_serialize_engine(adapter) for adapter in visible_for_ui()]

    @app.get("/api/connections")
    def api_list_connections() -> list[dict[str, Any]]:
        return [redact_connection(c) for c in _ctx().connections.list()]

    @app.post("/api/connections")
    def api_create_connection(body: ConnectionIn) -> dict[str, Any]:
        store_ctx = _ctx()
        existing = store_ctx.connections.get(body.id) if body.id else None
        config = _clean_secrets(body.engine, body.config)
        conn = store_ctx.repo.build(
            engine=body.engine,
            name=body.name,
            config=config,
            source_id=body.id,
            existing=existing,
        )
        store_ctx.repo.put(conn)
        return redact_connection(conn)

    @app.get("/api/connections/{source_id}")
    def api_get_connection(source_id: str) -> dict[str, Any]:
        conn = _ctx().connections.require(source_id)
        return redact_connection(conn)

    @app.put("/api/connections/{source_id}")
    def api_put_connection(source_id: str, body: ConnectionIn) -> dict[str, Any]:
        store_ctx = _ctx()
        existing = store_ctx.connections.require(source_id)
        engine = body.engine or existing.engine
        config = _clean_secrets(engine, body.config)
        conn = store_ctx.repo.build(
            engine=engine,
            name=body.name,
            config=config,
            source_id=source_id,
            existing=existing,
        )
        store_ctx.repo.put(conn)
        return redact_connection(conn)

    @app.delete("/api/connections/{source_id}")
    def api_delete_connection(source_id: str) -> dict[str, Any]:
        store_ctx = _ctx()
        store_ctx.connections.require(source_id)
        store_ctx.connections.delete(source_id)
        return {"ok": True}

    @app.post("/api/connections/{source_id}/ping")
    def api_ping(source_id: str) -> dict[str, Any]:
        store_ctx = _ctx()
        conn = store_ctx.connections.require(source_id)
        try:
            store_ctx.backends.get(conn.kind).ping(conn)
        except Exception:
            log_event(
                "ping",
                source_id=conn.id,
                kind=conn.kind,
                engine=conn.engine,
                ok=False,
            )
            raise
        log_event(
            "connect",
            source_id=conn.id,
            kind=conn.kind,
            engine=conn.engine,
            ok=True,
        )
        log_event(
            "ping",
            source_id=conn.id,
            kind=conn.kind,
            engine=conn.engine,
            ok=True,
        )
        return {"ok": True}

    @app.get("/api/catalog")
    def api_catalog(
        source_id: str,
        namespace: str | None = None,
        collection: str | None = None,
        q: str | None = None,
        cursor: str | None = None,
        limit: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, Any]:
        store_ctx = _ctx()
        conn = store_ctx.connections.require(source_id)
        try:
            query = CatalogQuery(
                source_id=source_id,
                q=q,
                namespace=namespace,
                collection=collection,
                cursor=cursor,
                limit=limit,
            )
        except ValidationError as exc:
            raise AidbError(CATALOG_PAGE_REQUIRED, details={"errors": exc.errors()}) from exc
        page = store_ctx.backends.get(conn.kind).introspect_catalog(conn, query)
        return _catalog_payload(page, store_ctx.overlays)

    @app.get("/api/sources/{source_id}/overlay")
    def api_get_source_overlay(source_id: str) -> dict[str, Any]:
        store_ctx = _ctx()
        rec = store_ctx.overlays.read_head(_source_ref(source_id))
        if rec is None:
            return {
                "meta": None,
                "body": SourceOverlay().model_dump(mode="json"),
                "patched": False,
                "current": True,
            }
        return _record_payload(rec, current=True)

    @app.put("/api/sources/{source_id}/overlay")
    def api_put_source_overlay(source_id: str, body: SourceOverlayIn) -> dict[str, Any]:
        store_ctx = _ctx()
        overlay = SourceOverlay(description=body.description, query_rules=body.query_rules)
        return _write_overlay(store_ctx, _source_ref(source_id), overlay)

    @app.get("/api/sources/{source_id}/overlay/versions")
    def api_source_versions(source_id: str) -> dict[str, Any]:
        store_ctx = _ctx()
        return _list_overlay_versions(store_ctx, _source_ref(source_id))

    @app.get("/api/sources/{source_id}/overlay/versions/{vid}")
    def api_source_version(source_id: str, vid: str) -> dict[str, Any]:
        store_ctx = _ctx()
        ref = _source_ref(source_id)
        rec = store_ctx.overlays.read_version(ref, _resolve_vid(store_ctx, ref, vid))
        head = store_ctx.overlays.read_head(ref)
        current = head is not None and rec.meta.id == head.meta.id
        return _record_payload(rec, current=current)

    @app.get("/api/sources/{source_id}/overlay/diff")
    def api_source_diff(
        source_id: str,
        from_: str = Query(..., alias="from"),
        to: str = Query(...),
    ) -> dict[str, Any]:
        store_ctx = _ctx()
        ref = _source_ref(source_id)
        text = store_ctx.overlays.diff(
            ref,
            _resolve_vid(store_ctx, ref, from_),
            _resolve_vid(store_ctx, ref, to),
        )
        return {"diff": text, "from": from_, "to": to}

    @app.post("/api/sources/{source_id}/overlay/versions/{vid}/restore")
    def api_source_restore(source_id: str, vid: str) -> dict[str, Any]:
        store_ctx = _ctx()
        ref = _source_ref(source_id)
        rec = store_ctx.overlays.restore(ref, _resolve_vid(store_ctx, ref, vid), author=AUTHOR)
        prune_auto_versions(store_ctx.overlays, ref, store_ctx.auto_keep)
        return _record_payload(rec, current=True)

    @app.post("/api/sources/{source_id}/overlay/versions/{vid}/name")
    def api_source_name(source_id: str, vid: str, body: LabelIn) -> dict[str, Any]:
        store_ctx = _ctx()
        label = body.label.strip()
        if not label:
            raise AidbError(INVALID_PATH, "标签不能为空")
        ref = _source_ref(source_id)
        rec = store_ctx.overlays.label_version(ref, _resolve_vid(store_ctx, ref, vid), label)
        return _record_payload(rec)

    @app.get("/api/sources/{source_id}/namespaces/{namespace}/collections/{collection}/overlay")
    def api_get_collection_overlay(source_id: str, namespace: str, collection: str) -> dict[str, Any]:
        store_ctx = _ctx()
        rec = store_ctx.overlays.read_head(_collection_ref(source_id, namespace, collection))
        if rec is None:
            return {
                "meta": None,
                "body": CollectionOverlay().model_dump(mode="json"),
                "patched": False,
                "current": True,
            }
        return _record_payload(rec, current=True)

    @app.put("/api/sources/{source_id}/namespaces/{namespace}/collections/{collection}/overlay")
    def api_put_collection_overlay(
        source_id: str,
        namespace: str,
        collection: str,
        body: CollectionOverlayIn,
    ) -> dict[str, Any]:
        store_ctx = _ctx()
        overlay = CollectionOverlay(description=body.description, fields=dict(body.fields or {}))
        return _write_overlay(store_ctx, _collection_ref(source_id, namespace, collection), overlay)

    @app.get("/api/sources/{source_id}/namespaces/{namespace}/collections/{collection}/overlay/versions")
    def api_collection_versions(source_id: str, namespace: str, collection: str) -> dict[str, Any]:
        store_ctx = _ctx()
        return _list_overlay_versions(store_ctx, _collection_ref(source_id, namespace, collection))

    @app.get("/api/sources/{source_id}/namespaces/{namespace}/collections/{collection}/overlay/versions/{vid}")
    def api_collection_version(source_id: str, namespace: str, collection: str, vid: str) -> dict[str, Any]:
        store_ctx = _ctx()
        ref = _collection_ref(source_id, namespace, collection)
        rec = store_ctx.overlays.read_version(ref, _resolve_vid(store_ctx, ref, vid))
        head = store_ctx.overlays.read_head(ref)
        current = head is not None and rec.meta.id == head.meta.id
        return _record_payload(rec, current=current)

    @app.get("/api/sources/{source_id}/namespaces/{namespace}/collections/{collection}/overlay/diff")
    def api_collection_diff(
        source_id: str,
        namespace: str,
        collection: str,
        from_: str = Query(..., alias="from"),
        to: str = Query(...),
    ) -> dict[str, Any]:
        store_ctx = _ctx()
        ref = _collection_ref(source_id, namespace, collection)
        text = store_ctx.overlays.diff(
            ref,
            _resolve_vid(store_ctx, ref, from_),
            _resolve_vid(store_ctx, ref, to),
        )
        return {"diff": text, "from": from_, "to": to}

    @app.post("/api/sources/{source_id}/namespaces/{namespace}/collections/{collection}/overlay/versions/{vid}/restore")
    def api_collection_restore(source_id: str, namespace: str, collection: str, vid: str) -> dict[str, Any]:
        store_ctx = _ctx()
        ref = _collection_ref(source_id, namespace, collection)
        rec = store_ctx.overlays.restore(ref, _resolve_vid(store_ctx, ref, vid), author=AUTHOR)
        prune_auto_versions(store_ctx.overlays, ref, store_ctx.auto_keep)
        return _record_payload(rec, current=True)

    @app.post("/api/sources/{source_id}/namespaces/{namespace}/collections/{collection}/overlay/versions/{vid}/name")
    def api_collection_name(
        source_id: str,
        namespace: str,
        collection: str,
        vid: str,
        body: LabelIn,
    ) -> dict[str, Any]:
        store_ctx = _ctx()
        label = body.label.strip()
        if not label:
            raise AidbError(INVALID_PATH, "标签不能为空")
        ref = _collection_ref(source_id, namespace, collection)
        rec = store_ctx.overlays.label_version(ref, _resolve_vid(store_ctx, ref, vid), label)
        return _record_payload(rec)

    @app.post("/api/export")
    def api_export(body: ExportIn | None = None) -> dict[str, Any]:
        include_history = True if body is None else body.include_history
        return export_bundle(_ctx().root, include_history=include_history)

    @app.post("/api/import")
    def api_import(body: dict[str, Any]) -> dict[str, Any]:
        import_bundle(body, _ctx().root)
        return {"ok": True}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    _maybe_attach_mcp(app)
    return app


__all__ = ["create_app"]

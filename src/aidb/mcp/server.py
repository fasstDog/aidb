"""官方 MCP SDK 服务器。三个工具名锁定：list_sources / search_catalog / execute_readonly。"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

from aidb import SERVER_VERSION
from aidb.errors import ENGINE_ERROR, MISSING_STATEMENT, AidbError
from aidb.logsetup import log_event
from aidb.mcp.service import AidbService

_INSTRUCTIONS = (
    "AIDB 只执行只读查询，不生成 SQL，不写补丁。"
    "顺序：list_sources → search_catalog → 宿主自写语句 → execute_readonly。"
)



def resolve_statement(
    statement: str | None = None,
    sql: str | None = None,
    query: str | None = None,
) -> str:
    """Canonical field is statement; sql / query are host aliases."""

    for candidate in (statement, sql, query):
        if candidate is not None and str(candidate).strip() != "":
            return str(candidate)
    raise AidbError(MISSING_STATEMENT)


def _tool_error(exc: BaseException, *, tool: str, source_id: str | None = None) -> dict[str, Any]:
    """Never raise out of a tool: always {code,message,details}. Do not log SQL."""

    if isinstance(exc, AidbError):
        log_event(tool, tool=tool, code=exc.code, source_id=source_id)
        return exc.to_dict()
    log_event(tool, tool=tool, code=ENGINE_ERROR, source_id=source_id)
    return AidbError(ENGINE_ERROR).to_dict()


def create_mcp_server(service: AidbService | None = None) -> MCPServer:
    """用官方 SDK 注册三个稳定工具。不暴露 ask_readonly / 写补丁。"""

    if service is None:
        from aidb.runtime import build_runtime

        service = build_runtime()

    server = MCPServer(name="aidb", version=SERVER_VERSION, instructions=_INSTRUCTIONS)

    @server.tool(name="list_sources", description="列出已配置数据源元数据（不含密钥）")
    def list_sources() -> dict[str, Any]:
        try:
            return service.list_sources()
        except Exception as exc:
            return _tool_error(exc, tool="list_sources")

    @server.tool(
        name="search_catalog",
        description="分页检索目录：结构 + COMMENT + overlays HEAD + dialect_prompt",
    )
    def search_catalog(
        source_id: str,
        q: str | None = None,
        namespace: str | None = None,
        collection: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
        include_sample_values: bool = False,
    ) -> dict[str, Any]:
        try:
            page = service.search_catalog(
                source_id,
                q=q,
                namespace=namespace,
                collection=collection,
                cursor=cursor,
                limit=limit,
                include_sample_values=include_sample_values,
            )
            return page.to_json_dict()
        except Exception as exc:
            return _tool_error(exc, tool="search_catalog", source_id=source_id)

    @server.tool(
        name="execute_readonly",
        description="执行只读原生语句；关系型仅接受 sql。正文参数名 statement，别名 sql / query。",
    )
    def execute_readonly(
        source_id: str,
        language: Literal["sql", "mql", "dsl", "redis"] = "sql",
        statement: str | None = None,
        sql: str | None = None,
        query: str | None = None,
    ) -> dict[str, Any]:
        try:
            text = resolve_statement(statement=statement, sql=sql, query=query)
            result = service.execute_readonly(source_id, language, text)
            return result.model_dump(mode="json")
        except Exception as exc:
            return _tool_error(exc, tool="execute_readonly", source_id=source_id)

    return server


def attach(app) -> None:
    """Mount the three MCP tools onto an existing FastAPI/Starlette app. Same process, NO second port."""

    from aidb.logsetup import configure_logging, log_event
    from aidb.runtime import build_runtime

    data_root = None
    state = getattr(app, "state", None)
    if state is not None:
        ctx = getattr(state, "ctx", None) or getattr(state, "aidb", None)
        if ctx is not None:
            data_root = getattr(ctx, "root", None)
    bind = os.environ.get("AIDB_BIND", "127.0.0.1")
    try:
        port = int(os.environ.get("AIDB_PORT", "8787"))
    except ValueError:
        port = 8787
    configure_logging(data_root=data_root, bind=bind, port=port)
    log_event("process_start", version=SERVER_VERSION, bind=bind, port=port)
    service = build_runtime()
    mcp = create_mcp_server(service)
    # streamable-http 挂在 /mcp；先建 app 以创建 session_manager，再把 lifespan 并入配置台。
    mcp_http = mcp.streamable_http_app(streamable_http_path="/", stateless_http=True)
    router = getattr(app, "router", app)
    original = getattr(router, "lifespan_context", None)

    @asynccontextmanager
    async def _lifespan(parent):
        async with mcp.session_manager.run():
            if original is not None:
                async with original(parent) as state:
                    yield state
            else:
                yield

    router.lifespan_context = _lifespan
    app.mount("/mcp", mcp_http)
    if hasattr(app, "state"):
        app.state.aidb_mcp = mcp
        app.state.aidb_service = service


def run_stdio() -> None:
    """本地宿主：stdio 传输。Docker 走 python -m aidb.web + attach()。"""

    from aidb.logsetup import configure_logging, log_event

    configure_logging()
    log_event("process_start", version=SERVER_VERSION, bind="stdio")
    create_mcp_server().run(transport="stdio")

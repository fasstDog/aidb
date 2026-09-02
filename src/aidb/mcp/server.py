"""官方 MCP SDK 服务器。三个工具名锁定：list_sources / search_catalog / execute_readonly。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

from aidb import SERVER_VERSION
from aidb.errors import AidbError
from aidb.mcp.service import AidbService

_INSTRUCTIONS = (
    "AIDB 只执行只读查询，不生成 SQL，不写补丁。"
    "顺序：list_sources → search_catalog → 宿主自写语句 → execute_readonly。"
)


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
        except AidbError as exc:
            return exc.to_dict()

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
        except AidbError as exc:
            return exc.to_dict()

    @server.tool(name="execute_readonly", description="执行只读原生语句；关系型仅接受 sql")
    def execute_readonly(
        source_id: str,
        language: Literal["sql", "mql", "dsl", "redis"],
        statement: str,
    ) -> dict[str, Any]:
        try:
            result = service.execute_readonly(source_id, language, statement)
            return result.model_dump(mode="json")
        except AidbError as exc:
            return exc.to_dict()

    return server


def attach(app) -> None:
    """Mount the three MCP tools onto an existing FastAPI/Starlette app. Same process, NO second port."""

    from aidb.runtime import build_runtime

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

    create_mcp_server().run(transport="stdio")

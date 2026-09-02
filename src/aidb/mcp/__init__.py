"""MCP 工具层：只执行，不生成 SQL。"""

from aidb.mcp.server import attach, create_mcp_server, resolve_statement
from aidb.mcp.service import AidbService

__all__ = ["AidbService", "attach", "create_mcp_server", "resolve_statement"]

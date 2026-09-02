"""python -m aidb：本地宿主走 stdio MCP。Docker 使用 python -m aidb.web + attach()。"""

from __future__ import annotations

from aidb.mcp.server import run_stdio


def main() -> None:
    run_stdio()


if __name__ == "__main__":
    main()

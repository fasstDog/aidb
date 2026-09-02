"""python -m aidb.web — 配置台入口（MCP 同进程挂接）。"""

from __future__ import annotations

import os

import uvicorn

from aidb import SERVER_VERSION
from aidb.logsetup import configure_logging, log_event
from aidb.web.app import create_app


def main() -> None:
    bind = os.environ.get("AIDB_BIND", "127.0.0.1")
    port = int(os.environ.get("AIDB_PORT", "8787"))
    configure_logging(bind=bind, port=port)
    log_event("process_start", version=SERVER_VERSION, bind=bind, port=port)
    app = create_app()
    uvicorn.run(app, host=bind, port=port, log_level="info")


if __name__ == "__main__":
    main()

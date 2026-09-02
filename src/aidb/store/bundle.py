"""连接 + 覆盖层导出/导入。库 API，不是 MCP 工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aidb.models.connection import Connection
from aidb.store.connections import ConnectionStore
from aidb.store.overlays import OverlayStore, default_data_root


def export_bundle(
    root: Path | str | None = None,
    *,
    include_history: bool = True,
    connections: ConnectionStore | None = None,
    overlays: OverlayStore | None = None,
) -> dict[str, Any]:
    """导出。include_history=True 含 HEAD+versions；False 仅 HEAD。

    包内可含 config（备份）。调用方不得把包内容打进日志。
    """

    base = Path(root) if root is not None else default_data_root()
    conn_store = connections if connections is not None else ConnectionStore(base)
    overlay_store = overlays if overlays is not None else OverlayStore(base)
    return {
        "connections": [c.model_dump(mode="json") for c in conn_store.list()],
        "overlays": {rel: doc for rel, doc in overlay_store.iter_files(include_history=include_history)},
    }


def import_bundle(
    bundle: dict[str, Any],
    root: Path | str | None = None,
    *,
    connections: ConnectionStore | None = None,
    overlays: OverlayStore | None = None,
) -> None:
    """写入连接与覆盖层文件。不记录 config/密钥。"""

    base = Path(root) if root is not None else default_data_root()
    conn_store = connections if connections is not None else ConnectionStore(base)
    overlay_store = overlays if overlays is not None else OverlayStore(base)
    for raw in bundle.get("connections") or []:
        conn_store.put(Connection.model_validate(raw))
    for rel, doc in (bundle.get("overlays") or {}).items():
        if not isinstance(doc, dict):
            continue
        overlay_store.write_file(str(rel), doc)

"""进程装配：引擎加载、后端注册表、文件存储。"""

from __future__ import annotations

import os
from pathlib import Path

from aidb.backends.registry import BackendRegistry
from aidb.backends.relational import RelationalBackend
from aidb.engines import load_engines
from aidb.mcp.service import AidbService
from aidb.store.connections import ConnectionStore
from aidb.store.overlays import OverlayStore, default_data_root


def data_root(path: Path | str | None = None) -> Path:
    if path is not None:
        return Path(path)
    return default_data_root()


def build_runtime(
    root: Path | str | None = None,
    *,
    max_concurrency: int | None = None,
    load: bool = True,
) -> AidbService:
    """load_engines + BackendRegistry.builtin + register_relational + stores。"""

    if load:
        load_engines()
    registry = BackendRegistry.builtin()
    registry.register_relational(RelationalBackend())
    base = data_root(root)
    cap = max_concurrency
    if cap is None:
        raw = os.environ.get("AIDB_MAX_CONCURRENCY")
        cap = int(raw) if raw else None
    return AidbService(
        connections=ConnectionStore(base),
        overlays=OverlayStore(base),
        backends=registry,
        max_concurrency=cap,
    )

"""连接 JSON 存储：{AIDB_DATA}/connections/{id}.json。"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from aidb.engines.registry import get as get_engine_adapter
from aidb.models.connection import Connection
from aidb.store.connections import ConnectionStore

RELATIONAL_FAMILIES = frozenset({"mysql", "postgres", "oracle_like"})


def kind_from_family(family: str) -> str:
    """kind 由 family 决定，禁止按引擎名分支。"""

    if family in RELATIONAL_FAMILIES:
        return "relational"
    return family


def new_connection_id() -> str:
    return uuid.uuid4().hex[:12]


def redact_connection(conn: Connection) -> dict[str, Any]:
    """按适配器 form_schema 抹去 secret/password 字段。"""

    data = conn.model_dump(mode="json")
    adapter = get_engine_adapter(conn.engine)
    secret_keys = {
        field.key
        for field in adapter.form_schema.fields
        if field.secret or field.type == "password"
    }
    config = dict(data.get("config") or {})
    for key in secret_keys:
        if key in config:
            config[key] = None
    data["config"] = config
    return data


def merge_config(
    existing: dict[str, Any],
    incoming: dict[str, Any],
    secret_keys: set[str],
) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key in secret_keys and (value is None or value == ""):
            continue
        merged[key] = value
    return merged


class ConnectionRepo:
    """配置台连接仓库。"""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.store = ConnectionStore(self.root)

    def list(self) -> list[Connection]:
        return self.store.list()

    def get(self, source_id: str) -> Connection | None:
        return self.store.get(source_id)

    def require(self, source_id: str) -> Connection:
        return self.store.require(source_id)

    def put(self, connection: Connection) -> Connection:
        self.store.put(connection)
        from aidb.store._files import atomic_write_json
        from aidb.store.overlays import safe_segment
        cid = safe_segment(connection.id, "source_id")
        atomic_write_json(self.root / "connections" / f"{cid}.json", connection.model_dump(mode="json"))
        return connection

    def delete(self, source_id: str) -> bool:
        ok = self.store.delete(source_id)
        path = self.root / "connections" / f"{source_id}.json"
        if path.is_file():
            path.unlink()
        return ok

    def build(
        self,
        *,
        engine: str,
        name: str,
        config: dict[str, Any],
        source_id: str | None = None,
        existing: Connection | None = None,
    ) -> Connection:
        adapter = get_engine_adapter(engine)
        family = adapter.family
        kind = kind_from_family(family)
        secret_keys = {
            field.key
            for field in adapter.form_schema.fields
            if field.secret or field.type == "password"
        }
        if existing is not None:
            config = merge_config(existing.config, config, secret_keys)
            cid = existing.id
        else:
            cid = source_id or new_connection_id()
        return Connection(
            id=cid,
            name=name,
            kind=kind,  # type: ignore[arg-type]
            engine=adapter.id,
            family=family,
            config=config,
        )

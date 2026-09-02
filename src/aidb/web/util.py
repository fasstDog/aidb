"""Web helpers: kind mapping, secret redaction, overlay prune/patch flags."""

from __future__ import annotations

import os
from typing import Any

from aidb.engines.registry import get as get_adapter
from aidb.errors import AidbError
from aidb.models.connection import Connection, Family, Kind
from aidb.models.overlay import CollectionOverlay, OverlayRef, SourceOverlay
from aidb.store.overlays import OverlayStore

_RELATIONAL_FAMILIES = frozenset({"mysql", "postgres", "oracle_like"})
_KIND_FAMILIES = frozenset({"document", "kv", "search"})


def kind_from_family(family: Family | str) -> Kind:
    """Map adapter.family -> Connection.kind without engine-name branches."""

    if family in _RELATIONAL_FAMILIES:
        return "relational"
    if family in _KIND_FAMILIES:
        return family  # type: ignore[return-value]
    return "relational"


def secret_keys_for_engine(engine: str) -> set[str]:
    try:
        adapter = get_adapter(engine)
    except AidbError:
        return set()
    keys: set[str] = set()
    for field in adapter.form_schema.fields:
        if field.secret or field.type == "password":
            keys.add(field.key)
    return keys


def redact_connection(conn: Connection) -> dict[str, Any]:
    """List/get payload: hide secret/password form fields."""

    data = conn.model_dump(mode="json")
    secrets = secret_keys_for_engine(conn.engine)
    if secrets and isinstance(data.get("config"), dict):
        config = dict(data["config"])
        for key in secrets:
            if key in config and config[key] not in (None, ""):
                config[key] = "***"
        data["config"] = config
    return data


def overlay_body_patched(body: SourceOverlay | CollectionOverlay) -> bool:
    if isinstance(body, SourceOverlay):
        return bool(body.description) or bool(body.query_rules)
    return bool(body.description) or bool(body.fields)


def read_patched(store: OverlayStore, ref: OverlayRef) -> bool:
    rec = store.read_head(ref)
    if rec is None:
        return False
    return overlay_body_patched(rec.body)


def auto_keep() -> int:
    raw = os.environ.get("AIDB_OVERLAY_AUTO_KEEP", "50")
    try:
        return max(0, int(raw))
    except ValueError:
        return 50


def prune_auto_versions(store: OverlayStore, ref: OverlayRef, keep: int | None = None) -> None:
    """Delete oldest auto versions beyond keep; named versions are never removed."""

    limit = auto_keep() if keep is None else keep
    autos = [m for m in store.list_versions(ref) if m.kind == "auto"]
    # list_versions is ascending by created_at
    if len(autos) <= limit:
        return
    drop = autos[: len(autos) - limit]
    versions_dir = store._head_path(ref).parent / "versions"  # noqa: SLF001
    if not versions_dir.is_dir():
        return
    for meta in drop:
        for path in versions_dir.glob(f"*_{meta.id}.json"):
            try:
                path.unlink()
            except OSError:
                pass

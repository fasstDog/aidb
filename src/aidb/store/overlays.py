"""覆盖层文件存储。MCP 查询只读 HEAD；历史 append-only。"""

from __future__ import annotations

import difflib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from aidb.errors import INVALID_PATH, OVERLAY_NOT_FOUND, AidbError
from aidb.models.overlay import (
    CollectionOverlay,
    OverlayRef,
    SourceOverlay,
    VersionMeta,
    collection_head_path,
    collection_version_path,
    overlay_head_path,
    source_version_path,
)
from aidb.store._files import atomic_write_json, read_json, write_json_new

DEFAULT_AUTHOR = "aidb"

_FORBIDDEN_SEGMENTS = frozenset({".", "..", ""})


def default_data_root() -> Path:
    return Path(os.environ.get("AIDB_DATA", "/var/lib/aidb"))


def safe_segment(value: str, field: str) -> str:
    """禁止路径穿越：不得含斜杠、.. 或空段。"""

    if value is None or not isinstance(value, str):
        raise AidbError(INVALID_PATH, details={"field": field})
    if value.strip() != value or value in _FORBIDDEN_SEGMENTS:
        raise AidbError(INVALID_PATH, details={"field": field, "value": value})
    if "/" in value or "\\" in value or "\x00" in value:
        raise AidbError(INVALID_PATH, details={"field": field, "value": value})
    return value


def sanitize_ref(ref: OverlayRef) -> OverlayRef:
    source_id = safe_segment(ref.source_id, "source_id")
    namespace = safe_segment(ref.namespace, "namespace") if ref.namespace is not None else None
    collection = safe_segment(ref.collection, "collection") if ref.collection is not None else None
    return OverlayRef(
        source_id=source_id,
        namespace=namespace,
        collection=collection,
        field=ref.field,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


def format_ts(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%S%fZ")


class OverlayRecord(BaseModel):
    """HEAD / versions 文件信封。"""

    model_config = ConfigDict(extra="forbid")

    meta: VersionMeta
    body: SourceOverlay | CollectionOverlay

    def to_storage_dict(self) -> dict[str, Any]:
        return {
            "meta": self.meta.model_dump(mode="json"),
            "body": self.body.model_dump(mode="json"),
        }


def _is_source_ref(ref: OverlayRef) -> bool:
    return ref.namespace is None or ref.collection is None


def _load_record(path: Path, *, source_level: bool) -> OverlayRecord:
    data = read_json(path)
    meta = VersionMeta.model_validate(data["meta"])
    if source_level:
        body: SourceOverlay | CollectionOverlay = SourceOverlay.model_validate(data["body"])
    else:
        body = CollectionOverlay.model_validate(data["body"])
    return OverlayRecord(meta=meta, body=body)


class OverlayStore:
    """覆盖层文件库。粒度：集合（description + fields 同一文件）；源级独立版本线。"""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else default_data_root()

    def _ref(self, ref: OverlayRef) -> OverlayRef:
        return sanitize_ref(ref)

    def _head_path(self, ref: OverlayRef) -> Path:
        return self.root / overlay_head_path(self._ref(ref))

    def _version_path(self, ref: OverlayRef, ts: str, version_id: str) -> Path:
        r = self._ref(ref)
        if _is_source_ref(r):
            rel = source_version_path(r.source_id, ts, version_id)
        else:
            assert r.namespace is not None and r.collection is not None
            rel = collection_version_path(r.source_id, r.namespace, r.collection, ts, version_id)
        return self.root / rel

    def _versions_dir(self, ref: OverlayRef) -> Path:
        return self._head_path(ref).parent / "versions"

    def read_head(self, ref: OverlayRef) -> OverlayRecord | None:
        """MCP / search_catalog 只读 HEAD。"""

        path = self._head_path(ref)
        if not path.is_file():
            return None
        return _load_record(path, source_level=_is_source_ref(self._ref(ref)))

    def write_head(
        self,
        ref: OverlayRef,
        body: SourceOverlay | CollectionOverlay,
        *,
        author: str = DEFAULT_AUTHOR,
        kind: Literal["auto", "named"] = "auto",
        label: str | None = None,
    ) -> OverlayRecord:
        """若 HEAD 已存在，先把当前 HEAD 原样快照进 versions/（kind 保持），再写新 HEAD。"""

        r = self._ref(ref)
        source_level = _is_source_ref(r)
        if source_level:
            if not isinstance(body, SourceOverlay):
                raise AidbError(INVALID_PATH, "源级覆盖层必须是 SourceOverlay", {"ref": r.model_dump()})
        elif not isinstance(body, CollectionOverlay):
            raise AidbError(INVALID_PATH, "集合级覆盖层必须是 CollectionOverlay", {"ref": r.model_dump()})

        head_path = self._head_path(r)
        parent_id: str | None = None
        if head_path.is_file():
            old = _load_record(head_path, source_level=source_level)
            parent_id = old.meta.id
            snap_path = self._version_path(r, format_ts(old.meta.created_at), old.meta.id)
            write_json_new(snap_path, old.to_storage_dict())

        record = OverlayRecord(
            meta=VersionMeta(
                id=_new_id(),
                created_at=_now(),
                kind=kind,
                label=label,
                author=author,
                parent_id=parent_id,
            ),
            body=body,
        )
        atomic_write_json(head_path, record.to_storage_dict())
        return record

    def restore(self, ref: OverlayRef, version_id: str, *, author: str = DEFAULT_AUTHOR) -> OverlayRecord:
        """先把当前 HEAD 快照为 auto，再写新 HEAD（body 来自目标版本；不改旧版本文件）。"""

        r = self._ref(ref)
        source_level = _is_source_ref(r)
        target = self._require_version(r, version_id)
        head_path = self._head_path(r)
        parent_id: str | None = None
        if head_path.is_file():
            old = _load_record(head_path, source_level=source_level)
            snapshot = OverlayRecord(
                meta=old.meta.model_copy(update={"kind": "auto"}),
                body=old.body,
            )
            snap_path = self._version_path(r, format_ts(snapshot.meta.created_at), snapshot.meta.id)
            write_json_new(snap_path, snapshot.to_storage_dict())
            parent_id = snapshot.meta.id

        record = OverlayRecord(
            meta=VersionMeta(
                id=_new_id(),
                created_at=_now(),
                kind="auto",
                label=None,
                author=author,
                parent_id=parent_id,
            ),
            body=target.body,
        )
        atomic_write_json(head_path, record.to_storage_dict())
        return record

    def label_version(self, ref: OverlayRef, version_id: str, label: str) -> OverlayRecord:
        """给已有 auto 版本打标为 named，不改 body。"""

        r = self._ref(ref)
        path = self._find_version_path(r, version_id)
        if path is None:
            raise AidbError(OVERLAY_NOT_FOUND, details={"version_id": version_id})
        data = read_json(path)
        data["meta"]["kind"] = "named"
        data["meta"]["label"] = label
        # 历史版本一般不改写；打标是明确允许的 meta-only 例外。
        atomic_write_json(path, data)
        return _load_record(path, source_level=_is_source_ref(r))

    def list_versions(self, ref: OverlayRef) -> list[VersionMeta]:
        r = self._ref(ref)
        source_level = _is_source_ref(r)
        versions_dir = self._versions_dir(r)
        metas: list[VersionMeta] = []
        if versions_dir.is_dir():
            for path in versions_dir.glob("*.json"):
                if path.name.endswith(".tmp"):
                    continue
                try:
                    rec = _load_record(path, source_level=source_level)
                except (OSError, KeyError, ValueError):
                    continue
                metas.append(rec.meta)
        metas.sort(key=lambda m: (m.created_at, m.id))
        return metas

    def read_version(self, ref: OverlayRef, version_id: str) -> OverlayRecord:
        return self._require_version(self._ref(ref), version_id)

    def diff(self, ref: OverlayRef, version_a: str, version_b: str) -> str:
        r = self._ref(ref)
        a = self._require_version(r, version_a)
        b = self._require_version(r, version_b)
        a_lines = json.dumps(a.body.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False).splitlines()
        b_lines = json.dumps(b.body.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False).splitlines()
        return "\n".join(
            difflib.unified_diff(
                a_lines,
                b_lines,
                fromfile=version_a,
                tofile=version_b,
                lineterm="",
            )
        )

    def iter_files(self, *, include_history: bool) -> list[tuple[str, dict[str, Any]]]:
        """相对 AIDB_DATA 根的覆盖层文件。include_history=False 仅 HEAD。"""

        overlays_dir = self.root / "overlays"
        if not overlays_dir.is_dir():
            return []
        out: list[tuple[str, dict[str, Any]]] = []
        for path in sorted(overlays_dir.rglob("*.json")):
            if path.name.endswith(".tmp") or path.name.endswith(".json.tmp"):
                continue
            if path.name != "HEAD.json" and not include_history:
                continue
            rel = path.relative_to(self.root).as_posix()
            out.append((rel, read_json(path)))
        return out

    def write_file(self, relative: str, data: dict[str, Any]) -> None:
        """导入用：按相对路径写入，拒绝穿越。"""

        rel = _safe_overlay_relative(relative)
        atomic_write_json(self.root / rel, data)

    def _find_version_path(self, ref: OverlayRef, version_id: str) -> Path | None:
        source_level = _is_source_ref(ref)
        versions_dir = self._versions_dir(ref)
        if versions_dir.is_dir():
            for path in versions_dir.glob("*.json"):
                if path.name.endswith(".tmp"):
                    continue
                try:
                    rec = _load_record(path, source_level=source_level)
                except (OSError, KeyError, ValueError):
                    continue
                if rec.meta.id == version_id:
                    return path
        head_path = self._head_path(ref)
        if head_path.is_file():
            rec = _load_record(head_path, source_level=source_level)
            if rec.meta.id == version_id:
                return head_path
        return None

    def _require_version(self, ref: OverlayRef, version_id: str) -> OverlayRecord:
        path = self._find_version_path(ref, version_id)
        if path is None:
            raise AidbError(OVERLAY_NOT_FOUND, details={"version_id": version_id})
        return _load_record(path, source_level=_is_source_ref(ref))


def _safe_overlay_relative(relative: str) -> str:
    if not relative or relative.startswith("/") or "\\" in relative:
        raise AidbError(INVALID_PATH, details={"path": relative})
    parts = relative.split("/")
    if ".." in parts or "." in parts:
        raise AidbError(INVALID_PATH, details={"path": relative})
    if parts[0] != "overlays" or not relative.endswith(".json"):
        raise AidbError(INVALID_PATH, details={"path": relative})
    for part in parts:
        if part.endswith(".tmp"):
            raise AidbError(INVALID_PATH, details={"path": relative})
    return relative

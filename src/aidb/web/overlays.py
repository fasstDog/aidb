"""覆盖层文件存储。路径遵循 CONTRACT，位于 {AIDB_DATA}/ 下。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from aidb.models.catalog import OverlayHead
from aidb.models.overlay import (
    CollectionOverlay,
    OverlayRef,
    SourceOverlay,
    overlay_head_path,
)
from aidb.store._files import read_json, write_json_new
from aidb.store.overlays import OverlayRecord, OverlayStore, format_ts, sanitize_ref

DEFAULT_AUTHOR = "aidb"


def overlay_is_patched(body: SourceOverlay | CollectionOverlay | None) -> bool:
    """HEAD 含 description / query_rules / fields 任一即 patched。"""

    if body is None:
        return False
    if getattr(body, "description", None):
        return True
    if getattr(body, "query_rules", None):
        return True
    fields = getattr(body, "fields", None)
    if fields:
        return True
    return False


def record_to_payload(rec: OverlayRecord | None) -> dict[str, Any]:
    if rec is None:
        return {"meta": None, "payload": {}, "patched": False}
    return {
        "meta": rec.meta.model_dump(mode="json"),
        "payload": rec.body.model_dump(mode="json"),
        "patched": overlay_is_patched(rec.body),
    }


class OverlayRepo:
    """配置台覆盖层：写入时快照 HEAD 为 auto，并裁剪多余自动版。"""

    def __init__(self, root: Path | str, *, auto_keep: int = 50) -> None:
        self.root = Path(root)
        self.auto_keep = max(1, int(auto_keep))
        self.store = OverlayStore(self.root)

    def read_head(self, ref: OverlayRef) -> OverlayRecord | None:
        return self.store.read_head(ref)

    def get_head(self, ref: OverlayRef) -> dict[str, Any]:
        return record_to_payload(self.read_head(ref))

    def put(
        self,
        ref: OverlayRef,
        body: SourceOverlay | CollectionOverlay,
        *,
        author: str = DEFAULT_AUTHOR,
    ) -> OverlayRecord:
        rec = self.store.write_head(ref, body, author=author, kind="auto")
        self._archive(ref, rec)
        self.prune(ref)
        return rec

    def restore(self, ref: OverlayRef, version_id: str, *, author: str = DEFAULT_AUTHOR) -> OverlayRecord:
        rec = self.store.restore(ref, version_id, author=author)
        self._archive(ref, rec)
        self.prune(ref)
        return rec

    def name(self, ref: OverlayRef, version_id: str, label: str) -> OverlayRecord:
        rec = self.store.label_version(ref, version_id, label)
        head = self.read_head(ref)
        if head is not None and head.meta.id == version_id and head.meta.kind != "named":
            from aidb.store._files import atomic_write_json

            updated = OverlayRecord(meta=rec.meta, body=head.body)
            rel = overlay_head_path(sanitize_ref(ref))
            atomic_write_json(self.root / rel, updated.to_storage_dict())
            return updated
        return rec

    def list_versions(self, ref: OverlayRef) -> list[dict[str, Any]]:
        metas = self.store.list_versions(ref)
        metas.sort(key=lambda m: (m.created_at, m.id), reverse=True)
        return [m.model_dump(mode="json") for m in metas]

    def read_version(self, ref: OverlayRef, version_id: str) -> OverlayRecord:
        return self.store.read_version(ref, version_id)

    def diff(self, ref: OverlayRef, version_from: str, version_to: str) -> str:
        return self.store.diff(ref, version_from, version_to)

    def overlay_head_view(
        self,
        source_id: str,
        namespace: str | None = None,
        collection: str | None = None,
    ) -> OverlayHead:
        source_body: SourceOverlay | None = None
        source_rec = self.read_head(OverlayRef(source_id=source_id))
        if source_rec is not None and isinstance(source_rec.body, SourceOverlay):
            source_body = source_rec.body
        collection_body: CollectionOverlay | None = None
        if namespace is not None and collection is not None:
            coll_rec = self.read_head(
                OverlayRef(source_id=source_id, namespace=namespace, collection=collection)
            )
            if coll_rec is not None and isinstance(coll_rec.body, CollectionOverlay):
                collection_body = coll_rec.body
        fields = dict(collection_body.fields) if collection_body is not None else {}
        patched = overlay_is_patched(source_body) or overlay_is_patched(collection_body)
        return OverlayHead(
            source=source_body,
            collection=collection_body,
            fields=fields,
            patched=patched,
        )

    def item_patched(self, source_id: str, namespace: str | None, collection: str | None) -> bool:
        if not namespace or not collection:
            return False
        rec = self.read_head(
            OverlayRef(source_id=source_id, namespace=namespace, collection=collection)
        )
        if rec is None:
            return False
        return overlay_is_patched(rec.body)

    def prune(self, ref: OverlayRef) -> None:
        """只删 auto，保留 named；auto 仅留最近 N 份。"""

        ref = sanitize_ref(ref)
        versions_dir = self.root / Path(overlay_head_path(ref)).parent / "versions"
        if not versions_dir.is_dir():
            return
        autos: list[tuple[datetime, str, Path]] = []
        for path in versions_dir.glob("*.json"):
            if path.name.endswith(".tmp"):
                continue
            try:
                data = read_json(path)
                meta = data.get("meta") or {}
                if meta.get("kind") != "auto":
                    continue
                created_raw = meta.get("created_at")
                created = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                vid = str(meta.get("id") or path.stem)
            except (OSError, ValueError, TypeError, KeyError):
                continue
            autos.append((created, vid, path))
        autos.sort(key=lambda row: (row[0], row[1]))
        drop = autos[: max(0, len(autos) - self.auto_keep)]
        for _, _, path in drop:
            try:
                path.unlink()
            except OSError:
                pass

    def _archive(self, ref: OverlayRef, rec: OverlayRecord) -> None:
        """当前 HEAD 同步进 versions/，保证一次写入即有 HEAD + auto。"""

        ref = sanitize_ref(ref)
        ts = format_ts(rec.meta.created_at)
        if ref.namespace is None or ref.collection is None:
            from aidb.models.overlay import source_version_path

            rel = source_version_path(ref.source_id, ts, rec.meta.id)
        else:
            from aidb.models.overlay import collection_version_path

            assert ref.namespace is not None and ref.collection is not None
            rel = collection_version_path(
                ref.source_id, ref.namespace, ref.collection, ts, rec.meta.id
            )
        write_json_new(self.root / rel, rec.to_storage_dict())

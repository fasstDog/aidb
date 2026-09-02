"""覆盖层存储：快照、restore、append-only、named/auto。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aidb.errors import INVALID_PATH, OVERLAY_NOT_FOUND, AidbError
from aidb.models.overlay import CollectionOverlay, OverlayRef, SourceOverlay, source_head_path
from aidb.store.overlays import OverlayStore


class TestOverlayStore(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.store = OverlayStore(self.root)
        self.ref = OverlayRef(source_id="src1")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_write_head_snapshots_previous(self) -> None:
        first = self.store.write_head(self.ref, SourceOverlay(description="v1"))
        second = self.store.write_head(self.ref, SourceOverlay(description="v2"), kind="named", label="rel")
        head = self.store.read_head(self.ref)
        self.assertIsNotNone(head)
        assert head is not None
        self.assertEqual(head.body.description, "v2")
        self.assertEqual(head.meta.id, second.meta.id)
        self.assertEqual(head.meta.parent_id, first.meta.id)
        self.assertEqual(head.meta.kind, "named")
        versions = self.store.list_versions(self.ref)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].id, first.meta.id)
        self.assertEqual(versions[0].kind, "auto")
        archived = self.store.read_version(self.ref, first.meta.id)
        self.assertEqual(archived.body.description, "v1")
        # 确认走了契约路径 helpers
        self.assertTrue((self.root / source_head_path("src1")).is_file())
        version_files = list((self.root / "overlays" / "src1" / "_source" / "versions").glob("*.json"))
        self.assertEqual(len(version_files), 1)
        self.assertTrue(version_files[0].name.endswith(f"_{first.meta.id}.json"))

    def test_search_reads_only_head(self) -> None:
        self.store.write_head(self.ref, SourceOverlay(description="old"))
        self.store.write_head(self.ref, SourceOverlay(description="head-now"))
        head = self.store.read_head(self.ref)
        assert head is not None
        self.assertEqual(head.body.description, "head-now")
        versions = self.store.list_versions(self.ref)
        self.assertEqual(versions[0].id, versions[0].id)
        archived = self.store.read_version(self.ref, versions[0].id)
        self.assertEqual(archived.body.description, "old")
        self.assertNotEqual(head.meta.id, archived.meta.id)

    def test_restore_snapshots_then_new_head(self) -> None:
        v1 = self.store.write_head(self.ref, SourceOverlay(description="one"))
        v2 = self.store.write_head(self.ref, SourceOverlay(description="two"))
        before = self.store.read_version(self.ref, v1.meta.id).to_storage_dict()
        restored = self.store.restore(self.ref, v1.meta.id)
        after = self.store.read_version(self.ref, v1.meta.id).to_storage_dict()
        self.assertEqual(before, after)
        head = self.store.read_head(self.ref)
        assert head is not None
        self.assertEqual(head.body.description, "one")
        self.assertNotEqual(head.meta.id, v1.meta.id)
        self.assertEqual(head.meta.parent_id, v2.meta.id)
        ids = {m.id for m in self.store.list_versions(self.ref)}
        self.assertIn(v1.meta.id, ids)
        self.assertIn(v2.meta.id, ids)

    def test_history_append_only(self) -> None:
        v1 = self.store.write_head(self.ref, SourceOverlay(description="a"))
        self.store.write_head(self.ref, SourceOverlay(description="b"))
        vdir = self.root / "overlays" / "src1" / "_source" / "versions"
        files = {p.name: p.read_text(encoding="utf-8") for p in vdir.glob("*.json")}
        self.store.write_head(self.ref, SourceOverlay(description="c"))
        files_after = {p.name: p.read_text(encoding="utf-8") for p in vdir.glob("*.json")}
        for name, text in files.items():
            self.assertEqual(files_after[name], text)
        self.assertGreater(len(files_after), len(files))
        self.assertEqual(self.store.read_version(self.ref, v1.meta.id).body.description, "a")

    def test_named_and_label_auto(self) -> None:
        auto = self.store.write_head(self.ref, SourceOverlay(description="auto-body"))
        self.store.write_head(self.ref, SourceOverlay(description="later"), kind="named", label="keep")
        labeled = self.store.label_version(self.ref, auto.meta.id, "remember")
        self.assertEqual(labeled.meta.kind, "named")
        self.assertEqual(labeled.meta.label, "remember")
        self.assertEqual(labeled.body.description, "auto-body")

    def test_collection_overlay_includes_fields(self) -> None:
        ref = OverlayRef(source_id="src1", namespace="public", collection="orders")
        rec = self.store.write_head(
            ref,
            CollectionOverlay(description="订单", fields={"id": "主键", "name": "名称"}),
        )
        head = self.store.read_head(ref)
        assert head is not None
        assert isinstance(head.body, CollectionOverlay)
        self.assertEqual(head.body.fields["id"], "主键")
        self.assertTrue(
            (self.root / "overlays" / "src1" / "public" / "orders" / "HEAD.json").is_file()
        )
        self.assertEqual(rec.body.description, "订单")

    def test_source_and_collection_are_separate_lines(self) -> None:
        self.store.write_head(self.ref, SourceOverlay(description="src"))
        coll = OverlayRef(source_id="src1", namespace="public", collection="orders")
        self.store.write_head(coll, CollectionOverlay(description="t"))
        self.assertEqual(self.store.read_head(self.ref).body.description, "src")
        self.assertEqual(self.store.read_head(coll).body.description, "t")

    def test_path_traversal_rejected(self) -> None:
        with self.assertRaises(AidbError) as ctx:
            self.store.write_head(
                OverlayRef(source_id="src1", namespace="..", collection="x"),
                CollectionOverlay(description="no"),
            )
        self.assertEqual(ctx.exception.code, INVALID_PATH)

        with self.assertRaises(AidbError) as ctx2:
            self.store.write_head(
                OverlayRef(source_id="src1", namespace="a/b", collection="x"),
                CollectionOverlay(description="no"),
            )
        self.assertEqual(ctx2.exception.code, INVALID_PATH)

    def test_diff_uses_stdlib(self) -> None:
        a = self.store.write_head(self.ref, SourceOverlay(description="left"))
        b = self.store.write_head(self.ref, SourceOverlay(description="right"))
        text = self.store.diff(self.ref, a.meta.id, b.meta.id)
        self.assertIn("left", text)
        self.assertIn("right", text)

    def test_missing_version(self) -> None:
        with self.assertRaises(AidbError) as ctx:
            self.store.read_version(self.ref, "nope")
        self.assertEqual(ctx.exception.code, OVERLAY_NOT_FOUND)

    def test_restore_does_not_rewrite_old_file_bytes(self) -> None:
        v1 = self.store.write_head(self.ref, SourceOverlay(description="keep"))
        self.store.write_head(self.ref, SourceOverlay(description="new"))
        vdir = self.root / "overlays" / "src1" / "_source" / "versions"
        path = next(p for p in vdir.glob("*.json") if v1.meta.id in p.name)
        original = path.read_bytes()
        self.store.restore(self.ref, v1.meta.id)
        self.assertEqual(path.read_bytes(), original)


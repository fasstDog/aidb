"""导出/导入：HEAD-only vs 含历史。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aidb.models.connection import Connection
from aidb.models.overlay import OverlayRef, SourceOverlay
from aidb.store.bundle import export_bundle, import_bundle
from aidb.store.connections import ConnectionStore
from aidb.store.overlays import OverlayStore


class TestBundle(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.conns = ConnectionStore(self.root)
        self.overlays = OverlayStore(self.root)
        self.conns.put(
            Connection(
                id="src1",
                name="订单库",
                kind="relational",
                engine="fake",
                family="postgres",
                config={"password": "s3cret-token-xyz"},
            )
        )
        ref = OverlayRef(source_id="src1")
        self.overlays.write_head(ref, SourceOverlay(description="v1"))
        self.overlays.write_head(ref, SourceOverlay(description="v2"))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_head_only_skips_versions(self) -> None:
        bundle = export_bundle(self.root, include_history=False)
        overlay_keys = list(bundle["overlays"].keys())
        self.assertTrue(any(k.endswith("HEAD.json") for k in overlay_keys))
        self.assertFalse(any("/versions/" in k for k in overlay_keys))
        self.assertEqual(bundle["connections"][0]["config"]["password"], "s3cret-token-xyz")

    def test_with_history_includes_versions(self) -> None:
        bundle = export_bundle(self.root, include_history=True)
        overlay_keys = list(bundle["overlays"].keys())
        self.assertTrue(any(k.endswith("HEAD.json") for k in overlay_keys))
        self.assertTrue(any("/versions/" in k for k in overlay_keys))

    def test_roundtrip_head_only_and_history(self) -> None:
        head_only = export_bundle(self.root, include_history=False)
        full = export_bundle(self.root, include_history=True)

        dest_head = Path(tempfile.mkdtemp())
        dest_full = Path(tempfile.mkdtemp())
        try:
            import_bundle(head_only, dest_head)
            import_bundle(full, dest_full)
            head_files = list((dest_head / "overlays").rglob("*.json"))
            self.assertTrue(all(p.name == "HEAD.json" for p in head_files))
            full_files = list((dest_full / "overlays").rglob("*.json"))
            self.assertTrue(any(p.parent.name == "versions" for p in full_files))
            imported = ConnectionStore(dest_full).get("src1")
            assert imported is not None
            self.assertEqual(imported.config["password"], "s3cret-token-xyz")
            self.assertEqual(
                OverlayStore(dest_head).read_head(OverlayRef(source_id="src1")).body.description,
                "v2",
            )
        finally:
            import shutil

            shutil.rmtree(dest_head, ignore_errors=True)
            shutil.rmtree(dest_full, ignore_errors=True)

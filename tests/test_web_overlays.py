"""配置台覆盖层 HTTP：patched、命名、恢复、diff。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from aidb.web.app import create_app


class TestWebOverlays(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.app = create_app(self.tmp_path)
        self.client = TestClient(self.app)
        self.source_id = "src1"
        created = self.client.post(
            "/api/connections",
            json={
                "id": self.source_id,
                "name": "订单库",
                "engine": "postgres",
                "config": {"host": "127.0.0.1", "dbname": "app", "user": "u"},
            },
        )
        self.assertEqual(created.status_code, 200)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _source_url(self) -> str:
        return f"/api/sources/{self.source_id}/overlay"

    def _coll_url(self) -> str:
        return f"/api/sources/{self.source_id}/namespaces/public/collections/orders/overlay"

    def test_put_overlay_then_get_shows_patched(self) -> None:
        put = self.client.put(
            self._source_url(),
            json={"description": "订单库说明", "query_rules": "只用只读查询"},
        )
        self.assertEqual(put.status_code, 200, put.text)
        self.assertTrue(put.json()["patched"])
        got = self.client.get(self._source_url())
        self.assertEqual(got.status_code, 200)
        body = got.json()
        self.assertTrue(body["patched"])
        self.assertEqual(body["body"]["description"], "订单库说明")
        self.assertEqual(body["body"]["query_rules"], "只用只读查询")

        cput = self.client.put(
            self._coll_url(),
            json={"description": "订单", "fields": {"id": "主键", "name": "名称"}},
        )
        self.assertEqual(cput.status_code, 200, cput.text)
        self.assertTrue(cput.json()["patched"])
        cgot = self.client.get(self._coll_url())
        self.assertEqual(cgot.status_code, 200)
        cbody = cgot.json()
        self.assertTrue(cbody["patched"])
        self.assertEqual(cbody["body"]["fields"]["id"], "主键")

    def test_name_restore_diff_endpoints_200(self) -> None:
        self.assertEqual(
            self.client.put(self._source_url(), json={"description": "v1", "query_rules": None}).status_code,
            200,
        )
        self.assertEqual(
            self.client.put(self._source_url(), json={"description": "v2", "query_rules": "rule"}).status_code,
            200,
        )
        listed = self.client.get(self._source_url() + "/versions")
        self.assertEqual(listed.status_code, 200, listed.text)
        payload = listed.json()
        versions = payload["versions"] if isinstance(payload, dict) else payload
        self.assertTrue(versions)
        archived = [v for v in versions if not v.get("current")]
        target = archived[0] if archived else versions[-1]
        vid = target["id"]
        head = self.client.get(self._source_url()).json()
        hid = (head.get("meta") or {}).get("id") or head.get("id")

        self.assertEqual(self.client.get(self._source_url() + f"/versions/{vid}").status_code, 200)

        named = self.client.post(
            self._source_url() + f"/versions/{vid}/name",
            json={"label": "keep"},
        )
        self.assertEqual(named.status_code, 200, named.text)

        diffed = self.client.get(
            self._source_url() + "/diff",
            params={"from": vid, "to": hid},
        )
        self.assertEqual(diffed.status_code, 200, diffed.text)
        self.assertIn("diff", diffed.json())

        restored = self.client.post(self._source_url() + f"/versions/{vid}/restore")
        self.assertEqual(restored.status_code, 200, restored.text)

        self.assertEqual(
            self.client.put(self._coll_url(), json={"description": "c1", "fields": {}}).status_code,
            200,
        )
        self.assertEqual(
            self.client.put(self._coll_url(), json={"description": "c2", "fields": {"id": "主键"}}).status_code,
            200,
        )
        clisted = self.client.get(self._coll_url() + "/versions")
        self.assertEqual(clisted.status_code, 200, clisted.text)
        cpayload = clisted.json()
        cversions = cpayload["versions"] if isinstance(cpayload, dict) else cpayload
        self.assertTrue(cversions)
        carch = [v for v in cversions if not v.get("current")]
        cvid = (carch[0] if carch else cversions[-1])["id"]
        chead = self.client.get(self._coll_url()).json()
        chead_id = (chead.get("meta") or {}).get("id") or chead.get("id")
        self.assertEqual(self.client.get(self._coll_url() + f"/versions/{cvid}").status_code, 200)
        self.assertEqual(
            self.client.post(self._coll_url() + f"/versions/{cvid}/name", json={"label": "rel"}).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(self._coll_url() + "/diff", params={"from": cvid, "to": chead_id}).status_code,
            200,
        )
        self.assertEqual(self.client.post(self._coll_url() + f"/versions/{cvid}/restore").status_code, 200)



    def test_catalog_paginates_and_patched(self) -> None:
        from tests.fakes import ensure_fake_adapter
        from aidb.store.overlays import OverlayStore
        from aidb.models.overlay import OverlayRef
        ensure_fake_adapter()
        created = self.client.post(
            "/api/connections",
            json={"id": "fake1", "name": "假库", "engine": "fake", "config": {}},
        )
        self.assertEqual(created.status_code, 200, created.text)
        self.client.put(
            "/api/sources/fake1/namespaces/public/collections/orders/overlay",
            json={"description": "订单", "fields": {"id": "主键"}},
        )
        page = self.client.get("/api/catalog", params={"source_id": "fake1", "namespace": "public", "limit": 2})
        self.assertEqual(page.status_code, 200, page.text)
        data = page.json()
        self.assertEqual(data.get("next_cursor"), "2")
        items = data["items"]
        orders = next(i for i in items if i.get("collection") == "orders")
        self.assertTrue(orders.get("patched"))
        store = OverlayStore(self.tmp_path)
        rec = store.read_head(OverlayRef(source_id="fake1", namespace="public", collection="orders"))
        self.assertIsNotNone(rec)


if __name__ == "__main__":
    unittest.main()


class TestOverlayPrune(unittest.TestCase):
    def test_prune_keeps_named_drops_old_autos(self) -> None:
        import os
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        os.environ["AIDB_OVERLAY_AUTO_KEEP"] = "2"
        root = Path(tmp.name)
        app = create_app(root)
        client = TestClient(app)
        client.post("/api/connections", json={"id": "p1", "name": "p", "engine": "postgres", "config": {"dbname": "d", "user": "u"}})
        first = client.put("/api/sources/p1/overlay", json={"description": "pin"}).json()
        vid = first.get("id") or first["meta"]["id"]
        client.put("/api/sources/p1/overlay", json={"description": "snap"})
        client.post(f"/api/sources/p1/overlay/versions/{vid}/name", json={"label": "keep"})
        for i in range(5):
            client.put("/api/sources/p1/overlay", json={"description": f"a{i}"})
        vdir = root / "overlays" / "p1" / "_source" / "versions"
        autos = named = 0
        for path in vdir.glob("*.json"):
            text = path.read_text(encoding="utf-8")
            if '"kind": "named"' in text:
                named += 1
            elif '"kind": "auto"' in text:
                autos += 1
        self.assertGreaterEqual(named, 1)
        self.assertLessEqual(autos, 2)

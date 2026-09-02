"""配置台引擎下拉与连接落盘。"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from aidb.store.connections import ConnectionStore
from aidb.web.app import create_app

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "aidb"


def _engine_rows(payload):
    if isinstance(payload, dict):
        rows = payload.get("engines") or payload.get("items")
        if isinstance(rows, list):
            return rows
    if isinstance(payload, list):
        return payload
    return []


def _frontend_blob() -> str:
    texts: list[str] = []
    ui_src = SRC / "web" / "ui" / "src"
    static = SRC / "web" / "static"
    for folder in (ui_src, static):
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if path.suffix.lower() in {".js", ".vue", ".ts", ".mjs", ".cjs"}:
                texts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(texts)


class TestWebEngines(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.app = create_app(self.tmp_path)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_get_engines_includes_postgres_mysql_not_dameng(self) -> None:
        resp = self.client.get("/api/engines")
        self.assertEqual(resp.status_code, 200)
        ids = [row["id"] for row in _engine_rows(resp.json())]
        self.assertIn("postgres", ids)
        self.assertIn("mysql", ids)
        self.assertNotIn("dameng", ids)

    def test_postgres_form_has_dbname_mysql_has_database(self) -> None:
        engines = {row["id"]: row for row in _engine_rows(self.client.get("/api/engines").json())}
        pg_keys = [f["key"] for f in engines["postgres"]["form_schema"]["fields"]]
        my_keys = [f["key"] for f in engines["mysql"]["form_schema"]["fields"]]
        self.assertIn("dbname", pg_keys)
        self.assertIn("database", my_keys)

    def test_app_py_uses_visible_for_ui(self) -> None:
        text = (SRC / "web" / "app.py").read_text(encoding="utf-8")
        self.assertIn("visible_for_ui", text)

    def test_js_fetches_api_engines_not_hardcoded_array(self) -> None:
        blob = _frontend_blob()
        self.assertTrue(blob.strip(), "vue source or built static js missing")
        self.assertTrue(
            "/api/engines" in blob,
            "frontend must fetch engines from API (dropdown)",
        )
        self.assertIn("/api/engines/gallery", blob)
        self.assertIn("form_schema", blob)
        compact = re.sub(r"\s+", "", blob)
        self.assertNotIn('["postgres","mysql"]', compact)
        self.assertNotIn("['postgres','mysql']", compact)
        self.assertIsNone(re.search(r"engines\s*=\s*\[\s*['\"]postgres['\"]", blob))

    def test_post_connection_writes_json_connection_store_can_read(self) -> None:
        body = {
            "id": "src1",
            "name": "订单库",
            "engine": "postgres",
            "config": {
                "host": "127.0.0.1",
                "port": 5432,
                "dbname": "app",
                "user": "u",
                "password": "s3cret",
            },
        }
        resp = self.client.post("/api/connections", json=body)
        self.assertEqual(resp.status_code, 200)
        cid = resp.json()["id"]
        self.assertEqual(cid, "src1")
        store = ConnectionStore(self.tmp_path)
        got = store.get(cid)
        self.assertIsNotNone(got)
        self.assertEqual(got.name, "订单库")
        self.assertEqual(got.engine, "postgres")
        self.assertEqual(got.config["password"], "s3cret")
        sources = self.tmp_path / "sources.json"
        per_file = self.tmp_path / "connections" / f"{cid}.json"
        self.assertTrue(sources.is_file() or per_file.is_file())

    def test_get_engines_gallery_includes_dameng_disabled(self) -> None:
        resp = self.client.get("/api/engines/gallery")
        self.assertEqual(resp.status_code, 200)
        rows = _engine_rows(resp.json())
        by_id = {row["id"]: row for row in rows}
        self.assertIn("postgres", by_id)
        self.assertIn("mysql", by_id)
        self.assertIn("dameng", by_id)
        self.assertFalse(by_id["dameng"]["visible"])
        required = {"id", "label", "family", "visible", "form_schema"}
        for row in rows:
            self.assertTrue(required.issubset(row.keys()), row)
        dropdown = [row["id"] for row in _engine_rows(self.client.get("/api/engines").json())]
        self.assertNotIn("dameng", dropdown)

    def test_index_html_served(self) -> None:
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("配置台", resp.text)
        self.assertTrue(
            "/static/" in resp.text or "app.js" in resp.text,
            "index should reference built static assets",
        )


if __name__ == "__main__":
    unittest.main()

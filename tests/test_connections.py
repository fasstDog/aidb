"""连接存储与 list_sources 不含密钥。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aidb.errors import SOURCE_NOT_FOUND, AidbError
from aidb.models.connection import Connection
from aidb.store.connections import ConnectionStore


def _conn(**kwargs) -> Connection:
    data = {
        "id": "src1",
        "name": "订单库",
        "kind": "relational",
        "engine": "fake",
        "family": "postgres",
        "config": {"password": "s3cret-token-xyz", "host": "db.internal"},
    }
    data.update(kwargs)
    return Connection.model_validate(data)


class TestConnectionStore(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.store = ConnectionStore(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_crud_roundtrip_keeps_config_on_disk(self) -> None:
        self.store.put(_conn())
        got = self.store.get("src1")
        assert got is not None
        self.assertEqual(got.config["password"], "s3cret-token-xyz")
        on_disk = json.loads((self.root / "sources.json").read_text(encoding="utf-8"))
        self.assertIn("sources", on_disk)
        on_disk = next(s for s in on_disk["sources"] if s["id"] == "src1")
        self.assertEqual(on_disk["config"]["password"], "s3cret-token-xyz")
        self.store.put(_conn(name="改名"))
        self.assertEqual(self.store.get("src1").name, "改名")
        self.assertTrue(self.store.delete("src1"))
        self.assertIsNone(self.store.get("src1"))

    def test_list_sources_never_includes_config_or_password(self) -> None:
        self.store.put(_conn())
        meta = self.store.public_meta()
        blob = json.dumps(meta)
        self.assertNotIn("s3cret-token-xyz", blob)
        self.assertNotIn("password", blob)
        self.assertNotIn("config", blob)
        self.assertNotIn("db.internal", blob)
        self.assertEqual(meta[0]["id"], "src1")
        self.assertEqual(meta[0]["name"], "订单库")
        self.assertEqual(meta[0]["kind"], "relational")
        self.assertEqual(meta[0]["engine"], "fake")
        self.assertEqual(meta[0]["family"], "postgres")

    def test_require_missing(self) -> None:
        with self.assertRaises(AidbError) as ctx:
            self.store.require("nope")
        self.assertEqual(ctx.exception.code, SOURCE_NOT_FOUND)

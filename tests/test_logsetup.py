"""0.2 日志：JSON 行、MCP 三次调用、只读拒绝、脱敏。"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import unittest
from pathlib import Path

from aidb.errors import NOT_READONLY, AidbError
from aidb.logsetup import (
    LOGGER_NAME,
    configure_logging,
    log_event,
    log_path,
)
from aidb.models.connection import Connection
from aidb.runtime import build_runtime
from tests.fakes import FakeAdapter, ensure_fake_adapter

_SECRET = "s3cret-token-xyz"


def _rel(source_id: str = "src1") -> Connection:
    return Connection(
        id=source_id,
        name="订单库",
        kind="relational",
        engine="fake",
        family="postgres",
        config={"password": _SECRET, "host": "db.internal", "dsn": "postgres://u:p@db/app"},
    )


class TestLogsetup(unittest.TestCase):
    def setUp(self) -> None:
        ensure_fake_adapter()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._old_data = os.environ.get("AIDB_DATA")
        os.environ["AIDB_DATA"] = str(self.root)
        configure_logging(data_root=self.root, force=True)

    def tearDown(self) -> None:
        import aidb.logsetup as logsetup

        logger = logging.getLogger(LOGGER_NAME)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            if isinstance(handler, logging.FileHandler):
                try:
                    handler.close()
                except OSError:
                    pass
        logsetup._configured_root = None
        if self._old_data is None:
            os.environ.pop("AIDB_DATA", None)
        else:
            os.environ["AIDB_DATA"] = self._old_data
        self._tmp.cleanup()

    def _flush(self) -> None:
        for handler in logging.getLogger(LOGGER_NAME).handlers:
            handler.flush()

    def _log_text(self) -> str:
        self._flush()
        path = log_path(self.root)
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    def _log_objs(self) -> list[dict]:
        text = self._log_text()
        objs = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            objs.append(json.loads(line))
        return objs

    def test_configure_logging_writes_json_lines(self) -> None:
        log_event("process_start", version="0.1.0", bind="127.0.0.1", port=8787)
        path = log_path(self.root)
        self.assertTrue(path.is_file(), path)
        objs = self._log_objs()
        self.assertGreaterEqual(len(objs), 1)
        last = objs[-1]
        self.assertEqual(last.get("event"), "process_start")
        self.assertEqual(last.get("message"), "process_start")
        self.assertEqual(last.get("version"), "0.1.0")
        self.assertEqual(last.get("bind"), "127.0.0.1")
        self.assertEqual(last.get("port"), 8787)
        self.assertIn("asctime", last)
        self.assertIn("levelname", last)
        self.assertEqual(last.get("name"), LOGGER_NAME)

    def test_configure_logging_idempotent(self) -> None:
        logger = configure_logging(data_root=self.root)
        n = len(logger.handlers)
        configure_logging(data_root=self.root)
        self.assertEqual(len(logging.getLogger(LOGGER_NAME).handlers), n)
        self.assertEqual(n, 2)  # stderr + rotating file

    def test_mcp_tools_emit_events(self) -> None:
        svc = build_runtime(self.root, load=True)
        svc.connections.put(_rel())
        svc.list_sources()
        svc.search_catalog("src1", limit=2)
        svc.execute_readonly("src1", "sql", "SELECT 1")
        text = self._log_text()
        self.assertIn("list_sources", text)
        self.assertIn("search_catalog", text)
        self.assertIn("execute_readonly", text)
        events = {obj.get("event") for obj in self._log_objs()}
        self.assertIn("list_sources", events)
        self.assertIn("search_catalog", events)
        self.assertIn("execute_readonly", events)

    def test_readonly_rejected_does_not_dump_secrets(self) -> None:
        adapter = FakeAdapter()
        self.assertFalse(adapter.is_readonly("DELETE FROM orders WHERE password='hunter2-not-readonly'"))
        svc = build_runtime(self.root, load=True)
        svc.connections.put(_rel())
        with self.assertRaises(AidbError) as ctx:
            svc.execute_readonly(
                "src1",
                "sql",
                "DELETE FROM orders WHERE password='hunter2-not-readonly'",
            )
        self.assertEqual(ctx.exception.code, NOT_READONLY)
        text = self._log_text()
        self.assertIn("readonly_rejected", text)
        self.assertNotIn(_SECRET, text)
        self.assertNotIn("hunter2-not-readonly", text)
        self.assertNotIn("db.internal", text)
        self.assertNotIn("postgres://u:p@db/app", text)
        for obj in self._log_objs():
            self.assertNotIn("password", obj)
            self.assertNotIn("dsn", obj)
            self.assertNotIn("config", obj)
            self.assertNotIn("statement", obj)
            blob = json.dumps(obj, ensure_ascii=False)
            self.assertNotIn(_SECRET, blob)
            self.assertNotIn("hunter2-not-readonly", blob)

    def test_redact_filter_drops_secret_extras(self) -> None:
        logging.getLogger(LOGGER_NAME).info(
            "leak_attempt password=should-not-stick",
            extra={
                "password": "hunter2",
                "dsn": "postgres://u:p@h/db",
                "config": {"password": "x", "host": "h"},
                "source_id": "src1",
            },
        )
        text = self._log_text()
        self.assertNotIn("hunter2", text)
        self.assertNotIn("postgres://u:p@h/db", text)
        self.assertNotIn("should-not-stick", text)
        log_event(
            "leak_attempt",
            password="hunter2",
            dsn="postgres://u:p@h/db",
            config={"password": "x"},
            statement="SELECT password FROM t",
            source_id="src1",
        )
        text = self._log_text()
        self.assertNotIn("hunter2", text)
        self.assertNotIn("SELECT password FROM t", text)
        objs = [o for o in self._log_objs() if o.get("event") == "leak_attempt" or o.get("source_id") == "src1"]
        self.assertTrue(objs)
        for obj in objs:
            self.assertNotIn("password", obj)
            self.assertNotIn("dsn", obj)
            self.assertNotIn("config", obj)
            self.assertNotIn("statement", obj)

    def test_ping_path_logs_source_meta(self) -> None:
        from fastapi.testclient import TestClient

        from aidb.web.app import create_app

        app = create_app(self.root)
        app.state.ctx.connections.put(_rel())
        client = TestClient(app)
        resp = client.post("/api/connections/src1/ping")
        self.assertEqual(resp.status_code, 200, resp.text)
        events = {o.get("event") for o in self._log_objs()}
        self.assertIn("connect", events, self._log_text())
        objs = [o for o in self._log_objs() if o.get("event") == "ping"]
        self.assertTrue(objs, self._log_text())
        ping = objs[-1]
        self.assertEqual(ping.get("source_id"), "src1")
        self.assertEqual(ping.get("kind"), "relational")
        self.assertEqual(ping.get("engine"), "fake")
        self.assertTrue(ping.get("ok"))
        text = self._log_text()
        self.assertNotIn(_SECRET, text)
        self.assertNotIn("db.internal", text)


if __name__ == "__main__":
    unittest.main()

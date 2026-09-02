"""engine_error details 只带 kind（连不上/超时/语法），不含语句和密码。"""

from __future__ import annotations

import unittest

from aidb.engines import get, load_engines
from aidb.engines._readonly import engine_error
from aidb.errors import AidbError


class TestEngineErrorKind(unittest.TestCase):
    def _assert_clean(self, err: AidbError, *secrets: str) -> None:
        blob = f"{err.code} {err.message} {err.details}"
        for secret in secrets:
            self.assertNotIn(secret, blob)
        self.assertNotIn("password=", blob.lower())
        self.assertEqual(set(err.details), {"engine", "kind", "op"})

    def test_connect_kind_no_leak(self) -> None:
        secret = "s3cret-dsn://user:hunter2@127.0.0.1/db"
        exc = ConnectionRefusedError(f"could not connect {secret} password=hunter2")
        err = engine_error("postgres", "连接", exc)
        self.assertEqual(err.code, "engine_error")
        self.assertEqual(err.details["kind"], "connect")
        self.assertEqual(err.message, "连不上")
        self._assert_clean(err, secret, "hunter2")

    def test_timeout_kind_no_leak(self) -> None:
        secret = "SELECT password FROM t WHERE token=s3cret"
        exc = TimeoutError(f"canceling statement due to statement timeout: {secret}")
        err = engine_error("postgres", "执行查询", exc)
        self.assertEqual(err.details["kind"], "timeout")
        self.assertEqual(err.message, "超时")
        self._assert_clean(err, secret)

    def test_syntax_kind_mysql_errno(self) -> None:
        secret = "SELECT * FROM users WHERE password='hunter2'"
        exc = type("ProgrammingError", (Exception,), {})(1064, secret)
        err = engine_error("mysql", "执行查询", exc)
        self.assertEqual(err.details["kind"], "syntax")
        self.assertEqual(err.message, "语法错误")
        self._assert_clean(err, secret, "hunter2")

    def test_mysql_cant_connect_errno(self) -> None:
        secret = "Can't connect to MySQL server on 'prod.internal' (password=hunter2)"
        exc = type("OperationalError", (Exception,), {})(2003, secret)
        err = engine_error("mysql", "连接", exc)
        self.assertEqual(err.details["kind"], "connect")
        self._assert_clean(err, "hunter2", "prod.internal")

    def test_pg_query_canceled_pgcode(self) -> None:
        exc = type("QueryCanceled", (Exception,), {"pgcode": "57014"})(
            "SELECT secret FROM x"
        )
        err = engine_error("postgres", "执行查询", exc)
        self.assertEqual(err.details["kind"], "timeout")
        self._assert_clean(err, "SELECT secret")

    def test_execute_readonly_maps_syntax(self) -> None:
        load_engines()
        pg = get("postgres")

        class Boom:
            def execute(self, *args, **kwargs):
                raise type("ProgrammingError", (Exception,), {})(
                    'syntax error at or near "SELEC" password=hunter2'
                )

        with self.assertRaises(AidbError) as ctx:
            pg.execute_readonly(Boom(), "SELECT 1", timeout_s=1, max_rows=10)
        self.assertEqual(ctx.exception.code, "engine_error")
        self.assertEqual(ctx.exception.details["kind"], "syntax")
        self.assertNotIn("hunter2", str(ctx.exception.details))
        self.assertNotIn("SELECT 1", str(ctx.exception.details))


if __name__ == "__main__":
    unittest.main()

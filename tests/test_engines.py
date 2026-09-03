"""引擎适配器：注册、别名、只读判定、方言片段。不连真实库。"""

from __future__ import annotations

import unittest

from aidb.engines import all_engines, get, load_engines, visible_for_ui
from aidb.errors import ENGINE_NOT_IMPLEMENTED, NOT_READONLY, AidbError
from aidb.models.catalog import QueryResult


class TestEngineRegistration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_engines()

    def test_visible_only_postgres_mysql(self) -> None:
        ids = [a.id for a in visible_for_ui()]
        self.assertEqual(set(ids), {"postgres", "mysql"})
        self.assertNotIn("dameng", ids)

    def test_all_engines_includes_hidden_placeholders(self) -> None:
        ids = [a.id for a in all_engines()]
        self.assertIn("postgres", ids)
        self.assertIn("mysql", ids)
        # CONTRACT 必含占位（画廊墙），不可选
        for engine_id in (
            "dameng",
            "oracle",
            "sqlite",
            "clickhouse",
            "doris",
            "duckdb",
            "gaussdb",
            "hive",
            "mssql",
            "oceanbase",
            "starrocks",
            "mongodb",
            "redis",
            "neo4j",
        ):
            self.assertIn(engine_id, ids)
            self.assertFalse(get(engine_id).ui.visible)
        self.assertNotIn("elasticsearch", ids)

    def test_aliases(self) -> None:
        self.assertEqual(get("postgresql").id, "postgres")
        self.assertEqual(get("pg").id, "postgres")
        self.assertEqual(get("mariadb").id, "mysql")
        self.assertEqual(get("tidb").id, "mysql")
        self.assertEqual(get("dm").id, "dameng")

    def test_dameng_is_placeholder(self) -> None:
        dm = get("dameng")
        self.assertFalse(dm.ui.visible)
        self.assertEqual(dm.family, "oracle_like")
        with self.assertRaises(AidbError) as ctx:
            dm.connect({})
        self.assertEqual(ctx.exception.code, ENGINE_NOT_IMPLEMENTED)

    def test_form_schema_declared(self) -> None:
        pg_keys = [f.key for f in get("postgres").form_schema.fields]
        my_keys = [f.key for f in get("mysql").form_schema.fields]
        self.assertIn("host", pg_keys)
        self.assertIn("dbname", pg_keys)
        self.assertIn("database", my_keys)
        self.assertTrue(any(f.secret for f in get("postgres").form_schema.fields))
        self.assertTrue(any(f.secret for f in get("mysql").form_schema.fields))


class TestDialectHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_engines()
        cls.pg = get("postgres")
        cls.my = get("mysql")

    def test_quote_ident(self) -> None:
        self.assertEqual(self.pg.quote_ident("Foo"), '"Foo"')
        self.assertEqual(self.pg.quote_ident('a"b'), '"a""b"')
        self.assertEqual(self.my.quote_ident("Foo"), "`Foo`")
        self.assertEqual(self.my.quote_ident("a`b"), "`a``b`")

    def test_limit_clause(self) -> None:
        self.assertEqual(self.pg.limit_clause(10), "LIMIT 10")
        self.assertEqual(self.my.limit_clause(3), "LIMIT 3")

    def test_dialect_prompt(self) -> None:
        for adapter in (self.pg, self.my):
            text = adapter.dialect_prompt()
            self.assertIn("LIMIT", text)
            self.assertTrue("日期" in text or "时间" in text)

    def test_sample_values_default_off(self) -> None:
        self.assertEqual(
            self.pg.sample_values(None, "s", "t", "c", enabled=False),
            [],
        )
        self.assertEqual(
            self.my.sample_values(None, "s", "t", "c"),
            [],
        )


class TestReadonly(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_engines()
        cls.pg = get("postgres")
        cls.my = get("mysql")

    def test_select_ok(self) -> None:
        for adapter in (self.pg, self.my):
            self.assertTrue(adapter.is_readonly("SELECT 1"))
            self.assertTrue(adapter.is_readonly("SELECT * FROM t WHERE id = 1"))
            self.assertTrue(
                adapter.is_readonly("WITH c AS (SELECT 1 AS x) SELECT * FROM c")
            )
            self.assertTrue(
                adapter.is_readonly("SELECT a FROM t UNION SELECT b FROM u")
            )

    def test_writes_rejected(self) -> None:
        for adapter in (self.pg, self.my):
            self.assertFalse(adapter.is_readonly("INSERT INTO t VALUES (1)"))
            self.assertFalse(adapter.is_readonly("UPDATE t SET a = 1"))
            self.assertFalse(adapter.is_readonly("DELETE FROM t"))
            self.assertFalse(adapter.is_readonly("DROP TABLE t"))
            self.assertFalse(adapter.is_readonly("CREATE TABLE t (id int)"))
            self.assertFalse(adapter.is_readonly("ALTER TABLE t ADD COLUMN x int"))
            self.assertFalse(adapter.is_readonly("SELECT 1; DROP TABLE t"))
            self.assertFalse(adapter.is_readonly(""))
            self.assertFalse(adapter.is_readonly("SET extra_float_digits = 3"))

    def test_for_update_rejected(self) -> None:
        self.assertFalse(self.pg.is_readonly("SELECT * FROM t FOR UPDATE"))

    def test_execute_readonly_rejects_write_without_db(self) -> None:
        with self.assertRaises(AidbError) as ctx:
            self.pg.execute_readonly(
                None, "DELETE FROM t", timeout_s=1, max_rows=10
            )
        self.assertEqual(ctx.exception.code, NOT_READONLY)

    def test_pg_statement_timeout_uses_literal_not_bind(self) -> None:
        """Postgres SET 不接受 $1；超时必须写成整字面量。"""

        class Col:
            def __init__(self, name: str) -> None:
                self.name = name

        class FakeCursor:
            description = (Col("n"),)

            def fetchmany(self, size):
                return [(1,)]

        class FakeConn:
            def __init__(self) -> None:
                self.calls: list[tuple] = []

            def execute(self, sql, params=None):
                self.calls.append((sql, params))
                if str(sql).startswith("SET "):
                    return self
                return FakeCursor()

        conn = FakeConn()
        result = self.pg.execute_readonly(
            conn, "SELECT 1 AS n", timeout_s=2.5, max_rows=10
        )
        self.assertEqual(result.rows, [[1]])
        self.assertEqual(len(conn.calls), 2)
        set_sql, set_params = conn.calls[0]
        self.assertEqual(set_sql, "SET statement_timeout = 2500")
        self.assertIsNone(set_params)
        self.assertEqual(conn.calls[1], ("SELECT 1 AS n", None))


class TestQueryResultShape(unittest.TestCase):
    def test_query_result_fields(self) -> None:
        qr = QueryResult(
            columns=["id"], rows=[[1]], truncated=False, row_count_capped=1
        )
        self.assertEqual(qr.columns, ["id"])


if __name__ == "__main__":
    unittest.main()

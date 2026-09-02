"""PostgreSQL 引擎适配器。驱动与 sqlglot 只出现在本文件及其适配器辅助模块。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from aidb.engines._readonly import engine_error, is_readonly_sql, jsonable_cell
from aidb.engines.base import EngineAdapter, EngineLabels, FormField, FormSchema, UiMeta
from aidb.engines.registry import register
from aidb.errors import NOT_READONLY, AidbError
from aidb.models.catalog import Column, QueryResult

_SYSTEM_SCHEMAS = frozenset({"pg_catalog", "information_schema", "pg_toast"})


class PostgresAdapter(EngineAdapter):
    id = "postgres"
    aliases: Sequence[str] = ("postgresql", "pg")
    family = "postgres"
    ui = UiMeta(visible=True)
    labels = EngineLabels(namespace="schema", collection="表", field="列")
    form_schema = FormSchema(
        fields=[
            FormField(key="host", label="主机", type="string", required=True, default="127.0.0.1"),
            FormField(key="port", label="端口", type="int", required=False, default=5432),
            FormField(key="dbname", label="数据库", type="string", required=True),
            FormField(key="user", label="用户", type="string", required=True),
            FormField(key="password", label="密码", type="password", required=False, secret=True),
            FormField(key="sslmode", label="SSL 模式", type="string", required=False, default="prefer"),
        ]
    )

    def connect(self, config: Mapping[str, Any]) -> Any:
        try:
            import psycopg
        except ImportError as exc:
            raise AidbError("engine_error", "缺少 psycopg 驱动", {"engine": self.id}) from exc
        try:
            dsn = config.get("dsn")
            if dsn:
                conn = psycopg.connect(str(dsn), autocommit=True)
            else:
                dbname = config.get("dbname") or config.get("database")
                if not dbname:
                    raise AidbError(
                        "invalid_config",
                        "缺少连接配置",
                        {"engine": self.id, "field": "dbname"},
                    )
                kwargs: dict[str, Any] = {
                    "host": config.get("host", "127.0.0.1"),
                    "port": int(config.get("port", 5432)),
                    "dbname": dbname,
                    "user": config.get("user"),
                    "password": config.get("password"),
                    "autocommit": True,
                }
                if config.get("sslmode"):
                    kwargs["sslmode"] = config["sslmode"]
                conn = psycopg.connect(**kwargs)
            return conn
        except AidbError:
            raise
        except Exception as exc:
            raise engine_error(self.id, "连接") from exc

    def ping(self, handle: Any) -> None:
        try:
            handle.execute("SELECT 1")
        except Exception as exc:
            raise engine_error(self.id, "探活") from exc

    def list_schemas(self, handle: Any) -> list[str]:
        sql = """
            SELECT nspname
            FROM pg_catalog.pg_namespace
            WHERE nspname <> ALL(%s)
              AND nspname NOT LIKE 'pg_temp%%'
              AND nspname NOT LIKE 'pg_toast_temp%%'
            ORDER BY 1
        """
        try:
            rows = handle.execute(sql, (list(_SYSTEM_SCHEMAS),)).fetchall()
            return [r[0] for r in rows]
        except Exception as exc:
            raise engine_error(self.id, "列出 schema") from exc

    def list_tables(self, handle: Any, schema: str) -> list[str]:
        sql = """
            SELECT c.relname
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s
              AND c.relkind IN ('r', 'p', 'v', 'm')
              AND NOT c.relispartition
            ORDER BY 1
        """
        try:
            rows = handle.execute(sql, (schema,)).fetchall()
            return [r[0] for r in rows]
        except Exception as exc:
            raise engine_error(self.id, "列出表") from exc

    def list_columns(self, handle: Any, schema: str, table: str) -> list[Column]:
        sql = """
            SELECT a.attname,
                   pg_catalog.format_type(a.atttypid, a.atttypmod),
                   pg_catalog.col_description(a.attrelid, a.attnum)
            FROM pg_catalog.pg_attribute a
            JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s
              AND c.relname = %s
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY a.attnum
        """
        try:
            rows = handle.execute(sql, (schema, table)).fetchall()
            return [Column(name=r[0], type=str(r[1]), comment=r[2]) for r in rows]
        except Exception as exc:
            raise engine_error(self.id, "列出列") from exc

    def list_fks(self, handle: Any, schema: str, table: str) -> list[dict[str, Any]]:
        sql = """
            SELECT con.conname,
                   att.attname,
                   nsp_ref.nspname,
                   rel_ref.relname,
                   att_ref.attname
            FROM pg_catalog.pg_constraint con
            JOIN pg_catalog.pg_class rel ON rel.oid = con.conrelid
            JOIN pg_catalog.pg_namespace nsp ON nsp.oid = rel.relnamespace
            JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS src(attnum, ord) ON TRUE
            JOIN pg_catalog.pg_attribute att
              ON att.attrelid = rel.oid AND att.attnum = src.attnum
            JOIN pg_catalog.pg_class rel_ref ON rel_ref.oid = con.confrelid
            JOIN pg_catalog.pg_namespace nsp_ref ON nsp_ref.oid = rel_ref.relnamespace
            JOIN LATERAL unnest(con.confkey) WITH ORDINALITY AS dst(attnum, ord)
              ON dst.ord = src.ord
            JOIN pg_catalog.pg_attribute att_ref
              ON att_ref.attrelid = rel_ref.oid AND att_ref.attnum = dst.attnum
            WHERE con.contype = 'f'
              AND nsp.nspname = %s
              AND rel.relname = %s
            ORDER BY con.conname, src.ord
        """
        try:
            rows = handle.execute(sql, (schema, table)).fetchall()
            return [
                {
                    "name": r[0],
                    "column": r[1],
                    "ref_namespace": r[2],
                    "ref_collection": r[3],
                    "ref_column": r[4],
                }
                for r in rows
            ]
        except Exception as exc:
            raise engine_error(self.id, "列出外键") from exc

    def sample_values(
        self,
        handle: Any,
        schema: str,
        table: str,
        column: str,
        *,
        enabled: bool = False,
        limit: int = 5,
    ) -> list[Any]:
        if not enabled:
            return []
        n = max(0, min(int(limit), 20))
        q = (
            f"SELECT DISTINCT {self.quote_ident(column)} "
            f"FROM {self.quote_ident(schema)}.{self.quote_ident(table)} "
            f"WHERE {self.quote_ident(column)} IS NOT NULL "
            f"{self.limit_clause(n)}"
        )
        try:
            rows = handle.execute(q).fetchall()
            return [jsonable_cell(r[0], max_len=64) for r in rows]
        except Exception as exc:
            raise engine_error(self.id, "采样") from exc

    def quote_ident(self, name: str) -> str:
        if not name or "\x00" in name:
            raise AidbError("invalid_ident", "非法标识符", {"engine": self.id})
        return '"' + name.replace('"', '""') + '"'

    def dialect_prompt(self) -> str:
        return (
            "PostgreSQL 方言："
            "标识符用双引号，未引用时折叠为小写；"
            "分页用 LIMIT n OFFSET m；"
            "字符串比较默认大小写敏感，不区分大小写用 ILIKE；"
            "日期时间用 timestamptz/timestamp/date，函数 NOW()/CURRENT_DATE，格式化 to_char；"
            "用 schema.table 限定对象，默认搜索路径含 public；"
            "布尔值为 true/false。"
        )

    def limit_clause(self, n: int) -> str:
        return f"LIMIT {max(0, int(n))}"

    def is_readonly(self, sql: str) -> bool:
        return is_readonly_sql(sql, "postgres")

    def execute_readonly(
        self,
        handle: Any,
        sql: str,
        *,
        timeout_s: float,
        max_rows: int,
    ) -> QueryResult:
        if not self.is_readonly(sql):
            raise AidbError(NOT_READONLY, "语句不是只读查询", {"engine": self.id})
        cap = max(0, int(max_rows))
        try:
            ms = max(1, int(float(timeout_s) * 1000))
            handle.execute("SET statement_timeout = %s", (ms,))
            cur = handle.execute(sql)
            columns = [d.name for d in cur.description] if cur.description else []
            fetched = cur.fetchmany(cap + 1) if cap else []
            truncated = len(fetched) > cap
            rows = fetched[:cap]
            return QueryResult(
                columns=columns,
                rows=[[jsonable_cell(c) for c in row] for row in rows],
                truncated=truncated,
                row_count_capped=len(rows),
            )
        except AidbError:
            raise
        except Exception as exc:
            raise engine_error(self.id, "执行查询") from exc

    def close(self, handle: Any) -> None:
        try:
            handle.close()
        except Exception:
            pass


register(PostgresAdapter())

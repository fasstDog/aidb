"""MySQL 引擎适配器。MariaDB / TiDB 通过 aliases 复用，不另开引擎。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import unquote, urlparse

from aidb.engines._readonly import engine_error, is_readonly_sql, jsonable_cell
from aidb.engines.base import EngineAdapter, EngineLabels, FormField, FormSchema, UiMeta
from aidb.engines.registry import register
from aidb.errors import NOT_READONLY, AidbError
from aidb.models.catalog import Column, QueryResult

_SYSTEM_SCHEMAS = frozenset(
    {"information_schema", "performance_schema", "mysql", "sys"}
)


class MysqlAdapter(EngineAdapter):
    id = "mysql"
    aliases: Sequence[str] = ("mariadb", "tidb")
    family = "mysql"
    ui = UiMeta(visible=True)
    labels = EngineLabels(namespace="数据库", collection="表", field="列")
    form_schema = FormSchema(
        fields=[
            FormField(key="host", label="主机", type="string", required=True, default="127.0.0.1"),
            FormField(key="port", label="端口", type="int", required=False, default=3306),
            FormField(key="database", label="数据库", type="string", required=True),
            FormField(key="user", label="用户", type="string", required=True),
            FormField(key="password", label="密码", type="password", required=False, secret=True),
            FormField(key="charset", label="字符集", type="string", required=False, default="utf8mb4"),
        ]
    )

    def _connect_kwargs(self, config: Mapping[str, Any]) -> dict[str, Any]:
        dsn = config.get("dsn")
        if dsn and "://" in str(dsn):
            parsed = urlparse(str(dsn))
            database = unquote(parsed.path.lstrip("/"))
            return {
                "host": parsed.hostname or "127.0.0.1",
                "port": parsed.port or 3306,
                "user": unquote(parsed.username or ""),
                "password": unquote(parsed.password or ""),
                "database": database or None,
                "charset": config.get("charset", "utf8mb4"),
            }
        database = config.get("database") or config.get("dbname")
        if not database:
            raise AidbError(
                "invalid_config",
                "缺少连接配置",
                {"engine": self.id, "field": "database"},
            )
        return {
            "host": config.get("host", "127.0.0.1"),
            "port": int(config.get("port", 3306)),
            "user": config.get("user"),
            "password": config.get("password") or "",
            "database": database,
            "charset": config.get("charset", "utf8mb4"),
        }

    def connect(self, config: Mapping[str, Any]) -> Any:
        try:
            import pymysql
        except ImportError as exc:
            raise AidbError("engine_error", "缺少 PyMySQL 驱动", {"engine": self.id}) from exc
        try:
            kwargs = self._connect_kwargs(config)
            kwargs.update(
                {
                    "autocommit": True,
                    "connect_timeout": 10,
                    "cursorclass": pymysql.cursors.Cursor,
                }
            )
            return pymysql.connect(**kwargs)
        except AidbError:
            raise
        except Exception as exc:
            raise engine_error(self.id, "连接", exc) from exc

    def ping(self, handle: Any) -> None:
        try:
            handle.ping(reconnect=True)
        except Exception as exc:
            raise engine_error(self.id, "探活", exc) from exc

    def _fetch(
        self,
        handle: Any,
        sql: str,
        params: tuple[Any, ...] | list[Any] = (),
    ) -> list[tuple[Any, ...]]:
        with handle.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def list_schemas(self, handle: Any) -> list[str]:
        sql = """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN (%s, %s, %s, %s)
            ORDER BY 1
        """
        try:
            rows = self._fetch(handle, sql, tuple(_SYSTEM_SCHEMAS))
            return [r[0] for r in rows]
        except Exception as exc:
            raise engine_error(self.id, "列出数据库", exc) from exc

    def list_tables(self, handle: Any, schema: str) -> list[str]:
        sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type IN ('BASE TABLE', 'VIEW')
            ORDER BY 1
        """
        try:
            rows = self._fetch(handle, sql, (schema,))
            return [r[0] for r in rows]
        except Exception as exc:
            raise engine_error(self.id, "列出表", exc) from exc

    def list_columns(self, handle: Any, schema: str, table: str) -> list[Column]:
        sql = """
            SELECT column_name, column_type, column_comment
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        try:
            rows = self._fetch(handle, sql, (schema, table))
            return [
                Column(name=r[0], type=str(r[1]), comment=(r[2] or None))
                for r in rows
            ]
        except Exception as exc:
            raise engine_error(self.id, "列出列", exc) from exc

    def list_fks(self, handle: Any, schema: str, table: str) -> list[dict[str, Any]]:
        sql = """
            SELECT constraint_name,
                   column_name,
                   referenced_table_schema,
                   referenced_table_name,
                   referenced_column_name
            FROM information_schema.key_column_usage
            WHERE table_schema = %s
              AND table_name = %s
              AND referenced_table_name IS NOT NULL
            ORDER BY constraint_name, ordinal_position
        """
        try:
            rows = self._fetch(handle, sql, (schema, table))
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
            raise engine_error(self.id, "列出外键", exc) from exc

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
            rows = self._fetch(handle, q)
            return [jsonable_cell(r[0], max_len=64) for r in rows]
        except Exception as exc:
            raise engine_error(self.id, "采样", exc) from exc

    def quote_ident(self, name: str) -> str:
        if not name or "\x00" in name:
            raise AidbError("invalid_ident", "非法标识符", {"engine": self.id})
        return "`" + name.replace("`", "``") + "`"

    def dialect_prompt(self) -> str:
        return (
            "MySQL 方言（MariaDB / TiDB 同此）："
            "标识符用反引号；"
            "分页用 LIMIT n OFFSET m；"
            "字符串比较默认不区分大小写（取决于 collation，常见 utf8mb4_unicode_ci）；"
            "日期时间用 DATETIME/DATE/TIMESTAMP，函数 NOW()/CURDATE()；"
            "namespace 即 database，用 database.table 限定对象；"
            "布尔值为 0/1。"
        )

    def limit_clause(self, n: int) -> str:
        return f"LIMIT {max(0, int(n))}"

    def is_readonly(self, sql: str) -> bool:
        return is_readonly_sql(sql, "mysql")

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
        ms = max(1, int(float(timeout_s) * 1000))
        try:
            with handle.cursor() as cur:
                try:
                    cur.execute("SET SESSION MAX_EXECUTION_TIME = %s", (ms,))
                except Exception:
                    try:
                        cur.execute(
                            "SET SESSION max_statement_time = %s",
                            (float(timeout_s),),
                        )
                    except Exception:
                        pass
                cur.execute(sql)
                columns = [d[0] for d in cur.description] if cur.description else []
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
            raise engine_error(self.id, "执行查询", exc) from exc

    def close(self, handle: Any) -> None:
        try:
            handle.close()
        except Exception:
            pass


register(MysqlAdapter())

"""测试用假适配器 / 假后端。不连真实数据库。"""

from __future__ import annotations

from typing import Any, Mapping

from aidb.engines.base import EngineAdapter, EngineLabels, FormSchema, UiMeta
from aidb.engines.registry import get as get_engine
from aidb.engines.registry import register
from aidb.errors import ENGINE_NOT_IMPLEMENTED, AidbError
from aidb.models.catalog import Column, QueryResult


class FakeAdapter(EngineAdapter):
    id = "fake"
    aliases = ("fake_pg",)
    family = "postgres"
    ui = UiMeta(visible=False)
    form_schema = FormSchema()
    labels = EngineLabels(namespace="schema", collection="表", field="列")

    def connect(self, config: Mapping[str, Any]) -> Any:
        return {"config": dict(config)}

    def ping(self, handle: Any) -> None:
        return None

    def list_schemas(self, handle: Any) -> list[str]:
        return ["public", "other", "analytics"]

    def list_tables(self, handle: Any, schema: str) -> list[str]:
        if schema == "public":
            return ["orders", "users", "items", "payments"]
        if schema == "other":
            return ["hidden"]
        return ["facts"]

    def list_columns(self, handle: Any, schema: str, table: str) -> list[Column]:
        return [
            Column(name="id", type="int", comment="主键"),
            Column(name="name", type="text", comment="名称"),
        ]

    def list_fks(self, handle: Any, schema: str, table: str) -> list[dict[str, Any]]:
        return []

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
        return ["a", "b"] if enabled else []

    def quote_ident(self, name: str) -> str:
        return name

    def dialect_prompt(self) -> str:
        return "pagination: limit n; identifiers: unquoted"

    def limit_clause(self, n: int) -> str:
        return f"limit {n}"

    def is_readonly(self, sql: str) -> bool:
        return sql.strip().casefold().startswith("select")

    def execute_readonly(
        self,
        handle: Any,
        sql: str,
        *,
        timeout_s: float,
        max_rows: int,
    ) -> QueryResult:
        return QueryResult(
            columns=["id"],
            rows=[[1]],
            truncated=False,
            row_count_capped=1,
        )

    def close(self, handle: Any) -> None:
        return None


def ensure_fake_adapter() -> None:
    try:
        get_engine("fake")
    except AidbError as exc:
        if exc.code != ENGINE_NOT_IMPLEMENTED:
            raise
        register(FakeAdapter())

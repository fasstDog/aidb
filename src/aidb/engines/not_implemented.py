"""引擎占位基类。引擎适配用它实例化/子类化 dameng 等尚未落地的引擎。

本模块不注册任何引擎，更不在此实例化 dameng。
"""

from __future__ import annotations

from typing import Any, Mapping, NoReturn, Sequence

from aidb.engines.base import (
    EngineAdapter,
    EngineLabels,
    FormSchema,
    UiMeta,
)
from aidb.errors import ENGINE_NOT_IMPLEMENTED, AidbError
from aidb.models.catalog import Column, QueryResult
from aidb.models.connection import Family


class NotImplementedAdapter(EngineAdapter):
    """所有方法抛 ENGINE_NOT_IMPLEMENTED。默认 ui.visible=False。"""

    def __init__(
        self,
        id: str,
        family: Family,
        aliases: Sequence[str] = (),
        form_schema: FormSchema | None = None,
        labels: EngineLabels | None = None,
        visible: bool = False,
    ) -> None:
        self.id = id
        self.aliases = tuple(aliases)
        self.family = family
        self.ui = UiMeta(visible=visible)
        self.form_schema = form_schema if form_schema is not None else FormSchema()
        self.labels = (
            labels
            if labels is not None
            else EngineLabels(namespace="namespace", collection="collection", field="field")
        )

    def _raise(self) -> NoReturn:
        raise AidbError(
            ENGINE_NOT_IMPLEMENTED,
            "该引擎尚未实现",
            {"engine": self.id},
        )

    def connect(self, config: Mapping[str, Any]) -> Any:
        self._raise()

    def ping(self, handle: Any) -> None:
        self._raise()

    def list_schemas(self, handle: Any) -> list[str]:
        self._raise()

    def list_tables(self, handle: Any, schema: str) -> list[str]:
        self._raise()

    def list_columns(self, handle: Any, schema: str, table: str) -> list[Column]:
        self._raise()

    def list_fks(self, handle: Any, schema: str, table: str) -> list[dict[str, Any]]:
        self._raise()

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
        self._raise()

    def quote_ident(self, name: str) -> str:
        self._raise()

    def dialect_prompt(self) -> str:
        self._raise()

    def limit_clause(self, n: int) -> str:
        self._raise()

    def is_readonly(self, sql: str) -> bool:
        self._raise()

    def execute_readonly(
        self,
        handle: Any,
        sql: str,
        *,
        timeout_s: float,
        max_rows: int,
    ) -> QueryResult:
        self._raise()

    def close(self, handle: Any) -> None:
        self._raise()

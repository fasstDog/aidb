"""注册表空口：未实现 kind 不得落到关系型。"""

from __future__ import annotations

import unittest

from aidb.backends.registry import BackendRegistry
from aidb.engines.base import EngineLabels, FormSchema, UiMeta
from aidb.engines.not_implemented import NotImplementedAdapter
from aidb.engines.registry import EngineRegistry
from aidb.errors import ENGINE_NOT_IMPLEMENTED, KIND_NOT_ENABLED, AidbError
from aidb.models.connection import Connection


class TestBackendRegistry(unittest.TestCase):
    def test_unsupported_kind(self) -> None:
        reg = BackendRegistry.builtin()
        backend = reg.get("document")
        source = Connection(
            id="x",
            name="x",
            kind="document",
            engine="mongodb",
            family="document",
            config={},
        )
        with self.assertRaises(AidbError) as ctx:
            backend.ping(source)
        self.assertEqual(ctx.exception.code, KIND_NOT_ENABLED)
        self.assertIn("该数据源类型尚未启用", ctx.exception.message)

    def test_unknown_kind_does_not_fall_to_sql(self) -> None:
        reg = BackendRegistry.builtin()
        self.assertIsNone(reg._backends.get("relational"))
        backend = reg.get("search")
        source = Connection(
            id="x",
            name="x",
            kind="search",
            engine="elasticsearch",
            family="search",
            config={},
        )
        with self.assertRaises(AidbError) as ctx:
            backend.ping(source)
        self.assertEqual(ctx.exception.code, KIND_NOT_ENABLED)

    def test_graph_kind_is_unsupported(self) -> None:
        reg = BackendRegistry.builtin()
        backend = reg.get("graph")
        source = Connection(
            id="x",
            name="x",
            kind="graph",
            engine="neo4j",
            family="graph",
            config={},
        )
        with self.assertRaises(AidbError) as ctx:
            backend.ping(source)
        self.assertEqual(ctx.exception.code, KIND_NOT_ENABLED)


class TestEngineRegistry(unittest.TestCase):
    def test_visible_empty_until_register(self) -> None:
        reg = EngineRegistry()
        self.assertEqual(reg.visible_for_ui(), [])

    def test_visible_for_ui_hides_dameng_like(self) -> None:
        reg = EngineRegistry()
        hidden = NotImplementedAdapter(
            id="dameng",
            family="oracle_like",
            visible=False,
            labels=EngineLabels(namespace="schema", collection="表", field="列"),
            form_schema=FormSchema(),
        )
        shown = NotImplementedAdapter(
            id="postgres",
            family="postgres",
            visible=True,
            aliases=("pg",),
            labels=EngineLabels(namespace="schema", collection="表", field="列"),
            form_schema=FormSchema(),
        )
        shown.ui = UiMeta(visible=True)
        hidden.ui = UiMeta(visible=False)
        reg.register(hidden)
        reg.register(shown)
        ids = [a.id for a in reg.visible_for_ui()]
        self.assertIn("postgres", ids)
        self.assertNotIn("dameng", ids)
        all_ids = [a.id for a in reg.all_engines()]
        self.assertIn("dameng", all_ids)

    def test_missing_engine(self) -> None:
        reg = EngineRegistry()
        with self.assertRaises(AidbError) as ctx:
            reg.get("oracle")
        self.assertEqual(ctx.exception.code, ENGINE_NOT_IMPLEMENTED)


if __name__ == "__main__":
    unittest.main()

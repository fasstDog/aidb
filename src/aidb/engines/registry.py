"""二级注册表：EngineAdapter by engine id + aliases.

postgres.py / mysql.py / dameng.py 由「引擎适配」拥有，不要在本架构 drop 里添加它们。
配置台下拉必须用 visible_for_ui()，禁止前端写死引擎列表。
all_engines() 含隐藏项（dameng 等），供 schema/enum。
禁止按引擎名分支。
"""

from __future__ import annotations

from aidb.engines.base import EngineAdapter
from aidb.errors import ENGINE_NOT_IMPLEMENTED, AidbError


class EngineRegistry:
    """按 engine 字符串取适配器。缺失 -> ENGINE_NOT_IMPLEMENTED。"""

    def __init__(self) -> None:
        self._by_key: dict[str, EngineAdapter] = {}
        self._adapters: list[EngineAdapter] = []

    def register(self, adapter: EngineAdapter) -> None:
        keys = [adapter.id, *list(adapter.aliases)]
        for raw in keys:
            key = raw.strip().casefold()
            self._by_key[key] = adapter
        existing_ids = {a.id for a in self._adapters}
        if adapter.id not in existing_ids:
            self._adapters.append(adapter)
        else:
            self._adapters = [adapter if a.id == adapter.id else a for a in self._adapters]

    def get(self, engine: str) -> EngineAdapter:
        adapter = self._by_key.get(engine.strip().casefold())
        if adapter is None:
            raise AidbError(
                ENGINE_NOT_IMPLEMENTED,
                "该引擎尚未实现",
                {"engine": engine},
            )
        return adapter

    def visible_for_ui(self) -> list[EngineAdapter]:
        """配置台下拉数据源。只返回 ui.visible=True。"""

        return [a for a in self._adapters if a.ui.visible]

    def all_engines(self) -> list[EngineAdapter]:
        """含不可见引擎，供连接 schema/enum。"""

        return list(self._adapters)


default_registry = EngineRegistry()


def register(adapter: EngineAdapter) -> None:
    default_registry.register(adapter)


def get(engine: str) -> EngineAdapter:
    return default_registry.get(engine)


def visible_for_ui() -> list[EngineAdapter]:
    return default_registry.visible_for_ui()


def all_engines() -> list[EngineAdapter]:
    return default_registry.all_engines()

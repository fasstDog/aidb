"""引擎包。load_engines() 用 glob/importlib 作为扩展点，不写引擎名分支。"""

from __future__ import annotations

import importlib
from pathlib import Path

from aidb.engines.base import (
    EngineAdapter,
    EngineLabels,
    FormField,
    FormSchema,
    UiMeta,
)
from aidb.engines.not_implemented import NotImplementedAdapter
from aidb.engines.registry import (
    EngineRegistry,
    all_engines,
    get,
    register,
    visible_for_ui,
)

_SKIP_MODULES = frozenset({"base", "registry", "not_implemented", "__init__"})


def load_engines() -> None:
    """导入本包内除契约文件外的每一个 *.py，让适配器在 import 时自注册。"""

    pkg_dir = Path(__file__).resolve().parent
    for path in sorted(pkg_dir.glob("*.py")):
        modname = path.stem
        if modname in _SKIP_MODULES or modname.startswith("_"):
            continue
        importlib.import_module(f"{__package__}.{modname}")


__all__ = [
    "EngineAdapter",
    "EngineLabels",
    "EngineRegistry",
    "FormField",
    "FormSchema",
    "NotImplementedAdapter",
    "UiMeta",
    "all_engines",
    "get",
    "load_engines",
    "register",
    "visible_for_ui",
]

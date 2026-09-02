"""Architecture regression gate: dialect/driver/engine-branch must stay out of core."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "aidb"

FORBIDDEN_SUBSTRINGS = (
    "information_schema",
    "pg_catalog",
    "LIMIT {",
)

DRIVER_IMPORTS = frozenset({"psycopg", "pymysql"})
ENGINE_BRANCH = ("if engine ==", "if source.engine ==")


def _iter_core_py() -> list[Path]:
    files: list[Path] = []
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC)
        if rel.parts and rel.parts[0] == "engines":
            continue
        files.append(path)
    return files


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestNoDialectInCore(unittest.TestCase):
    def test_forbidden_dialect_substrings_outside_engines(self) -> None:
        hits: list[str] = []
        for path in _iter_core_py():
            text = _read(path)
            for needle in FORBIDDEN_SUBSTRINGS:
                if needle in text:
                    hits.append(f"{path.relative_to(SRC)}: {needle!r}")
        self.assertEqual(hits, [], "dialect leaked into core:\n" + "\n".join(hits))

    def test_overlay_and_catalog_use_collection_not_table_name_key(self) -> None:
        for rel in ("models/overlay.py", "models/catalog.py"):
            path = SRC / rel
            text = _read(path)
            self.assertIn(
                "collection",
                text,
                f"{rel} must use collection as the generic storage name",
            )
            tree = ast.parse(text)
            bad: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.AnnAssign):
                    target = node.target
                    if isinstance(target, ast.Name) and target.id == "table_name":
                        bad.append(f"AnnAssign table_name at line {node.lineno}")
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and t.id == "table_name":
                            bad.append(f"Assign table_name at line {node.lineno}")
                if isinstance(node, ast.arg) and node.arg == "table_name":
                    bad.append(f"arg table_name at line {node.lineno}")
                if isinstance(node, ast.Constant) and node.value == "table_name":
                    bad.append(f"string key table_name at line {node.lineno}")
            self.assertEqual(bad, [], f"{rel} must not define storage key table_name:\n" + "\n".join(bad))

    def test_backends_and_models_do_not_import_drivers(self) -> None:
        hits: list[str] = []
        for folder in ("backends", "models"):
            for path in (SRC / folder).rglob("*.py"):
                tree = ast.parse(_read(path))
                for node in ast.walk(tree):
                    names: list[str] = []
                    if isinstance(node, ast.Import):
                        names = [a.name.split(".")[0] for a in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        names = [node.module.split(".")[0]]
                    for name in names:
                        if name in DRIVER_IMPORTS:
                            hits.append(f"{path.relative_to(SRC)} imports {name}")
        self.assertEqual(hits, [], "driver import in core:\n" + "\n".join(hits))

    def test_no_engine_name_branch_outside_engines(self) -> None:
        hits: list[str] = []
        for path in _iter_core_py():
            text = _read(path)
            for needle in ENGINE_BRANCH:
                if needle in text:
                    hits.append(f"{path.relative_to(SRC)}: {needle!r}")
        self.assertEqual(hits, [], "engine name branch in core:\n" + "\n".join(hits))



    def test_dto_is_pydantic(self) -> None:
        from pydantic import BaseModel

        from aidb.models.connection import Connection

        src = _read(SRC / "models" / "connection.py")
        self.assertIn("BaseModel", src)
        self.assertIn("from pydantic import", src)
        self.assertTrue(issubclass(Connection, BaseModel))


if __name__ == "__main__":
    unittest.main()

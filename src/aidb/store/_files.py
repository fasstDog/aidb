"""JSON 原子写入。覆盖层版本文件走 append-only，HEAD/连接用原子替换。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def write_json_new(path: Path, data: dict[str, Any]) -> None:
    """Append-only：已存在则不覆盖。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)

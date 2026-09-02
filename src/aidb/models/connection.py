"""数据源连接 DTO。核心不得解析 config 键。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

Kind = Literal["relational", "document", "kv", "search", "graph"]
Family = Literal["mysql", "postgres", "oracle_like", "document", "kv", "search", "graph"]


class Connection(BaseModel):
    """数据源连接。config 对核心不透明，禁止解析其中具体键。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: Kind
    engine: str
    family: Family
    config: dict[str, Any]

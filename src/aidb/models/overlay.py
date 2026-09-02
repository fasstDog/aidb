"""补丁路径与版本 DTO。MCP 核心实现文件存储；本模块仅路径+DTO。

两份 JSON 的 diff 使用标准库 difflib（或 deepdiff），禁止自建版本库。
存储键仅为 source_id / namespace / collection / field。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OverlayRef(BaseModel):
    """覆盖层寻址。field 为空表示集合级；namespace 与 collection 皆空表示源级。"""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    namespace: str | None = None
    collection: str | None = None
    field: str | None = None


class VersionMeta(BaseModel):
    """补丁版本元数据。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    created_at: datetime
    kind: Literal["auto", "named"]
    label: str | None = None
    author: str
    parent_id: str | None = None


class SourceOverlay(BaseModel):
    """数据源级补丁。"""

    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    query_rules: str | None = None


class CollectionOverlay(BaseModel):
    """集合级补丁（含字段注释映射）。"""

    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    fields: dict[str, str] = Field(default_factory=dict)


def source_head_path(source_id: str) -> str:
    """数据源级 HEAD。"""
    return f"overlays/{source_id}/_source/HEAD.json"


def source_version_path(source_id: str, ts: str, version_id: str) -> str:
    """数据源级历史版本。"""
    return f"overlays/{source_id}/_source/versions/{ts}_{version_id}.json"


def collection_head_path(source_id: str, namespace: str, collection: str) -> str:
    """集合级 HEAD。"""
    return f"overlays/{source_id}/{namespace}/{collection}/HEAD.json"


def collection_version_path(
    source_id: str,
    namespace: str,
    collection: str,
    ts: str,
    version_id: str,
) -> str:
    """集合级历史版本。"""
    return f"overlays/{source_id}/{namespace}/{collection}/versions/{ts}_{version_id}.json"


def overlay_head_path(ref: OverlayRef) -> str:
    """源级 HEAD 或集合级 HEAD。字段补丁不单独成文件。"""
    if ref.namespace is None or ref.collection is None:
        return source_head_path(ref.source_id)
    return collection_head_path(ref.source_id, ref.namespace, ref.collection)

"""目录与只读查询 DTO。search_catalog 必须分页；样本值默认关闭（可能含 PII）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from aidb.models.overlay import CollectionOverlay, SourceOverlay


class CatalogQuery(BaseModel):
    """目录检索。必须分页；默认不采样值以防 PII。"""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    q: str | None = None
    namespace: str | None = None
    collection: str | None = None
    cursor: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
    include_sample_values: bool = False


class Column(BaseModel):
    """字段描述。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: str
    comment: str | None = None
    samples: list[Any] | None = None


class CatalogLabels(BaseModel):
    """目录层级展示标签。"""

    model_config = ConfigDict(extra="forbid")

    namespace_label: str
    collection_label: str
    field_label: str


class CatalogItem(BaseModel):
    """一页里的一个命名空间或一个集合。列只在下钻到单一 collection 时填充。"""

    model_config = ConfigDict(extra="forbid")

    namespace: str | None = None
    collection: str | None = None
    columns: list[Column] = Field(default_factory=list)
    labels: CatalogLabels | None = None
    fks: list[dict[str, Any]] = Field(default_factory=list)


CatalogNode = CatalogItem


class OverlayHead(BaseModel):
    """MCP 组装 search_catalog 时附上的 HEAD 视图（存储层读取，后端 introspect 不拉）。"""

    model_config = ConfigDict(extra="forbid")

    source: SourceOverlay | None = None
    collection: CollectionOverlay | None = None
    fields: dict[str, str] = Field(default_factory=dict)
    patched: bool = False

    def to_json_dict(self) -> dict[str, Any]:
        fields = dict(self.fields)
        if not fields and self.collection is not None:
            fields = dict(self.collection.fields)
        collection_payload: dict[str, Any] | None
        if self.collection is None:
            collection_payload = None
        else:
            collection_payload = {"description": self.collection.description}
        source_payload: dict[str, Any] | None
        if self.source is None:
            source_payload = None
        else:
            source_payload = {
                "description": self.source.description,
                "query_rules": self.source.query_rules,
            }
        return {
            "source": source_payload,
            "collection": collection_payload,
            "fields": fields,
            "patched": self.patched,
        }


class CatalogPage(BaseModel):
    """分页目录页。overlays 由 MCP 组装器挂上 HEAD，后端返回 None。

    JSON 对齐：source_id, namespace, collection, columns, overlays{source,collection,fields}, dialect_prompt。
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str
    items: list[CatalogItem]
    overlays: OverlayHead | None = None
    dialect_prompt: str
    next_cursor: str | None = None
    labels: CatalogLabels

    def to_json_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_id": self.source_id,
            "items": [
                {
                    "namespace": node.namespace,
                    "collection": node.collection,
                    "columns": [
                        {"name": col.name, "type": col.type, "comment": col.comment}
                        for col in node.columns
                    ],
                }
                for node in self.items
            ],
            "overlays": None if self.overlays is None else self.overlays.to_json_dict(),
            "dialect_prompt": self.dialect_prompt,
            "next_cursor": self.next_cursor,
            "labels": {
                "namespace_label": self.labels.namespace_label,
                "collection_label": self.labels.collection_label,
                "field_label": self.labels.field_label,
            },
        }
        if len(self.items) == 1:
            node = self.items[0]
            payload["namespace"] = node.namespace
            payload["collection"] = node.collection
            payload["columns"] = [
                {"name": col.name, "type": col.type, "comment": col.comment}
                for col in node.columns
            ]
        return payload


class ReadonlyPayload(BaseModel):
    """只读原生查询。language：sql|mql|dsl|redis；关系型仅 sql。"""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    language: Literal["sql", "mql", "dsl", "redis"]
    statement: str


class QueryResult(BaseModel):
    """只读查询结果。"""

    model_config = ConfigDict(extra="forbid")

    columns: list[str]
    rows: list[list[Any]]
    truncated: bool
    row_count_capped: int

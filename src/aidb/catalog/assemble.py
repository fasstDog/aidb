"""search_catalog 组装：后端 introspect + 覆盖层 HEAD（从不读历史版本）。"""

from __future__ import annotations

from aidb.backends.registry import BackendRegistry
from aidb.models.catalog import CatalogPage, CatalogQuery, OverlayHead
from aidb.models.connection import Connection
from aidb.models.overlay import CollectionOverlay, OverlayRef, SourceOverlay
from aidb.store.overlays import OverlayStore


def assemble_catalog(
    source: Connection,
    query: CatalogQuery,
    registry: BackendRegistry,
    overlays: OverlayStore,
) -> CatalogPage:
    """backend.introspect_catalog 提供结构/COMMENT/dialect_prompt；此处只挂 HEAD。"""

    backend = registry.get(source.kind)
    page = backend.introspect_catalog(source, query)

    source_body: SourceOverlay | None = None
    source_head = overlays.read_head(OverlayRef(source_id=source.id))
    if source_head is not None and isinstance(source_head.body, SourceOverlay):
        source_body = source_head.body

    collection_body: CollectionOverlay | None = None
    collection_ref = _collection_ref(source.id, query, page)
    if collection_ref is not None:
        coll_head = overlays.read_head(collection_ref)
        if coll_head is not None and isinstance(coll_head.body, CollectionOverlay):
            collection_body = coll_head.body

    fields = dict(collection_body.fields) if collection_body is not None else {}
    page.overlays = OverlayHead(
        source=source_body,
        collection=collection_body,
        fields=fields,
        patched=source_body is not None or collection_body is not None,
    )
    return page


def _collection_ref(source_id: str, query: CatalogQuery, page: CatalogPage) -> OverlayRef | None:
    if query.namespace is not None and query.collection is not None:
        return OverlayRef(
            source_id=source_id,
            namespace=query.namespace,
            collection=query.collection,
        )
    if len(page.items) == 1:
        item = page.items[0]
        if item.namespace is not None and item.collection is not None:
            return OverlayRef(
                source_id=source_id,
                namespace=item.namespace,
                collection=item.collection,
            )
    return None

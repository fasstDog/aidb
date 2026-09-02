"""AIDB 公共契约。Skill 作者将 min 版本钉在 MIN_SERVER_VERSION。"""

from __future__ import annotations

from aidb.backends import (
    BackendRegistry,
    QueryBackend,
    RelationalBackend,
    UnsupportedBackend,
)
from aidb.engines.base import (
    EngineAdapter,
    EngineLabels,
    FormField,
    FormSchema,
    UiMeta,
)
from aidb.engines.not_implemented import NotImplementedAdapter
from aidb.engines.registry import EngineRegistry, get, register, visible_for_ui
from aidb.errors import (
    CATALOG_PAGE_REQUIRED,
    CONCURRENCY_LIMIT,
    ENGINE_NOT_IMPLEMENTED,
    KIND_NOT_ENABLED,
    LANGUAGE_MISMATCH,
    NOT_READONLY,
    SOURCE_NOT_FOUND,
    AidbError,
    raise_kind_not_enabled,
)
from aidb.models import (
    CatalogLabels,
    CatalogNode,
    CatalogPage,
    CatalogQuery,
    CollectionOverlay,
    Column,
    Connection,
    Family,
    Kind,
    OverlayHead,
    OverlayRef,
    QueryResult,
    ReadonlyPayload,
    SourceOverlay,
    VersionMeta,
)

SERVER_VERSION = "0.2.0"
MIN_SERVER_VERSION = "0.1.0"  # Skill authors pin this

__all__ = [
    "AidbError",
    "BackendRegistry",
    "CATALOG_PAGE_REQUIRED",
    "CONCURRENCY_LIMIT",
    "CatalogLabels",
    "CatalogNode",
    "CatalogPage",
    "CatalogQuery",
    "CollectionOverlay",
    "Column",
    "Connection",
    "ENGINE_NOT_IMPLEMENTED",
    "EngineAdapter",
    "EngineLabels",
    "EngineRegistry",
    "Family",
    "FormField",
    "FormSchema",
    "KIND_NOT_ENABLED",
    "Kind",
    "LANGUAGE_MISMATCH",
    "MIN_SERVER_VERSION",
    "NOT_READONLY",
    "NotImplementedAdapter",
    "OverlayHead",
    "OverlayRef",
    "QueryBackend",
    "QueryResult",
    "ReadonlyPayload",
    "RelationalBackend",
    "SERVER_VERSION",
    "SOURCE_NOT_FOUND",
    "SourceOverlay",
    "UiMeta",
    "UnsupportedBackend",
    "VersionMeta",
    "get",
    "raise_kind_not_enabled",
    "register",
    "visible_for_ui",
]

"""连接配置存储。一份 sources.json，配置台读写，MCP 只读。"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from aidb.errors import SOURCE_NOT_FOUND, AidbError
from aidb.models.connection import Connection
from aidb.store._files import atomic_write_json, read_json
from aidb.store.overlays import default_data_root, safe_segment

SOURCES_FILENAME = "sources.json"


class SourcesDocument(BaseModel):
    """AIDB_DATA/sources.json。sources 项即架构 Connection DTO。"""

    model_config = ConfigDict(extra="forbid")

    sources: list[Connection] = Field(default_factory=list)


class ConnectionStore:
    """{AIDB_DATA}/sources.json。MCP 只读；put/delete 给配置台。"""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else default_data_root()

    def path(self) -> Path:
        return self.root / SOURCES_FILENAME

    def _load(self) -> list[Connection]:
        path = self.path()
        if not path.is_file():
            return []
        raw = read_json(path)
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("sources") or []
        else:
            items = []
        out: list[Connection] = []
        for item in items:
            try:
                out.append(Connection.model_validate(item))
            except (ValueError, TypeError, KeyError):
                continue
        return out

    def _save(self, items: list[Connection]) -> None:
        doc = SourcesDocument(sources=items)
        atomic_write_json(self.path(), doc.model_dump(mode="json"))

    def put(self, connection: Connection) -> Connection:
        safe_segment(connection.id, "source_id")
        items = [c for c in self._load() if c.id != connection.id]
        items.append(connection)
        items.sort(key=lambda c: c.id)
        self._save(items)
        return connection

    def get(self, source_id: str) -> Connection | None:
        for item in self._load():
            if item.id == source_id:
                return item
        return None

    def require(self, source_id: str) -> Connection:
        found = self.get(source_id)
        if found is None:
            raise AidbError(SOURCE_NOT_FOUND, details={"source_id": source_id})
        return found

    def delete(self, source_id: str) -> bool:
        items = self._load()
        kept = [c for c in items if c.id != source_id]
        if len(kept) == len(items):
            return False
        self._save(kept)
        return True

    def list(self) -> list[Connection]:
        items = self._load()
        items.sort(key=lambda c: c.id)
        return items

    def public_meta(self) -> list[dict[str, str]]:
        """MCP list_sources：id/name/kind/engine/family，不含 config。"""

        return [
            {
                "id": c.id,
                "name": c.name,
                "kind": c.kind,
                "engine": c.engine,
                "family": c.family,
            }
            for c in self.list()
        ]

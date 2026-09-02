"""配置台环境变量。"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 8787
DEFAULT_DATA = "/var/lib/aidb"
FALLBACK_DATA = "/tmp/aidb-data"
DEFAULT_AUTO_KEEP = 50


def _dir_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".aidb-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def resolve_data_dir(raw: str | None = None) -> Path:
    """AIDB_DATA，默认 /var/lib/aidb；不可写则回退 /tmp/aidb-data。"""

    candidate = Path(raw if raw is not None else os.environ.get("AIDB_DATA", DEFAULT_DATA))
    if _dir_writable(candidate):
        return candidate
    fallback = Path(FALLBACK_DATA)
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


class Settings:
    """进程配置。"""

    def __init__(
        self,
        *,
        bind: str = DEFAULT_BIND,
        port: int = DEFAULT_PORT,
        data_dir: Path | str | None = None,
        token: str | None = None,
        overlay_auto_keep: int = DEFAULT_AUTO_KEEP,
    ) -> None:
        self.bind = bind
        self.port = int(port)
        if data_dir is None:
            self.data_dir = resolve_data_dir()
        else:
            self.data_dir = Path(data_dir)
            self.data_dir.mkdir(parents=True, exist_ok=True)
        self.token = token or None
        self.overlay_auto_keep = max(1, int(overlay_auto_keep))

    @classmethod
    def from_env(cls) -> Settings:
        token = os.environ.get("AIDB_TOKEN") or None
        keep_raw = os.environ.get("AIDB_OVERLAY_AUTO_KEEP", str(DEFAULT_AUTO_KEEP))
        try:
            keep = int(keep_raw)
        except ValueError:
            keep = DEFAULT_AUTO_KEEP
        return cls(
            bind=os.environ.get("AIDB_BIND", DEFAULT_BIND),
            port=int(os.environ.get("AIDB_PORT", str(DEFAULT_PORT))),
            data_dir=resolve_data_dir(),
            token=token,
            overlay_auto_keep=keep,
        )

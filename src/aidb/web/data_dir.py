"""Resolve AIDB_DATA with a writable fallback."""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT = Path("/var/lib/aidb")
_FALLBACK = Path("/tmp/aidb-data")


def resolve_data_dir(explicit: Path | str | None = None) -> Path:
    """Prefer AIDB_DATA / explicit; else /var/lib/aidb if writable, else /tmp/aidb-data."""

    if explicit is not None:
        root = Path(explicit)
    elif os.environ.get("AIDB_DATA"):
        root = Path(os.environ["AIDB_DATA"])
    else:
        root = _DEFAULT
        if not _writable(root):
            root = _FALLBACK
    root.mkdir(parents=True, exist_ok=True)
    return root


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".aidb_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False

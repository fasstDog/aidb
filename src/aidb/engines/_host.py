"""容器内把本机回环转到宿主机。仅适配器使用。"""

from __future__ import annotations

import socket
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})
_GATEWAY = "host.docker.internal"


def in_container() -> bool:
    return Path("/.dockerenv").is_file()


def gateway_ipv4() -> str:
    """只要 IPv4。Docker Desktop 给 host.docker.internal 配了不可达的 IPv6。"""

    try:
        infos = socket.getaddrinfo(_GATEWAY, None, socket.AF_INET, socket.SOCK_STREAM)
        if infos:
            return infos[0][4][0]
    except OSError:
        pass
    return _GATEWAY


def resolve_host(host: str | None, *, default: str = "127.0.0.1") -> str:
    value = (host or default).strip()
    if not in_container():
        return value
    if value.lower() in _LOOPBACK or value.lower() == _GATEWAY:
        return gateway_ipv4()
    return value


def rewrite_loopback_config(config: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(config)
    if not in_container():
        return out
    if out.get("host") is not None:
        out["host"] = resolve_host(str(out["host"]))
    elif not out.get("dsn"):
        out["host"] = resolve_host(None)
    dsn = out.get("dsn")
    if dsn and "://" in str(dsn):
        parsed = urlparse(str(dsn))
        hostname = (parsed.hostname or "").lower()
        if hostname in _LOOPBACK:
            userinfo = ""
            if parsed.username is not None:
                userinfo = parsed.username
                if parsed.password is not None:
                    userinfo += f":{parsed.password}"
                userinfo += "@"
            port = f":{parsed.port}" if parsed.port else ""
            out["dsn"] = urlunparse(parsed._replace(netloc=f"{userinfo}{gateway_ipv4()}{port}"))
    return out

"""Download real brand logos into public/engines/ (local host, no runtime CDN).

Primary source: Simple Icons (CC0-1.0). Fallbacks: official / ASF / brand CDN assets.
Brand names and logos remain trademarks of their owners. See SOURCES.json.
"""

from __future__ import annotations

import base64
import json
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "public" / "engines"
SI = "https://cdn.simpleicons.org"
SI_V11 = "https://cdn.jsdelivr.net/npm/simple-icons@11.15.0/icons"
SI_V13 = "https://cdn.jsdelivr.net/npm/simple-icons@v13/icons"

# aidb engine id -> candidate URLs (first success wins)
SOURCES: dict[str, list[str]] = {
    "postgres": [f"{SI}/postgresql", f"{SI_V13}/postgresql.svg"],
    "mysql": [f"{SI}/mysql", f"{SI_V13}/mysql.svg"],
    "mongodb": [f"{SI}/mongodb", f"{SI_V13}/mongodb.svg"],
    "redis": [f"{SI}/redis", f"{SI_V13}/redis.svg"],
    "neo4j": [f"{SI}/neo4j", f"{SI_V13}/neo4j.svg"],
    "sqlite": [f"{SI}/sqlite", f"{SI_V13}/sqlite.svg"],
    "clickhouse": [f"{SI}/clickhouse", f"{SI_V13}/clickhouse.svg"],
    "duckdb": [f"{SI}/duckdb", f"{SI_V13}/duckdb.svg"],
    "oracle": [f"{SI_V13}/oracle.svg", f"{SI}/oracle"],
    "hive": [f"{SI}/apachehive", f"{SI_V13}/apachehive.svg"],
    "mssql": [
        f"{SI_V11}/microsoftsqlserver.svg",
        f"{SI}/microsoftsqlserver",
    ],
    "doris": [
        "https://www.apache.org/logos/originals/doris.svg",
        "https://svn.apache.org/repos/asf/comdev/project-logos/originals/doris.svg",
    ],
    "starrocks": [
        "https://avatars.githubusercontent.com/u/88238841?s=200&v=4",
    ],
    "oceanbase": [
        "https://mdn.alipayobjects.com/huamei_22khvb/afts/img/A*xH7yQbaaFXoAAAAAAAAAAAAADiGDAQ/original",
        "https://avatars.githubusercontent.com/u/72238180?s=200&v=4",
    ],
    "gaussdb": [
        "https://res-static.hc-cdn.cn/cloudbu-site/intl/en-us/gaussdbforopengauss/product_gaussdb_package_icon2.png",
    ],
    "dameng": [
        "https://www.dameng.com/static/images/logo.png",
        "https://www.dameng.com/assets/images/logo.png",
    ],
}


def fetch(url: str) -> tuple[bytes, str] | None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 aidb-logo-fetch/0.2"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read(), (resp.headers.get("Content-Type") or "").lower()
    except Exception as exc:  # noqa: BLE001
        print(f"  fail {url}: {exc}")
        return None


def looks_like_svg(data: bytes, ctype: str) -> bool:
    if "svg" in ctype:
        return True
    head = data[:400].lstrip().lower()
    return head.startswith(b"<svg") or head.startswith(b"<?xml") or b"<svg" in head


def guess_mime(data: bytes, ctype: str, url: str) -> str | None:
    if "png" in ctype or data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if "jpeg" in ctype or "jpg" in ctype or data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if "webp" in ctype:
        return "image/webp"
    if "icon" in ctype or url.endswith(".ico"):
        return "image/x-icon"
    if "gif" in ctype:
        return "image/gif"
    return None


def wrap_raster_as_svg(data: bytes, mime: str) -> bytes:
    b64 = base64.b64encode(data).decode("ascii")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        f'<image href="data:{mime};base64,{b64}" width="64" height="64" '
        'preserveAspectRatio="xMidYMid meet"/>'
        "</svg>\n"
    )
    return svg.encode("utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict[str, str] = {}
    for engine_id, urls in SOURCES.items():
        print(engine_id)
        saved = False
        for url in urls:
            got = fetch(url)
            if not got:
                continue
            data, ctype = got
            if not data:
                continue
            dest = OUT / f"{engine_id}.svg"
            if looks_like_svg(data, ctype):
                text = data.decode("utf-8", errors="replace")
                if "<svg" not in text.lower():
                    continue
                dest.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
                report[engine_id] = url
                saved = True
                print(f"  ok svg <- {url}")
                break
            mime = guess_mime(data, ctype, url)
            if not mime:
                continue
            dest.write_bytes(wrap_raster_as_svg(data, mime))
            report[engine_id] = f"{url} (embedded {mime})"
            saved = True
            print(f"  ok raster <- {url}")
            break
        if not saved:
            report[engine_id] = "MISSING"
            print("  MISSING")
    meta = Path(__file__).resolve().parent / "engine_logo_sources.json"
    meta.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    missing = [k for k, v in report.items() if v == "MISSING"]
    if missing:
        raise SystemExit(f"missing logos: {missing}")
    print("done", len(report), "logos")


if __name__ == "__main__":
    main()

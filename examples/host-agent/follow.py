"""宿主侧过程骨架：演示 Skill 规定的工具顺序。不实现 MCP，不调 LLM。

把 `call_tool` 换成官方 mcp 客户端即可接到真实服务。
补丁优先级、只读门禁、禁止 dump / 禁止回传样例行，都在这里写死，避免宿主抄漏。
"""

from __future__ import annotations

from typing import Any, Callable, Protocol

MIN_SERVER_VERSION = "0.1.0"  # 与 aidb.MIN_SERVER_VERSION / SKILL.md 对齐

CONFIG_CONSOLE = "http://127.0.0.1:8787"


class ToolClient(Protocol):
    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]: ...


CallTool = Callable[[str, dict[str, Any] | None], dict[str, Any]]


def _ver_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split(".") if p.isdigit())


def ensure_server_version(payload: dict[str, Any]) -> None:
    got = str(payload.get("server_version") or "")
    if not got:
        raise RuntimeError("list_sources 未返回 server_version，拒绝猜测工具形状")
    if _ver_tuple(got) < _ver_tuple(MIN_SERVER_VERSION):
        raise RuntimeError(
            f"aidb {got} 低于 Skill min_server_version {MIN_SERVER_VERSION}，请升级服务端"
        )


def list_or_ask_console(client: ToolClient) -> list[dict[str, Any]]:
    data = client.call("list_sources", {})
    ensure_server_version(data)
    sources = list(data.get("sources") or [])
    if not sources:
        raise RuntimeError(
            f"还没有数据源。请开发者打开配置台 {CONFIG_CONSOLE}（仅本机）添加，不要在对话里要密码。"
        )
    return sources


def search_until_found(
    client: ToolClient,
    source_id: str,
    *,
    q: str | None = None,
    namespace: str | None = None,
    collection: str | None = None,
    max_pages: int = 5,
) -> dict[str, Any]:
    """分页检索目录。禁止一次拉全库；默认不采样值。"""
    cursor: str | None = None
    last: dict[str, Any] = {}
    for _ in range(max_pages):
        last = client.call(
            "search_catalog",
            {
                "source_id": source_id,
                "q": q,
                "namespace": namespace,
                "collection": collection,
                "cursor": cursor,
                "limit": 20,
                "include_sample_values": False,
            },
        )
        items = last.get("items") or []
        if collection and last.get("columns"):
            return last
        if items:
            return last
        cursor = last.get("next_cursor")
        if not cursor:
            break
    return last


def overlay_beats_comment(column: dict[str, Any], overlays: dict[str, Any] | None) -> str | None:
    """优先级：补丁 fields > COMMENT > None（列名猜测留给宿主，且不得当成口径）。"""
    name = column.get("name") or ""
    fields = (overlays or {}).get("fields") or {}
    if name in fields and fields[name]:
        return str(fields[name])
    comment = column.get("comment")
    if comment:
        return str(comment)
    return None


def execute_readonly(
    client: ToolClient,
    *,
    source_id: str,
    language: str,
    statement: str,
) -> dict[str, Any]:
    """只执行。正文参数名写死 statement（服务端兼容 sql/query，这里不用）。

    若 not_readonly，改语句再调，不要绕过门禁。
    """
    result = client.call(
        "execute_readonly",
        {"source_id": source_id, "language": language, "statement": statement},
    )
    code = result.get("code")
    if code == "missing_statement":
        raise RuntimeError("缺少 statement：补上查询正文，不要改用 text/q/body")
    if code == "not_readonly":
        raise RuntimeError("语句不是只读查询：改写成只读后再 execute_readonly，不要绕过门禁")
    if code == "kind_not_enabled":
        raise RuntimeError("该数据源类型尚未启用，不要改写成 SQL 硬查")
    if code == "language_mismatch":
        raise RuntimeError("查询语言与数据源类型不匹配（关系型必须 language=sql）")
    if code == "engine_error":
        kind = (result.get("details") or {}).get("kind")
        raise RuntimeError(f"引擎失败 kind={kind}（connect/timeout/syntax），不要回放语句或要密码")
    return result


def samples_are_not_for_end_users(page: dict[str, Any]) -> None:
    """样例行可能是 PII：宿主可用来消歧，回答里禁止原文回放。"""
    for item in page.get("items") or []:
        for col in item.get("columns") or []:
            col.pop("samples", None)
    for col in page.get("columns") or []:
        if isinstance(col, dict):
            col.pop("samples", None)


def answer_footer(*, source_id: str, collections: list[str], filters: str) -> str:
    return f"数据源 `{source_id}`，集合 {', '.join(collections) or '（未指定）'}，过滤：{filters}"

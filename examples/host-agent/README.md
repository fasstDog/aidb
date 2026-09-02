# 宿主 Agent 接法

aidb 不内置模型。宿主（Cursor / Claude Code / 自建 Agent）负责读 Skill、生成只读查询；MCP 只执行。

本目录是接法示例，不是 MCP 实现，也不是配置台。

## 1. 挂上 Skill

把仓库里的 `skills/aidb/SKILL.md` 交给宿主（Cursor 的 skills 目录、Agent 系统提示，或启动时注入）。不要复制进 overlays，**补丁绝不改写 Skill 文件**。

核对 Skill 声明的 `min_server_version`（当前 **0.1.0**，对齐 `aidb.MIN_SERVER_VERSION`）。服务端更低就升级，不要猜工具。

## 2. 挂上 MCP

三个工具名稳定：`list_sources`、`search_catalog`、`execute_readonly`。如何拉起进程以 MCP 核心为准（官方 `mcp` SDK，禁止手写 JSON-RPC）。

把 `mcp.json.example` 拷到宿主的 MCP 配置里，按实际入口改 `command` / `url`。默认只连本机；不要把 aidb 暴露到公网。

配置台（连库、目录、补丁）默认 http://127.0.0.1:8787 ，和 MCP 分开：聊天里配不了连接，也要不到密码。

## 3. 每次问答的顺序

见 `follow.py`。摘要：

1. `list_sources`（无数据源 → 请人去配置台，停止）
2. `search_catalog`（分页 + `q`；读 overlays HEAD 与 `dialect_prompt`）
3. 宿主写只读查询：补丁 > COMMENT > 列名猜测
4. `execute_readonly`；`not_readonly` 就改语句，不绕门禁
5. 回答里写清用了哪些集合和过滤条件；样例行原文不回给终端用户

未启用的 kind（document / kv / search）会返回「该数据源类型尚未启用」，不要改写成 SQL 硬查。

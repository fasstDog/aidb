# Changelog

## 0.1.0 — 2026-09-02

- Docker 默认镜像：配置台 + 只读执行器（无模型、无 API Key）；PostgreSQL / MySQL 适配器；MCP 同进程挂 `/mcp`，默认绑 `127.0.0.1:8787`
- 三个稳定 MCP 工具：`list_sources`（元数据、不含密钥）、`search_catalog`（分页目录 + overlays HEAD）、`execute_readonly`（只读原生语句）
- 宿主 Skill：`skills/aidb/SKILL.md`（`min_server_version` 0.1.0）；补丁只写 overlays JSON，不得改写 Skill
- 配置台：数据源、目录 overlays、导入导出（不是聊天、不是 SQL 工作台）
- MariaDB / TiDB 复用 `mysql` 别名；达梦、Mongo 为占位，不进默认镜像

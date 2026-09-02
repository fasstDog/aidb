# Changelog

## 0.2.1 — 2026-09-02

- 配置台连接页：卡片网格（引擎图标、名称、host/库摘要、测通、已修）
- 新建数据源：引擎画廊 `GET /api/engines/gallery`，`visible` 可建连，其余灰卡「即将支持」
- 目录树：schema → 表 → 字段（图标 + 类型 Tag + 已修）；右侧补丁/历史
- `UiMeta.label`；前端不写死引擎名单

## 0.2.0 — 2026-09-02

- 进程日志：标准库 `logging` + `RotatingFileHandler` + `python-json-logger`（非 structlog / 非自研 JSON）
- 双 sink：stderr 与 `{AIDB_DATA}/logs/aidb.log`
- 覆盖启动（version/bind）、MCP `list_sources` / `search_catalog` / `execute_readonly`、连库 ping、只读拒绝
- 红线：日志不得出现密码、DSN、`Connection.config`、SQL 正文；可留 source_id / engine / kind / language / tool / error code
- 配置台前端：Pico 静态页退役，改为 Vue 3 + Naive UI（源码 `src/aidb/web/ui`，产物 `src/aidb/web/static`）

## 0.1.0 — 2026-09-02

- Docker 默认镜像：配置台 + 只读执行器（无模型、无 API Key）；PostgreSQL / MySQL 适配器；MCP 同进程挂 `/mcp`，默认绑 `127.0.0.1:8787`
- 三个稳定 MCP 工具：`list_sources`（元数据、不含密钥）、`search_catalog`（分页目录 + overlays HEAD）、`execute_readonly`（只读原生语句）
- 宿主 Skill：`skills/aidb/SKILL.md`（`min_server_version` 0.1.0）；补丁只写 overlays JSON，不得改写 Skill
- 配置台：数据源、目录 overlays、导入导出（不是聊天、不是 SQL 工作台）
- MariaDB / TiDB 复用 `mysql` 别名；达梦、Mongo 为占位，不进默认镜像

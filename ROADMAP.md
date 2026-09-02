# aidb 路线图

契约不变：MCP 只有 `list_sources` / `search_catalog` / `execute_readonly`；Docker 不调模型、不配 API Key；核心禁止 `if engine ==`、方言与驱动。入口对不上改调用，不改契约。

当前发布：`v0.2.0`。

## 0.2（已发布）

- **日志**：标准库 `logging` + `RotatingFileHandler`；格式用 `python-json-logger` 或 structlog（二选一，禁止自研）。默认 stderr + `AIDB_DATA/logs/aidb.log`。必须覆盖：进程启动（version / bind）、MCP 三次调用、连库、只读拒绝。
- **日志红线**：记录里不准出现密码、DSN、`Connection.config` 明文。可留 `source_id` / engine / kind。
- **配置台改版**：现有 Pico 静态页退役。Vue 3 + Naive UI（或 Element Plus，禁止从零画组件）。布局：左数据源、中目录树、右补丁/历史。深色可选。FastAPI API 不动；静态构建产物仍由 `python -m aidb.web` 托管（`AIDB_BIND`/`AIDB_PORT`，默认 127.0.0.1:8787，`/mcp` 同进程）。

归属：日志接线 → MCP 核心；配置台改版 → 配置台；本文件与红线 → 架构守门。

## 0.3

- **可观测性补齐**：超时、并发上限、结果截断可在配置台看见（只读展示，不把执行做成工作台）。
- **目录搜索体验**：`search_catalog` 已分页；配置台目录树跟搜索/筛选对齐，禁止一次拉全库。

## 明确不做（0.2 / 0.3 都不做）

- 达梦真驱动（占位 `NotImplementedAdapter`、`ui.visible=false` 保持）
- 问数聊天
- SQL 工作台
- `ask_readonly`、NL→SQL、写补丁做成 MCP 工具
- 核心写方言 / 直连 psycopg / pymysql
- 把 Mongo / ES / Redis 塞进 SQL 适配器注册表

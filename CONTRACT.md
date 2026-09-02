# AIDB 架构契约（锁定）

接口以产品文档 + 下列库清单为准。入口对不上，改调用，不改契约。

Skill 给宿主 Agent；MCP 只执行只读查询。Docker = 配置台 + 执行器（无模型、无 API key）。默认镜像 = 配置台+执行器：PG/MySQL 驱动 + FastAPI/uvicorn，CMD `python -m aidb.web` 绑 127.0.0.1:8787。MCP 挂同一进程，不开第二端口。不含 dameng/mongo。

## 指定库（造轮子直接打回）

- DTO：Pydantic v2（禁止对外 dataclass）
- MCP：官方 Python SDK（`mcp`），禁止手搓 JSON-RPC
- PG：psycopg3（`psycopg`），池用驱动自带，禁止自写连接池
- MySQL：PyMySQL
- `is_readonly`：sqlglot，进适配器，禁止正则当 SQL 解析
- 配置台：FastAPI + 现成前端
- 补丁版本：文档规定的 JSON 文件；diff 用 difflib / deepdiff，禁止自研 git

## 两级注册表

1. `QueryBackend` 按 kind：`relational` / `document` / `kv` / `search` / `graph`
2. `EngineAdapter` 按 engine（`engines.registry.get(source.engine)`）

禁止按引擎名分支。新引擎 = 新文件 + `register()`。未实现 kind 必须走 `UnsupportedBackend`。

`UiMeta`：`visible` + `label`（空则回退 `adapter.id`）+ `icon`（相对路径，如 `engines/postgres.svg`；前端本地托管，禁止外链）+ `description`（画廊卡片短描述）。

关系型占位（达梦等）：`NotImplementedAdapter`，`visible=false`，无真驱动。

Mongo / Redis / 搜索 / 图：`family=document|kv|search|graph` → `kind` 同 family；挂 Engine 注册表仅作画廊占位（`NotImplementedAdapter`），执行走 `UnsupportedBackend`；禁止写成 SQL 方言适配器。

图标放在 `src/aidb/web/ui/public/engines/`（构建后 `static/engines/`），由配置台本地托管，禁止外链。

## Connection

`id` / `name` / `kind` / `engine` / `family` + **不透明** `config` JSON。核心不得解析 host/user。表单由 `form_schema` 声明。覆盖层键只有 `source_id` / `namespace` / `collection` / `field`。禁止用 `table_name` 当存储键；「表」只出现在 labels。

## Overlay 路径（MCP 查询只读 HEAD）

- `overlays/{source_id}/_source/HEAD.json`
- `overlays/{source_id}/_source/versions/{ts}_{id}.json`
- `overlays/{source_id}/{namespace}/{collection}/HEAD.json`
- `overlays/{source_id}/{namespace}/{collection}/versions/{ts}_{id}.json`

## 配置台引擎 API

- `GET /api/engines` → 仅 `visible_for_ui()`（下拉，不含 dameng 等占位）
- `GET /api/engines/gallery` → `all_engines()`（含 `visible=false` 占位）；字段 `id` / `label` / `family` / `kind` / `visible` / `form_schema` / `icon` / `description`（`aliases` 可选）
- 前端禁止写死引擎名单；新建连接页走 gallery；已有连接页保持独立
- Connection CRUD 路径不变：`/api/connections` 不因画廊改动
- `kind` 由 `kind_from_family(adapter.family)`：`mysql`/`postgres`/`oracle_like` → `relational`；其余 family（`document`/`kv`/`search`/`graph`）→ kind 同 family

## 引擎适配必须覆盖的画廊引擎

占位即可。禁止真驱动、禁止 `if engine==`、禁止把 Mongo/Redis/Neo4j 写成 SQL 方言适配器。新占位 = `engines/` 下新文件或 `engines/placeholders.py` + `register(NotImplementedAdapter(...))`。本架构 drop 不建完整占位墙。

已 `visible=true`：`postgres`、`mysql`

占位 `visible=false`（必须）：`dameng`、`oracle`、`sqlite`、`clickhouse`、`apache_doris`（id=`doris` 可，配 alias）、`duckdb`、`gaussdb`、`hive`、`mssql`、`oceanbase`、`starrocks`、`mongodb`、`redis`、`neo4j`

可选（DB-GPT 墙）：`tugraph`、`spark`、`vertica`、`opengauss`、`access`、`hbase`、`cassandra`、`couchbase`、`db2`

## 进程模型

CMD `python -m aidb.web` 读 `AIDB_BIND` / `AIDB_PORT`（默认 127.0.0.1:8787）。`create_app()` 尝试 `from aidb.mcp.server import attach`：有则 `attach(app)`，没有则跳过。MCP 核心实现 `attach`，挂同一 FastAPI 进程，路径 `/mcp`，不开第二端口。

## MCP 工具（本 drop 不实现）

`list_sources`、`search_catalog`（必须分页）、`execute_readonly`。payload.language = `sql|mql|dsl|redis`；关系型只接受 `sql`。`is_readonly` 在适配器上，用 sqlglot。catalog 名词来自适配器 labels。

## 禁止出现在 core（`engines/` 以外）的模式

- `information_schema` / `pg_catalog` / 自行拼接分页 / 反引号标识符
- `execute_readonly` 直接调用 psycopg / pymysql
- Overlay DTO 只有 `table_name` 没有 `collection`
- 前端写死引擎列表（下拉必须 `visible_for_ui()` / `GET /api/engines`；新建页必须 `all_engines()` / `GET /api/engines/gallery`）
- `if engine ==` / `if source.engine ==`

## 目录归属

| 路径 | 归属 |
| --- | --- |
| `src/aidb/backends`、`models`、`engines/{base,registry,not_implemented}` | 架构守门（本 drop） |
| `src/aidb/engines/postgres.py` `mysql.py` `dameng.py` | 引擎适配 |
| MCP 工具、overlay 版本库、`aidb.mcp.server.attach` | MCP 核心 |
| `src/aidb/web/` | 配置台；下拉 = `visible_for_ui()`；画廊 = `all_engines()` |
| `skills/aidb/SKILL.md` | Skill 作者；`min` = `aidb.MIN_SERVER_VERSION` |
| `deploy/` | 本 drop |

optional-deps 隔离 dameng/mongo；默认镜像不得装 dmPython。

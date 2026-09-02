# aidb

**0.1.0（MVP）** — 给宿主 Agent 一份 Skill：MCP 只执行只读查询；Docker 镜像是配置台 + 执行器。不内置大模型，不需要 API Key。

配置台用来登记数据源、写目录 overlays（口径 / 查询规则），**不是**聊天窗口，也**不是** SQL 工作台。自然语言 → 语句由宿主完成。

默认镜像只带 PostgreSQL、MySQL 适配器。MariaDB / TiDB 走 `mysql` 别名。达梦、Mongo 仅为扩展占位，不在本版本默认镜像里。

## 快速开始

仓库里的 Compose **已经**绑在本机回环，不要改成 `0.0.0.0`，不要对公网暴露。

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

| 项 | 实际值 |
| --- | --- |
| 服务名 | `aidb` |
| 发布端口 | `127.0.0.1:8787:8787` |
| 进程 | `python -m aidb.web`（配置台 + MCP 同进程） |
| 配置台 | http://127.0.0.1:8787 |
| MCP | 同一端口，路径 `/mcp`（不开第二端口） |
| 数据卷 | `aidb-data` → `/var/lib/aidb` |

打开配置台 → 选引擎（下拉来自 `visible_for_ui()`，MVP 可见：`postgres` / `mysql`）→ 填连接并保存 / 测连通 → 需要时给数据源或集合写 overlays。**不要在对话里要密码或 DSN。**

宿主再挂上 Skill，连本机 MCP。本地 stdio 入口是 `python -m aidb`（示例见 `examples/host-agent/mcp.json.example`）。Docker 场景连 `http://127.0.0.1:8787/mcp`。

## 三个 MCP 工具

名称锁定，不要发明第四个。顺序：`list_sources` → `search_catalog` → 宿主自写只读语句 → `execute_readonly`。

| 工具 | 做什么 |
| --- | --- |
| `list_sources` | 列出已配置数据源元数据（`id` / `name` / `kind` / `engine` / `family` + `server_version`）。**不含密钥、不含 `config`。** |
| `search_catalog` | 分页检索目录：结构 + COMMENT + overlays **HEAD** + `dialect_prompt`。必须带 `limit`（默认 20，最大 100）。 |
| `execute_readonly` | 执行只读原生语句。`payload.language` 为 `sql` / `mql` / `dsl` / `redis`；关系型只接受 `sql`。 |

MCP 不生成语句、不写补丁、没有 `ask_readonly`。

## 宿主如何挂 Skill

1. 把仓库里的 [`skills/aidb/SKILL.md`](skills/aidb/SKILL.md) 交给宿主（Cursor skills 目录、系统提示，或启动时注入）。不要拷进 overlays。
2. 按上一节连 MCP。Skill 声明 `min_server_version` **0.1.0**（对齐 `aidb.MIN_SERVER_VERSION`）；`list_sources` 的 `server_version` 更低就升级，不要猜工具形状。
3. 没有数据源 → 停，请开发者打开配置台添加。不要向任何人要密码，不要全表 dump，不要把样例行原文回给终端用户。

接法骨架：`examples/host-agent/`。

**补丁版本策略：** overlays 是 `AIDB_DATA` 下的 JSON（HEAD + `versions/`）。补丁系统**不得改写** `skills/aidb/SKILL.md`（Skill 与宿主示例均写明这一点）。

## 扩展点

两级注册表，核心禁止按引擎名分支。

1. **`QueryBackend` 按 kind**：`relational` / `document` / `kv` / `search`。MVP 只启用关系型；其余走 `UnsupportedBackend`（`kind_not_enabled`），不得落到 SQL。
2. **`EngineAdapter` 按 engine**：挂在关系型下，`engines.registry.get(source.engine)`。适配器文件在 `src/aidb/engines/`，import 时 `register()`；`load_engines()` 扫包内 `*.py`，核心不写死引擎列表。配置台下拉只用 `visible_for_ui()`。

| 引擎 | MVP 状态 |
| --- | --- |
| `postgres`（别名 `postgresql` / `pg`） | 默认镜像 |
| `mysql`（别名 `mariadb` / `tidb`） | 默认镜像 |
| `dameng`（别名 `dm`） | `NotImplementedAdapter`，`ui.visible=False`，默认镜像不装 dmPython |
| Mongo | `document` kind 占位（`UnsupportedBackend`）；optional extra `mongo`，无引擎文件 |

新引擎 = 新文件 + `register()`，不要改 core 里的 `if engine ==`。

## 安全

- 只绑 `127.0.0.1` / 内网。Compose 已是 `127.0.0.1:8787:8787`。不要改 `AIDB_BIND=0.0.0.0`，不要对公网发布。
- 仓库不放真实 DSN、密码、API Key。连接只在配置台填写。
- `list_sources` 永不返回凭据；配置台对外连接会脱敏。
- MCP 只跑只读查询；`is_readonly` 在适配器上（sqlglot）。`not_readonly` 就改语句，不要绕门禁。
- 不内置 LLM，不需要模型 API Key。
- 禁止无过滤全表 / 全集 dump；`search_catalog` 必须分页。

## 目录骨架

```
aidb/
├── CONTRACT.md
├── CHANGELOG.md
├── pyproject.toml
├── deploy/
│   ├── Dockerfile
│   └── docker-compose.yml
├── examples/host-agent/
│   ├── README.md
│   ├── follow.py
│   └── mcp.json.example
├── skills/aidb/SKILL.md
├── src/aidb/
│   ├── backends/          # QueryBackend 按 kind
│   ├── catalog/
│   ├── engines/           # EngineAdapter：postgres / mysql / dameng 占位
│   ├── mcp/               # list_sources / search_catalog / execute_readonly
│   ├── models/
│   ├── store/             # sources.json + overlays
│   └── web/               # 配置台 FastAPI，attach MCP /mcp
└── tests/
```

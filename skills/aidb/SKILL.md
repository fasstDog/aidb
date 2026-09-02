---
name: aidb
description: >-
  用户要查已配置数据源里的业务数据、指标或名单时启用。只读。
  按 list_sources → search_catalog → 宿主写只读查询 → execute_readonly 作答。
  不要密码、不写库、不在对话里发明口径。
---

# aidb

给宿主 Agent 的说明书。MCP 只执行只读查询，不生成语句、不写补丁、不内置模型。
业务语义写在配置台的 overlays，**补丁系统不得改写本文件**。

`min_server_version`: **0.1.0**（对齐 `aidb.MIN_SERVER_VERSION`）。
若握手或 `list_sources` 给出的 `server_version` 低于此值，停止并让开发者升级 aidb，不要按旧工具形状猜测。

配置台与 MCP 默认只绑 `127.0.0.1`。不要把服务暴露到公网，不要改成 `0.0.0.0`。

## 何时启用

- 问题要靠已配置数据源里的记录才能答（数量、名单、明细、对账、字段含义）。
- 开发者在问「连上了吗 / 有哪些数据源 / 某张表什么意思」。

不要启用：改数据、建表、要密码或 DSN、让你「把整个库倒出来」、给终端用户念样例行原文。

用语用「数据源 / 目录 / 只读查询」。SQL 只是 `kind=relational` 且 `language=sql` 时的例子，不要写死「只能 SELECT 表」——以后 document/kv/search 走 `mql` / `dsl` / `redis`，现在未启用会返回「该数据源类型尚未启用」。

## 禁止

- 向任何人要密码、DSN、连接串。连不上就让开发者打开配置台（默认 http://127.0.0.1:8787，仅本机）。
- 全表 dump：禁止无过滤地拉完整集合；`search_catalog` 必须分页，禁止循环直到拿完全部对象（除非正在定位某一条）。
- 把 `samples` / 样例行原文回给终端用户（可能是 PII）。默认不要开 `include_sample_values`；若目录里带了样本，只用来自己消歧，回答里改写成类别或范围。
- 绕过只读门禁。收到 `not_readonly` 就改语句再执行，不要换工具、不要改服务端。
- 在对话里发明口径（字段含义、主键、状态码）。答不准就让开发者在同一配置台补数据源 / 集合 / 字段说明。
- 调用不存在的 `ask_readonly`，或把「写补丁」当成 MCP 工具。NL→语句由宿主完成，MCP 不负责。

## 工具顺序（必须）

三个工具名稳定，不要改、不要发明第四个。

1. **`list_sources`** — 元数据，不含密钥。核对 `server_version`。
2. **`search_catalog`** — 中性目录 + overlays 的 **HEAD** + `dialect_prompt`。必须带分页（`limit` 默认 20，最大 100）；用 `q` / `namespace` / `collection` 缩小范围，跟 `next_cursor` 翻页。禁止一次要全部对象。
3. 宿主根据目录、overlays、`dialect_prompt` **自己写**只读查询。
4. **`execute_readonly`** — 正文参数名是 `statement`（别名 `sql` / `query` 仅兼容旧宿主）。`payload.language` 为 `sql | mql | dsl | redis`；关系型只接受 `sql`。

没有数据源 → 停，请开发者在配置台添加。不要空转去搜目录。

## 生成查询

优先级（高 → 低），冲突时以前者为准：

1. **overlays HEAD**（配置台补丁）：`source.description` / `source.query_rules`、集合说明、`fields` 映射。
2. 目录里的 **COMMENT**（列/集合注释）。
3. 从列名猜测（最后手段；不确定就去配置台补说明，不要在对话里敲定）。

必须遵守当前页的 `dialect_prompt`（分页、日期、字符串比较、标识符引用）。不要按别的引擎的习惯写。关系型用 `language: "sql"`；不要把 Mongo/ES/Redis 语句塞进关系型。

出错：先改查询再 `execute_readonly`，不要绕过只读门禁。`truncated: true` 时基于已返回行作答，不要为了「看全」去拆门禁或循环 dump。

## 回答终端用户时

标明用了哪些数据源、哪些集合（关系型可说「表」作为该引擎的 label）、哪些过滤条件。不要贴原始样例行，不要回放密钥或连接配置。

## 工具形状（与 MCP 对齐）

### `list_sources`

无必填参数。返回例如：

```json
{
  "server_version": "0.1.0",
  "sources": [
    {"id": "src_1", "name": "订单库", "kind": "relational", "engine": "postgres", "family": "postgres"}
  ]
}
```

`sources` 为空 → 引导去配置台，不要猜库。不要索要 `config`。

### `search_catalog`

```json
{
  "source_id": "src_1",
  "q": "order",
  "namespace": null,
  "collection": null,
  "cursor": null,
  "limit": 20,
  "include_sample_values": false
}
```

返回一页：`items`、`overlays`（HEAD：`source` / `collection` / `fields` / `patched`）、`dialect_prompt`、`next_cursor`、`labels`（名词来自适配器，如 schema/表/列）。下钻到单一集合时还有 `namespace`、`collection`、`columns`。历史版本不会出现在这里。

### `execute_readonly`

正文参数名**写死 `statement`**。服务端兼容别名 `sql` / `query`（有 `statement` 时以它为准），宿主新代码不要用别名，避免和 `language: "sql"` 搞混。不要另发明 `text` / `q` / `body`。

```json
{
  "source_id": "src_1",
  "language": "sql",
  "statement": "SELECT status, count(*) AS n FROM orders WHERE created_at >= DATE '2026-01-01' GROUP BY 1"
}
```

结果：`columns`、`rows`、`truncated`、`row_count_capped`。行数与超时由服务端截断，宿主不要为了拿更多行去关截断。失败一律 `{code,message,details}`，不要把 SDK 调用打红当成无结构异常。

## 结构化错误（改查询，不要改协议）

| code | 含义 | 宿主怎么做 |
| --- | --- | --- |
| `kind_not_enabled` | 该数据源类型尚未启用 | 告诉开发者这类数据源还没开，不要改写成 SQL 硬查 |
| `engine_not_implemented` | 该引擎尚未实现 | 同上 |
| `language_mismatch` | 查询语言与数据源类型不匹配 | 关系型改回 `sql` |
| `not_readonly` | 语句不是只读查询 | 改成只读再执行 |
| `catalog_page_required` | 目录查询必须分页 | 补上 `limit` |
| `missing_statement` | 没有查询正文 | 补上 `statement`（不要只传空字符串） |
| `engine_error` | 引擎执行失败 | 看 `details.kind`：`connect` 连不上 / `timeout` 超时 / `syntax` 语法。不要把语句或密码要出来 |

## 答不准时

有连接但 overlays / COMMENT 仍不够判断口径 → 请开发者在**同一配置台**补数据源说明、集合说明或字段说明，然后你再 `search_catalog` 读新的 HEAD。不要在聊天里替他们定义「这个字段等于什么」。

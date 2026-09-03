"""画廊占位引擎（CONTRACT 必含）。visible=false，无真驱动。

达梦仍在 dameng.py；本文件补齐其余占位，供配置台引擎墙展示。
"""

from __future__ import annotations

from aidb.engines.base import EngineLabels, FormField, FormSchema
from aidb.engines.not_implemented import NotImplementedAdapter
from aidb.engines.registry import register

_SQL_LABELS = EngineLabels(namespace="schema", collection="表", field="列")
_DOC_LABELS = EngineLabels(namespace="数据库", collection="集合", field="字段")
_KV_LABELS = EngineLabels(namespace="db", collection="keyspace", field="key")
_GRAPH_LABELS = EngineLabels(namespace="database", collection="label", field="property")

_HOST_PORT = FormSchema(
    fields=[
        FormField(key="host", label="主机", type="string", required=True, default="127.0.0.1"),
        FormField(key="port", label="端口", type="int", required=False),
        FormField(key="user", label="用户", type="string", required=False),
        FormField(key="password", label="密码", type="password", required=False, secret=True),
        FormField(key="database", label="数据库", type="string", required=False),
    ]
)

_URI = FormSchema(
    fields=[
        FormField(key="uri", label="连接 URI", type="string", required=True),
    ]
)


def _ph(
    *,
    id: str,
    family: str,
    label: str,
    icon: str,
    description: str,
    aliases: tuple[str, ...] = (),
    labels: EngineLabels | None = None,
    form_schema: FormSchema | None = None,
) -> None:
    register(
        NotImplementedAdapter(
            id=id,
            family=family,  # type: ignore[arg-type]
            aliases=aliases,
            visible=False,
            label=label,
            icon=icon,
            description=description,
            labels=labels or _SQL_LABELS,
            form_schema=form_schema if form_schema is not None else _HOST_PORT,
        )
    )


_ph(
    id="oracle",
    family="oracle_like",
    label="Oracle",
    icon="engines/oracle.svg",
    description="企业级关系型数据库，广泛应用于核心业务系统",
    aliases=("oracledb",),
)
_ph(
    id="sqlite",
    family="postgres",
    label="SQLite",
    icon="engines/sqlite.svg",
    description="轻量嵌入式关系型数据库，适合本地与小型应用",
    form_schema=FormSchema(
        fields=[FormField(key="path", label="数据库文件", type="string", required=True, default=":memory:")]
    ),
)
_ph(
    id="clickhouse",
    family="postgres",
    label="ClickHouse",
    icon="engines/clickhouse.svg",
    description="列式 OLAP 数据库，适合大规模实时分析",
    aliases=("ch",),
)
_ph(
    id="doris",
    family="mysql",
    label="Apache Doris",
    icon="engines/doris.svg",
    description="实时数仓，高并发分析场景",
    aliases=("apache_doris",),
)
_ph(
    id="duckdb",
    family="postgres",
    label="DuckDB",
    icon="engines/duckdb.svg",
    description="进程内分析型数据库，适合本地与嵌入式分析",
    form_schema=FormSchema(
        fields=[FormField(key="path", label="数据库文件", type="string", required=True, default=":memory:")]
    ),
)
_ph(
    id="gaussdb",
    family="postgres",
    label="GaussDB",
    icon="engines/gaussdb.svg",
    description="华为分布式数据库，兼容 PostgreSQL 生态",
)
_ph(
    id="hive",
    family="mysql",
    label="Hive",
    icon="engines/hive.svg",
    description="基于 Hadoop 的数据仓库，适合批处理分析",
)
_ph(
    id="mssql",
    family="postgres",
    label="SQL Server",
    icon="engines/mssql.svg",
    description="Microsoft 企业级关系型数据库",
    aliases=("sqlserver", "sql_server"),
)
_ph(
    id="oceanbase",
    family="mysql",
    label="OceanBase",
    icon="engines/oceanbase.svg",
    description="分布式关系型数据库，兼容 MySQL / Oracle 模式",
    aliases=("ob",),
)
_ph(
    id="starrocks",
    family="mysql",
    label="StarRocks",
    icon="engines/starrocks.svg",
    description="高性能实时分析型数据库",
)
_ph(
    id="mongodb",
    family="document",
    label="MongoDB",
    icon="engines/mongodb.svg",
    description="文档型数据库，灵活的 JSON 文档模型",
    aliases=("mongo",),
    labels=_DOC_LABELS,
    form_schema=_URI,
)
_ph(
    id="redis",
    family="kv",
    label="Redis",
    icon="engines/redis.svg",
    description="内存键值存储，常用作缓存与消息中间件",
    labels=_KV_LABELS,
)
_ph(
    id="neo4j",
    family="graph",
    label="Neo4j",
    icon="engines/neo4j.svg",
    description="原生图数据库，适合关系网络与知识图谱",
    labels=_GRAPH_LABELS,
    form_schema=_URI,
)

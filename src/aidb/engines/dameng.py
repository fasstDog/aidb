"""达梦占位。NotImplementedAdapter，ui.visible=False；不 import dmPython。"""

from __future__ import annotations

from aidb.engines.base import EngineLabels, FormField, FormSchema
from aidb.engines.not_implemented import NotImplementedAdapter
from aidb.engines.registry import register

register(
    NotImplementedAdapter(
        id="dameng",
        family="oracle_like",
        aliases=("dm",),
        visible=False,
        label="达梦",
        icon="engines/dameng.svg",
        description="国产关系型数据库，兼容 Oracle 生态",
        labels=EngineLabels(namespace="schema", collection="表", field="列"),
        form_schema=FormSchema(
            fields=[
                FormField(key="host", label="主机", type="string", required=True, default="127.0.0.1"),
                FormField(key="port", label="端口", type="int", required=False, default=5236),
                FormField(key="user", label="用户", type="string", required=True),
                FormField(key="password", label="密码", type="password", required=False, secret=True),
                FormField(key="schema", label="模式", type="string", required=False),
            ]
        ),
    )
)

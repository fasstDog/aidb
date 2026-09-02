"""AIDB 配置台。引擎下拉必须 visible_for_ui()，禁止写死引擎名。"""

from __future__ import annotations

from aidb.web.app import create_app

__all__ = ["create_app"]

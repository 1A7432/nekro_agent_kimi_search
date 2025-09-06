"""
Kimi 联网搜索插件

基于 Moonshot AI Kimi 模型内置 $web_search 工具的第三方联网搜索插件
"""

from .plugin import kimi_search_plugin as plugin

__all__ = ["plugin"]

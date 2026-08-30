"""
工具集（重新导出）

工具注册的实际实现在 agent/tools.py 中，
此文件仅做重新导出，方便 services 模块内部引用。
"""

from agent.tools import register_all_tools

__all__ = ["register_all_tools"]
"""
Agent 服务（重新导出）

Agent 核心循环的实际实现在 agent/core.py 中，
此文件仅做重新导出，方便 services 模块内部引用。
"""

from agent.core import AgentService, agent_service, AGENT_SYSTEM_PROMPT

__all__ = ["AgentService", "agent_service", "AGENT_SYSTEM_PROMPT"]
import json
from typing import List, Dict, Any, Callable, Awaitable, Optional


class Tool:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable[..., Awaitable[str]],
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_all_schemas(self) -> List[dict]:
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def get_tool_descriptions(self) -> str:
        lines = []
        for tool in self._tools.values():
            params_desc = json.dumps(tool.parameters.get("properties", {}), ensure_ascii=False)
            lines.append(f"- {tool.name}: {tool.description} (参数: {params_desc})")
        return "\n".join(lines)

    async def execute(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)
        if not tool:
            available = ", ".join(self._tools.keys())
            return f"工具 '{name}' 不存在。可用工具: {available}"
        try:
            return await tool.handler(**arguments)
        except TypeError as e:
            return f"工具 '{name}' 参数错误: {e}"
        except Exception as e:
            return f"工具 '{name}' 执行失败: {e}"


tool_registry = ToolRegistry()
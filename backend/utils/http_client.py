import json
from typing import AsyncGenerator, Optional, List
import httpx

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


class DeepSeekClient:
    """统一的 DeepSeek API 客户端，管理连接、认证和请求"""

    def __init__(self):
        self.api_key = DEEPSEEK_API_KEY
        self.base_url = DEEPSEEK_BASE_URL
        self.model = DEEPSEEK_MODEL

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    async def chat_completion(
        self,
        messages: List[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        timeout: float = 30.0,
    ) -> Optional[str]:
        """非流式对话补全，返回完整响应文本"""
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                self._url("/v1/chat/completions"),
                headers=self._headers(),
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False,
                },
            )
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content")

    async def chat_completion_stream(
        self,
        messages: List[dict],
        temperature: float = 0.3,
        top_p: float = 0.9,
        max_tokens: int = 4096,
        timeout: float = 120.0,
    ) -> AsyncGenerator[str, None]:
        """流式对话补全，逐 token 产出"""
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                self._url("/v1/chat/completions"),
                headers=self._headers(),
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                },
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

    async def chat_completion_with_tools(
        self,
        messages: List[dict],
        tools: List[dict] = None,
        tool_choice: str = "auto",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> dict:
        """带 Function Calling 的非流式对话补全，返回完整响应消息"""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                self._url("/v1/chat/completions"),
                headers=self._headers(),
                json=payload,
            )
            data = response.json()

            if "error" in data:
                error_msg = data["error"].get("message", str(data["error"]))
                raise RuntimeError(f"DeepSeek API 错误: {error_msg}")

            if response.status_code != 200:
                raise RuntimeError(f"DeepSeek API 返回 HTTP {response.status_code}: {data}")

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            return {
                "content": message.get("content"),
                "tool_calls": message.get("tool_calls"),
                "finish_reason": choice.get("finish_reason"),
            }

    async def chat_completion_stream_with_tools(
        self,
        messages: List[dict],
        tools: List[dict] = None,
        tool_choice: str = "auto",
        temperature: float = 0.3,
        top_p: float = 0.9,
        max_tokens: int = 4096,
        timeout: float = 120.0,
    ):
        """带 Function Calling 的流式对话补全，逐 token 产出内容和工具调用"""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                self._url("/v1/chat/completions"),
                headers=self._headers(),
                json=payload,
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            yield {
                                "content": delta.get("content", ""),
                                "tool_calls": delta.get("tool_calls"),
                                "finish_reason": data.get("choices", [{}])[0].get("finish_reason"),
                            }
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    self._url("/v1/models"),
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code == 200
        except Exception:
            return False


deepseek_client = DeepSeekClient()
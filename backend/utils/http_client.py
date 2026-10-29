"""
统一的 LLM 客户端（OpenAI 兼容协议）

设计要点：
  - 只依赖 OpenAI 兼容的 /v1/chat/completions 与 /v1/models，因此可对接
    vLLM / Ollama / LMDeploy / Xinference / 国产云 API 兼容模式 / One-API 网关等，
    换模型只需改环境变量，无需改代码。
  - base_url 两种写法都兼容：https://host 与 https://host/v1
    （用户按 OpenAI 文档习惯写 /v1 时，不做归一化就会拼成 /v1/v1/chat/completions）
  - 错误信息不再写死 "DeepSeek"，便于私有化交付时向客户展示真实原因。

变量名兼容：config.py 中 LLM_*（推荐）与 DEEPSEEK_*（历史）都能用。
"""

import json
from typing import AsyncGenerator, Optional, List

import httpx

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


class LLMClient:
    """OpenAI 兼容协议的 LLM 客户端，管理连接、认证和请求"""

    def __init__(self):
        self.api_key = LLM_API_KEY
        self.base_url = LLM_BASE_URL
        self.model = LLM_MODEL

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        """拼接请求地址，容忍 base_url 结尾带 / 或带 /v1 两种写法。"""
        base = (self.base_url or "").rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        return f"{base}{path}"

    def _error(self, response, data) -> RuntimeError:
        detail = ""
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                detail = err.get("message", "")
            elif err:
                detail = str(err)
        if not detail:
            detail = (response.text or "")[:300]
        return RuntimeError(
            f"LLM 调用失败: HTTP {response.status_code}（端点 {self.base_url}，模型 {self.model}）"
            f"{'：' + detail if detail else ''}"
        )

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
            if response.status_code != 200:
                raise self._error(response, data)
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

            if response.status_code != 200:
                raise self._error(response, data)

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
        """探测端点可用性。

        注意：并非所有 OpenAI 兼容服务都实现 /v1/models（部分网关返回 404/405）。
        这类响应说明"端点存在但未实现该探测接口"，仍视为可用；
        401/403 表示地址可达但密钥不对，视为不可用。
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    self._url("/v1/models"),
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if resp.status_code == 200:
                    return True
                return resp.status_code in (404, 405)
        except Exception:
            return False


llm_client = LLMClient()
# 向后兼容别名（历史代码使用 deepseek_client）
deepseek_client = llm_client

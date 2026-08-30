import json
from typing import AsyncGenerator, List, Dict, Optional
from utils.http_client import deepseek_client
from agent.tool_registry import tool_registry
from config import (
    LLM_TEMPERATURE,
    LLM_TOP_P,
    LLM_MAX_TOKENS,
    AGENT_MAX_ITERATIONS,
)


AGENT_SYSTEM_PROMPT = """你是一个智能全能助手，负责闲聊对话和工具调用。你可以自然友好地与用户交流，同时在需要时主动调用工具获取信息或执行操作。

## 对话风格
- 热情友好：用自然、亲切的语气交流
- 简洁明了：回答简洁有力，不啰嗦
- 积极主动：理解用户意图，主动提供帮助
- 诚实透明：不知道的事情直接说不知道，不编造
- 中文回答：始终使用中文

## 闲聊场景（直接回复，无需调用工具）
- 打招呼：你好、Hi、早上好等
- 感谢与告别：谢谢、再见、拜拜等
- 自我介绍：你是谁、你能做什么等
- 情感交流：心情不好、好累、无聊等
- 日常闲聊：讲笑话、推荐电影、天气等
- 简短寒暄：在吗、干嘛呢等

## 工具使用场景
- 知识库文档列表：查看有哪些文档 → file_list
- 知识库文档内容：读取指定文档全文 → file_read（传入文档ID或名称）
- 知识库语义搜索：通过关键词搜索相关内容 → search_knowledge
- 网络搜索：实时信息、新闻、百科 → web_search
- 代码执行：计算、数据分析 → code_execute
- 外部集成：调用 API → http_request
- 图片处理：生成或分析图片 → image_generate / image_analyze
- 上下文回忆：回顾对话历史 → get_session_history

## 可用工具
- file_list(directory): 列出知识库中所有文档
- file_read(file_path, encoding): 读取知识库文档全文（传入文档ID或名称）
- search_knowledge(query, top_k): 语义搜索知识库内容
- web_search(query, num_results): 互联网搜索
- code_execute(code, language): 执行 Python 代码
- image_generate(prompt, size): 生成图片
- image_analyze(file_path, question): 分析图片
- http_request(url, method, headers, body, timeout): HTTP 请求
- get_session_history(session_id): 获取对话历史

## 核心原则
1. 闲聊直接回复，不调用工具
2. 需要外部信息或操作时才调用工具
3. 基于工具返回的事实回答，不编造
4. 复杂问题分步调用多个工具
5. 每次工具调用有明确目的
6. 一次回复工具调用不超过 3 个"""


class AgentService:
    """
    Agent 核心服务（ReAct 模式）

    核心职责：实现 ReAct（Reasoning + Acting）循环，让 LLM 自主调用工具完成任务。

    工作流程：
      1. 构建 messages（system prompt + 历史 + 用户问题）
      2. LLM 生成响应（可能是文本回复或工具调用请求）
      3. 如果 LLM 请求调用工具 → 执行工具 → 将结果追加到 messages → 回到步骤 2
      4. 如果 LLM 直接回复文本 → 结束循环，返回答案
      5. 最大迭代次数限制（AGENT_MAX_ITERATIONS），防止无限循环

    可用工具（通过 tool_registry 注册）：
      - file_list: 列出知识库文档
      - file_read: 读取文档全文
      - search_knowledge: 语义搜索知识库
      - web_search: 互联网搜索
      - code_execute: 执行 Python 代码
      - image_generate / image_analyze: 图片处理
      - http_request: HTTP 请求
      - get_session_history: 获取对话历史
    """

    def __init__(self):
        self.client = deepseek_client
        self.max_iterations = AGENT_MAX_ITERATIONS

    def _build_messages(
        self, query: str, history: List[dict]
    ) -> List[dict]:
        messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]

        if history:
            recent = history[-10:]
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant", "tool"):
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": query})
        return messages

    async def run(
        self,
        query: str,
        history: List[dict] = None,
        session_id: str = "",
    ) -> AsyncGenerator[dict, None]:
        history = history or []
        messages = self._build_messages(query, history)
        tools = tool_registry.get_all_schemas()
        iteration = 0
        full_response = ""
        all_sources = []

        while iteration < self.max_iterations:
            iteration += 1

            yield {
                "type": "thinking",
                "content": f"正在分析（第 {iteration} 轮）...",
            }

            try:
                result = await self.client.chat_completion_with_tools(
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=LLM_TEMPERATURE,
                    max_tokens=LLM_MAX_TOKENS,
                    timeout=60.0,
                )
            except Exception as e:
                yield {"type": "error", "content": f"LLM 调用失败: {e}"}
                return

            finish_reason = result.get("finish_reason", "")
            content = result.get("content", "")
            tool_calls = result.get("tool_calls")

            if tool_calls and finish_reason == "tool_calls":
                for tc in tool_calls:
                    tool_name = tc.get("function", {}).get("name", "")
                    arguments_str = tc.get("function", {}).get("arguments", "{}")

                    try:
                        arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                    except json.JSONDecodeError:
                        arguments = {}

                    if tool_name == "get_session_history" and "session_id" not in arguments:
                        arguments["session_id"] = session_id

                    yield {
                        "type": "tool_call",
                        "tool_name": tool_name,
                        "arguments": arguments,
                    }

                    tool_result = await tool_registry.execute(tool_name, arguments)

                    yield {
                        "type": "tool_result",
                        "tool_name": tool_name,
                        "result": tool_result[:800],
                    }

                    if tool_name in ("web_search", "search_knowledge"):
                        all_sources.append({
                            "content": tool_result,
                            "filename": tool_name,
                            "score": 1.0,
                        })

                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tc.get("id", f"call_{iteration}"),
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": arguments_str if isinstance(arguments_str, str) else json.dumps(arguments_str, ensure_ascii=False),
                                },
                            }
                        ],
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{iteration}"),
                        "content": tool_result,
                    })

                continue

            if content:
                full_response = content
                yield {
                    "type": "token",
                    "content": content,
                }
                break

            if finish_reason == "stop":
                break

            if finish_reason not in ("tool_calls", "stop") and not content:
                yield {
                    "type": "error",
                    "content": f"LLM 返回了意外的响应状态: finish_reason={finish_reason}, 已无内容可输出",
                }
                break

            yield {
                "type": "thinking",
                "content": f"第 {iteration} 轮未获得有效响应，继续尝试...",
            }

        yield {
            "type": "done",
            "content": full_response,
            "sources": all_sources,
        }

    async def run_streaming(
        self,
        query: str,
        history: List[dict] = None,
        session_id: str = "",
    ) -> AsyncGenerator[dict, None]:
        history = history or []
        messages = self._build_messages(query, history)
        tools = tool_registry.get_all_schemas()
        iteration = 0
        full_response = ""
        all_sources = []

        while iteration < self.max_iterations:
            iteration += 1

            yield {
                "type": "thinking",
                "content": f"正在分析（第 {iteration} 轮）...",
            }

            try:
                result = await self.client.chat_completion_with_tools(
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=LLM_TEMPERATURE,
                    max_tokens=LLM_MAX_TOKENS,
                    timeout=60.0,
                )
            except Exception as e:
                yield {"type": "error", "content": f"LLM 调用失败: {e}"}
                return

            finish_reason = result.get("finish_reason", "")
            content = result.get("content", "")
            tool_calls = result.get("tool_calls")

            if tool_calls and finish_reason == "tool_calls":
                for tc in tool_calls:
                    tool_name = tc.get("function", {}).get("name", "")
                    arguments_str = tc.get("function", {}).get("arguments", "{}")

                    try:
                        arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                    except json.JSONDecodeError:
                        arguments = {}

                    if tool_name == "get_session_history" and "session_id" not in arguments:
                        arguments["session_id"] = session_id

                    yield {
                        "type": "tool_call",
                        "tool_name": tool_name,
                        "arguments": arguments,
                    }

                    tool_result = await tool_registry.execute(tool_name, arguments)

                    yield {
                        "type": "tool_result",
                        "tool_name": tool_name,
                        "result": tool_result[:800],
                    }

                    if tool_name in ("web_search", "search_knowledge"):
                        all_sources.append({
                            "content": tool_result,
                            "filename": tool_name,
                            "score": 1.0,
                        })

                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tc.get("id", f"call_{iteration}"),
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": arguments_str if isinstance(arguments_str, str) else json.dumps(arguments_str, ensure_ascii=False),
                                },
                            }
                        ],
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{iteration}"),
                        "content": tool_result,
                    })

                continue

            if content:
                full_response = content
                yield {
                    "type": "token",
                    "content": content,
                }
                break

            if finish_reason == "stop":
                break

            if finish_reason not in ("tool_calls", "stop") and not content:
                yield {
                    "type": "error",
                    "content": f"LLM 返回了意外的响应状态: finish_reason={finish_reason}, 已无内容可输出",
                }
                break

            yield {
                "type": "thinking",
                "content": f"第 {iteration} 轮未获得有效响应，继续尝试...",
            }

        yield {
            "type": "done",
            "content": full_response,
            "sources": all_sources,
        }


agent_service = AgentService()
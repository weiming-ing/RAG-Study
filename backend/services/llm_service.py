from typing import AsyncGenerator, List, Optional

from config import LLM_TEMPERATURE, LLM_TOP_P, LLM_MAX_TOKENS
from utils.http_client import deepseek_client


KNOWLEDGE_SYSTEM_PROMPT = """你是一个专业的企业内部知识库智能客服助手。你的职责是帮助员工快速准确地获取企业内部文档中的信息。

## 核心规则
1. 优先使用参考资料：如果提供了参考资料，请基于参考资料回答问题
2. 自主回答兜底：如果没有提供参考资料，或参考资料不足以回答问题，则使用你自己的知识进行回答，但要明确说明这是基于通用知识的回答，而非企业内部信息
3. 明确引用来源：使用参考资料回答时，注明引用了哪个文档
4. 诚实透明：如果参考资料和你的知识都无法回答，请明确告知用户
5. 专业简洁：使用专业但易懂的语言，保持回答清晰有条理
6. 中文回答：始终使用中文回答

## 回答格式
- 先给出核心答案
- 再列出关键要点（如有必要）
- 有参考资料时注明信息来源；无参考资料时标注"基于通用知识"

## 特殊情况处理
- 如果用户打招呼或闲聊，友好回应
- 如果多个参考资料存在矛盾，指出矛盾并建议用户核实"""

CHAT_SYSTEM_PROMPT = """你是一个友好、热心的AI助手。你可以自由地与用户进行对话，回答各种问题。

## 你的特点
- 友善热情：用温暖、亲切的语气与用户交流
- 知识渊博：你可以回答各种领域的问题，包括科学、技术、生活、文化等
- 诚实透明：不知道的事情会坦诚说明，不会编造信息
- 简洁清晰：回答简洁明了，避免冗长
- 中文交流：始终使用中文回答

## 回答风格
- 先给出核心答案
- 如有必要，再展开说明
- 适当使用表情符号让对话更生动（但不要过度使用）"""


class LLMService:
    def __init__(self):
        self.client = deepseek_client

    def _build_messages(
        self, query: str, context: str, history: List[dict], system_prompt: str = None
    ) -> List[dict]:
        if system_prompt is None:
            system_prompt = KNOWLEDGE_SYSTEM_PROMPT
        messages = [{"role": "system", "content": system_prompt}]

        if history:
            recent = history[-6:]
            for msg in recent:
                messages.append({"role": msg["role"], "content": msg["content"]})

        user_content = ""
        if context.strip():
            user_content += f"## 参考资料\n{context}\n\n"
        user_content += f"## 用户问题\n{query}"

        messages.append({"role": "user", "content": user_content})
        return messages

    async def generate(
        self, query: str, context: str, history: List[dict], system_prompt: str = None
    ) -> AsyncGenerator[str, None]:
        messages = self._build_messages(query, context, history, system_prompt)
        async for token in self.client.chat_completion_stream(
            messages=messages,
            temperature=LLM_TEMPERATURE,
            top_p=LLM_TOP_P,
            max_tokens=LLM_MAX_TOKENS,
        ):
            yield token

    async def check_health(self) -> bool:
        return await self.client.check_health()


llm_service = LLMService()
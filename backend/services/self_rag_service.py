import json
from typing import List, Optional, Dict

from config import ENABLE_SELF_RAG, SELF_RAG_CONFIDENCE_THRESHOLD
from utils.http_client import deepseek_client

VERIFY_PROMPT = """你是一个事实核查员。请验证以下 AI 生成的回答是否得到了参考资料的支持。

## 参考资料
{sources_text}

## AI 回答
{answer}

## 验证要求
1. 检查回答中的每个关键事实是否能在参考资料中找到依据
2. 如果回答引用了资料中没有的信息，标记为"无依据"
3. 如果回答与参考资料矛盾，标记为"矛盾"
4. 给出整体可信度评分（0.0-1.0）

请以 JSON 格式输出：
{{"confidence": 0.85, "issues": ["问题1", "问题2"], "verdict": "supported/partially_supported/unsupported"}}

只输出 JSON，不要其他内容。"""


class SelfRAGService:
    """Self-RAG 反思机制：验证生成的答案是否基于事实"""

    def __init__(self):
        self._enabled = ENABLE_SELF_RAG

    async def verify(
        self, answer: str, sources: List[dict]
    ) -> Optional[Dict]:
        """验证答案的事实依据，返回验证结果"""
        if not self._enabled:
            return None

        if not sources or not answer.strip():
            return None

        # 答案太短跳过验证
        if len(answer.strip()) < 20:
            return None

        try:
            return await self._llm_verify(answer, sources)
        except Exception as e:
            print(f"[SELF-RAG] 验证失败: {e}")
            return None

    async def _llm_verify(
        self, answer: str, sources: List[dict]
    ) -> Dict:
        """使用 LLM 验证答案"""
        sources_text = self._format_sources(sources)
        prompt = VERIFY_PROMPT.format(sources_text=sources_text, answer=answer)

        result_text = await deepseek_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=300,
            timeout=30.0,
        )

        return self._parse_verification(result_text or "")

    def _format_sources(self, sources: List[dict]) -> str:
        parts = []
        for i, src in enumerate(sources[:5], 1):
            content = src.get("content", "")[:500]
            filename = src.get("filename", "未知")
            parts.append(f"[资料{i}] 来源: {filename}\n{content}")
        return "\n\n".join(parts)

    def _parse_verification(self, text: str) -> Dict:
        """解析 LLM 返回的验证 JSON"""
        try:
            # 尝试提取 JSON 块
            import re
            match = re.search(r'\{[^}]+\}', text, re.DOTALL)
            if match:
                result = json.loads(match.group())
                return {
                    "confidence": float(result.get("confidence", 0.5)),
                    "issues": result.get("issues", []),
                    "verdict": result.get("verdict", "unknown"),
                }
        except (json.JSONDecodeError, ValueError, AttributeError):
            pass

        return {
            "confidence": 0.5,
            "issues": [],
            "verdict": "unknown",
        }

    def build_warning(self, verification: Dict) -> str:
        """根据验证结果生成警告信息"""
        if not verification:
            return ""

        confidence = verification.get("confidence", 0)
        verdict = verification.get("verdict", "")
        issues = verification.get("issues", [])

        if confidence >= 0.8:
            return ""

        if verdict == "unsupported" or confidence < SELF_RAG_CONFIDENCE_THRESHOLD:
            warning = "\n\n---\n⚠️ **事实核查提醒**：以上回答的可信度较低"
            if issues:
                warning += "\n- " + "\n- ".join(issues)
            warning += "\n建议核实原始文档或重新提问。"
            return warning

        if verdict == "partially_supported" or confidence < 0.7:
            warning = "\n\n---\n⚠️ **注意**：部分内容可能缺乏充分的资料支持"
            if issues:
                warning += "\n- " + "\n- ".join(issues)
            return warning

        return ""


self_rag_service = SelfRAGService()
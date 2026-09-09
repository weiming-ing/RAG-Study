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

VERIFY_AND_REFLECT_PROMPT = """你是一个事实核查员兼检索质量评估员。请完成以下三项任务：

## 原始问题
{question}

## 参考资料
{sources_text}

## AI 回答
{answer}

## 任务
1. **事实核查**：检查回答中的每个关键事实是否能在参考资料中找到依据。如果回答引用了资料中没有的信息，标记为"无依据"；如果回答与参考资料矛盾，标记为"矛盾"。
2. **检索质量评估**：判断参考资料是否足以回答原始问题。考虑：资料是否覆盖了问题的核心方面？是否存在明显的信息缺口？如果回答大量依赖 LLM 自身知识而非参考资料，说明检索不充分。
3. **查询改写**：如果检索不充分，基于原始问题和信息缺口，生成一个更精准的搜索查询来获取缺失的信息。

请以 JSON 格式输出：
{{"confidence": 0.85, "issues": ["问题1"], "verdict": "supported/partially_supported/unsupported", "needs_retrieval": false, "retrieval_gap": "缺失了XX方面的信息", "reformulated_query": "改写后的查询词"}}

字段说明：
- confidence: 答案可信度（0.0-1.0），基于事实核查结果
- verdict: 判定结果（supported / partially_supported / unsupported）
- issues: 发现的事实问题列表
- needs_retrieval: 布尔值，如果参考资料明显不足以回答原始问题，设为 true
- retrieval_gap: 简要描述参考资料缺失了哪些关键信息（仅 needs_retrieval=true 时填写）
- reformulated_query: 改写后的搜索查询，不超过50字（仅 needs_retrieval=true 时填写）

只输出 JSON，不要其他内容。"""


class SelfRAGService:
    """
    Self-RAG 反思验证服务（v2 — 完整闭环）

    核心职责：
      1. 事实核查：验证 LLM 答案是否得到参考资料的事实支持
      2. 检索质量评估：判断参考资料是否足以回答原始问题
      3. 查询改写：当检索不充分时，生成更精准的搜索查询
      4. 补充检索闭环：触发重新检索 → 重新生成 → 反馈用户

    验证流程：
      1. verify(): 对答案进行事实核查（兼容旧接口，仅核查不评估检索质量）
      2. verify_with_reflection(): 完整验证（事实核查 + 检索质量评估 + 查询改写）
      3. _llm_verify_with_reflection(): 使用 LLM 完成三项任务
      4. _parse_verification(): 解析 LLM 返回的 JSON 验证结果
      5. build_warning(): 根据验证结果生成用户可见的警告信息

    验证结果：
      - confidence: 可信度评分（0.0-1.0）
      - verdict: 判定结果（supported / partially_supported / unsupported）
      - issues: 发现的事实问题列表
      - needs_retrieval: 是否需要补充检索（新增）
      - retrieval_gap: 信息缺口描述（新增）
      - reformulated_query: 改写后的查询（新增）

    警告触发条件：
      - confidence < 阈值（默认 0.5）：显示"可信度较低"警告
      - needs_retrieval == true：触发补充检索 → 重新生成答案
    """

    def __init__(self):
        self._enabled = ENABLE_SELF_RAG

    async def verify(
        self, answer: str, sources: List[dict]
    ) -> Optional[Dict]:
        """验证答案的事实依据，返回验证结果（兼容旧接口）"""
        if not self._enabled:
            return None

        if not sources or not answer.strip():
            return None

        if len(answer.strip()) < 20:
            return None

        try:
            return await self._llm_verify(answer, sources)
        except Exception as e:
            print(f"[SELF-RAG] 验证失败: {e}")
            return None

    async def verify_with_reflection(
        self, answer: str, sources: List[dict], question: str
    ) -> Optional[Dict]:
        """
        完整 Self-RAG 验证：事实核查 + 检索质量评估 + 查询改写

        与 verify() 的区别：
          - 额外传入原始问题 question，用于评估检索是否充分
          - 返回 needs_retrieval / retrieval_gap / reformulated_query
          - 当 needs_retrieval=true 时，调用方应触发补充检索
        """
        if not self._enabled:
            return None

        if not sources or not answer.strip():
            return None

        if len(answer.strip()) < 20:
            return None

        try:
            return await self._llm_verify_with_reflection(answer, sources, question)
        except Exception as e:
            print(f"[SELF-RAG] 反思验证失败: {e}")
            return None

    async def _llm_verify(
        self, answer: str, sources: List[dict]
    ) -> Dict:
        """使用 LLM 验证答案（仅事实核查）"""
        sources_text = self._format_sources(sources)
        prompt = VERIFY_PROMPT.format(sources_text=sources_text, answer=answer)

        result_text = await deepseek_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=300,
            timeout=30.0,
        )

        return self._parse_verification(result_text or "")

    async def _llm_verify_with_reflection(
        self, answer: str, sources: List[dict], question: str
    ) -> Dict:
        """使用 LLM 完成三项任务：事实核查 + 检索质量评估 + 查询改写"""
        sources_text = self._format_sources(sources)
        prompt = VERIFY_AND_REFLECT_PROMPT.format(
            sources_text=sources_text, answer=answer, question=question
        )

        result_text = await deepseek_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=500,
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
        """解析 LLM 返回的验证 JSON，兼容新旧两种格式"""
        try:
            import re
            match = re.search(r'\{[^}]+\}', text, re.DOTALL)
            if match:
                result = json.loads(match.group())
                return {
                    "confidence": float(result.get("confidence", 0.5)),
                    "issues": result.get("issues", []),
                    "verdict": result.get("verdict", "unknown"),
                    "needs_retrieval": bool(result.get("needs_retrieval", False)),
                    "retrieval_gap": result.get("retrieval_gap", ""),
                    "reformulated_query": result.get("reformulated_query", ""),
                }
        except (json.JSONDecodeError, ValueError, AttributeError):
            pass

        return {
            "confidence": 0.5,
            "issues": [],
            "verdict": "unknown",
            "needs_retrieval": False,
            "retrieval_gap": "",
            "reformulated_query": "",
        }

    def build_warning(self, verification: Dict) -> str:
        """根据验证结果生成用户可见的警告信息"""
        if not verification:
            return ""

        confidence = verification.get("confidence", 0)
        verdict = verification.get("verdict", "")
        issues = verification.get("issues", [])
        needs_retrieval = verification.get("needs_retrieval", False)
        retrieval_gap = verification.get("retrieval_gap", "")

        if confidence >= 0.8 and not needs_retrieval:
            return ""

        if needs_retrieval:
            warning = "\n\n---\n⚠️ **事实核查提醒**：初始回答的参考资料不够充分"
            if retrieval_gap:
                warning += f"（{retrieval_gap}）"
            if issues:
                warning += "\n- " + "\n- ".join(issues)
            warning += "\n已自动补充检索并生成改进回答。"
            return warning

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
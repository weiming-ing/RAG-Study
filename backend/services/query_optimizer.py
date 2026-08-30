import re
from typing import List, Optional

from config import ENABLE_LLM_QUERY_REWRITE
from utils.http_client import deepseek_client

QUERY_REWRITE_PROMPT = """你是一个 RAG 检索系统的查询改写器。你的任务是将用户的口语化问题改写为更适合向量检索的关键词查询。

规则：
1. 提取核心关键词和概念，去除冗余的礼貌用语
2. 展开缩写词，消解指代词（结合历史对话上下文）
3. 如果问题包含多个子问题，请拆分为多个独立查询
4. 只输出改写后的查询（每行一个），不要输出任何解释

用户问题：{query}
历史对话：{history}

改写后的查询（每行一个）："""


class QueryOptimizer:
    """
    查询优化器：改写用户问题以提高检索召回率

    核心职责：对用户口语化问题进行改写，提高检索命中率。

    两种模式：
      1. 规则改写（_rule_rewrite）：去停用词 → 指代消解 → 提取核心关键词 → 增强查询
      2. LLM 改写（_llm_rewrite）：使用 DeepSeek 改写为多个检索友好的查询变体

    优化策略：
      - optimize(): 同步版本，仅使用规则
      - optimize_async(): 异步版本，优先 LLM 改写 → 失败回退规则改写
    """

    # 常见停用词
    STOP_WORDS = {
        "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一",
        "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
        "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些",
        "什么", "怎么", "如何", "为什么", "哪个", "哪里", "可以", "吗", "呢",
        "吧", "啊", "哦", "嗯", "哈", "呀", "请", "问", "请问", "帮", "帮忙",
    }

    # 问题模式 -> 搜索关键词提取
    QUESTION_PATTERNS = [
        (r"什么是(.+?)[?？]?$", r"\1 定义 概念"),
        (r"如何(.+?)[?？]?$", r"\1 方法 步骤"),
        (r"怎么(.+?)[?？]?$", r"\1 方法 步骤"),
        (r"(.+?)是什么[?？]?$", r"\1 定义"),
        (r"(.+?)怎么写[?？]?$", r"\1 模板 格式"),
        (r"(.+?)的流程[?？]?$", r"\1 流程 步骤"),
        (r"(.+?)的规定[?？]?$", r"\1 规定 制度"),
    ]

    def __init__(self):
        self._llm_enabled = ENABLE_LLM_QUERY_REWRITE

    def optimize(self, query: str, history: List[dict] = None) -> str:
        """
        优化查询语句（同步版本，仅使用规则）：
        1. 去除冗余的礼貌用语和停用词
        2. 根据问题模式提取核心关键词
        3. 结合历史对话做指代消解
        """
        return self._rule_rewrite(query, history)

    async def optimize_async(self, query: str, history: List[dict] = None) -> str:
        """
        优化查询语句（异步版本，优先使用 LLM 改写）：
        1. 先用 LLM 改写查询
        2. 如果 LLM 失败，回退到规则改写
        """
        if self._llm_enabled:
            try:
                llm_result = await self._llm_rewrite(query, history)
                if llm_result and len(llm_result) > 5:
                    return llm_result
            except Exception:
                pass
        return self._rule_rewrite(query, history)

    def _rule_rewrite(self, query: str, history: List[dict] = None) -> str:
        """规则改写：提取核心关键词 + 增强查询"""
        original = query.strip()

        # 指代消解：如果当前问题是简短的指代词，结合历史补充
        if history and len(original) <= 10:
            original = self._resolve_reference(original, history)

        # 提取核心查询
        core = self._extract_core_query(original)

        # 如果是 question 模式，生成增强查询
        enhanced = self._enhance_query(original)

        if enhanced != original:
            return f"{original} {enhanced}"
        return original

    async def _llm_rewrite(self, query: str, history: List[dict] = None) -> Optional[str]:
        """使用 LLM 改写查询，生成多个检索友好的查询变体"""
        history_text = "无"
        if history:
            recent = history[-3:]
            history_text = "\n".join(
                f"{'用户' if h['role'] == 'user' else '助手'}: {h['content']}"
                for h in recent
            )

        prompt = QUERY_REWRITE_PROMPT.format(query=query, history=history_text)

        rewritten = await deepseek_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
            timeout=30.0,
        )

        if not rewritten:
            return None

        lines = [line.strip() for line in rewritten.strip().split("\n") if line.strip()]
        merged = " ".join(lines)
        if len(merged) < 5:
            return None
        return merged

    def _resolve_reference(self, query: str, history: List[dict]) -> str:
        """指代消解：如 '它是什么' → 结合上文补全"""
        reference_words = {"它", "他", "她", "这个", "那个", "这些", "那些", "这", "那"}
        if any(w in query for w in reference_words) and history:
            for msg in reversed(history):
                if msg["role"] == "user":
                    prev = msg["content"]
                    return f"{prev} {query}"
        return query

    def _extract_core_query(self, query: str) -> str:
        """去除停用词和礼貌用语，提取核心查询"""
        # 去除常见前缀
        prefixes = ["请问", "我想问", "我想知道", "请告诉我", "帮我查一下", "帮我查查"]
        for prefix in prefixes:
            if query.startswith(prefix):
                query = query[len(prefix):]
                break

        # 去除常见后缀
        suffixes = ["谢谢", "感谢", "麻烦了", "拜托了", "可以吗", "行吗"]
        for suffix in suffixes:
            if query.endswith(suffix):
                query = query[:-len(suffix)]
                break

        return query.strip()

    def _enhance_query(self, query: str) -> str:
        """根据问题模式添加增强关键词"""
        for pattern, replacement in self.QUESTION_PATTERNS:
            match = re.match(pattern, query)
            if match:
                expanded = re.sub(pattern, replacement, query)
                return expanded
        return query


query_optimizer = QueryOptimizer()
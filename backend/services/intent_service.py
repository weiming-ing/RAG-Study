import json
from typing import List, Optional

from config import ENABLE_INTENT_ROUTING
from utils.http_client import deepseek_client

INTENT_PROMPT = """分析用户意图，严格从以下三类中选择一个：

- chat: 闲聊、打招呼、问候、感谢、无实质信息需求
- knowledge: 需要查询知识库获取信息（如询问流程、制度、规定、操作指南等）
- action: 需要执行具体操作（如"查统计"、"列出所有文档"、"搜索xx"、"导出"等）

用户问题：{query}
历史对话：{history}

意图（只输出一个词，不要解释）："""


class IntentService:
    """
    意图识别与路由分发服务

    核心职责：分析用户输入，分类为三类意图之一，决定后续处理流程。

    意图类型：
      - chat: 闲聊（打招呼、感谢、情感交流等）→ 直接回复，不检索知识库
      - knowledge: 知识问答（询问流程、制度、规定等）→ 走 RAG 检索管线
      - action: 操作执行（统计、导出、文档列表等）→ 走 Agent 工具调用

    分类策略：
      - _quick_classify(): 基于规则快速匹配（前缀匹配、关键词匹配、长度判断），命中则跳过 LLM
      - _llm_classify(): 使用 LLM 做精确分类（仅规则未命中时调用）
    """

    def __init__(self):
        self._enabled = ENABLE_INTENT_ROUTING

    async def classify(self, query: str, history: List[dict] = None) -> str:
        """分类用户意图 → chat / knowledge / action（先规则快速匹配，未命中则 LLM 分类）"""
        if not self._enabled:
            return "knowledge"

        # 快速规则判断（避免不必要的 LLM 调用）
        quick = self._quick_classify(query)
        if quick:
            return quick

        # LLM 细分类
        try:
            return await self._llm_classify(query, history)
        except Exception:
            return "knowledge"

    def _quick_classify(self, query: str) -> Optional[str]:
        """快速规则分类，命中则跳过 LLM 调用"""
        q = query.strip().lower()

        # 闲聊关键词（前缀匹配）
        chat_prefixes = [
            "你好", "hi", "hello", "嗨", "早上好", "下午好", "晚上好",
            "谢谢", "感谢", "再见", "拜拜", "bye", "你是谁", "你能做什么",
            "你叫什么", "在吗", "在不在", "你叫什么名字",
            "聊天", "闲聊", "陪我", "讲个", "说个",
        ]
        for p in chat_prefixes:
            if q.startswith(p):
                return "chat"

        # 闲聊关键词（子串匹配）
        chat_keywords = [
            "笑话", "故事", "天气", "心情", "无聊", "干嘛", "在干嘛",
            "累了", "好累", "不错", "真好", "真棒", "厉害",
            "哈哈", "嘿嘿", "呵呵",
        ]
        for kw in chat_keywords:
            if kw in q:
                return "chat"

        # 短问题（≤8字且无实质内容关键词）判定为闲聊
        if len(q) <= 8:
            knowledge_keywords = ["怎么", "如何", "什么", "流程", "规定", "制度", "报销",
                                   "请假", "考勤", "入职", "转正", "IT", "故障", "保密",
                                   "文档", "下载", "安装", "配置", "申请", "审批"]
            if not any(kw in q for kw in knowledge_keywords):
                return "chat"

        # 操作模式
        action_patterns = [
            "统计", "列出文档", "所有文档", "有几个文档", "多少文档",
            "导出", "导出对话", "导出聊天",
        ]
        for p in action_patterns:
            if p in q:
                return "action"

        return None

    async def _llm_classify(self, query: str, history: List[dict] = None) -> str:
        """使用 LLM 进行意图分类"""
        history_text = "无"
        if history:
            recent = history[-3:]
            history_text = "\n".join(
                f"{'用户' if h['role'] == 'user' else '助手'}: {h['content']}"
                for h in recent
            )

        prompt = INTENT_PROMPT.format(query=query, history=history_text)

        result = await deepseek_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10,
            timeout=15.0,
        )

        if not result:
            return "knowledge"

        result = result.strip().lower()
        if result in ("chat", "knowledge", "action"):
            return result
        return "knowledge"

    async def handle_action(self, query: str, history: List[dict] = None) -> str:
        """处理操作类请求，返回执行结果"""
        # knowledge_base_service 已迁移至 Java 后端
        # from services.knowledge_base import knowledge_base_service

        q = query.strip()

        # 知识库操作已迁移至 Java 后端
        # if "统计" in q:
        #     stats = knowledge_base_service.get_statistics()
        #     ...
        # if "列出文档" in q or "所有文档" in q or "文档列表" in q:
        #     docs = knowledge_base_service.get_documents()
        #     ...

        return f"收到操作请求：{query}\n知识库操作已迁移至 Java 后端，请使用 Java 后端 API"


intent_service = IntentService()
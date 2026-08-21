from services.session_service import session_service
from services.rag_service import rag_service


async def _get_session_history(session_id: str) -> str:
    history = await session_service.get_history(session_id)
    if not history:
        return "当前会话暂无历史记录。"
    recent = history[-6:]
    lines = ["最近对话记录:"]
    for h in recent:
        role = "用户" if h["role"] == "user" else "助手"
        content = h["content"][:100]
        lines.append(f"- {role}: {content}")
    return "\n".join(lines)


async def _search_knowledge(query: str, top_k: int = 5) -> str:
    sources = await rag_service.retrieve(query, top_k=top_k, use_hybrid=True)
    if not sources:
        return "未在知识库中找到相关内容。"
    lines = [f"知识库检索结果（共 {len(sources)} 条）:"]
    for i, src in enumerate(sources, 1):
        filename = src.get("filename", "未知文档")
        score = src.get("score", 0)
        content = src.get("content", "")[:500]
        lines.append(f"\n[来源 {i}] {filename} (相关度: {score:.2f})")
        lines.append(content)
    return "\n".join(lines)
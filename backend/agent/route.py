import json
import time
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse

from models.schemas import ChatRequest
from agent.core import agent_service
from agent.tool_registry import tool_registry
from services.session_service import session_service
from routes.auth import get_current_user
from routes.chat import _record_audit, _save_conversation
from routes.dashboard import record_api_call, record_doc_hit, record_token_usage

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat")
async def agent_chat(request: ChatRequest, raw_request: Request, current_user: dict = Depends(get_current_user)):
    session_id = request.session_id
    query = request.message.strip()
    if not query:
        raise HTTPException(status_code=400, detail="消息不能为空")

    # 获取 JWT token 用于调用 Java 后端
    auth_header = raw_request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header else ""

    username = current_user.get("username", "unknown")
    user_id = current_user.get("id")

    await session_service.add_message(session_id, "user", query)
    await session_service.update_title(session_id, query)

    # 记录审计日志
    await _record_audit(user_id, username, "QUERY", f"发送问题: {query[:100]}", target_name=session_id, token=token)

    history = await session_service.get_history(session_id)
    history_for_llm = [
        {"role": h["role"], "content": h["content"]}
        for h in history[:-1]
    ]

    async def generate():
        t_start = time.time()
        full_response = ""
        sources = []
        agent_error = False
        try:
            async for event in agent_service.run_streaming(
                query=query,
                history=history_for_llm,
                session_id=session_id,
            ):
                event_type = event.get("type", "")
                event_json = json.dumps(event, ensure_ascii=False)

                if event_type == "token":
                    full_response += event.get("content", "")
                elif event_type == "done":
                    full_response = event.get("content", full_response)
                    sources = event.get("sources", [])

                yield event_json + "\n"

        except Exception as e:
            agent_error = True
            yield json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False) + "\n"

        await session_service.add_message(session_id, "assistant", full_response, sources)
        await _save_conversation(session_id, user_id, query, full_response, sources, token=token)

        # 记录统计数据到管理平台大盘
        latency_ms = (time.time() - t_start) * 1000
        kb_id_str = request.kb_id if hasattr(request, 'kb_id') and request.kb_id else ""
        await record_api_call(kb_id_str, "/api/agent/chat", not agent_error, latency_ms)

        if sources:
            for s in sources[:20]:
                doc_id = s.get("document_id", s.get("doc_id", "unknown"))
                doc_name = s.get("document_name", s.get("title", s.get("source", "未知文档")))
                await record_doc_hit(str(doc_id), str(doc_name), kb_id_str)

        estimated_prompt = len(query + str(history_for_llm)) // 4
        estimated_completion = len(full_response) // 4
        await record_token_usage(kb_id_str, user_id, estimated_prompt, estimated_completion)

        yield json.dumps({"type": "finished", "content": "", "done": True}, ensure_ascii=False) + "\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/tools")
async def list_tools():
    return {
        "tools": [
            {
                "name": name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for name, tool in tool_registry._tools.items()
        ]
    }
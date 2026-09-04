import json
import os
import time
import asyncio
import httpx
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse

from models.schemas import ChatRequest, GuestChatRequest
from services.llm_service import llm_service, KNOWLEDGE_SYSTEM_PROMPT
from services.session_service import session_service
from services.self_rag_service import self_rag_service
from services.rag_service import rag_service
from services.query_optimizer import query_optimizer
from routes.auth import get_current_user
from routes.dashboard import record_api_call, record_doc_hit, record_token_usage

JAVA_BACKEND = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")

router = APIRouter(prefix="/api/chat", tags=["chat"])

"""
对话路由模块 — RAG 核心链路

核心对话流程（/api/chat POST）：
  1. [并行] 保存用户消息 → session_service.add_message()
  2. [并行] 记录审计日志 → _record_audit()
  3. [并行] 获取历史对话 → session_service.get_history()
  4. 查询优化 → query_optimizer.optimize_async()（规则改写，毫秒级）
  5. 知识检索 → rag_service.retrieve()
  6. 构建上下文 → rag_service.build_context()
  7. LLM 流式生成 → llm_service.generate()（SSE 流式返回）
  8. [异步] Self-RAG 验证 → self_rag_service.verify()（后台执行，不阻塞响应）
  9. 保存助手消息 → session_service.add_message()
  10. 保存对话记录 → _save_conversation()
  11. 记录统计数据 → record_api_call / record_doc_hit / record_token_usage
"""


async def _verify_and_log(full_response: str, sources: list):
    """后台异步验证：Self-RAG 事实核查，不阻塞 SSE 响应"""
    try:
        verification = await self_rag_service.verify(full_response, sources)
        if verification:
            warning = self_rag_service.build_warning(verification)
            if warning:
                print(f"[SELF-RAG] 验证警告: {warning[:200]}")
    except Exception as e:
        print(f"[SELF-RAG] 验证失败: {e}")


async def _record_audit(user_id: int, username: str, operation: str, detail: str, target_name: str = "", ip_address: str = "", result: str = "SUCCESS", token: str = ""):
    """记录审计日志到 Java 后端（异步，失败不影响主流程）"""
    try:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{JAVA_BACKEND}/api/audit-logs",
                json={
                    "userId": user_id,
                    "username": username,
                    "operation": operation,
                    "detail": detail,
                    "targetName": target_name,
                    "ipAddress": ip_address,
                    "result": result,
                },
                headers=headers,
            )
    except Exception as e:
        print(f"[_record_audit] 审计日志记录失败: {e}")


async def _save_conversation(session_id: str, user_id: int, question: str, answer: str, sources: list = None, kb_id: str = None, token: str = ""):
    """保存对话记录到 Java 后端（含 chunk_id 引用列表，失败不影响主流程）
    
    存储格式: [{"chunkId": "42_child_15", "docName": "报销管理制度.pdf"}, ...]
    实现对话→切片→文档的完整精确追溯，消除同名歧义。
    
    返回: conversation_id (int) 或 None
    """
    try:
        referenced = ""
        if sources:
            chunk_refs = []
            seen = set()
            for s in sources:
                chunk_id = s.get("chunk_id", "")
                doc_name = s.get("filename", s.get("document_name", s.get("title", s.get("source", ""))))
                # 用 chunk_id 去重（如果没有 chunk_id 则用 doc_name 去重）
                dedup_key = chunk_id or doc_name
                if dedup_key and dedup_key not in seen:
                    seen.add(dedup_key)
                    chunk_refs.append({
                        "chunkId": chunk_id,
                        "docName": doc_name
                    })
            referenced = json.dumps(chunk_refs, ensure_ascii=False)

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{JAVA_BACKEND}/api/conversations/save-or-update",
                json={
                    "sessionId": session_id,
                    "userId": user_id,
                    "question": question,
                    "answer": answer,
                    "referencedChunks": referenced,
                    "kbId": kb_id or "",
                    "status": "COMPLETED",
                },
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                # Java 后端返回 {code: 0, message: "success", data: {id: ...}} 格式
                if data.get("code") == 0 and data.get("data", {}).get("id"):
                    return data["data"]["id"]
            else:
                print(f"[_save_conversation] 保存失败: HTTP {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"[_save_conversation] 保存对话失败: {e}")
    return None


@router.post("")
async def chat(request: ChatRequest, raw_request: Request, current_user: dict = Depends(get_current_user)):
    """
    RAG 对话核心接口（SSE 流式响应）

    完整流程：
      前置（并行）：保存用户消息 → 审计日志 → 获取历史 → 查询优化 → 知识检索 → 构建上下文
      SSE 流（异步生成器）：LLM 流式输出 → Self-RAG 验证 → 保存助手消息 → 保存对话记录 → 统计记录
    """
    session_id = request.session_id
    query = request.message.strip()
    if not query:
        raise HTTPException(status_code=400, detail="消息不能为空")

    # 获取 JWT token 用于调用 Java 后端
    auth_header = raw_request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header else ""

    username = current_user.get("username", "unknown")
    user_id = current_user.get("id")

    # 前置步骤并行化：保存消息、审计日志、获取历史互不依赖，同时执行
    async def _save_user_message():
        try:
            await session_service.add_message(session_id, "user", query)
            await session_service.update_title(session_id, query)
        except Exception as e:
            print(f"[chat] session_service 错误: {e}")

    save_task = asyncio.create_task(_save_user_message())
    audit_task = asyncio.create_task(
        _record_audit(user_id, username, "QUERY", f"发送问题: {query[:100]}", target_name=session_id, token=token)
    )
    history_task = asyncio.create_task(session_service.get_history(session_id))

    history = await history_task
    history = history or []
    history_for_llm = [
        {"role": h["role"], "content": h["content"]}
        for h in history[:-1]
    ] if history else []

    # 查询优化（规则改写，毫秒级）+ 知识检索
    sources = []
    context = ""
    try:
        optimized_query = await query_optimizer.optimize_async(query, history) if query_optimizer else query
        sources = await rag_service.retrieve(optimized_query, use_hybrid=True) or []
        context = rag_service.build_context(sources) if sources else ""
    except Exception as e:
        print(f"[chat] 检索/历史记录错误: {e}")

    # 确保 save 和 audit 任务完成（不阻塞，仅做异常捕获）
    try:
        await save_task
    except Exception:
        pass
    try:
        await audit_task
    except Exception:
        pass

    async def generate():
        t_start = time.time()
        full_response = ""
        llm_error = False
        try:
            yield json.dumps({"status": "start", "mode": "rag"}, ensure_ascii=False) + "\n"
            async for llm_token in llm_service.generate(query, context, history_for_llm, KNOWLEDGE_SYSTEM_PROMPT):
                full_response += llm_token
                yield json.dumps({"token": llm_token, "done": False, "mode": "rag"}, ensure_ascii=False) + "\n"
        except Exception as e:
            llm_error = True
            error_msg = f"\n\n[生成出错: {str(e)}]"
            full_response += error_msg
            yield json.dumps({"token": error_msg, "done": False}, ensure_ascii=False) + "\n"

        if sources:
            asyncio.create_task(_verify_and_log(full_response, sources))

        await session_service.add_message(session_id, "assistant", full_response, sources)
        conv_id = await _save_conversation(session_id, user_id, query, full_response, sources, token=token)

        # 记录统计数据到管理平台大盘
        latency_ms = (time.time() - t_start) * 1000
        kb_id_str = request.kb_id if hasattr(request, 'kb_id') and request.kb_id else ""
        await record_api_call(kb_id_str, "/api/chat", not llm_error, latency_ms)

        if sources:
            for s in sources[:20]:
                doc_id = s.get("document_id", s.get("doc_id", "unknown"))
                doc_name = s.get("filename", s.get("document_name", s.get("title", s.get("source", "未知文档"))))
                await record_doc_hit(str(doc_id), str(doc_name), kb_id_str)

        estimated_prompt = len(query + context + str(history_for_llm)) // 4
        estimated_completion = len(full_response) // 4
        await record_token_usage(kb_id_str, user_id, estimated_prompt, estimated_completion)

        yield json.dumps({"token": "", "done": True, "sources": sources, "mode": "rag", "conversation_id": conv_id}, ensure_ascii=False) + "\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/health")
async def health_check():
    ollama_ok = await llm_service.check_health()
    return {"ollama": ollama_ok, "kb_chunks": 0}


@router.post("/test-stream")
async def test_stream(request: ChatRequest, raw_request: Request, current_user: dict = Depends(get_current_user)):
    """测试流式响应"""
    session_id = request.session_id
    query = request.message.strip()

    print(f"[test-stream] session_id={session_id}, query={query}")

    async def generate():
        try:
            yield json.dumps({"status": "start"}, ensure_ascii=False) + "\n"
            async for token in llm_service.generate(query, "", [], KNOWLEDGE_SYSTEM_PROMPT):
                yield json.dumps({"token": token, "done": False}, ensure_ascii=False) + "\n"
        except Exception as e:
            print(f"[test-stream] 生成错误: {e}")
            yield json.dumps({"token": f"\n\n[生成出错: {str(e)}]", "done": False}, ensure_ascii=False) + "\n"
        yield json.dumps({"token": "", "done": True}, ensure_ascii=False) + "\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/guest")
async def guest_chat(request: GuestChatRequest):
    query = request.message.strip()
    if not query:
        raise HTTPException(status_code=400, detail="消息不能为空")

    async def generate():
        try:
            async for token in llm_service.generate(query, "", [], KNOWLEDGE_SYSTEM_PROMPT):
                yield json.dumps({"token": token, "done": False}, ensure_ascii=False) + "\n"
            yield json.dumps({"token": "", "done": True}, ensure_ascii=False) + "\n"
        except Exception as e:
            yield json.dumps({"token": f"\n\n[生成出错: {str(e)}]", "done": True}, ensure_ascii=False) + "\n"

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
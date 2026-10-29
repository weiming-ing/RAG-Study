import json
import os
import time
import asyncio
import hashlib
import re
import httpx
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse

from models.schemas import ChatRequest, GuestChatRequest
from services.llm_service import llm_service, KNOWLEDGE_SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT
from services.session_service import session_service
from services.self_rag_service import self_rag_service
from services.rag_service import rag_service
from services.query_optimizer import query_optimizer
from services.semantic_cache import semantic_cache
from services import kb_access
from routes.auth import get_current_user, get_user_or_api_key
from routes.dashboard import record_batch
from utils import java_http
from utils.internal_api import internal_headers
from utils.runtime_config import get_config_bool, get_config_int
from config import (
    SELF_RAG_VERIFY_TIMEOUT, SELF_RAG_MODE, LLM_BASE_URL,
    GUEST_KB_IDS, ENABLE_SENSITIVE_WORD_CHECK,
)

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
  8. Self-RAG 验证 → self_rag_service.verify_with_reflection()（事实核查 + 检索质量评估）
  9. 补充检索闭环 → 如果检索不充分：改写 query → 重新检索 → 重新生成
  10. 警告反馈 → 将验证警告追加到 SSE 流中
  11. 保存助手消息 → session_service.add_message()
  12. 保存对话记录 → _save_conversation()
  13. 记录统计数据 → record_api_call / record_doc_hit / record_token_usage
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


async def _check_sensitive(query: str, kb_id: str = "") -> bool:
    """敏感词检查：调用 Java 敏感词服务，命中返回 True。

    Java 不可达时 fail open（放行并记日志），不阻断主链路；
    拒绝话术不回显命中词详情，避免给绕过者提供词库反馈。

    开关消费管理台"系统配置"：sys_config 的 chat.enable_sensitive_check
    （60s 缓存），未配置时回退 config.py 的环境变量默认值。
    """
    if not await get_config_bool("chat.enable_sensitive_check", ENABLE_SENSITIVE_WORD_CHECK):
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{JAVA_BACKEND}/api/internal/security/sensitive-check",
                headers=internal_headers(),
                json={"text": query, "kbId": kb_id or None},
            )
            if resp.status_code != 200:
                return False
            data = resp.json()
            if data.get("code") != 0:
                return False
            if data.get("data", {}).get("hasSensitive"):
                print(f"[chat] 敏感词拦截: 命中 {data['data'].get('matchCount', 0)} 个敏感词")
                return True
            return False
    except Exception as e:
        print(f"[chat] 敏感词检查不可用，放行: {e}")
        return False


def _blocked_stream_response():
    """敏感词命中的拒绝响应（SSE 格式与正常回答一致，前端无需特判）"""
    async def generate():
        yield json.dumps({"token": "您的提问包含不允许的内容，请调整后重试。", "done": False}, ensure_ascii=False) + "\n"
        yield json.dumps({"token": "", "done": True, "sources": []}, ensure_ascii=False) + "\n"
    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


def _cache_scope_key(kb_scope: list) -> str:
    """语义缓存隔离键：单 KB 用其 id；多 KB 用排序后 ids 的 md5（set: 前缀）。

    与检索范围一致是隔离的关键——不同可见级别的用户各用各的键，
    公共/员工用户共享同一集合键，命中率不受多库合并影响。
    """
    if not kb_scope:
        return "none"
    if len(kb_scope) == 1:
        return str(kb_scope[0])
    return "set:" + hashlib.md5(",".join(str(k) for k in sorted(kb_scope)).encode()).hexdigest()[:16]


async def _record_stats(
    t_start: float, query: str, context: str, history_for_llm: list,
    full_response: str, llm_error: bool, all_sources: list,
    user_id: int, kb_id_str: str
):
    """后台异步记录统计（fire-and-forget，不阻塞 done 信号）。

    一次批量上报（doc-hit 按文档去重），替代此前 api-call → N×doc-hit →
    token-usage 逐条串行 POST、逐次建连的模式。
    """
    try:
        latency_ms = (time.time() - t_start) * 1000
        api_calls = [{
            "kbId": kb_id_str, "apiPath": "/api/chat",
            "success": not llm_error, "latencyMs": latency_ms,
        }]

        doc_hits, seen_docs = [], set()
        for s in all_sources[:20]:
            doc_id = str(s.get("document_id", s.get("doc_id", "unknown")))
            if doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)
            doc_name = s.get("filename", s.get("document_name", s.get("title", s.get("source", "未知文档"))))
            doc_hits.append({"documentId": doc_id, "docName": doc_name, "kbId": kb_id_str})

        token_usages = [{
            "kbId": kb_id_str, "userId": user_id,
            "promptTokens": _estimate_tokens(query + context + str(history_for_llm)),
            "completionTokens": _estimate_tokens(full_response),
        }]

        await record_batch(api_calls, doc_hits, token_usages)
    except Exception as e:
        print(f"[_record_stats] 统计记录失败: {e}")

_CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')

def _estimate_tokens(text: str) -> int:
    """CJK-aware token 估算：中文字符约 1.5 token/字，非中文约 0.25 token/字"""
    text = str(text)
    cjk_chars = len(_CJK_RE.findall(text))
    non_cjk = len(text) - cjk_chars
    return int(cjk_chars * 1.5 + non_cjk * 0.25)


async def _record_audit(user_id: int, username: str, operation: str, detail: str, target_name: str = "", ip_address: str = "", result: str = "SUCCESS", token: str = ""):
    """记录审计日志到 Java 后端（复用共享连接池，失败不影响主流程）"""
    try:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        await java_http.post("/api/audit-logs", {
            "userId": user_id,
            "username": username,
            "operation": operation,
            "detail": detail,
            "targetName": target_name,
            "ipAddress": ip_address,
            "result": result,
        }, timeout=5.0, headers=headers)
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

        resp = await java_http.post("/api/conversations/save-or-update", {
            "sessionId": session_id,
            "userId": user_id,
            "question": question,
            "answer": answer,
            "referencedChunks": referenced,
            "kbId": kb_id or "",
            "status": "COMPLETED",
        }, timeout=5.0, headers=headers)
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


async def _save_conversation_bounded(session_id: str, user_id: int, question: str, answer: str, sources: list = None, kb_id: str = None, token: str = ""):
    """带 3 秒上限的对话保存：超时不取消请求，转后台继续补发，done 帧先行。

    前端仅用 conversation_id 决定是否显示反馈按钮，缺省只是降级不报错。
    shield 保证 wait_for 超时后后台任务不被取消。
    """
    task = asyncio.create_task(_save_conversation(
        session_id, user_id, question, answer, sources, kb_id=kb_id, token=token,
    ))
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=3.0)
    except asyncio.TimeoutError:
        print("[chat] 对话保存超 3s，转后台补发，done 帧先行")
        return None


@router.post("")
async def chat(request: ChatRequest, raw_request: Request, current_user: dict = Depends(get_user_or_api_key)):
    """
    RAG 对话核心接口（SSE 流式响应）

    完整流程：
      前置（并行）：保存用户消息 → 审计日志 → 获取历史 → 查询优化 → 知识检索 → 构建上下文
      SSE 流（异步生成器）：LLM 流式输出 → Self-RAG 验证 → 保存助手消息 → 保存对话记录 → 统计记录
    """
    session_id = request.session_id
    query = request.message.strip()
    kb_id = request.kb_id
    if not query:
        raise HTTPException(status_code=400, detail="消息不能为空")

    # 敏感词检查：命中即拒绝，不进入检索与生成
    if await _check_sensitive(query, kb_id):
        return _blocked_stream_response()

    # ===== 服务端检索范围强制（三级可见级别） =====
    # 请求携带的 kb_id 仅为范围缩小提示，不作授权依据；不可访问直接 403
    accessible_ids, _is_admin = await kb_access.get_accessible_kb_ids(current_user.get("id"))
    if kb_id:
        if int(kb_id) not in accessible_ids:
            raise HTTPException(status_code=403, detail="无权访问该知识库")
        kb_scope = [int(kb_id)]
    else:
        kb_scope = accessible_ids
    cache_scope = _cache_scope_key(kb_scope)

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

    await save_task
    history = await session_service.get_history(session_id, token=token)
    history = history or []
    MAX_HISTORY_MSGS = 6
    history_for_llm = [
        {"role": h["role"], "content": h["content"]}
        for h in history[-MAX_HISTORY_MSGS - 1:-1]
    ] if len(history) > 1 else []

    # 查询优化（规则改写，毫秒级）+ 语义缓存检查 + 知识检索
    sources = []
    context = ""
    optimized_query = query
    try:
        optimized_query = await query_optimizer.optimize_async(query, history) if query_optimizer else query
    except Exception as e:
        print(f"[chat] 查询优化失败: {e}")
        optimized_query = query

    # 缓存键用原始 query：optimized_query 依赖会话历史（LLM 改写随轮次变化），
    # 跨轮不稳定；同一问题的原始文本才是稳定键。改写只用于检索，不用于缓存。
    # 缓存 scope 与检索范围一致：公共/员工用户共享同一集合键，管理级用户各自隔离。
    cached_result = await semantic_cache.lookup(query, kb_id=cache_scope)

    if not cached_result:
        try:
            sources = await rag_service.retrieve(optimized_query, use_hybrid=True, kb_ids=kb_scope or None) or []
            context = rag_service.build_context(sources) if sources else ""
        except Exception as e:
            print(f"[chat] 检索/历史记录错误: {e}")

    # 确保 audit 任务完成（save 已在前面 await，仅做异常捕获）
    try:
        await audit_task
    except Exception:
        pass

    async def generate():
        t_start = time.time()
        full_response = ""
        llm_error = False
        all_sources = sources  # 跟踪所有使用的检索结果（可能在补充检索后更新）

        if cached_result:
            cached_answer = cached_result["answer"]
            cached_sources = cached_result["sources"]
            sim = cached_result.get("similarity", 0)

            yield json.dumps(
                {"status": "start", "mode": "cache", "cache_similarity": sim},
                ensure_ascii=False,
            ) + "\n"

            chunk_size = 10
            for i in range(0, len(cached_answer), chunk_size):
                chunk = cached_answer[i:i + chunk_size]
                yield json.dumps(
                    {"token": chunk, "done": False, "mode": "cache"},
                    ensure_ascii=False,
                ) + "\n"

            full_response = cached_answer
            all_sources = cached_sources

            conv_id = await _save_conversation_bounded(
                session_id, user_id, query, full_response, all_sources,
                kb_id=kb_id, token=token,
            )
            await session_service.add_message(session_id, "assistant", full_response, all_sources)

            yield json.dumps(
                {"token": "", "done": True, "sources": all_sources, "mode": "cache", "conversation_id": conv_id},
                ensure_ascii=False,
            ) + "\n"
            return

        # ===== Phase 1: 初始检索 + LLM 流式生成 =====
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

        # ===== Phase 2: Self-RAG 反思验证（模式见 config.SELF_RAG_MODE） =====
        verify_task = None
        save_initial = None
        if all_sources and not llm_error:
            if SELF_RAG_MODE == "corrective":
                # 同步验证：资料不充分时补充检索并重新生成（最多等 VERIFY_TIMEOUT 秒）
                verify_task = asyncio.create_task(
                    asyncio.wait_for(
                        self_rag_service.verify_with_reflection(full_response, all_sources, query),
                        timeout=SELF_RAG_VERIFY_TIMEOUT,
                    )
                )
            elif SELF_RAG_MODE == "log":
                # 后台验证仅记日志，不阻塞响应
                asyncio.create_task(_verify_and_log(full_response, all_sources))
            # off：不验证

            # 并行启动初始消息保存（验证期间完成，节省 50-100ms）
            save_initial = asyncio.create_task(
                session_service.add_message(session_id, "assistant", full_response, all_sources)
            )

        if verify_task:
            try:
                verification = await verify_task
            except asyncio.TimeoutError:
                print(f"[SELF-RAG] 验证超时（>{SELF_RAG_VERIFY_TIMEOUT}s），跳过验证")
                verification = None
            except Exception as e:
                print(f"[SELF-RAG] 反思验证异常: {e}")
                verification = None

            if verification:
                if verification.get("needs_retrieval"):
                    reformulated_query = verification.get("reformulated_query", query)
                    retrieval_gap = verification.get("retrieval_gap", "参考资料不够充分")

                    # 等待初始消息保存完成
                    if save_initial:
                        await save_initial
                        save_initial = None

                    # 通知用户正在补充检索
                    gap_msg = (
                        f"\n\n---\n"
                        f"🔍 **检测到初始回答的资料不够充分**（{retrieval_gap}），"
                        f"正在补充检索更相关的资料..."
                    )
                    yield json.dumps({"token": gap_msg, "done": False, "mode": "self_rag"}, ensure_ascii=False) + "\n"

                    # 补充检索
                    try:
                        additional_sources = await rag_service.retrieve(
                            reformulated_query, use_hybrid=True, kb_ids=kb_scope or None
                        ) or []

                        if additional_sources:
                            new_context = rag_service.build_context(additional_sources)
                            refined_response = ""

                            yield json.dumps(
                                {"token": "\n\n**📝 补充检索后的改进回答：**\n\n", "done": False, "mode": "self_rag"},
                                ensure_ascii=False,
                            ) + "\n"

                            async for llm_token in llm_service.generate(
                                query, new_context, history_for_llm, KNOWLEDGE_SYSTEM_PROMPT
                            ):
                                refined_response += llm_token
                                yield json.dumps(
                                    {"token": llm_token, "done": False, "mode": "self_rag"},
                                    ensure_ascii=False,
                                ) + "\n"

                            # 用改进后的回答替换初始回答，并保存到会话
                            full_response = refined_response
                            all_sources = additional_sources
                            await session_service.add_message(
                                session_id, "assistant", full_response, all_sources
                            )
                            print(
                                f"[SELF-RAG] 补充检索完成，query='{reformulated_query}'，"
                                f"获取 {len(additional_sources)} 条结果"
                            )
                        else:
                            print(f"[SELF-RAG] 补充检索无结果，query='{reformulated_query}'")
                    except Exception as e:
                        print(f"[SELF-RAG] 补充检索失败: {e}")

                # 追加警告信息到 SSE 流
                warning = self_rag_service.build_warning(verification)
                if warning:
                    yield json.dumps(
                        {"token": warning, "done": False, "mode": "warning"},
                        ensure_ascii=False,
                    ) + "\n"
                    print(f"[SELF-RAG] 验证警告已反馈用户: {warning[:150]}")

        # 等待初始消息保存（如果还没完成且未被 re-retrieval 替换）
        if save_initial:
            await save_initial

        # ===== Phase 3: 保存对话记录 + 统计 =====
        conv_id = await _save_conversation_bounded(
            session_id, user_id, query, full_response, all_sources,
            kb_id=kb_id, token=token,
        )

        kb_id_str = kb_id or ""
        asyncio.create_task(_record_stats(
            t_start, query, context, history_for_llm,
            full_response, llm_error, all_sources, user_id, kb_id_str
        ))

        if full_response and not llm_error:
            # 与 lookup 同口径：原始 query + kb_id 隔离
            asyncio.create_task(semantic_cache.store(query, full_response, all_sources, kb_id=cache_scope))

        yield json.dumps(
            {"token": "", "done": True, "sources": all_sources, "mode": "rag", "conversation_id": conv_id},
            ensure_ascii=False,
        ) + "\n"

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
    """LLM 端点健康状态"""
    llm_ok = await llm_service.check_health()
    return {
        "llm": llm_ok,
        "llm_endpoint": LLM_BASE_URL,
        "deepseek": llm_ok,
        "kb_chunks": 0,
        "semantic_cache": semantic_cache.stats(),
    }


@router.get("/semantic-cache/stats")
async def semantic_cache_stats():
    """语义缓存统计信息"""
    return semantic_cache.stats()


@router.post("/semantic-cache/clear")
async def semantic_cache_clear(current_user: dict = Depends(get_current_user)):
    """清空语义缓存（需管理员权限）"""
    username = current_user.get("username", "")
    if username != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可清空缓存")
    await semantic_cache.clear()
    return {"success": True, "message": "语义缓存已清空"}


@router.get("/cache/health", deprecated=True)
async def cache_health_alias():
    return await health_check()


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
    """访客问答：与登录链路同构（检索 → 上下文 → 流式生成），范围强制为公共级。

    - 检索范围 = visibility=PUBLIC 的知识库（服务端解析，访客无授权决定权）
    - GUEST_KB_IDS 非空时取交集作为附加限制
    - 范围为空：fail closed——不检索任何知识库，退化为通用闲聊
    """
    query = request.message.strip()
    if not query:
        raise HTTPException(status_code=400, detail="消息不能为空")

    if await _check_sensitive(query):
        return _blocked_stream_response()

    public_ids = await kb_access.get_public_kb_ids()
    guest_scope = sorted(set(public_ids) & {int(k) for k in GUEST_KB_IDS}) if GUEST_KB_IDS else public_ids

    sources = []
    context = ""
    if guest_scope:
        try:
            sources = await rag_service.retrieve(query, use_hybrid=True, kb_ids=guest_scope) or []
        except Exception as e:
            print(f"[guest] 访客检索失败: {e}")
        context = rag_service.build_context(sources) if sources else ""

    system_prompt = KNOWLEDGE_SYSTEM_PROMPT if guest_scope else CHAT_SYSTEM_PROMPT

    async def generate():
        try:
            async for token in llm_service.generate(query, context, [], system_prompt):
                yield json.dumps({"token": token, "done": False}, ensure_ascii=False) + "\n"
            yield json.dumps({"token": "", "done": True, "sources": sources}, ensure_ascii=False) + "\n"
        except Exception as e:
            yield json.dumps({"token": f"\n\n[生成出错: {str(e)}]", "done": True, "sources": []}, ensure_ascii=False) + "\n"

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
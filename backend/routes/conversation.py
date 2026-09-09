import os
import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from typing import Optional

from routes.auth import get_current_user

JAVA_BACKEND = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


async def _proxy_java_get(path: str, request: Request, params: dict = None):
    """代理到 Java 后端，转换 Java {code, message, data} 格式到 {success, data} 格式"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            resp = await client.get(f"{JAVA_BACKEND}{path}", params=params, headers=headers)
            java_resp = resp.json()

            if java_resp.get("code") == 0:
                return JSONResponse(content={
                    "success": True,
                    "data": java_resp.get("data")
                })
            else:
                return JSONResponse(content={
                    "success": False,
                    "data": None,
                    "error": java_resp.get("message") or "请求失败"
                })
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "data": None, "error": "Java 后端服务未启动（端口 8002）"})
        except Exception as e:
            return JSONResponse(content={"success": False, "data": None, "error": f"请求失败: {e}"})


@router.get("/grouped")
async def list_conversations_grouped(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return await _proxy_java_get("/api/conversations/grouped", request)


@router.get("/{conversation_id}")
async def get_conversation_detail(
    conversation_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return await _proxy_java_get(f"/api/conversations/{conversation_id}", request)


@router.get("/{conversation_id}/chunk-trace")
async def get_conversation_chunk_trace(
    conversation_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """追溯对话→切片→文档：返回 chunk_id 列表及其对应的切片内容和文档信息"""
    return await _proxy_java_get(f"/api/conversations/{conversation_id}/chunk-trace", request)


@router.post("/save-or-update")
async def save_or_update_conversation(
    request: Request,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            resp = await client.post(
                f"{JAVA_BACKEND}/api/conversations/save-or-update",
                json=body,
                headers=headers,
            )
            java_resp = resp.json()
            if java_resp.get("code") == 0:
                return JSONResponse(content={"success": True, "data": java_resp.get("data")})
            else:
                return JSONResponse(content={"success": False, "error": java_resp.get("message") or "保存失败"})
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"保存对话失败: {e}"})


@router.get("")
async def list_conversations(
    request: Request,
    pageNum: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    feedback: Optional[int] = Query(None),
    startDate: Optional[str] = Query(None),
    endDate: Optional[str] = Query(None),
    userId: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    params = {"pageNum": pageNum, "pageSize": pageSize}
    if keyword:
        params["keyword"] = keyword
    if feedback is not None:
        params["feedback"] = feedback
    if startDate:
        params["startDate"] = startDate
    if endDate:
        params["endDate"] = endDate
    if userId is not None:
        params["userId"] = userId
    return await _proxy_java_get("/api/conversations", request, params)


@router.put("/{conversation_id}/feedback")
async def update_feedback(
    conversation_id: int,
    request: Request,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            resp = await client.put(
                f"{JAVA_BACKEND}/api/conversations/{conversation_id}/feedback",
                json=body,
                headers=headers,
            )
            java_resp = resp.json()
            if java_resp.get("code") == 0:
                return JSONResponse(content={"success": True, "data": java_resp.get("data")})
            else:
                return JSONResponse(content={"success": False, "error": java_resp.get("message") or "更新失败"})
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"更新反馈失败: {e}"})


@router.get("/stats/feedback")
async def get_feedback_stats(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return await _proxy_java_get("/api/conversations/stats/feedback", request)


@router.get("/stats/recent")
async def get_recent_stats(
    request: Request,
    days: int = Query(7, ge=1),
    current_user: dict = Depends(get_current_user),
):
    return await _proxy_java_get("/api/conversations/stats/recent", request, {"days": days})


@router.get("/stats/top-kb")
async def get_top_kb_stats(
    request: Request,
    days: int = Query(7, ge=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    return await _proxy_java_get("/api/conversations/stats/top-kb", request, {"days": days, "limit": limit})


@router.get("/stats/doc-ref-rank")
async def get_doc_ref_rank(
    request: Request,
    days: int = Query(7, ge=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    return await _proxy_java_get("/api/conversations/stats/doc-ref-rank", request, {"days": days, "limit": limit})


@router.get("/stats/feedback-distribution")
async def get_feedback_distribution(
    request: Request,
    days: int = Query(7, ge=1),
    current_user: dict = Depends(get_current_user),
):
    return await _proxy_java_get("/api/conversations/stats/feedback-distribution", request, {"days": days})


@router.get("/stats/daily-trend")
async def get_daily_trend(
    request: Request,
    days: int = Query(7, ge=1),
    current_user: dict = Depends(get_current_user),
):
    return await _proxy_java_get("/api/conversations/stats/daily-trend", request, {"days": days})


@router.get("/stats/active-user-rank")
async def get_active_user_rank(
    request: Request,
    days: int = Query(7, ge=1),
    limit: int = Query(10, ge=1),
    current_user: dict = Depends(get_current_user),
):
    return await _proxy_java_get("/api/conversations/stats/active-user-rank", request, {"days": days, "limit": limit})


@router.get("/stats/recent-conversations")
async def get_recent_conversations(
    request: Request,
    limit: int = Query(10, ge=1),
    current_user: dict = Depends(get_current_user),
):
    return await _proxy_java_get("/api/conversations/stats/recent-conversations", request, {"limit": limit})


@router.get("/stats/today")
async def get_today_stats(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return await _proxy_java_get("/api/conversations/stats/today", request)
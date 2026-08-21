import os
import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from typing import Optional

from routes.auth import get_current_user

JAVA_BACKEND = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("/grouped")
async def list_conversations_grouped(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            resp = await client.get(
                f"{JAVA_BACKEND}/api/conversations/grouped",
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"获取分组对话记录失败: {e}"})


@router.get("/{conversation_id}")
async def get_conversation_detail(
    conversation_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            resp = await client.get(
                f"{JAVA_BACKEND}/api/conversations/{conversation_id}",
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"获取对话详情失败: {e}"})


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
            return JSONResponse(content=resp.json())
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
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
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

            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            resp = await client.get(
                f"{JAVA_BACKEND}/api/conversations",
                params=params,
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"获取对话记录失败: {e}"})


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
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"更新反馈失败: {e}"})


@router.get("/stats/feedback")
async def get_feedback_stats(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            resp = await client.get(
                f"{JAVA_BACKEND}/api/conversations/stats/feedback",
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"获取反馈统计失败: {e}"})


@router.get("/stats/recent")
async def get_recent_stats(
    request: Request,
    days: int = Query(7, ge=1),
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            resp = await client.get(
                f"{JAVA_BACKEND}/api/conversations/stats/recent",
                params={"days": days},
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"获取近期统计失败: {e}"})


@router.get("/stats/top-kb")
async def get_top_kb_stats(
    request: Request,
    days: int = Query(7, ge=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            resp = await client.get(
                f"{JAVA_BACKEND}/api/conversations/stats/top-kb",
                params={"days": days, "limit": limit},
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"获取知识库排名失败: {e}"})


@router.get("/stats/doc-ref-rank")
async def get_doc_ref_rank(
    request: Request,
    days: int = Query(7, ge=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth
            resp = await client.get(
                f"{JAVA_BACKEND}/api/conversations/stats/doc-ref-rank",
                params={"days": days, "limit": limit},
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"获取文档引用排行失败: {e}"})


@router.get("/stats/feedback-distribution")
async def get_feedback_distribution(
    request: Request,
    days: int = Query(7, ge=1),
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            resp = await client.get(
                f"{JAVA_BACKEND}/api/conversations/stats/feedback-distribution",
                params={"days": days},
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"获取反馈分布失败: {e}"})


@router.get("/stats/daily-trend")
async def get_daily_trend(
    request: Request,
    days: int = Query(7, ge=1),
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            resp = await client.get(
                f"{JAVA_BACKEND}/api/conversations/stats/daily-trend",
                params={"days": days},
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"获取每日趋势失败: {e}"})


@router.get("/stats/active-user-rank")
async def get_active_user_rank(
    request: Request,
    days: int = Query(7, ge=1),
    limit: int = Query(10, ge=1),
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth
            resp = await client.get(
                f"{JAVA_BACKEND}/api/conversations/stats/active-user-rank",
                params={"days": days, "limit": limit},
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"获取活跃用户排名失败: {e}"})


@router.get("/stats/recent-conversations")
async def get_recent_conversations(
    request: Request,
    limit: int = Query(10, ge=1),
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth
            resp = await client.get(
                f"{JAVA_BACKEND}/api/conversations/stats/recent-conversations",
                params={"limit": limit},
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"获取最近对话失败: {e}"})


@router.get("/stats/today")
async def get_today_stats(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth
            resp = await client.get(
                f"{JAVA_BACKEND}/api/conversations/stats/today",
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"获取今日统计失败: {e}"})
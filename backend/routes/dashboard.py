import os
import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from typing import Optional

from routes.auth import get_current_user

JAVA_BACKEND = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


async def proxy_to_java(path: str, request: Request, params: dict = None):
    """将请求代理转发到 Java 后端"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            url = f"{JAVA_BACKEND}/api/dashboard/{path}"
            resp = await client.get(url, params=params, headers=headers)
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={
                "success": False,
                "data": None,
                "error": "Java 后端服务未启动（端口 8002）"
            })
        except Exception as e:
            return JSONResponse(content={
                "success": False,
                "data": None,
                "error": f"请求失败: {e}"
            })


@router.get("/overview")
async def get_overview(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return await proxy_to_java("overview", request)


@router.get("/api-stats")
async def get_api_stats(
    request: Request,
    days: int = Query(7),
    current_user: dict = Depends(get_current_user),
):
    return await proxy_to_java("api-stats", request, {"days": days})


@router.get("/token-stats")
async def get_token_stats(
    request: Request,
    days: int = Query(7),
    current_user: dict = Depends(get_current_user),
):
    return await proxy_to_java("token-stats", request, {"days": days})


@router.get("/hot-docs")
async def get_hot_docs(
    request: Request,
    days: int = Query(7),
    limit: int = Query(20),
    current_user: dict = Depends(get_current_user),
):
    return await proxy_to_java("hot-docs", request, {"days": days, "limit": limit})


@router.get("/kb-hot-rank")
async def get_kb_hot_rank(
    request: Request,
    days: int = Query(7),
    current_user: dict = Depends(get_current_user),
):
    return await proxy_to_java("kb-hot-rank", request, {"days": days})


@router.get("/task-stats")
async def get_task_stats(
    request: Request,
    days: int = Query(7),
    current_user: dict = Depends(get_current_user),
):
    return await proxy_to_java("task-stats", request, {"days": days})


@router.get("/alerts")
async def get_alerts(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return await proxy_to_java("alerts", request)


@router.put("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            resp = await client.put(
                f"{JAVA_BACKEND}/api/dashboard/alerts/{alert_id}/resolve",
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"处理告警失败: {e}"})


# ========== 数据记录代理接口（供 Python 业务层调用） ==========

async def _post_to_java(path: str, body: dict):
    """POST 请求代理到 Java 后端"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{JAVA_BACKEND}/api/dashboard/{path}",
                json=body,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                print(f"[dashboard proxy] POST {path} 失败: HTTP {resp.status_code}")
    except Exception as e:
        print(f"[dashboard proxy] POST {path} 异常: {e}")


async def record_api_call(kb_id: str, api_path: str, success: bool, latency_ms: float):
    await _post_to_java("record/api-call", {
        "kbId": kb_id,
        "apiPath": api_path,
        "success": success,
        "latencyMs": latency_ms,
    })


async def record_doc_hit(document_id: str, doc_name: str, kb_id: str):
    await _post_to_java("record/doc-hit", {
        "documentId": document_id,
        "docName": doc_name,
        "kbId": kb_id,
    })


async def record_token_usage(kb_id: str, user_id: int, prompt_tokens: int, completion_tokens: int):
    await _post_to_java("record/token-usage", {
        "kbId": kb_id,
        "userId": user_id,
        "promptTokens": prompt_tokens,
        "completionTokens": completion_tokens,
    })
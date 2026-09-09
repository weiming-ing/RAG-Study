import os
import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from typing import Optional

from routes.auth import get_current_user

JAVA_BACKEND = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
async def list_audit_logs(
    request: Request,
    pageNum: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    operation: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    startDate: Optional[str] = Query(None),
    endDate: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            params = {"pageNum": pageNum, "pageSize": pageSize}
            if keyword:
                params["keyword"] = keyword
            if operation:
                params["operation"] = operation
            if result:
                params["result"] = result
            if startDate:
                params["startDate"] = startDate
            if endDate:
                params["endDate"] = endDate

            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            resp = await client.get(
                f"{JAVA_BACKEND}/api/audit-logs",
                params=params,
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"获取审计日志失败: {e}"})


@router.get("/stats/operations")
async def get_operation_stats(
    request: Request,
    days: int = Query(7, ge=1, le=365),
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            resp = await client.get(
                f"{JAVA_BACKEND}/api/audit-logs/stats/operations",
                params={"days": days},
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"获取操作统计失败: {e}"})


@router.get("/stats/daily")
async def get_daily_stats(
    request: Request,
    days: int = Query(7, ge=1, le=365),
    current_user: dict = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth

            resp = await client.get(
                f"{JAVA_BACKEND}/api/audit-logs/stats/daily",
                params={"days": days},
                headers=headers,
            )
            return JSONResponse(content=resp.json())
        except httpx.ConnectError:
            return JSONResponse(content={"success": False, "error": "Java 后端服务未启动"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": f"获取每日统计失败: {e}"})
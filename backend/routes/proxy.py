"""
代理路由模块 — 请求转发到 Java 管理后端

核心职责：将管理类 API 请求透明转发到 Java 后端（rag-engine :8002），
同时透传 JWT 认证头，保证前端只需与 Python 后端通信。

代理路径映射：
  /api/admin/*      → Java /api/admin/*
  /api/system/*     → Java /api/system/*
  /api/security/*   → Java /api/security/*
  /api/debug/*      → Java /api/debug/*
  /api/api-keys/*   → Java /api/api-keys/*
  /api/dashboard/*  → Java /api/dashboard/*

设计原因：
  - 前端（rag-admin :5173）只需配置一个后端地址（Python :8001）
  - Python 后端负责 AI 对话核心逻辑，管理数据通过代理转发到 Java
  - 认证信息通过 JWT Bearer Token 透传
"""

import os
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["proxy"])

JAVA_BACKEND = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")


def _get_auth_headers(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if auth:
        return {"Authorization": auth}
    return {}


@router.api_route("/admin/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_admin(request: Request, rest: str):
    url = f"{JAVA_BACKEND}/api/admin/{rest}"
    return await _proxy_request(request, url)


@router.api_route("/system/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_system(request: Request, rest: str):
    url = f"{JAVA_BACKEND}/api/system/{rest}"
    return await _proxy_request(request, url)


@router.api_route("/security/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_security(request: Request, rest: str):
    url = f"{JAVA_BACKEND}/api/security/{rest}"
    return await _proxy_request(request, url)


@router.api_route("/debug/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_debug(request: Request, rest: str):
    url = f"{JAVA_BACKEND}/api/debug/{rest}"
    return await _proxy_request(request, url)


@router.api_route("/api-keys", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_apikey_base(request: Request):
    url = f"{JAVA_BACKEND}/api/api-keys"
    return await _proxy_request(request, url)


@router.api_route("/api-keys/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_apikey(request: Request, rest: str):
    url = f"{JAVA_BACKEND}/api/api-keys/{rest}"
    return await _proxy_request(request, url)


@router.api_route("/dashboard/token-stats", methods=["GET"])
async def proxy_dashboard_token_stats(request: Request):
    url = f"{JAVA_BACKEND}/api/dashboard/token-stats"
    return await _proxy_request(request, url)


@router.api_route("/dashboard/kb-hot-rank", methods=["GET"])
async def proxy_dashboard_kb_hot_rank(request: Request):
    url = f"{JAVA_BACKEND}/api/dashboard/kb-hot-rank"
    return await _proxy_request(request, url)


async def _proxy_request(request: Request, url: str):
    headers = _get_auth_headers(request)
    headers["Content-Type"] = request.headers.get("Content-Type", "application/json")

    query_params = dict(request.query_params)
    body = None
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
        except Exception:
            body = None

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=url,
                params=query_params if query_params else None,
                json=body,
                headers=headers,
            )
            try:
                return JSONResponse(content=resp.json(), status_code=resp.status_code)
            except Exception:
                return JSONResponse(
                    content={"success": True, "data": resp.text},
                    status_code=resp.status_code,
                )
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"代理请求失败: {e}")
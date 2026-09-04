import os
import httpx
from fastapi import APIRouter, HTTPException, Query, Body, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])

JAVA_BACKEND = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = None


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class KnowledgeBaseConfig(BaseModel):
    chunkSize: Optional[int] = None
    chunkOverlap: Optional[int] = None
    topK: Optional[int] = None
    vectorWeight: Optional[float] = None
    bm25Weight: Optional[float] = None


def _get_auth_headers(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if auth:
        return {"Authorization": auth}
    return {}


def _fix_kb_item(kb: dict) -> dict:
    return {
        "id": kb.get("id"),
        "name": kb.get("name", kb.get("kbName", "")),
        "description": kb.get("description", ""),
        "documentCount": kb.get("documentCount", kb.get("totalDocuments", 0)),
        "chunkCount": kb.get("chunkCount", kb.get("totalChunks", 0)),
        "createTime": kb.get("createTime", kb.get("createdAt", "")),
        "status": kb.get("status", "active"),
    }


@router.get("")
async def list_kbs(request: Request, size: int = Query(1000)):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{JAVA_BACKEND}/api/internal/knowledge-bases",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                kbs = [{"id": 0, "name": "全部知识库", "description": "默认知识库", "documentCount": 0, "chunkCount": 0, "createTime": "", "status": "active"}]
                records = java_data.get("data", {}).get("records", [])
                for kb in records[:size]:
                    kbs.append(_fix_kb_item(kb))
                return JSONResponse(content={"success": True, "data": kbs})
            return JSONResponse(content={
                "success": True,
                "data": [{"id": 0, "name": "全部知识库", "description": "默认知识库", "documentCount": 0, "chunkCount": 0, "createTime": "", "status": "active"}],
            })
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取知识库列表失败: {e}")


@router.get("/{kb_id}")
async def get_kb(kb_id: int, request: Request):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{JAVA_BACKEND}/api/internal/knowledge-bases/{kb_id}",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                return JSONResponse(content={"success": True, "data": _fix_kb_item(java_data.get("data", {}))})
            return JSONResponse(content={"success": False, "error": java_data.get("message", "知识库不存在")})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取知识库详情失败: {e}")


@router.post("")
async def create_kb(body: KnowledgeBaseCreate, request: Request):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{JAVA_BACKEND}/api/internal/knowledge-bases",
                json={"name": body.name, "description": body.description},
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                return JSONResponse(content={"success": True, "data": _fix_kb_item(java_data.get("data", {}))})
            return JSONResponse(content={"success": False, "error": java_data.get("message", "创建失败")})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"创建知识库失败: {e}")


@router.put("/{kb_id}")
async def update_kb(kb_id: int, body: KnowledgeBaseUpdate, request: Request):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            update_data = {}
            if body.name is not None:
                update_data["name"] = body.name
            if body.description is not None:
                update_data["description"] = body.description
            resp = await client.put(
                f"{JAVA_BACKEND}/api/internal/knowledge-bases/{kb_id}",
                json=update_data,
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                return JSONResponse(content={"success": True, "data": _fix_kb_item(java_data.get("data", {}))})
            return JSONResponse(content={"success": False, "error": java_data.get("message", "更新失败")})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"更新知识库失败: {e}")


@router.delete("/{kb_id}")
async def delete_kb(kb_id: int, request: Request):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.delete(
                f"{JAVA_BACKEND}/api/internal/knowledge-bases/{kb_id}",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                return JSONResponse(content={"success": True, "message": "删除成功"})
            return JSONResponse(content={"success": False, "error": java_data.get("message", "删除失败")})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"删除知识库失败: {e}")


@router.get("/{kb_id}/config")
async def get_kb_config(kb_id: int, request: Request):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{JAVA_BACKEND}/api/internal/knowledge-bases/{kb_id}/config",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                return JSONResponse(content={"success": True, "data": java_data.get("data", {})})
            return JSONResponse(content={"success": True, "data": {}})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取配置失败: {e}")


@router.put("/{kb_id}/config")
async def update_kb_config(kb_id: int, body: KnowledgeBaseConfig, request: Request):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            config_data = {}
            if body.chunkSize is not None:
                config_data["chunkSize"] = body.chunkSize
            if body.chunkOverlap is not None:
                config_data["chunkOverlap"] = body.chunkOverlap
            if body.topK is not None:
                config_data["topK"] = body.topK
            if body.vectorWeight is not None:
                config_data["vectorWeight"] = body.vectorWeight
            if body.bm25Weight is not None:
                config_data["bm25Weight"] = body.bm25Weight
            resp = await client.put(
                f"{JAVA_BACKEND}/api/internal/knowledge-bases/{kb_id}/config",
                json=config_data,
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                return JSONResponse(content={"success": True, "data": java_data.get("data", {})})
            return JSONResponse(content={"success": False, "error": java_data.get("message", "更新配置失败")})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"更新配置失败: {e}")


@router.get("/{kb_id}/users")
async def get_authorized_users(kb_id: int, request: Request):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{JAVA_BACKEND}/api/internal/knowledge-bases/{kb_id}/users",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                return JSONResponse(content={"success": True, "data": java_data.get("data", [])})
            return JSONResponse(content={"success": False, "error": java_data.get("message", "获取授权用户失败")})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取授权用户失败: {e}")


class GrantAccessRequest(BaseModel):
    userIds: list[int]
    accessLevel: str


@router.post("/{kb_id}/users")
async def grant_access(kb_id: int, body: GrantAccessRequest, request: Request):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{JAVA_BACKEND}/api/internal/knowledge-bases/{kb_id}/users",
                json={"userIds": body.userIds, "accessLevel": body.accessLevel},
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                return JSONResponse(content={"success": True, "message": "授权成功"})
            return JSONResponse(content={"success": False, "error": java_data.get("message", "授权失败")})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"授权失败: {e}")


@router.delete("/{kb_id}/users/{user_id}")
async def revoke_access(kb_id: int, user_id: int, request: Request):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.delete(
                f"{JAVA_BACKEND}/api/internal/knowledge-bases/{kb_id}/users/{user_id}",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                return JSONResponse(content={"success": True, "message": "撤销授权成功"})
            return JSONResponse(content={"success": False, "error": java_data.get("message", "撤销授权失败")})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"撤销授权失败: {e}")
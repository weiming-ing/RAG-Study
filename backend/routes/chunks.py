import os
import httpx
from fastapi import APIRouter, HTTPException, Query, Body, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/api/chunks", tags=["chunks"])

JAVA_BACKEND = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")


class ChunkUpdate(BaseModel):
    content: str


class ChunkSplit(BaseModel):
    splitPosition: int


class ChunkMerge(BaseModel):
    chunkIds: List[str]


def _get_auth_headers(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if auth:
        return {"Authorization": auth}
    return {}


@router.get("")
async def list_chunks(request: Request, docId: str = Query(None), pageNum: int = Query(1), pageSize: int = Query(20), keyword: str = Query(None)):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            params = {"pageNum": pageNum, "pageSize": pageSize}
            if docId:
                params["docId"] = docId
            if keyword:
                params["keyword"] = keyword
            resp = await client.get(
                f"{JAVA_BACKEND}/api/chunks",
                params=params,
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                page_data = java_data.get("data", {})
                chunks = page_data.get("records", [])
                result = []
                for c in chunks:
                    content = c.get("content", "")
                    result.append({
                        "id": c.get("chunkId", c.get("id", "")),
                        "chunkId": c.get("chunkId", ""),
                        "chunkIndex": c.get("chunkIndex", 0),
                        "content": content,
                        "contentPreview": content[:200],
                        "contentLength": c.get("contentLength", len(content)),
                        "parentChunkId": c.get("parentChunkId", ""),
                        "parentChunkIndex": c.get("parentChunkIndex", 0),
                        "docId": c.get("documentId", docId),
                        "docName": c.get("fileName", ""),
                        "createTime": c.get("createTime", ""),
                    })
                return JSONResponse(content={
                    "success": True,
                    "data": {
                        "records": result,
                        "total": page_data.get("total", len(result)),
                        "pageNum": page_data.get("current", pageNum),
                        "pageSize": page_data.get("size", pageSize),
                    },
                })
            return JSONResponse(content={"success": True, "data": {"records": [], "total": 0, "pageNum": pageNum, "pageSize": pageSize}})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取分块列表失败: {e}")


@router.put("/{chunk_id}")
async def update_chunk(chunk_id: str, body: ChunkUpdate, request: Request):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.put(
                f"{JAVA_BACKEND}/api/chunks/{chunk_id}",
                json={"content": body.content},
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                return JSONResponse(content={"success": True, "message": "更新成功"})
            return JSONResponse(content={"success": False, "error": java_data.get("message", "更新失败")})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"更新分块失败: {e}")


@router.post("/{chunk_id}/split")
async def split_chunk(chunk_id: str, body: ChunkSplit, request: Request):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{JAVA_BACKEND}/api/chunks/{chunk_id}/split",
                json={"splitPosition": body.splitPosition},
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                return JSONResponse(content={"success": True, "message": "拆分成功"})
            return JSONResponse(content={"success": False, "error": java_data.get("message", "拆分失败")})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"拆分分块失败: {e}")


@router.post("/merge")
async def merge_chunks(body: ChunkMerge, request: Request):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{JAVA_BACKEND}/api/chunks/merge",
                json={"chunkIds": body.chunkIds},
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                return JSONResponse(content={"success": True, "message": "合并成功"})
            return JSONResponse(content={"success": False, "error": java_data.get("message", "合并失败")})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"合并分块失败: {e}")


@router.post("/rebuild/{kb_id}")
async def rebuild_vectors(kb_id: str, request: Request):
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(
                f"{JAVA_BACKEND}/api/chunks/rebuild/{kb_id}",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                return JSONResponse(content={"success": True, "message": "重建向量索引成功"})
            return JSONResponse(content={"success": False, "error": java_data.get("message", "重建失败")})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"重建向量索引失败: {e}")
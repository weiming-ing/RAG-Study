import os
import uuid
import asyncio
import httpx
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, Body, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config import DATA_DIR, DOCUMENTS_DIR
from database.db import get_db
from utils.internal_api import internal_headers
from routes.auth import require_admin, get_current_user
from utils.admin_audit import record_admin_op_bg
from services import kb_access

from services.docling_service import docling_service

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

JAVA_BACKEND = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".txt", ".md", ".html", ".htm", ".rtf", ".csv", ".xml"}
MAX_FILE_SIZE = 50 * 1024 * 1024


class ChunkUpdateRequest(BaseModel):
    content: str


class ManualEntryCreate(BaseModel):
    title: str
    content: str
    tags: Optional[List[str]] = None


class ManualEntryUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None


async def _audit(username: str, operation: str, detail: str, target_name: str = "", ip_address: str = "", result: str = "SUCCESS"):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{JAVA_BACKEND}/api/audit-logs",
                json={
                    "username": username,
                    "operation": operation,
                    "detail": detail,
                    "targetName": target_name,
                    "ipAddress": ip_address,
                    "result": result,
                },
            )
    except Exception:
        pass


def _get_username(request: Request) -> str:
    try:
        from jose import jwt as jose_jwt
        from config import JWT_SECRET_KEY, JWT_ALGORITHM
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            payload = jose_jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return payload.get("username", "unknown")
    except Exception:
        pass
    return "unknown"


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _get_auth_headers(request: Request) -> dict:
    """构造转发到 Java 后端的请求头。

    同时携带用户 Authorization（用于 /api/knowledge/** 等用户态接口）
    与 X-Internal-Token（用于 /api/internal/** 服务间接口，由 Java 的
    InternalApiAuthFilter 校验）。多余的请求头会被对端忽略。
    """
    auth = request.headers.get("Authorization", "")
    return internal_headers({"Authorization": auth} if auth else None)


async def _ensure_kb_read_access(kb_id: int, current_user: dict):
    """文档读取的 KB 级校验，收敛到 kb_access 共享实现（与 kb_browse 同口径）。"""
    await kb_access.ensure_kb_read_access(kb_id, current_user)


def _java_response_to_python(java_data: dict) -> dict:
    code = java_data.get("code", -1)
    if code == 0:
        return {"success": True, "data": java_data.get("data")}
    return {"success": False, "error": java_data.get("message", "未知错误")}


def _transform_stats(java_data: dict) -> dict:
    stats = java_data.get("data") or {}
    return {
        "success": True,
        "data": {
            "total_documents": stats.get("totalDocuments", 0),
            "total_chunks": stats.get("totalChunks", 0),
            "total_size": stats.get("totalSize", 0),
        },
    }


def _transform_doc_list(java_data: dict) -> dict:
    page_data = java_data.get("data") or {}
    records = page_data.get("records", [])
    docs = []
    for r in records:
        docs.append({
            "id": r.get("id"),
            "name": r.get("name", r.get("fileName", "未知文件")),
            "filename": r.get("name", r.get("fileName", "未知文件")),
            "fileType": r.get("fileType", ""),
            "fileSize": r.get("fileSize", 0),
            "size": r.get("fileSize", 0),
            "chunkCount": r.get("chunkCount", r.get("totalChunks", 0)),
            "chunks": r.get("chunkCount", r.get("totalChunks", 0)),
            "status": r.get("status", "COMPLETED"),
            "createTime": r.get("createTime", ""),
            "kbId": r.get("kbId", r.get("knowledgeBaseId", 0)),
            "kbName": r.get("kbName", r.get("kbName", "")),
        })
    return {
        "success": True,
        "data": {
            "records": docs,
            "total": page_data.get("total", len(docs)),
            "pageNum": page_data.get("pageNum", 1),
            "pageSize": page_data.get("pageSize", 10),
        },
    }


def _transform_doc_detail(java_data: dict) -> dict:
    doc = java_data.get("data", {})
    return {
        "success": True,
        "data": {
            "id": doc.get("id"),
            "filename": doc.get("name", doc.get("fileName", "未知文件")),
            "size": doc.get("fileSize", 0),
            "chunks": doc.get("chunkCount", doc.get("totalChunks", 0)),
            "file_type": doc.get("fileType", ""),
            "department": doc.get("department", ""),
            "category": doc.get("category", ""),
            "status": doc.get("status", "unknown"),
            "summary": doc.get("summary", ""),
            "create_time": doc.get("createTime", ""),
        },
    }


def _to_java_chunk_id(chunk_id: str) -> str:
    parts = chunk_id.rsplit("_", 1)
    if len(parts) == 2:
        doc_id, chunk_index = parts
        return f"doc_{doc_id}_child_{chunk_index}"
    return chunk_id


def _transform_search_results(java_data: dict) -> dict:
    search_data = java_data.get("data", {})
    results = search_data.get("results", [])
    items = []
    for r in results:
        metadata = r.get("metadata", {}) or {}
        doc_name = metadata.get("docName") or metadata.get("fileName") or metadata.get("documentName", "未知文件")
        kb_name = metadata.get("kbName") or metadata.get("datasetName", "未知知识库")
        items.append({
            "doc_id": metadata.get("documentId", ""),
            "documentName": doc_name,
            "kbName": kb_name,
            "filename": doc_name,
            "chunk_index": metadata.get("chunkIndex", 0),
            "page": metadata.get("page", 0),
            "score": r.get("score", 0),
            "content": r.get("content", ""),
            "parent_content": r.get("parentContent", ""),
        })
    return {"success": True, "data": items}


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


# ==================== 兼容旧路由（无 kbId，必须定义在参数化路由之前，否则会被 /{kb_id}/documents 覆盖） ====================

@router.get("/documents")
async def list_documents_legacy(
    request: Request,
    pageNum: int = Query(1), pageSize: int = Query(10), keyword: str = Query(None),
    current_user: dict = Depends(require_admin),
):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            params = {"pageNum": pageNum, "pageSize": pageSize}
            if keyword:
                params["keyword"] = keyword
            resp = await client.get(
                f"{JAVA_BACKEND}/api/internal/knowledge/list",
                params=params,
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") != 0:
                raise HTTPException(status_code=500, detail=java_data.get("message", "Java 后端返回错误"))
            return JSONResponse(content=_transform_doc_list(java_data))
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取文档列表失败: {e}")


@router.get("/documents/{doc_id}")
async def get_document_legacy(doc_id: str, request: Request, current_user: dict = Depends(require_admin)):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{JAVA_BACKEND}/api/internal/knowledge/{doc_id}",
                headers=_get_auth_headers(request),
            )
            return JSONResponse(content=_transform_doc_detail(resp.json()))
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取文档详情失败: {e}")


@router.post("/upload")
async def upload_document_legacy(request: Request, file: UploadFile = File(...), current_user: dict = Depends(require_admin)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过限制 (50MB)")

    parsed_markdown = ""
    if docling_service.ready:
        try:
            # 同步 CPU 密集解析放到线程池，避免阻塞事件循环拖住全部并发请求
            parsed_markdown, _ = await asyncio.to_thread(
                docling_service.parse_to_markdown, content, file.filename
            )
        except Exception as e:
            print(f"[docling] 解析失败: {e}，降级到 Java Tika 兜底")
    else:
        print("[docling] 解析器尚未就绪，跳过 Docling，降级到 Java Tika 兜底")

    files = {"file": (file.filename, content, file.content_type or "application/octet-stream")}
    data_fields = {}
    if parsed_markdown:
        data_fields["parsedContent"] = parsed_markdown

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(
                f"{JAVA_BACKEND}/api/internal/knowledge/upload",
                files=files,
                data=data_fields,
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                doc = java_data.get("data", {})
                await _audit(_get_username(request), "UPLOAD", f"上传文件: {file.filename}", target_name=file.filename, ip_address=_get_client_ip(request))
                return JSONResponse(content={
                    "success": True,
                    "data": {
                        "id": doc.get("id"),
                        "filename": doc.get("fileName", file.filename),
                        "size": doc.get("fileSize", 0),
                        "chunks": doc.get("totalChunks", 0),
                    },
                })
            print(f"[UPLOAD ERROR] Java backend returned: {java_data}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": java_data.get("message", "上传失败")},
            )
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"上传失败: {e}")


@router.delete("/documents/{doc_id}")
async def delete_document_legacy(doc_id: str, request: Request, current_user: dict = Depends(require_admin)):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.delete(
                f"{JAVA_BACKEND}/api/internal/knowledge/{doc_id}",
                headers=_get_auth_headers(request),
            )
            result = resp.json()
            await _audit(_get_username(request), "DELETE", f"删除文档: {doc_id}", target_name=doc_id, ip_address=_get_client_ip(request))
            return JSONResponse(content=_java_response_to_python(result))
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"删除文档失败: {e}")


@router.get("/documents/{doc_id}/chunks")
async def get_document_chunks_legacy(doc_id: str, request: Request, current_user: dict = Depends(require_admin)):
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.get(
                f"{JAVA_BACKEND}/api/internal/knowledge/chunks/{doc_id}",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                chunks = java_data.get("data", [])
                result = []
                for c in chunks:
                    content = c.get("content", "")
                    result.append({
                        "chunk_index": c.get("chunkIndex", 0),
                        "chunk_id": c.get("chunkId", ""),
                        "content": content,
                        "content_preview": content[:300],
                        "is_truncated": len(content) > 300,
                        "content_length": c.get("contentLength", 0),
                        "parent_chunk_id": c.get("parentChunkId", ""),
                        "parent_chunk_index": c.get("parentChunkIndex", 0),
                        "page": 0,
                        "metadata": {},
                    })
                return JSONResponse(content={"success": True, "data": result})
            return JSONResponse(content={"success": True, "data": []})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取分块失败: {e}")


# ==================== 文档 CRUD（带 kbId） ====================

@router.get("/{kb_id}/documents")
async def list_documents(
    kb_id: int, request: Request, pageNum: int = Query(1), pageSize: int = Query(10), keyword: str = Query(None),
    current_user: dict = Depends(get_current_user),
):
    await _ensure_kb_read_access(kb_id, current_user)
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            params = {"pageNum": pageNum, "pageSize": pageSize}
            if keyword:
                params["keyword"] = keyword
            resp = await client.get(
                f"{JAVA_BACKEND}/api/knowledge/{kb_id}/documents",
                params=params,
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") != 0:
                raise HTTPException(status_code=500, detail=java_data.get("message", "Java 后端返回错误"))
            return JSONResponse(content=_transform_doc_list(java_data))
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取文档列表失败: {e}")


@router.get("/{kb_id}/documents/{doc_id}")
async def get_document(kb_id: int, doc_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    await _ensure_kb_read_access(kb_id, current_user)
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{JAVA_BACKEND}/api/knowledge/{kb_id}/documents/{doc_id}",
                headers=_get_auth_headers(request),
            )
            return JSONResponse(content=_transform_doc_detail(resp.json()))
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取文档详情失败: {e}")


@router.post("/{kb_id}/documents/upload")
async def upload_document(kb_id: int, request: Request, file: UploadFile = File(...), current_user: dict = Depends(require_admin)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过限制 (50MB)")

    parsed_markdown = ""
    if docling_service.ready:
        try:
            # 同步 CPU 密集解析放到线程池，避免阻塞事件循环拖住全部并发请求
            parsed_markdown, _ = await asyncio.to_thread(
                docling_service.parse_to_markdown, content, file.filename
            )
        except Exception as e:
            print(f"[docling] 解析失败: {e}，降级到 Java Tika 兜底")
    else:
        print("[docling] 解析器尚未就绪，跳过 Docling，降级到 Java Tika 兜底")

    files = {"file": (file.filename, content, file.content_type or "application/octet-stream")}
    data_fields = {}
    if parsed_markdown:
        data_fields["parsedContent"] = parsed_markdown

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(
                f"{JAVA_BACKEND}/api/knowledge/{kb_id}/documents/upload",
                files=files,
                data=data_fields,
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                doc = java_data.get("data", {})
                await _audit(_get_username(request), "UPLOAD", f"上传文件: {file.filename} (kb_id={kb_id})", target_name=file.filename, ip_address=_get_client_ip(request))
                return JSONResponse(content={
                    "success": True,
                    "data": {
                        "id": doc.get("id"),
                        "filename": doc.get("fileName", file.filename),
                        "size": doc.get("fileSize", 0),
                        "chunks": doc.get("totalChunks", 0),
                    },
                })
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": java_data.get("message", "上传失败")},
            )
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"上传失败: {e}")


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(kb_id: int, doc_id: str, request: Request, current_user: dict = Depends(require_admin)):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.delete(
                f"{JAVA_BACKEND}/api/knowledge/{kb_id}/documents/{doc_id}",
                headers=_get_auth_headers(request),
            )
            result = resp.json()
            await _audit(_get_username(request), "DELETE", f"删除文档: {doc_id} (kb_id={kb_id})", target_name=doc_id, ip_address=_get_client_ip(request))
            return JSONResponse(content=_java_response_to_python(result))
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"删除文档失败: {e}")


@router.post("/{kb_id}/documents/{doc_id}/reparse")
async def reparse_document(kb_id: int, doc_id: str, request: Request, current_user: dict = Depends(require_admin)):
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(
                f"{JAVA_BACKEND}/api/knowledge/{kb_id}/documents/{doc_id}/reparse",
                headers=_get_auth_headers(request),
            )
            record_admin_op_bg(current_user, "REPARSE", f"重新解析文档 {doc_id} (kb_id={kb_id})", target_id=doc_id)
            return JSONResponse(content=_java_response_to_python(resp.json()))
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"重新解析失败: {e}")


@router.get("/{kb_id}/documents/{doc_id}/content")
async def get_document_content(kb_id: int, doc_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    await _ensure_kb_read_access(kb_id, current_user)
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{JAVA_BACKEND}/api/internal/knowledge/{doc_id}",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            doc_meta = java_data.get("data", {}) if java_data.get("code") == 0 else {}

            merged_content = ""
            total_chunks = doc_meta.get("chunkCount", 0)

            resp2 = await client.get(
                f"{JAVA_BACKEND}/api/internal/knowledge/chunks/{doc_id}",
                headers=_get_auth_headers(request),
            )
            chunks_data = resp2.json()

            if chunks_data.get("code") == 0:
                raw_chunks = chunks_data.get("data", [])
                total_chunks = len(raw_chunks)
                raw_chunks.sort(key=lambda c: c.get("chunkIndex", 0))
                merged_content = "\n\n".join([
                    c.get("content", "") for c in raw_chunks
                ])

            if not merged_content:
                merged_content = doc_meta.get("content", "")

            return JSONResponse(content={
                "success": True,
                "data": {
                    "id": doc_meta.get("id"),
                    "content": merged_content,
                    "fileName": doc_meta.get("name", doc_meta.get("fileName", "")),
                    "fileType": doc_meta.get("fileType", ""),
                    "fileSize": doc_meta.get("fileSize", 0),
                    "status": doc_meta.get("status", ""),
                    "totalChunks": total_chunks,
                },
            })
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取文档内容失败: {e}")


@router.get("/{kb_id}/documents/{doc_id}/chunks")
async def get_document_chunks(kb_id: int, doc_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    await _ensure_kb_read_access(kb_id, current_user)
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.get(
                f"{JAVA_BACKEND}/api/knowledge/{kb_id}/documents/{doc_id}/chunks",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                chunks = java_data.get("data", [])
                result = []
                for c in chunks:
                    content = c.get("content", "")
                    result.append({
                        "chunk_index": c.get("chunkIndex", 0),
                        "chunk_id": c.get("chunkId", ""),
                        "content": content,
                        "content_preview": content[:300],
                        "is_truncated": len(content) > 300,
                        "content_length": c.get("contentLength", 0),
                        "parent_chunk_id": c.get("parentChunkId", ""),
                        "parent_chunk_index": c.get("parentChunkIndex", 0),
                        "page": 0,
                        "metadata": {},
                    })
                return JSONResponse(content={"success": True, "data": result})
            return JSONResponse(content={"success": True, "data": []})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取分块失败: {e}")


# ==================== 知识库 CRUD ====================

@router.get("/kbs")
async def list_kbs(request: Request, current_user: dict = Depends(get_current_user)):
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
                accessible, is_admin = await kb_access.get_accessible_kb_ids(current_user["id"])
                if not is_admin:
                    records = [r for r in records if isinstance(r.get("id"), int) and r["id"] in accessible]
                for kb in records:
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


@router.get("/kbs/{kb_id}")
async def get_kb(kb_id: int, request: Request, current_user: dict = Depends(get_current_user)):
    await _ensure_kb_read_access(kb_id, current_user)
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


# ==================== 文档分块操作 ====================

@router.put("/chunks/{chunk_id}")
async def update_chunk(chunk_id: str, body: ChunkUpdateRequest, request: Request, current_user: dict = Depends(require_admin)):
    java_chunk_id = _to_java_chunk_id(chunk_id)
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.put(
                f"{JAVA_BACKEND}/api/internal/knowledge/chunks/{java_chunk_id}",
                json={"content": body.content},
                headers=_get_auth_headers(request),
            )
            record_admin_op_bg(current_user, "UPDATE", f"编辑分块 {chunk_id}", target_id=chunk_id)
            return JSONResponse(content=_java_response_to_python(resp.json()))
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"更新分块失败: {e}")


@router.get("/chunks/{chunk_id}")
async def get_chunk_detail(chunk_id: str, request: Request, current_user: dict = Depends(require_admin)):
    """分块详情跨 KB、无法按 chunk 反查 kb_id 做细粒度校验，消费方仅管理台，直接挂管理员门禁。"""
    java_chunk_id = _to_java_chunk_id(chunk_id)
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{JAVA_BACKEND}/api/internal/knowledge/chunk/{java_chunk_id}",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                chunk = java_data.get("data", {})
                content = chunk.get("content", "")
                return JSONResponse(content={
                    "success": True,
                    "data": {
                        "chunk_id": chunk.get("chunkId", java_chunk_id),
                        "chunk_index": chunk.get("chunkIndex", 0),
                        "content": content,
                        "content_length": chunk.get("contentLength", 0),
                        "parent_chunk_id": chunk.get("parentChunkId", ""),
                        "parent_chunk_index": chunk.get("parentChunkIndex", 0),
                    },
                })
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": java_data.get("message", "分块不存在")},
            )
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取分块详情失败: {e}")


# ==================== 其他 ====================

@router.post("/rebuild")
async def rebuild_knowledge_base(request: Request, current_user: dict = Depends(require_admin)):
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(
                f"{JAVA_BACKEND}/api/internal/knowledge/rebuild",
                headers=_get_auth_headers(request),
            )
            record_admin_op_bg(current_user, "REBUILD", "重建知识库向量索引")
            return JSONResponse(content=_java_response_to_python(resp.json()))
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"重建索引失败: {e}")


@router.post("/scan")
async def scan_new_files(request: Request, current_user: dict = Depends(require_admin)):
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(
                f"{JAVA_BACKEND}/api/internal/knowledge/scan",
                headers=_get_auth_headers(request),
            )
            record_admin_op_bg(current_user, "SCAN", "扫描文档目录新增文件")
            return JSONResponse(content=_java_response_to_python(resp.json()))
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"扫描失败: {e}")


@router.get("/statistics")
async def get_statistics(request: Request):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{JAVA_BACKEND}/api/internal/knowledge/statistics",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") != 0:
                raise HTTPException(status_code=500, detail=java_data.get("message", "Java 后端返回错误"))
            return JSONResponse(content=_transform_stats(java_data))
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取统计信息失败: {e}")


@router.get("/search")
async def search_knowledge_base(
    request: Request,
    q: str = Query(..., min_length=1, description="搜索关键词"),
    doc_id: str = Query(None, description="限定文档ID"),
):
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            body = {
                "query": q,
                "topK": 5,
                "enableHybrid": True,
            }
            if doc_id:
                body["filters"] = {"documentId": int(doc_id)}

            resp = await client.post(
                f"{JAVA_BACKEND}/api/internal/search",
                json=body,
                headers=_get_auth_headers(request),
            )
            return JSONResponse(content=_transform_search_results(resp.json()))
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"搜索失败: {e}")


@router.post("/manual")
async def add_manual_entry(body: ManualEntryCreate, request: Request, current_user: dict = Depends(require_admin)):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{JAVA_BACKEND}/api/knowledge/0/documents/manual",
                json={"title": body.title, "content": body.content, "tags": body.tags},
                headers=_get_auth_headers(request),
            )
            record_admin_op_bg(current_user, "CREATE", f"新增手动知识条目「{body.title}」", target_name=body.title)
            return JSONResponse(content=_java_response_to_python(resp.json()))
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"创建手动条目失败: {e}")


@router.get("/manual")
async def get_manual_entries(request: Request):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{JAVA_BACKEND}/api/knowledge/0/documents",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                records = java_data.get("data", {}).get("records", [])
                return JSONResponse(content={"success": True, "data": records})
            return JSONResponse(content={"success": True, "data": []})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取手动条目失败: {e}")


@router.put("/manual/{entry_id}")
async def update_manual_entry(entry_id: str, body: ManualEntryUpdate, request: Request, current_user: dict = Depends(require_admin)):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            update_data = {}
            if body.title is not None:
                update_data["title"] = body.title
            if body.content is not None:
                update_data["content"] = body.content
            if body.tags is not None:
                update_data["tags"] = body.tags
            resp = await client.put(
                f"{JAVA_BACKEND}/api/knowledge/0/documents/{entry_id}",
                json=update_data,
                headers=_get_auth_headers(request),
            )
            record_admin_op_bg(current_user, "UPDATE", f"更新手动知识条目 {entry_id}", target_id=entry_id)
            return JSONResponse(content=_java_response_to_python(resp.json()))
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"更新手动条目失败: {e}")


@router.delete("/manual/{entry_id}")
async def delete_manual_entry(entry_id: str, request: Request, current_user: dict = Depends(require_admin)):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.delete(
                f"{JAVA_BACKEND}/api/knowledge/0/documents/{entry_id}",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") == 0:
                record_admin_op_bg(current_user, "DELETE", f"删除手动知识条目 {entry_id}", target_id=entry_id)
                return JSONResponse(content={"success": True, "message": "删除成功"})
            return JSONResponse(content={"success": False, "error": java_data.get("message", "删除失败")})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"删除手动条目失败: {e}")
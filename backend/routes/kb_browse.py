"""
员工侧知识库查看（只读，服务端权限过滤）。

员工聊天页的"查看知识库"面板此前直接调管理端 /api/knowledge/documents——
全量文档列表、无任何权限过滤，管理级知识库的文档对所有人可见。这里收敛为：
  - 仅返回 kb_access 解析出的可访问知识库（PUBLIC / EMPLOYEE / 已授权 MANAGEMENT）；
  - 文档列表按知识库分组返回，分块预览按 KB 归属二次校验，越权 403；
  - 纯只读：不提供任何写操作入口（手动条目增删改、分块回写均不在此暴露）。
"""

import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from routes.auth import get_current_user
from routes.knowledge import _get_auth_headers, _transform_doc_list
from services import kb_access

router = APIRouter(prefix="/api/kb/browse", tags=["kb-browse"])

JAVA_BACKEND = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")

VIS_TEXT = {"PUBLIC": "公共级", "EMPLOYEE": "员工级", "MANAGEMENT": "管理级"}


@router.get("")
async def browse_knowledge_bases(request: Request, current_user: dict = Depends(get_current_user)):
    """当前用户可见的知识库模块（含各自文档列表），按三级可见级别过滤。"""
    accessible, _is_admin = await kb_access.get_accessible_kb_ids(current_user["id"])
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{JAVA_BACKEND}/api/internal/knowledge-bases",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") != 0:
                raise HTTPException(status_code=500, detail=java_data.get("message", "获取知识库失败"))
            # Java 返回分页对象 {records: [...]}，兼容直接返回列表的形态
            kb_data = java_data.get("data")
            kbs = kb_data.get("records") if isinstance(kb_data, dict) else kb_data
            kbs = kbs or []

            modules = []
            for kb in kbs:
                kb_id = kb.get("id")
                if kb_id is None or int(kb_id) not in accessible:
                    continue
                docs = []
                try:
                    r2 = await client.get(
                        f"{JAVA_BACKEND}/api/knowledge/{kb_id}/documents",
                        params={"pageNum": 1, "pageSize": 200},
                        headers=_get_auth_headers(request),
                    )
                    jd = r2.json()
                    if jd.get("code") == 0:
                        transformed = _transform_doc_list(jd)
                        page = transformed.get("data") or {}
                        docs = page.get("records") or page.get("docs") or []
                except Exception as e:
                    print(f"[kb-browse] KB {kb_id} 文档列表加载失败: {e}")
                # 目录式浏览：没有内容（0 篇文档）的知识库不展示
                if not docs:
                    continue
                modules.append({
                    "id": kb_id,
                    "name": kb.get("name") or kb.get("kbName", ""),
                    "description": kb.get("description", ""),
                    "visibility": kb.get("visibilityLevel", ""),
                    "visibilityText": VIS_TEXT.get(kb.get("visibilityLevel"), ""),
                    "docs": docs,
                })
            return JSONResponse(content={"success": True, "data": modules})
        except HTTPException:
            raise
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"加载知识库失败: {e}")


@router.get("/search")
async def browse_search(request: Request, q: str, current_user: dict = Depends(get_current_user)):
    """知识库内容搜索——检索范围强制限定为当前用户可访问的知识库。

    管理端 /api/knowledge/search 无权限过滤（全库检索），员工页不能再用。
    """
    accessible, _is_admin = await kb_access.get_accessible_kb_ids(current_user["id"])
    if not accessible:
        return JSONResponse(content={"success": True, "data": []})
    from routes.knowledge import _transform_search_results

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(
                f"{JAVA_BACKEND}/api/internal/search",
                json={
                    "query": q,
                    "topK": 5,
                    "enableHybrid": True,
                    "filters": {"kbIds": ",".join(str(int(k)) for k in accessible)},
                },
                headers=_get_auth_headers(request),
            )
            return JSONResponse(content=_transform_search_results(resp.json()))
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"搜索失败: {e}")


@router.get("/{kb_id}/documents/{doc_id}/chunks")
async def browse_document_chunks(
    kb_id: int, doc_id: str, request: Request, current_user: dict = Depends(get_current_user)
):
    """文档分块预览（只读）。先校验 KB 可访问性，防止用管理端接口越权读。"""
    accessible, _is_admin = await kb_access.get_accessible_kb_ids(current_user["id"])
    if kb_id not in accessible:
        raise HTTPException(status_code=403, detail="无权访问该知识库")
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.get(
                f"{JAVA_BACKEND}/api/internal/knowledge/chunks/{doc_id}",
                headers=_get_auth_headers(request),
            )
            java_data = resp.json()
            if java_data.get("code") != 0:
                return JSONResponse(content={"success": True, "data": []})
            chunks = []
            for c in java_data.get("data") or []:
                content = c.get("content", "")
                chunks.append({
                    "chunk_index": c.get("chunkIndex", 0),
                    "chunk_id": c.get("chunkId", ""),
                    "content": content,
                    "content_preview": content[:300],
                    "is_truncated": len(content) > 300,
                    "content_length": c.get("contentLength", 0),
                    "page": 0,
                })
            return JSONResponse(content={"success": True, "data": chunks})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Java 后端服务未启动")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取分块失败: {e}")

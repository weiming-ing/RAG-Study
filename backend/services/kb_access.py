"""
知识库访问范围解析（三级可见级别的服务端强制）

核心职责：把"用户 → 可访问知识库集合"的解析收敛到服务端，
前端传入的 kb_id 仅为范围缩小提示，不作授权依据。

级别语义（由 Java 侧 kb_knowledge_base.visibility 定义）：
  PUBLIC     公共级——所有人，含访客
  EMPLOYEE   员工级——任何登录用户
  MANAGEMENT 管理级——仅 kb_user_access 授权人 + KB owner + ROLE_ADMIN

缓存：进程内 60s TTL——管理台授权/撤销后最迟 1 分钟生效，
避免每条对话消息都打一次 Java 解析接口。
"""

import time

import httpx
from fastapi import HTTPException

from config import JAVA_BACKEND_URL
from utils.internal_api import internal_headers

TTL_SECONDS = 60
TIMEOUT = 5.0

# {user_id: (expires_at, kb_ids, is_admin)}
_cache: dict = {}
_public_cache: tuple = (0.0, [])  # (expires_at, kb_ids)


async def get_accessible_kb_ids(user_id) -> tuple:
    """登录用户可访问的知识库 id 列表。

    Returns:
        (kb_ids, is_admin)；Java 不可达时返回 ([], False)——fail closed，
        用户检索不到任何知识库比越权检索更安全。
    """
    if user_id is None:
        return await get_public_kb_ids(), False

    key = str(user_id)
    now = time.time()
    cached = _cache.get(key)
    if cached and cached[0] > now:
        return cached[1], cached[2]

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{JAVA_BACKEND_URL}/api/internal/knowledge-bases/accessible",
                params={"userId": key},
                headers=internal_headers(),
            )
            data = resp.json()
            if resp.status_code != 200 or data.get("code") != 0:
                raise RuntimeError(f"HTTP {resp.status_code} {str(data)[:120]}")
            payload = data.get("data") or {}
            kb_ids = [int(k) for k in (payload.get("kbIds") or [])]
            is_admin = bool(payload.get("isAdmin"))
    except Exception as e:
        print(f"[kb_access] 解析可访问知识库失败（fail closed）: {e}")
        return [], False

    _cache[key] = (now + TTL_SECONDS, kb_ids, is_admin)
    return kb_ids, is_admin


async def get_public_kb_ids() -> list:
    """PUBLIC 级知识库 id 列表（访客检索范围）。Java 不可达时返回空列表（fail closed）。"""
    global _public_cache
    now = time.time()
    if _public_cache[0] > now:
        return _public_cache[1]
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{JAVA_BACKEND_URL}/api/internal/knowledge-bases/accessible",
                headers=internal_headers(),
            )
            data = resp.json()
            if resp.status_code != 200 or data.get("code") != 0:
                raise RuntimeError(f"HTTP {resp.status_code}")
            kb_ids = [int(k) for k in ((data.get("data") or {}).get("kbIds") or [])]
    except Exception as e:
        print(f"[kb_access] 解析 PUBLIC 知识库失败（fail closed）: {e}")
        return []

    _public_cache = (now + TTL_SECONDS, kb_ids)
    return kb_ids


def invalidate(user_id=None):
    """管理台授权变更后可主动失效缓存（未调用时靠 TTL 自然过期）"""
    if user_id is None:
        _cache.clear()
        globals()["_public_cache"] = (0.0, [])
    else:
        _cache.pop(str(user_id), None)


async def ensure_kb_read_access(kb_id: int, current_user: dict):
    """文档/知识库读取路由共用的 KB 级校验。

    管理角色全通；普通用户仅限 get_accessible_kb_ids 解析出的可访问集合，
    越权统一 403。解析失败即无可访问集合（fail closed）。
    """
    accessible, is_admin = await get_accessible_kb_ids(current_user["id"])
    if is_admin:
        return
    if kb_id not in accessible:
        raise HTTPException(status_code=403, detail="无权访问该知识库")

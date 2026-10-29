"""
API Key 鉴权（X-API-Key 请求头）。

供外部系统调用开放 API：校验转发到 Java 内部接口（有效期/禁用/限额判定 +
调用计数，与 Java 直连路径 SecurityCheckFilter 语义一致），通过后以密钥
归属用户身份进入链路，知识库可见范围沿用该用户的三级可见级别。

JWTAuthMiddleware 与对话路由的 get_user_or_api_key 依赖共用本模块：
中间件先校验并写入 request.state.user，路由依赖命中缓存避免重复计数。
"""

import httpx

from config import JAVA_BACKEND_URL
from utils.internal_api import internal_headers


async def resolve_api_key_user(api_key: str):
    """校验 API Key，有效返回用户 dict，无效/服务异常返回 None。

    调用方需区分"无效（None→401）"与"Java 不可达"场景时可自行调用
    /api/internal/admin/api-key/validate；这里统一按 None→401 处理，
    fail closed 与检索授权的取向一致。
    """
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{JAVA_BACKEND_URL}/api/internal/admin/api-key/validate",
                params={"apiKey": api_key},
                headers=internal_headers(),
            )
            data = resp.json()
    except Exception:
        return None
    if resp.status_code != 200 or data.get("code") != 0:
        return None
    payload = data.get("data") or {}
    if not payload.get("valid"):
        return None
    return {
        "id": int(payload.get("userId") or 0),
        "username": payload.get("username") or "api-key",
        "roles": ["ROLE_API_KEY"],
        "via_api_key": True,
    }

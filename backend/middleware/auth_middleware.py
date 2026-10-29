from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from utils.auth import decode_token_and_get_user
from utils.api_key_auth import resolve_api_key_user

WHITELIST_PATHS = {
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/me",
    "/api/health",
    "/api/chat/guest",
    "/api/chat/health",
}


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if request.method == "OPTIONS":
            return await call_next(request)

        if path in WHITELIST_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # 开放 API 调用方携带 X-API-Key 而非 JWT：校验通过则以密钥归属
            # 用户身份放行（写入 request.state.user 供限流与路由复用）
            api_key = request.headers.get("X-API-Key", "")
            if api_key:
                api_user = await resolve_api_key_user(api_key)
                if api_user is None:
                    return JSONResponse(
                        status_code=401,
                        content={"success": False, "error": "无效或已禁用的 API Key"},
                    )
                request.state.user = api_user
                return await call_next(request)
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "未提供认证令牌，请先登录"},
            )

        token = auth_header[7:]
        try:
            user = await decode_token_and_get_user(token)
        except (JWTError, ValueError) as e:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": str(e) or "认证令牌无效或已过期，请重新登录"},
            )

        request.state.user = user
        return await call_next(request)
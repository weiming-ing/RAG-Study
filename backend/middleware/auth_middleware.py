from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from utils.auth import decode_token_and_get_user

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
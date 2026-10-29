"""
对话链路限流中间件

核心职责：对 LLM 烧钱路径（/api/chat、/api/chat/guest、/api/agent/chat）
做 Redis 滑动窗口限流。Java 侧 SecurityCheckFilter 只覆盖 Java 对外 API，
主问答路径在本服务上，必须在此限流，否则管理台限流形同虚设。

计数维度：
  - 登录用户：user:{user_id}（从 JWTAuthMiddleware 注入的 request.state.user 取）
  - 访客/未登录：ip:{client_ip}

降级策略：Redis 不可用时 fail open（放行并记日志），不阻断主链路。

注意中间件顺序：本中间件注册在 JWTAuthMiddleware 之后（内层），
因此能读到 request.state 上的用户信息。
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import (
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_USER_PER_MIN,
    RATE_LIMIT_GUEST_PER_MIN,
)
from database.db import get_redis

# 限流窗口 60 秒
WINDOW_SECONDS = 60

# 仅限流对话类端点（LLM 调用路径），管理/查询接口不限
RATE_LIMITED_PATHS = {"/api/chat", "/api/chat/guest", "/api/agent/chat"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not RATE_LIMIT_ENABLED or request.url.path not in RATE_LIMITED_PATHS:
            return await call_next(request)

        # 登录用户按 user_id 计数（JWT 中间件在外层已解析）；否则按客户端 IP
        user = getattr(request.state, "user", None) or {}
        user_id = user.get("id") if isinstance(user, dict) else None
        if user_id:
            limit = RATE_LIMIT_USER_PER_MIN
            key = f"rl:user:{user_id}"
        else:
            limit = RATE_LIMIT_GUEST_PER_MIN
            client_ip = request.client.host if request.client else "unknown"
            forwarded = request.headers.get("X-Forwarded-For", "")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()
            key = f"rl:ip:{client_ip}"

        try:
            r = await get_redis()
            now = time.time()
            window_start = now - WINDOW_SECONDS

            pipe = r.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            _, count = await pipe.execute()

            if count >= limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": f"请求过于频繁，请稍后再试（每分钟最多 {limit} 次）",
                        "type": "RateLimitExceeded",
                        "status_code": 429,
                    },
                )

            await r.zadd(key, {str(now): now})
            await r.expire(key, WINDOW_SECONDS)
        except Exception as e:
            # fail open：Redis 不可用时不阻断主链路
            print(f"[RateLimit] Redis 不可用，限流放行: {e}")

        return await call_next(request)

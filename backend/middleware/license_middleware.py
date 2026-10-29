"""
授权拦截中间件

授权无效（缺失 / 签名不符 / 过期 / 机器不匹配）时的策略，刻意做得"可恢复、不激进"：

  立即禁止：
    - /api/chat*、/api/agent*         —— 问答是本产品的核心价值
    - /api/knowledge* 的写操作        —— 不能继续入库

  始终放行：
    - /api/auth/*（要能登录）、/api/license（要能看状态）、/api/health
    - 所有 GET 请求                    —— 客户的数据始终可查看、可导出
    - 非 /api/ 路径（静态前端）

这样做的原因：把管理台一并锁死会让客户无法自查、也让供应商无法远程支持，
只会激化矛盾；而"数据可以导出"也能显著降低商务与法务摩擦。
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from services.license_service import license_service

# 授权失效时完全禁止的路径前缀（问答与 Agent）
BLOCKED_PREFIXES = ("/api/chat", "/api/agent")

# 授权失效时禁止"写操作"的路径前缀（仍允许 GET 查看）
WRITE_BLOCKED_PREFIXES = ("/api/knowledge",)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def should_block(path: str, method: str) -> bool:
    """授权无效时，该请求是否应被拦截（纯函数，便于单元测试）。

    规则：
      - 非 /api/ 路径（静态前端）、OPTIONS 预检、以及所有 GET 请求：放行
      - /api/chat*、/api/agent*：拦截（问答与 Agent 是产品核心价值）
      - /api/knowledge* 的写操作：拦截（不能继续入库）
    """
    if not path.startswith("/api/") or method == "OPTIONS" or method == "GET":
        return False
    if path.startswith(BLOCKED_PREFIXES):
        return True
    return method in WRITE_METHODS and path.startswith(WRITE_BLOCKED_PREFIXES)


class LicenseMiddleware(BaseHTTPMiddleware):
    """在授权无效时拦截问答与入库类请求。"""

    async def dispatch(self, request, call_next):
        path = request.url.path

        status = license_service.status()
        if status.valid:
            return await call_next(request)

        if not should_block(path, request.method):
            return await call_next(request)

        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "type": "LicenseError",
                "error": status.message,
                "license": status.to_dict(),
            },
        )
"""
管理写操作审计（Python 侧）。

Java 侧管理域（/api/admin、/api/system、/api/security）由 AdminAuditInterceptor
统一拦截；KB/文档/分块的写接口在 Java 侧是 internal 接口、不经过拦截器，
由这里补齐审计。审计与系统日志的区分点：带操作人、可按人/操作聚合。
"""

import asyncio

import httpx

from config import JAVA_BACKEND_URL


async def record_admin_op(
    current_user: dict,
    operation: str,
    detail: str,
    target_name: str = "",
    target_id: str = "",
    result: str = "SUCCESS",
):
    """记录管理写操作审计，失败静默：审计不可用不阻断业务。"""
    body = {
        "username": current_user.get("username", "unknown"),
        "userId": current_user.get("id"),
        "operation": operation,
        "detail": detail,
        "targetName": target_name,
        "targetId": str(target_id) if target_id else "",
        "result": result,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(f"{JAVA_BACKEND_URL}/api/audit-logs", json=body)
    except Exception:
        pass


def record_admin_op_bg(*args, **kwargs):
    """调度后台审计任务，路由 handler 里一行调用。"""
    try:
        asyncio.get_running_loop()
        asyncio.create_task(record_admin_op(*args, **kwargs))
    except RuntimeError:
        pass

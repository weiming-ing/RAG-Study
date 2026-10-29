"""
Java 后端共享 HTTP 连接池

内部服务间调用（监控统计上报、审计日志、对话保存等）统一复用同一个
httpx.AsyncClient：避免每次调用重建 TCP 连接（此前每次 POST 都
async with 新建客户端，一次消息最多 22 次串行建连）。

keepalive 上限按并发预估；FastAPI shutdown 时经 aclose() 统一关闭，
避免进程退出时连接悬挂。
"""

import httpx

from config import JAVA_BACKEND_URL

client = httpx.AsyncClient(
    base_url=JAVA_BACKEND_URL,
    timeout=httpx.Timeout(10.0, connect=3.0),
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
)


async def aclose():
    await client.aclose()


async def post(path: str, json_body: dict, timeout: float = None, headers: dict = None):
    """POST JSON 到 Java 后端，返回 Response；网络异常由调用方处理。"""
    return await client.post(path, json=json_body, timeout=timeout, headers=headers)

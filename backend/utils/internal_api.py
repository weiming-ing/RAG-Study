"""
Java 服务间接口调用辅助。

Java 的 /api/internal/** 由 InternalApiAuthFilter 门禁，要求请求头
X-Internal-Token 与配置项 rag.internal.token 一致（见 backend/config.py
的 INTERNAL_API_TOKEN）。这里统一构造请求头，避免各处自行拼装而漏带令牌。
"""

from config import INTERNAL_API_TOKEN

INTERNAL_TOKEN_HEADER = "X-Internal-Token"


def internal_headers(extra: dict = None) -> dict:
    """返回调用 Java /api/internal/** 所需的请求头。

    Args:
        extra: 额外请求头（例如用户 Authorization）；值为 None 的键会被忽略。
    """
    headers = {INTERNAL_TOKEN_HEADER: INTERNAL_API_TOKEN}
    if extra:
        headers.update({k: v for k, v in extra.items() if v})
    return headers

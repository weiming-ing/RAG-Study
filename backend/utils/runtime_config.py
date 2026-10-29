"""
运行时配置读取（消费 Java sys_config 表）。

管理台"系统配置"页修改的参数此前只落库、无人消费。这里让 Python 聊天链路
按 key 读取 sys_config 的值：进程内 60s 缓存，Java 不可达或键不存在时回退
到 config.py 的环境变量默认值——配置页改参数最迟 1 分钟生效，且后端挂了
也不影响聊天主链路。

与 Java SysConfigService 的关系：Java 侧业务代码读 getConfigValue 走
Spring Cache，Python 侧经 /api/internal/admin/sys-config 读取。
"""

import time

import httpx

from config import JAVA_BACKEND_URL
from utils.internal_api import internal_headers

TTL_SECONDS = 60
TIMEOUT = 5.0

_cache: dict = {}  # key -> (expires_at, value)


async def get_config(key: str, default: str = "") -> str:
    """读取 sys_config 单值，失败/缺省时返回 default（同步语义、内部带缓存）。"""
    now = time.time()
    cached = _cache.get(key)
    if cached and cached[0] > now:
        return cached[1]
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{JAVA_BACKEND_URL}/api/internal/admin/sys-config",
                params={"key": key},
                headers=internal_headers(),
            )
            data = resp.json()
            if resp.status_code != 200 or data.get("code") != 0:
                raise RuntimeError(f"HTTP {resp.status_code}")
            value = (data.get("data") or {}).get("value") or ""
    except Exception:
        _cache[key] = (now + TTL_SECONDS, default)
        return default
    if value == "":
        value = default
    _cache[key] = (now + TTL_SECONDS, value)
    return value


async def get_config_int(key: str, default: int) -> int:
    raw = await get_config(key, str(default))
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


async def get_config_bool(key: str, default: bool) -> bool:
    raw = await get_config(key, "true" if default else "false")
    return str(raw).strip().lower() in ("true", "1", "yes", "on")

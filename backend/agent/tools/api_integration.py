import ipaddress
import json
import os
import socket
from urllib.parse import urlparse

import httpx

HTTP_TIMEOUT = 30.0
HTTP_MAX_RESPONSE = 5000

ALLOWED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}
ALLOWED_SCHEMES = {"http", "https"}

# 允许访问的主机白名单（逗号分隔，支持 *.example.com 通配）。
# 默认空 = 禁止所有出站请求（fail closed），必须显式配置后该工具才可用。
ALLOWED_HOSTS = [
    h.strip().lower()
    for h in os.getenv("HTTP_TOOL_ALLOWED_HOSTS", "").split(",")
    if h.strip()
]

# 是否允许访问内网/回环地址，默认禁止。
# 若业务确需调用内网 OA/业务系统，显式设置 HTTP_TOOL_ALLOW_PRIVATE=true。
ALLOW_PRIVATE = os.getenv("HTTP_TOOL_ALLOW_PRIVATE", "false").lower() == "true"

# 需要拦截的 HTTP 头，避免工具被用来注入认证信息或绕过网关
BLOCKED_REQUEST_HEADERS = {"host", "content-length", "connection", "transfer-encoding"}


def _host_allowed(host: str) -> bool:
    """按白名单校验主机名，支持 *.example.com 形式的前缀通配。"""
    host = host.lower()
    for pattern in ALLOWED_HOSTS:
        if pattern.startswith("*."):
            suffix = pattern[1:]  # ".example.com"
            # 通配只匹配子域，不匹配裸域本身
            if host.endswith(suffix) and host != pattern[2:]:
                return True
        elif host == pattern:
            return True
    return False


def _resolves_to_internal(host: str) -> bool:
    """判断主机是否解析到内网/回环/链路本地/保留地址。

    注意：这里只做请求前的解析校验，无法完全防御 DNS rebinding
    （解析与真正连接之间仍存在时间窗），生产环境应叠加出站网络策略。
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        # 解析失败时按不安全处理
        return True

    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return True
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return True
    return False


def _validate_url(url: str) -> str:
    """校验目标 URL。合法时返回空字符串，否则返回给模型看的错误说明。"""
    try:
        parsed = urlparse(url)
    except ValueError:
        return f"无效的 URL: {url}"

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return f"不支持的协议: {parsed.scheme or '(空)'}。仅允许 http/https。"

    host = parsed.hostname
    if not host:
        return f"URL 缺少主机名: {url}"

    if not ALLOWED_HOSTS:
        return (
            "http_request 工具未启用：管理员需先配置 HTTP_TOOL_ALLOWED_HOSTS"
            "（逗号分隔的允许主机列表，支持 *.example.com 通配）。"
        )

    if not _host_allowed(host):
        return (
            f"目标主机不在白名单内: {host}。"
            f"当前白名单: {', '.join(ALLOWED_HOSTS)}"
        )

    if not ALLOW_PRIVATE and _resolves_to_internal(host):
        return (
            f"拒绝访问内网/回环地址: {host}。"
            "如确需调用内网服务，请显式设置 HTTP_TOOL_ALLOW_PRIVATE=true。"
        )

    return ""


async def _http_request(
    url: str,
    method: str = "GET",
    headers: str = "{}",
    body: str = "",
    timeout: float = HTTP_TIMEOUT,
) -> str:
    method = method.upper()
    if method not in ALLOWED_METHODS:
        return f"不支持的 HTTP 方法: {method}。支持的方法: {', '.join(sorted(ALLOWED_METHODS))}"

    url_error = _validate_url(url)
    if url_error:
        return url_error

    try:
        parsed_headers = json.loads(headers)
    except json.JSONDecodeError:
        parsed_headers = {"Content-Type": "application/json"}

    if not isinstance(parsed_headers, dict):
        return "headers 参数必须是 JSON 对象格式。"

    blocked = [k for k in parsed_headers if k.lower() in BLOCKED_REQUEST_HEADERS]
    if blocked:
        return f"不允许设置以下请求头: {', '.join(blocked)}"

    parsed_headers.setdefault("User-Agent", "RAG-Agent/1.0")

    try:
        # 不跟随重定向：否则白名单校验可被 302 跳转绕过
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            kwargs = {"headers": parsed_headers}

            if method in ("POST", "PUT", "PATCH") and body:
                try:
                    json.loads(body)
                    kwargs["content"] = body
                except json.JSONDecodeError:
                    kwargs["content"] = body

            resp = await client.request(method, url, **kwargs)

            content_type = resp.headers.get("content-type", "")

            if "application/json" in content_type:
                try:
                    data = resp.json()
                    formatted = json.dumps(data, ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    formatted = resp.text
            else:
                formatted = resp.text

            if len(formatted) > HTTP_MAX_RESPONSE:
                formatted = formatted[:HTTP_MAX_RESPONSE] + f"\n\n... (响应过长，已截断至 {HTTP_MAX_RESPONSE} 字符)"

            redirect_note = ""
            if resp.is_redirect:
                location = resp.headers.get("location", "")
                redirect_note = (
                    f"\n(该响应为重定向到 {location}，出于安全考虑未自动跟随；"
                    "如确需访问，请将该主机加入白名单后直接请求该地址)"
                )

            return (
                f"HTTP {method} {url}\n"
                f"状态码: {resp.status_code}\n"
                f"Content-Type: {content_type}\n"
                f"{'=' * 40}\n"
                f"{formatted}{redirect_note}"
            )

    except httpx.TimeoutException:
        return f"HTTP 请求超时 ({timeout} 秒): {method} {url}"
    except httpx.InvalidURL:
        return f"无效的 URL: {url}"
    except Exception as e:
        return f"HTTP 请求失败: {type(e).__name__}: {e}"

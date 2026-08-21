import json
import httpx

HTTP_TIMEOUT = 30.0
HTTP_MAX_RESPONSE = 5000

ALLOWED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


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

    try:
        parsed_headers = json.loads(headers)
    except json.JSONDecodeError:
        parsed_headers = {"Content-Type": "application/json"}

    if not isinstance(parsed_headers, dict):
        return "headers 参数必须是 JSON 对象格式。"

    parsed_headers.setdefault("User-Agent", "RAG-Agent/1.0")

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
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

            return (
                f"HTTP {method} {url}\n"
                f"状态码: {resp.status_code}\n"
                f"Content-Type: {content_type}\n"
                f"{'=' * 40}\n"
                f"{formatted}"
            )

    except httpx.TimeoutException:
        return f"HTTP 请求超时 ({timeout} 秒): {method} {url}"
    except httpx.InvalidURL:
        return f"无效的 URL: {url}"
    except Exception as e:
        return f"HTTP 请求失败: {type(e).__name__}: {e}"
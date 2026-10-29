#!/usr/bin/env python
"""LLM 端点能力探测（交付验收工具）

在任何**能访问目标模型服务**的机器上运行，判断该端点是否满足本项目三项要求：

  1. 基础对话   —— 能不能用
  2. 流式输出   —— 聊天页用 SSE 逐字渲染；不支持会变成"长时间空白后一次性弹出"
  3. 工具调用   —— Agent 模式（ReAct 循环）依赖 function calling；
                   不支持则必须关闭 Agent 模式，只保留纯 RAG 问答

只依赖 Python 标准库，不 import 项目代码，因此在未配置 JWT/令牌的干净检出上也能跑。

用法：
    python deploy/check-llm.py
    python deploy/check-llm.py --model qwen2.5-7b-instruct
    python deploy/check-llm.py --base-url http://10.0.0.21:8000/v1 --api-key EMPTY

配置来源（优先级）：命令行参数 > 真实环境变量 > 仓库根 .env > backend/.env
变量名兼容 LLM_* 与 DEEPSEEK_*。

退出码：0 = 三项全部可用；1 = 存在不可用项；2 = 连端点都连不上
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

GREEN, RED, YELLOW, CYAN, NC = "\033[32m", "\033[31m", "\033[33m", "\033[36m", "\033[0m"


def step(title: str) -> None:
    print(f"\n{CYAN}=== {title} ==={NC}")


def ok(msg: str) -> None:
    print(f"  {GREEN}[OK]{NC} {msg}")


def bad(msg: str) -> None:
    print(f"  {RED}[FAIL]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}[WARN]{NC} {msg}")


def read_env_file(path: Path) -> dict:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def resolve_config(args) -> tuple[str, str, str]:
    """返回 (base_url, api_key, model)，命令行 > 环境变量 > .env 文件。"""
    file_env: dict[str, str] = {}
    for p in (REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"):
        for k, v in read_env_file(p).items():
            file_env.setdefault(k, v)

    def pick(*names, default=""):
        for n in names:
            if os.environ.get(n):
                return os.environ[n]
        for n in names:
            if file_env.get(n):
                return file_env[n]
        return default

    base = args.base_url or pick("LLM_BASE_URL", "DEEPSEEK_BASE_URL", default="https://api.deepseek.com")
    key = args.api_key or pick("LLM_API_KEY", "DEEPSEEK_API_KEY")
    model = args.model or pick("LLM_MODEL", "DEEPSEEK_MODEL", default="deepseek-chat")
    return base, key, model


def endpoint_url(base_url: str, path: str) -> str:
    """拼接地址，兼容 base_url 结尾带 / 或带 /v1 两种写法。"""
    base = (base_url or "").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return f"{base}{path}"


def post_json(url: str, api_key: str, payload: dict, timeout: float = 60.0):
    """返回 (status, data_or_text, elapsed_ms, raw_response)。异常时抛 urllib.error。"""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    t0 = time.time()
    resp = urllib.request.urlopen(req, timeout=timeout)
    elapsed = (time.time() - t0) * 1000
    raw = resp.read().decode("utf-8", errors="replace")
    try:
        return resp.status, json.loads(raw), elapsed, resp
    except json.JSONDecodeError:
        return resp.status, raw, elapsed, resp


def describe_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
    except Exception:  # noqa: BLE001
        detail = ""
    return f"HTTP {exc.code}{'：' + detail if detail else ''}"


# --------------------------------------------------------------- 探测 1：基础对话
def probe_chat(url: str, key: str, model: str) -> bool:
    step("探测 1/3：基础对话")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "请只回复两个字：正常"}],
        "stream": False,
        "max_tokens": 32,
    }
    try:
        status, data, ms, _ = post_json(url, key, payload)
    except urllib.error.HTTPError as exc:
        bad(f"调用失败：{describe_http_error(exc)}")
        return False
    except Exception as exc:  # noqa: BLE001
        bad(f"无法连接端点：{type(exc).__name__}: {exc}")
        return False

    if status != 200 or not isinstance(data, dict):
        bad(f"返回异常：HTTP {status}")
        return False
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    if not content.strip():
        bad("返回内容为空")
        return False
    usage = data.get("usage") or {}
    ok(f"可用，耗时 {ms:.0f}ms，回复={content.strip()[:30]!r}")
    if usage:
        print(f"       token 用量：prompt={usage.get('prompt_tokens')} "
              f"completion={usage.get('completion_tokens')}")
    return True


# --------------------------------------------------------------- 探测 2：流式输出
def probe_stream(url: str, key: str, model: str) -> bool:
    step("探测 2/3：流式输出（聊天页逐字渲染依赖）")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "请数出 1 到 10，用逗号分隔，不要解释。"}],
        "stream": True,
        "max_tokens": 64,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    t0 = time.time()
    first_ms = None
    chunks = 0
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    obj = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                delta = (obj.get("choices") or [{}])[0].get("delta") or {}
                if delta.get("content"):
                    chunks += 1
                    if first_ms is None:
                        first_ms = (time.time() - t0) * 1000
    except urllib.error.HTTPError as exc:
        bad(f"流式调用失败：{describe_http_error(exc)}")
        return False
    except Exception as exc:  # noqa: BLE001
        bad(f"流式调用异常：{type(exc).__name__}: {exc}")
        return False

    if chunks == 0:
        bad("未收到任何流式分片（服务端可能不支持 stream=true）")
        return False
    if chunks == 1:
        warn(f"只收到 1 个分片，可能是伪流式（一次性返回）；首字 {first_ms:.0f}ms")
        return True
    ok(f"支持流式：{chunks} 个分片，首字延迟 {first_ms:.0f}ms")
    return True


# --------------------------------------------------------------- 探测 3：工具调用
TOOL_SCHEMA = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询指定城市的天气",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "城市名称"}},
            "required": ["city"],
        },
    },
}]


def probe_tools(url: str, key: str, model: str) -> bool:
    step("探测 3/3：工具调用 / function calling（Agent 模式依赖）")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "杭州现在天气怎么样？请调用工具查询。"}],
        "tools": TOOL_SCHEMA,
        "tool_choice": "auto",
        "stream": False,
        "max_tokens": 128,
    }
    try:
        status, data, ms, _ = post_json(url, key, payload)
    except urllib.error.HTTPError as exc:
        code = exc.code
        bad(f"调用失败：{describe_http_error(exc)}")
        if code in (400, 422):
            warn("端点拒绝带 tools 的请求 → 该模型很可能不支持 function calling")
        return False
    except Exception as exc:  # noqa: BLE001
        bad(f"异常：{type(exc).__name__}: {exc}")
        return False

    if status != 200 or not isinstance(data, dict):
        bad(f"返回异常：HTTP {status}")
        return False

    message = (data.get("choices") or [{}])[0].get("message") or {}
    calls = message.get("tool_calls") or []
    if calls:
        fn = (calls[0].get("function") or {})
        ok(f"支持工具调用：{fn.get('name')}({fn.get('arguments')})  耗时 {ms:.0f}ms")
        return True

    finish = (data.get("choices") or [{}])[0].get("finish_reason")
    bad("未返回 tool_calls")
    if finish == "tool_calls":
        warn("finish_reason 显示为 tool_calls 但未解析到调用内容，可能是协议实现差异")
    else:
        warn("模型忽略了工具定义，直接作答 → Agent 模式不可用，建议关闭（见下方建议）")
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="LLM 端点能力探测")
    ap.add_argument("--base-url", help="OpenAI 兼容端点，如 http://10.0.0.21:8000/v1")
    ap.add_argument("--api-key", help="API Key（私有端点常可为任意非空值）")
    ap.add_argument("--model", help="模型名，如 qwen2.5-7b-instruct")
    ap.add_argument("--timeout", type=float, default=60.0, help="单次请求超时秒数")
    args = ap.parse_args()

    base, key, model = resolve_config(args)

    print("=" * 66)
    print("LLM 端点能力探测")
    print("=" * 66)
    print(f"  端点   : {base}")
    print(f"  模型   : {model}")
    print(f"  API Key: {'已配置（长度 %d）' % len(key) if key else '未配置（多数私有端点可留空，但此处会以空 Bearer 发送）'}")

    chat_url = endpoint_url(base, "/v1/chat/completions")

    r_chat = probe_chat(chat_url, key, model)
    if not r_chat:
        print(f"\n{RED}端点不可用，后续探测跳过。{NC}")
        print("  排查建议：")
        print("    1) 确认地址与端口可达（curl -v <端点>/v1/models）")
        print("    2) 若端点本身带 /v1，两种写法都已兼容，无需去掉")
        print("    3) 检查 API Key 是否正确（401 表示地址通、密钥错）")
        return 2

    r_stream = probe_stream(chat_url, key, model)
    r_tools = probe_tools(chat_url, key, model)

    print("\n" + "=" * 66)
    print("结论")
    print("=" * 66)
    print(f"  基础对话 : {'可用' if r_chat else '不可用'}")
    print(f"  流式输出 : {'可用' if r_stream else '不可用'}")
    print(f"  工具调用 : {'可用' if r_tools else '不可用'}")

    print("\n  配置建议：")
    if r_tools:
        print("    ENABLE_AGENT_MODE=true    # 三项均可用，Agent 模式可开启")
    else:
        print("    ENABLE_AGENT_MODE=false   # 模型不支持工具调用，关闭 Agent 模式")
        print("    ENABLE_INTENT_ROUTING=true  # 仍可按意图分流到纯 RAG 问答")
        print("    说明：关闭 Agent 后「查统计/导出/联网搜索」等操作类请求不可用，")
        print("          但制度问答（核心场景）不受影响。")
    if not r_stream:
        print("    警告：不支持流式，聊天页会变为长时间空白后一次性显示，建议更换端点。")
    if not key:
        print("    提示：当前未配置 API Key；若端点要求鉴权，请设置 LLM_API_KEY。")

    print("\n  换模型只需改 .env（无需改代码）：")
    print("    LLM_BASE_URL=...   LLM_API_KEY=...   LLM_MODEL=...")
    print("=" * 66)

    return 0 if (r_chat and r_stream and r_tools) else 1


if __name__ == "__main__":
    sys.exit(main())

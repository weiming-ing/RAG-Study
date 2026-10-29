#!/usr/bin/env python
"""P0 安全整改验证脚本（只读，不修改任何文件）

逐项核验本轮整改是否生效，可直接重复运行：

  1. 配置层：JWT 密钥、内部接口令牌、CORS 白名单是否来自环境且非弱默认值
  2. 一致性：根 .env / docker/.env / backend/.env 的关键值是否一致
  3. 残留扫描：源码/编排文件中是否还有硬编码口令、开发密钥、通配 CORS
  4. Java 侧：内部接口过滤器与 Security 配置是否就位
  5. SSRF 白名单：对 http_request 工具做行为矩阵测试
  6. 请求头注入：internal_headers() 是否正确携带令牌

用法：
    python deploy/verify-p0.py
退出码：0 = 全部通过，1 = 存在失败项
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "", warn_only: bool = False) -> None:
    status = PASS if ok else (WARN if warn_only else FAIL)
    results.append((status, name, detail))


def read_env(path: Path) -> dict:
    data = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v
    return data


# ---------------------------------------------------------------- 1. 配置层
print("=" * 68)
print("1) 配置层检查（backend/config.py）")
print("=" * 68)
try:
    import config  # noqa: E402

    jwt_len = len(config.JWT_SECRET_KEY)
    check("JWT 密钥已配置且 >= 32 字符", jwt_len >= 32, f"长度={jwt_len}")
    check(
        "JWT 密钥非内置开发默认值",
        "rag-study-dev-secret-key" not in config.JWT_SECRET_KEY,
        "未回落到旧默认值",
    )
    check(
        "内部接口令牌已配置",
        bool(config.INTERNAL_API_TOKEN),
        f"长度={len(config.INTERNAL_API_TOKEN)}",
    )
    check(
        "CORS 不含通配来源",
        "*" not in config.CORS_ALLOW_ORIGINS,
        f"{len(config.CORS_ALLOW_ORIGINS)} 个来源",
    )
    check("CORS 来源列表非空", len(config.CORS_ALLOW_ORIGINS) > 0)
except Exception as exc:  # 配置层失败则后续依赖它的检查无意义
    check("导入 backend/config.py", False, f"{type(exc).__name__}: {exc}")

# ------------------------------------------------------- 2. 跨文件一致性
print("\n" + "=" * 68)
print("2) 跨 .env 一致性（Python 与 Java 必须共用同一 JWT 密钥）")
print("=" * 68)
root_env = read_env(REPO_ROOT / ".env")
docker_env = read_env(REPO_ROOT / "docker" / ".env")
backend_env = read_env(BACKEND / ".env")

check(
    "根 .env 的 JWT_SECRET 与 backend/.env 的 JWT_SECRET_KEY 一致",
    bool(root_env.get("JWT_SECRET"))
    and root_env.get("JWT_SECRET") == backend_env.get("JWT_SECRET_KEY"),
)
check(
    "根 .env 的 JWT_SECRET 与 docker/.env 的 JWT_SECRET 一致",
    bool(root_env.get("JWT_SECRET")) and root_env.get("JWT_SECRET") == docker_env.get("JWT_SECRET"),
)
for label, env in (("根 .env", root_env), ("docker/.env", docker_env), ("backend/.env", backend_env)):
    token = env.get("INTERNAL_API_TOKEN", "")
    check(f"{label} 含 INTERNAL_API_TOKEN 且与根一致",
          bool(token) and token == root_env.get("INTERNAL_API_TOKEN"),
          f"长度={len(token)}")
check(
    "根 .env 的 DB_PASSWORD 与 MYSQL_ROOT_PASSWORD 一致",
    bool(root_env.get("DB_PASSWORD"))
    and root_env.get("DB_PASSWORD") == root_env.get("MYSQL_ROOT_PASSWORD"),
)
check(
    "Qdrant 端口变量名已修正（HTTP=6333 / gRPC=6334）",
    root_env.get("QDRANT_HTTP_PORT") == "6333" and root_env.get("QDRANT_GRPC_PORT") == "6334",
    f"HTTP={root_env.get('QDRANT_HTTP_PORT')} gRPC={root_env.get('QDRANT_GRPC_PORT')}",
)

# ---------------------------------------------------------- 3. 残留扫描
print("\n" + "=" * 68)
print("3) 残留扫描（源码 / 编排 / 脚本）")
print("=" * 68)
PATTERNS = {
    "硬编码 MySQL 口令 19980315": re.compile(r"19980315"),
    "开发用 JWT 默认密钥": re.compile(r"rag-study-dev-secret-key|rag-study-docker-secret-key"),
    "通配 CORS 来源": re.compile(r'allow_origins\s*=\s*\[\s*["\']\*["\']|AllowedOriginPatterns\(List\.of\("\*"\)\)'),
    "compose 中的弱口令默认值": re.compile(r":-19980315|:-rag-study-docker-secret-key"),
}
SCAN_ROOTS = ["backend", "rag-engine/src", "rag-admin/src", "deploy", "frontend", "docker", ".github"]
SKIP_DIRS = {"node_modules", "target", "dist", ".venv", "__pycache__", ".git"}
SOURCE_EXT = {".py", ".yml", ".yaml", ".java", ".bat", ".ps1", ".js", ".vue", ".conf", ".sql", ".ts"}
# 仅注释中提及旧写法的行不算残留
COMMENT_ONLY = re.compile(r"^\s*(#|//|\*|<!--)")

found_any = False
SELF = Path(__file__).resolve()
for rel in SCAN_ROOTS:
    base = REPO_ROOT / rel
    if not base.exists():
        continue
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_EXT:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        # 跳过本脚本自身：它必须包含这些模式作为检测规则
        if path.resolve() == SELF:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, rx in PATTERNS.items():
            for i, line in enumerate(text.splitlines(), 1):
                if rx.search(line) and not COMMENT_ONLY.match(line):
                    print(f"  [{label}] {path.relative_to(REPO_ROOT)}:{i}: {line.strip()[:90]}")
                    found_any = True
check("未发现残留硬编码密钥/弱口令/通配 CORS", not found_any)

compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
for var in ("MYSQL_ROOT_PASSWORD", "DB_PASSWORD", "JWT_SECRET", "INTERNAL_API_TOKEN"):
    check(f"compose 中 {var} 为必填项（无弱默认值）", f"${{{var}:?" in compose)

# ------------------------------------------------------------ 4. Java 侧
print("\n" + "=" * 68)
print("4) Java 侧（内部接口鉴权）")
print("=" * 68)
filter_path = REPO_ROOT / "rag-engine/src/main/java/com/ragstudy/security/InternalApiAuthFilter.java"
security_path = REPO_ROOT / "rag-engine/src/main/java/com/ragstudy/config/SecurityConfig.java"
check("InternalApiAuthFilter 存在", filter_path.exists())
if filter_path.exists():
    fsrc = filter_path.read_text(encoding="utf-8")
    check("过滤器校验 X-Internal-Token", "X-Internal-Token" in fsrc)
    check("过滤器使用常量时间比较", "MessageDigest.isEqual" in fsrc)
    check("过滤器对 /api/internal 前缀生效", '"/api/internal"' in fsrc)
if security_path.exists():
    ssrc = security_path.read_text(encoding="utf-8")
    check("过滤器已注册到安全链", "internalApiAuthFilter" in ssrc and "addFilterBefore" in ssrc)
    check("CORS 来源改为可配置", "rag.cors.allowed-origins" in ssrc)
    check("不再使用通配来源模式", 'List.of("*")' not in ssrc.split("corsConfigurationSource")[0])
    check("actuator 仅放行 health", '"/actuator/health"' in ssrc and '"/actuator/**").authenticated()' in ssrc)

app_yml = (REPO_ROOT / "rag-engine/src/main/resources/application.yml").read_text(encoding="utf-8")
check("datasource 口令无默认值", "password: ${DB_PASSWORD}" in app_yml)
check("jwt.secret 无默认值", "secret: ${JWT_SECRET}" in app_yml)
check("内部令牌无默认值", "token: ${INTERNAL_API_TOKEN}" in app_yml)

# --------------------------------------------------- 5. SSRF 行为矩阵
print("\n" + "=" * 68)
print("5) SSRF 白名单行为矩阵（http_request 工具）")
print("=" * 68)


def ssrf_matrix(allowed: str, allow_private: str) -> list[tuple[str, str, bool]]:
    """在指定环境变量下重新加载模块，返回 (URL, 说明, 是否放行) 列表。"""
    os.environ["HTTP_TOOL_ALLOWED_HOSTS"] = allowed
    os.environ["HTTP_TOOL_ALLOW_PRIVATE"] = allow_private
    from agent.tools import api_integration as ai

    import importlib

    importlib.reload(ai)
    cases = [
        ("http://example.com/api", "白名单内主机"),
        ("http://evil.example.org/api", "白名单外主机"),
        ("http://sub.internal.example.com/api", "通配子域"),
        ("http://internal.example.com/api", "通配不匹配裸域"),
        ("file:///etc/passwd", "非 http(s) 协议"),
        ("http://127.0.0.1:3306/", "回环地址"),
        ("http://169.254.169.254/latest/meta-data/", "云元数据地址"),
    ]
    out = []
    for url, desc in cases:
        out.append((url, desc, ai._validate_url(url) == ""))
    return out


print("  [A] 未配置白名单（默认，应全部拒绝）")
for url, desc, ok in ssrf_matrix("", "false"):
    print(f"      {'放行' if ok else '拒绝'}  {desc:<22} {url}")
    check(f"空白名单拒绝：{desc}", not ok)

print("  [B] 白名单 example.com,*.internal.example.com 且允许内网（用于验证域名匹配）")
for url, desc, ok in ssrf_matrix("example.com,*.internal.example.com", "true"):
    print(f"      {'放行' if ok else '拒绝'}  {desc:<22} {url}")
    if desc in ("白名单内主机", "通配子域"):
        check(f"白名单放行：{desc}", ok)
    elif desc == "通配不匹配裸域":
        check(f"通配不匹配裸域（应拒绝）：{desc}", not ok)
    else:
        check(f"白名单外拒绝：{desc}", not ok)

print("  [C] 白名单含 localhost 但禁止内网（应拒绝回环）")
for url, desc, ok in ssrf_matrix("localhost,127.0.0.1,169.254.169.254", "false"):
    print(f"      {'放行' if ok else '拒绝'}  {desc:<22} {url}")
    if desc in ("回环地址", "云元数据地址"):
        check(f"禁止内网时拒绝：{desc}", not ok)

api_src = (BACKEND / "agent/tools/api_integration.py").read_text(encoding="utf-8")
check("不自动跟随重定向", "follow_redirects=False" in api_src)
check("拦截危险请求头", "BLOCKED_REQUEST_HEADERS" in api_src)

# -------------------------------------------------------- 6. 请求头注入
print("\n" + "=" * 68)
print("6) 内部接口请求头注入")
print("=" * 68)
try:
    from utils.internal_api import INTERNAL_TOKEN_HEADER, internal_headers

    h = internal_headers()
    check("internal_headers() 携带令牌", bool(h.get(INTERNAL_TOKEN_HEADER)))
    h2 = internal_headers({"Authorization": "Bearer x", "Empty": None})
    check("保留额外请求头", h2.get("Authorization") == "Bearer x")
    check("忽略空值请求头", "Empty" not in h2)
except Exception as exc:
    check("导入 utils/internal_api.py", False, f"{type(exc).__name__}: {exc}")

CALLERS = [
    "backend/services/rag_service.py",
    "backend/routes/knowledge.py",
    "backend/routes/knowledge_bases.py",
    "backend/agent/tools/file_parser.py",
    "backend/mcp_server.py",
    "backend/seed_kb.py",
    "backend/migrate_docs.py",
]
for rel in CALLERS:
    src = (REPO_ROOT / rel).read_text(encoding="utf-8")
    check(f"{rel} 已注入内部令牌", "internal_headers" in src)

# ------------------------------------------------------------------ 汇总
print("\n" + "=" * 68)
failed = [r for r in results if r[0] == FAIL]
warned = [r for r in results if r[0] == WARN]
print(f"汇总：通过 {len(results) - len(failed) - len(warned)} / 失败 {len(failed)} / 警告 {len(warned)}")
if failed:
    print("\n失败项：")
    for _, name, detail in failed:
        print(f"  - {name} {detail}")
print("=" * 68)
sys.exit(1 if failed else 0)

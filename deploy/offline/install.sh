#!/usr/bin/env bash
# =============================================================================
# RAG 助手 — 客户侧离线安装脚本
# =============================================================================
# 在客户内网机器上执行，全程不需要外网。流程：
#   1. 环境预检（docker / compose / 磁盘 / 端口）
#   2. 校验交付包完整性（SHA256SUMS）
#   3. 加载镜像并核对 manifest
#   4. 生成 .env（自动生成 JWT 与内部接口令牌）
#   5. 启动服务并等待健康
#   6. 安全断言：确认 /api/internal/** 已受保护
#
# 用法：
#   ./install.sh                     # 完整安装
#   ./install.sh --check-only        # 只做预检与校验，不改动系统
#   ./install.sh --http-port 8080    # 指定对外 HTTP 端口（默认 80）
#   ./install.sh --yes               # 非交互，缺失项用安全默认值
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CHECK_ONLY=0
ASSUME_YES=0
HTTP_PORT=80

RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; CYAN=$'\033[36m'; NC=$'\033[0m'
step()  { printf '\n%s=== %s ===%s\n' "$CYAN" "$1" "$NC"; }
ok()    { printf '  %s[OK]%s %s\n' "$GREEN" "$NC" "$1"; }
warn()  { printf '  %s[WARN]%s %s\n' "$YELLOW" "$NC" "$1"; }
fail()  { printf '  %s[FAIL]%s %s\n' "$RED" "$NC" "$1" >&2; exit 1; }

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --check-only) CHECK_ONLY=1 ;;
    --yes|-y)     ASSUME_YES=1 ;;
    --http-port)  HTTP_PORT="${2:-}"; [ -n "$HTTP_PORT" ] || fail "--http-port 需要参数"; shift ;;
    -h|--help)    usage; exit 0 ;;
    *)            printf '未知参数: %s\n' "$1" >&2; usage; exit 2 ;;
  esac
  shift
done

# ---------------------------------------------------------------- 工具函数
gen_secret() {
  # 生成 URL-safe 密钥；JWT 要求 >= 32 字符，这里给 64 字符
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 48 | tr -d '\n=' | tr '+/' '-_'
  else
    head -c 48 /dev/urandom | base64 | tr -d '\n=' | tr '+/' '-_'
  fi
}

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${port}\$"; then return 0; fi
    return 1
  fi
  if command -v netstat >/dev/null 2>&1; then
    if netstat -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${port}\$"; then return 0; fi
    return 1
  fi
  return 1
}

http_code() {
  curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$@" 2>/dev/null || echo '000'
}

# ------------------------------------------------------------- 1. 环境预检
step '1/6 环境预检'

command -v docker >/dev/null 2>&1 || fail '未找到 docker，请先安装 Docker Engine 20.10+'
ok 'docker 命令存在'

if ! docker info >/dev/null 2>&1; then
  fail 'Docker daemon 未运行或当前用户无权限（可尝试 sudo，或将用户加入 docker 组后重新登录）'
fi
ok 'Docker daemon 可用'

if ! docker compose version >/dev/null 2>&1; then
  fail '未找到 docker compose v2 插件（注意是 "docker compose"，不是 "docker-compose"）'
fi
ok "docker compose 可用（$(docker compose version --short 2>/dev/null || echo v2)）"

for c in sha256sum tar curl; do
  command -v "$c" >/dev/null 2>&1 || fail "缺少必需命令: $c"
done
ok 'sha256sum / tar / curl 均可用'

[ -f docker-compose.yml ] || fail '当前目录缺少 docker-compose.yml，请在交付包根目录执行'
[ -f manifest.json ]      || fail '当前目录缺少 manifest.json，交付包不完整'
ok '交付包结构完整'

IMAGE_TAR="$(find . -maxdepth 2 -name 'rag-assistant-images-*.tar' -type f | head -n1)"
[ -n "$IMAGE_TAR" ] || fail '未找到镜像 tar 包（images/rag-assistant-images-*.tar）'
TAR_GB=$(awk -v b="$(stat -c %s "$IMAGE_TAR")" 'BEGIN{printf "%.2f", b/1024/1024/1024}')
ok "镜像包: ${IMAGE_TAR#./} (${TAR_GB}GB)"

AVAIL_KB=$(df -Pk . | awk 'NR==2{print $4}')
NEED_KB=$(awk -v b="$(stat -c %s "$IMAGE_TAR")" 'BEGIN{printf "%d", b/1024*2.5}')
if [ "$AVAIL_KB" -lt "$NEED_KB" ]; then
  fail "磁盘空间不足：需要约 $((NEED_KB/1024/1024))GB（镜像 tar 解压 + 数据卷），当前可用 $((AVAIL_KB/1024/1024))GB"
fi
ok "磁盘空间充足（可用 $((AVAIL_KB/1024/1024))GB）"

for p in "$HTTP_PORT" 3306 6379 6333 6334 8001 8002; do
  if port_in_use "$p"; then fail "端口 $p 已被占用，请先释放或改用 --http-port 指定其他端口"; fi
done
ok '所需端口均空闲'

if [ "$(id -u)" -ne 0 ] && [ "$HTTP_PORT" -lt 1024 ]; then
  warn "当前非 root 用户且 HTTP 端口为 ${HTTP_PORT}（<1024），可能无法绑定；必要时用 --http-port 8080"
fi

# ------------------------------------------------------- 2. 校验交付包完整性
step '2/6 校验交付包完整性'
if [ -f SHA256SUMS ]; then
  if sha256sum -c SHA256SUMS --quiet 2>/dev/null; then
    ok 'SHA256SUMS 全部校验通过'
  else
    fail '校验和不匹配：交付包可能损坏或被篡改，请重新获取'
  fi
else
  warn '未找到 SHA256SUMS，跳过完整性校验'
fi

if [ "$CHECK_ONLY" = "1" ]; then
  step '预检完成（--check-only）'
  ok '环境满足安装条件，去掉 --check-only 即可正式安装'
  exit 0
fi

# ------------------------------------------------------------ 3. 加载镜像
step '3/6 加载镜像'
printf '  正在 docker load（数分钟，取决于磁盘速度）...\n'
docker load -i "$IMAGE_TAR" >/dev/null || fail 'docker load 失败'
ok '镜像已加载'

# 按 manifest 核对每个镜像是否就位。
# 注意区分两种结果，避免把 docker 自身的报错误报成"镜像缺失"：
#   退出码 3 = 确实缺失   退出码 4 = docker inspect 无法完成（环境问题）
if command -v python3 >/dev/null 2>&1; then
  set +e
  CHECK_OUT=$(python3 - <<'PY'
import json, subprocess, sys

try:
    with open('manifest.json', encoding='utf-8') as fh:
        manifest = json.load(fh)
except Exception as exc:                      # noqa: BLE001
    print(f'manifest.json 解析失败: {exc}')
    sys.exit(4)

images = [i for i in manifest.get('images', []) if i.get('name')]
if not images:
    sys.exit(0)

missing, errors = [], []
for img in images:
    name = img['name']
    r = subprocess.run(
        ['docker', 'image', 'inspect', name, '--format', '{{.Id}}'],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        detail = (r.stderr or '').strip().splitlines()
        errors.append(f"{name}: {detail[-1] if detail else 'docker image inspect 失败'}")
    elif not r.stdout.strip():
        missing.append(name)

if missing:
    print(', '.join(missing))
    sys.exit(3)
if errors:
    print('; '.join(errors[:3]))
    sys.exit(4)
sys.exit(0)
PY
)
  CHECK_RC=$?
  set -e
  case "$CHECK_RC" in
    0) ok 'manifest 中的镜像全部就位' ;;
    3) fail "以下镜像未就位: $CHECK_OUT" ;;
    *) warn "无法核对 manifest 镜像（docker inspect 未成功，可能 daemon 或权限问题）：$CHECK_OUT"
       warn '如后续启动失败，请先手动确认镜像已加载：docker images' ;;
  esac
else
  warn '无 python3，跳过 manifest 镜像核对'
fi

# ------------------------------------------------------------- 4. 生成 .env
step '4/6 生成配置文件'
if [ -f .env ]; then
  warn '.env 已存在，保留原有配置不做覆盖'
  # shellcheck disable=SC1091
  set -a; . ./.env; set +a
else
  printf '  需要几个部署参数（直接回车使用默认值）：\n'

  MYSQL_PWD_IN="${MYSQL_ROOT_PASSWORD:-}"
  if [ -z "$MYSQL_PWD_IN" ]; then
    if [ "$ASSUME_YES" = "1" ]; then
      MYSQL_PWD_IN="$(gen_secret | cut -c1-24)"
      warn 'MySQL root 口令已自动生成，请记录：见 .env'
    else
      read -r -s -p '  MySQL root 口令（留空自动生成）: ' MYSQL_PWD_IN || true; printf '\n'
      [ -n "${MYSQL_PWD_IN:-}" ] || MYSQL_PWD_IN="$(gen_secret | cut -c1-24)"
    fi
  fi

  # 私有化部署时指向客户内网的 OpenAI 兼容端点
  LLM_BASE="${DEEPSEEK_BASE_URL:-}"
  if [ -z "$LLM_BASE" ] && [ "$ASSUME_YES" != "1" ]; then
    read -r -p '  LLM 服务地址（内网 vLLM/Ollama，回车用 DeepSeek 公网）: ' LLM_BASE || true
  fi
  [ -n "$LLM_BASE" ] || LLM_BASE='https://api.deepseek.com'

  LLM_KEY="${DEEPSEEK_API_KEY:-}"
  if [ -z "$LLM_KEY" ] && [ "$ASSUME_YES" != "1" ]; then
    read -r -s -p '  LLM API Key（内网模型可留空）: ' LLM_KEY || true; printf '\n'
  fi
  [ -n "$LLM_KEY" ] || LLM_KEY='sk-offline-placeholder'

  JWT_IN="$(gen_secret)"
  TOKEN_IN="$(gen_secret)"
  CORS_IN="http://localhost:${HTTP_PORT},http://127.0.0.1:${HTTP_PORT}"

  cat > .env <<EOF
# 由 install.sh 自动生成于 $(date '+%Y-%m-%d %H:%M:%S')
# 请勿提交到版本库；修改后需 docker compose up -d 重新生效

MYSQL_ROOT_PASSWORD=${MYSQL_PWD_IN}
MYSQL_PASSWORD=${MYSQL_PWD_IN}
MYSQL_DATABASE=rag_engine
MYSQL_PORT=3306
REDIS_PORT=6379
QDRANT_HTTP_PORT=6333
QDRANT_GRPC_PORT=6334

DB_USERNAME=root
DB_PASSWORD=${MYSQL_PWD_IN}

# Python 与 Java 必须共用同一 JWT 密钥（至少 32 字符）
JWT_SECRET=${JWT_IN}

# /api/internal/** 的服务间接口令牌，Python 与 Java 必须一致
INTERNAL_API_TOKEN=${TOKEN_IN}

# 大模型（OpenAI 兼容端点）。
# 注意数据流向：用户提问 + 检索到的制度原文片段会发送到该地址。
# 客户有"数据不得出内网"要求时，必须改为内网私有模型。
LLM_BASE_URL=${LLM_BASE}
LLM_API_KEY=${LLM_KEY}
LLM_MODEL=${LLM_MODEL:-deepseek-chat}

# 允许访问的前端来源，逗号分隔；不要使用 *
CORS_ALLOW_ORIGINS=${CORS_IN}

# Agent http_request 工具出站控制：留空即禁用该工具
HTTP_TOOL_ALLOWED_HOSTS=${HTTP_TOOL_ALLOWED_HOSTS:-}
HTTP_TOOL_ALLOW_PRIVATE=${HTTP_TOOL_ALLOW_PRIVATE:-false}

PYTHON_PORT=8001
JAVA_PORT=8002
FRONTEND_PORT=${HTTP_PORT}
EOF
  chmod 600 .env
  ok '.env 已生成（权限 600）'
fi

# 必填项自查：这些项缺失会直接导致 Java 启动失败
for k in MYSQL_ROOT_PASSWORD DB_PASSWORD JWT_SECRET INTERNAL_API_TOKEN; do
  v="$(grep -E "^${k}=" .env | head -n1 | cut -d= -f2- || true)"
  [ -n "$v" ] || fail ".env 缺少必填项 ${k}"
done
JWT_LEN="$(grep -E '^JWT_SECRET=' .env | head -n1 | cut -d= -f2- | wc -c)"
[ "$JWT_LEN" -ge 33 ] || fail 'JWT_SECRET 长度不足 32 字符'
ok '.env 必填项齐备'

# 授权相关配置：机器标识取自宿主机（容器内 /etc/machine-id 重建后会变），
# 这样绑定机器的授权在容器重建后依然有效。
HOST_MACHINE_ID="$(cat /etc/machine-id 2>/dev/null || hostname)"
if ! grep -qE '^LICENSE_MACHINE_ID=' .env; then
  printf '\n# 授权机器绑定用的机器标识（取自宿主机）\nLICENSE_MACHINE_ID=%s\n' "$HOST_MACHINE_ID" >> .env
fi
if ! grep -qE '^LICENSE_FILE=' .env; then
  printf 'LICENSE_FILE=/app/license.json\n' >> .env
fi

# 保证挂载点是文件：若 license.json 不存在，Docker 会把挂载点建成目录，
# 之后再放真实授权文件就会失败。
if [ ! -f license.json ]; then
  : > license.json
  warn '未找到授权文件 license.json（已创建占位空文件）：问答/Agent/入库将被禁用，请向供应商获取授权'
fi
ok '授权配置就绪'

# --------------------------------------------------------------- 5. 启动
step '5/6 启动服务'
# --no-build 是关键：客户内网没有外网，绝不能触发镜像构建
docker compose up -d --no-build || fail 'docker compose up 失败，请查看 docker compose logs'
ok '容器已启动'

PY_PORT="$(grep -E '^PYTHON_PORT=' .env | head -n1 | cut -d= -f2-)"; PY_PORT="${PY_PORT:-8001}"
JAVA_PORT="$(grep -E '^JAVA_PORT=' .env | head -n1 | cut -d= -f2-)"; JAVA_PORT="${JAVA_PORT:-8002}"

printf '  等待 Java 引擎就绪（首次启动需加载 ONNX 模型，可能 1-3 分钟）...\n'
for i in $(seq 1 60); do
  code="$(http_code "http://127.0.0.1:${JAVA_PORT}/actuator/health")"
  [ "$code" = "200" ] && break
  sleep 5
  [ "$i" = "60" ] && fail "Java 引擎未在 5 分钟内就绪（最后状态码 $code），请执行 docker compose logs rag-engine"
done
ok 'Java 引擎健康'

printf '  等待 Python 编排层就绪...\n'
for i in $(seq 1 24); do
  code="$(http_code "http://127.0.0.1:${PY_PORT}/api/health")"
  [ "$code" = "200" ] && break
  sleep 5
  [ "$i" = "24" ] && fail "Python 后端未在 2 分钟内就绪（最后状态码 $code），请执行 docker compose logs backend"
done
ok 'Python 后端健康'

# ------------------------------------------------- 6. 安全断言与模型自检
step '6/6 安全与模型自检'
TOKEN="$(grep -E '^INTERNAL_API_TOKEN=' .env | head -n1 | cut -d= -f2-)"
ANON="$(http_code "http://127.0.0.1:${JAVA_PORT}/api/internal/health")"
if [ "$ANON" = "401" ]; then
  ok '服务间接口已受保护（匿名访问返回 401）'
else
  fail "服务间接口未受保护：匿名访问 /api/internal/health 返回 ${ANON}，应为 401。
       请确认 INTERNAL_API_TOKEN 已设置且 rag-engine 与 backend 使用同一值。"
fi
AUTH="$(http_code -H "X-Internal-Token: ${TOKEN}" "http://127.0.0.1:${JAVA_PORT}/api/internal/health")"
if [ "$AUTH" = "200" ]; then
  ok '携带正确令牌可正常访问（鉴权链路通）'
else
  fail "携带令牌访问失败（HTTP ${AUTH}），请检查 .env 中 INTERNAL_API_TOKEN 是否与容器内一致"
fi

# ---- LLM 端点可达性 ----
# 目的：避免"安装成功但聊天不可用"的静默失败——最典型的就是 API Key 仍是
# install.sh 自动填的占位值，或客户内网根本连不上公网模型服务。
LLM_BASE_CFG="$(grep -E '^(LLM_BASE_URL|DEEPSEEK_BASE_URL)=' .env | head -n1 | cut -d= -f2-)"
LLM_KEY_CFG="$(grep -E '^(LLM_API_KEY|DEEPSEEK_API_KEY)=' .env | head -n1 | cut -d= -f2-)"
if [ -z "$LLM_BASE_CFG" ]; then
  warn '未配置 LLM_BASE_URL / DEEPSEEK_BASE_URL：聊天功能将不可用'
else
  case "${LLM_BASE_CFG%/}" in
    */v1) LLM_MODELS_URL="${LLM_BASE_CFG%/}/models" ;;
    *)    LLM_MODELS_URL="${LLM_BASE_CFG%/}/v1/models" ;;
  esac
  LLM_HTTP="$(http_code -H "Authorization: Bearer ${LLM_KEY_CFG}" "$LLM_MODELS_URL")"
  case "$LLM_HTTP" in
    200)     ok "LLM 端点可用（${LLM_BASE_CFG}）" ;;
    401|403) warn "LLM 端点可达但鉴权失败（HTTP ${LLM_HTTP}）：聊天将不可用，请检查 LLM_API_KEY" ;;
    404|405) warn "LLM 端点未实现 /v1/models（HTTP ${LLM_HTTP}），无法自动校验；建议执行 python deploy/check-llm.py" ;;
    000)     warn "无法连接 LLM 端点（${LLM_BASE_CFG}）：请确认该地址在客户内网可达；纯离线环境需自建模型服务" ;;
    *)       warn "LLM 端点返回 HTTP ${LLM_HTTP}，请确认地址与密钥是否正确" ;;
  esac
  case "$LLM_KEY_CFG" in
    '')            warn 'LLM_API_KEY 为空：若端点需要鉴权，聊天会失败' ;;
    *placeholder*) warn "LLM_API_KEY 仍是占位值（${LLM_KEY_CFG}）：聊天会因鉴权失败，请在 .env 中填入真实 Key" ;;
  esac
fi

# ---- 授权状态与机器指纹 ----
LIC_MID="$(grep -E '^LICENSE_MACHINE_ID=' .env | head -n1 | cut -d= -f2-)"
if [ -s license.json ]; then
  ok "已放置授权文件（$(stat -c %s license.json) 字节）"
else
  warn '授权文件为空或缺失：问答/Agent/入库将被禁用（管理台可访问、数据可查看导出）'
fi
LIC_FP="$(printf 'rag-assistant|%s' "$LIC_MID" | sha256sum | cut -d' ' -f1)"
ok "本机机器指纹：${LIC_FP}"
printf '        （如需绑定本机的授权，把该指纹提供给供应商；授权文件放到本目录的 license.json 后执行 docker compose restart backend）\n'

# ---------------------------------------------------------------- 完成
step '安装完成'
cat <<EOF

  员工聊天页 : http://<本机IP>:${HTTP_PORT}/
  管理台     : http://<本机IP>:${HTTP_PORT}/admin/   （仅管理员使用）
  Python API : http://127.0.0.1:${PY_PORT}
  Java 引擎  : http://127.0.0.1:${JAVA_PORT}

  安全提醒（务必执行）:
    1) 初始管理员账号为 admin/admin123，请立即登录管理台修改密码
    2) .env 内含数据库口令与 JWT 密钥，权限已设为 600，请勿外传
    3) 若需把聊天页嵌进 OA / 企业微信，请参考 README 的 iframe 配置说明

  若上方出现 LLM 相关的 [WARN]，说明聊天功能可能不可用，请执行完整能力探测：
    python deploy/check-llm.py

  常用运维命令:
    docker compose ps                 # 查看状态
    docker compose logs -f backend    # 查看后端日志
    docker compose down               # 停止（保留数据卷）
    docker compose down -v            # 停止并删除数据（危险）

EOF

#!/usr/bin/env bash
# =============================================================================
# install.sh 集成自测（不需要真实 Docker）
# =============================================================================
# 目的：客户现场第一次执行 install.sh 之前，把能验的逻辑都验掉。
# 做法：构造一个假的交付包 + 用桩程序（stub）替代 docker / curl，
#       然后真实执行 install.sh 的完整流程与若干失败场景。
#
# 覆盖：
#   T1  --check-only 预检通过
#   T2  完整安装（--yes）：.env 生成合规、安全断言 401/200 通过
#   T3  交付包被篡改 → 校验和失败并拒绝安装
#   T4  缺少 manifest.json → 拒绝安装
#   T5  缺少镜像 tar → 拒绝安装
#   T6  安全断言失败场景：内部接口未受保护（匿名返回 200）→ 必须拒绝完成安装
#
# 用法：bash deploy/offline/test-install.sh
# 退出码：0 = 全部通过；1 = 存在失败
# =============================================================================

set -u

# Git for Windows 下若直接以 bash.exe 调用本脚本，PATH 可能不含 coreutils
# （表现为 dirname/mktemp/grep 全部 command not found）。这里显式补齐；
# Linux 上这些路径本就存在，无副作用。
export PATH="/usr/bin:/bin:/usr/local/bin:$PATH"

_missing=""
for _c in dirname mktemp mkdir cp rm chmod grep sed awk find sha256sum stat df \
          head cut sort xargs cat date printf; do
  command -v "$_c" >/dev/null 2>&1 || _missing="$_missing $_c"
done
if [ -n "$_missing" ]; then
  printf '[FATAL] 缺少必需命令:%s\n        PATH=%s\n' "$_missing" "$PATH" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORK="$(mktemp -d)"
STUB_BIN="$WORK/bin"

PASS=0
FAIL=0
ok()  { PASS=$((PASS + 1)); printf '    [PASS] %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '    [FAIL] %s\n' "$1"; }
head2() { printf '\n=== %s ===\n' "$1"; }

cleanup() { rm -rf "$WORK" 2>/dev/null || true; }
trap cleanup EXIT

# ---------------------------------------------------------------- 桩程序
mkdir -p "$STUB_BIN"

# docker 桩：所有需要的子命令都返回成功；image inspect 输出一个假 ID，
# 以便 install.sh 中的 manifest 核对逻辑能判定"镜像已就位"。
cat > "$STUB_BIN/docker" <<'STUB'
#!/usr/bin/env bash
case "${1:-}" in
  info)    exit 0 ;;
  load)    exit 0 ;;
  version) echo "27.0.0"; exit 0 ;;
  image)   echo "sha256:1111111111111111111111111111111111111111111111111111111111111111"; exit 0 ;;
  compose)
    shift
    case "${1:-}" in
      version) echo "v2.29.0" ;;
      *)       exit 0 ;;
    esac
    exit 0 ;;
  *) exit 0 ;;
esac
STUB
chmod +x "$STUB_BIN/docker"

# Windows 上的 python3 通过 CreateProcess 查找可执行文件，无法直接运行
# 无扩展名的 shell 脚本（会退回到真实 docker.exe）。因此额外提供一个
# docker.cmd，使 install.sh 中的 python 镜像核对逻辑在测试里也走桩程序。
printf '@echo off\r\necho sha256:1111111111111111111111111111111111111111111111111111111111111111\r\nexit /b 0\r\n' \
  > "$STUB_BIN/docker.cmd"

# curl 桩：按 URL 与是否带内部令牌返回状态码。
#   /actuator/health, /api/health        -> 200
#   /api/internal/health + 令牌          -> 200
#   /api/internal/health 无令牌          -> 401
# 环境变量 STUB_INTERNAL_OPEN=1 时模拟"内部接口未受保护"（匿名也 200）。
cat > "$STUB_BIN/curl" <<'STUB'
#!/usr/bin/env bash
url=""
has_internal=0
while [ $# -gt 0 ]; do
  case "$1" in
    -H)
      case "${2:-}" in
        *X-Internal-Token*) has_internal=1 ;;
      esac
      shift ;;
    -w|-o|-X|--max-time|--connect-timeout) shift ;;
    http*|HTTP*) url="$1" ;;
  esac
  shift
done
case "$url" in
  */api/internal/health)
    if [ "$has_internal" = "1" ]; then echo 200
    elif [ "${STUB_INTERNAL_OPEN:-0}" = "1" ]; then echo 200
    else echo 401; fi ;;
  */actuator/health|*/api/health) echo 200 ;;
  # LLM 端点探测：默认 200，可用 STUB_LLM_CODE 模拟鉴权失败(401)或未实现(404)
  */v1/models) echo "${STUB_LLM_CODE:-200}" ;;
  *) echo 404 ;;
esac
STUB
chmod +x "$STUB_BIN/curl"

# ---------------------------------------------------------- 假交付包构造
make_bundle() {
  local dir="$1"
  rm -rf "$dir"; mkdir -p "$dir/images" "$dir/docker/mysql"
  cp "$SCRIPT_DIR/install.sh"        "$dir/install.sh"
  cp "$REPO_ROOT/docker-compose.yml" "$dir/docker-compose.yml"
  cp "$REPO_ROOT/.env.example"       "$dir/env.example"
  echo "-- init sql --"            > "$dir/docker/mysql/init.sql"
  head -c 200000 /dev/urandom      > "$dir/images/rag-assistant-images-test.tar"
  cat > "$dir/manifest.json" <<'JSON'
{
  "product": "rag-assistant",
  "version": "test",
  "images": [
    { "name": "rag-backend:latest", "id": "sha256:1111", "digest": "" },
    { "name": "rag-engine:latest",  "id": "sha256:2222", "digest": "" }
  ]
}
JSON
  ( cd "$dir" && find . -type f ! -name SHA256SUMS | sed 's|^\./||' | sort \
      | xargs sha256sum > SHA256SUMS )
  chmod +x "$dir/install.sh"
}

# 运行 install.sh，返回退出码；输出落到 $2
run_install() {
  local dir="$1" out="$2"; shift 2
  ( cd "$dir" && PATH="$STUB_BIN:$PATH" bash ./install.sh "$@" ) > "$out" 2>&1
  echo $?
}

# =============================================================== T1
head2 "T1 --check-only 预检"
B1="$WORK/b1"; make_bundle "$B1"
rc="$(run_install "$B1" "$WORK/t1.log" --check-only)"
[ "$rc" = "0" ] && ok "退出码 0" || bad "退出码 $rc（期望 0）"
grep -q '预检完成' "$WORK/t1.log" && ok "输出包含「预检完成」" || bad "未到达预检完成"
grep -q 'SHA256SUMS 全部校验通过' "$WORK/t1.log" && ok "校验和通过" || bad "校验和未通过"
[ ! -f "$B1/.env" ] && ok "--check-only 未生成 .env（无副作用）" || bad "--check-only 竟然写了 .env"

# =============================================================== T2
head2 "T2 完整安装（--yes）"
B2="$WORK/b2"; make_bundle "$B2"
rc="$(run_install "$B2" "$WORK/t2.log" --yes --http-port 8080)"
[ "$rc" = "0" ] && ok "退出码 0" || bad "退出码 $rc（期望 0）"
grep -q '安装完成' "$WORK/t2.log" && ok "到达「安装完成」" || bad "未完成安装"
grep -q '服务间接口已受保护' "$WORK/t2.log" && ok "安全断言：匿名 401" || bad "缺少匿名 401 断言"
grep -q '携带正确令牌可正常访问' "$WORK/t2.log" && ok "安全断言：带令牌 200" || bad "缺少带令牌 200 断言"

if [ -f "$B2/.env" ]; then
  ok ".env 已生成"
  for k in MYSQL_ROOT_PASSWORD DB_PASSWORD JWT_SECRET INTERNAL_API_TOKEN; do
    v="$(grep -E "^${k}=" "$B2/.env" | head -n1 | cut -d= -f2-)"
    [ -n "$v" ] && ok ".env 含必填项 $k" || bad ".env 缺少 $k"
  done
  jwt="$(grep -E '^JWT_SECRET=' "$B2/.env" | head -n1 | cut -d= -f2-)"
  [ "${#jwt}" -ge 32 ] && ok "JWT_SECRET 长度 ${#jwt}（>=32）" || bad "JWT_SECRET 过短：${#jwt}"
  tok="$(grep -E '^INTERNAL_API_TOKEN=' "$B2/.env" | head -n1 | cut -d= -f2-)"
  [ "$jwt" != "$tok" ] && ok "JWT 与内部令牌互不相同" || bad "两个密钥相同（不应复用）"
  grep -qE '^FRONTEND_PORT=8080$' "$B2/.env" && ok "--http-port 已写入 FRONTEND_PORT" || bad "FRONTEND_PORT 未生效"
  grep -qE '^LLM_API_KEY=..*' "$B2/.env" && ok "LLM_API_KEY 已写入（非空，避免启动后鉴权失败）" || bad "LLM_API_KEY 为空"
  grep -qE '^LLM_BASE_URL=' "$B2/.env" && ok "LLM_BASE_URL 已写入" || bad "LLM_BASE_URL 缺失"
  grep -q 'LLM 端点可用' "$WORK/t2.log" && ok "LLM 端点探测：200 通过" || bad "未执行 LLM 端点探测"
  grep -q '仍是占位值' "$WORK/t2.log" && ok "识别出占位 Key 并明确告警" || bad "未对占位 Key 告警（会静默留下不可用的聊天）"
else
  bad ".env 未生成"
fi

# =============================================================== T3
head2 "T3 交付包被篡改（校验和失败）"
B3="$WORK/b3"; make_bundle "$B3"
printf 'tampered' >> "$B3/images/rag-assistant-images-test.tar"
rc="$(run_install "$B3" "$WORK/t3.log" --check-only)"
[ "$rc" != "0" ] && ok "拒绝继续（退出码 $rc）" || bad "篡改后仍然通过，校验和形同虚设"
grep -q '校验和不匹配' "$WORK/t3.log" && ok "给出「校验和不匹配」提示" || bad "未给出校验和错误提示"

# =============================================================== T4
head2 "T4 缺少 manifest.json"
B4="$WORK/b4"; make_bundle "$B4"; rm -f "$B4/manifest.json"
rc="$(run_install "$B4" "$WORK/t4.log" --check-only)"
[ "$rc" != "0" ] && ok "拒绝继续（退出码 $rc）" || bad "缺少 manifest 仍然通过"
grep -q 'manifest.json' "$WORK/t4.log" && ok "提示缺少 manifest.json" || bad "未提示 manifest 缺失"

# =============================================================== T5
head2 "T5 缺少镜像 tar"
B5="$WORK/b5"; make_bundle "$B5"; rm -f "$B5"/images/*.tar
rc="$(run_install "$B5" "$WORK/t5.log" --check-only)"
[ "$rc" != "0" ] && ok "拒绝继续（退出码 $rc）" || bad "缺少镜像包仍然通过"
grep -q '未找到镜像 tar' "$WORK/t5.log" && ok "提示未找到镜像 tar" || bad "未提示镜像 tar 缺失"

# =============================================================== T6
head2 "T6 安全断言失败场景（内部接口未受保护）"
B6="$WORK/b6"; make_bundle "$B6"
( cd "$B6" && PATH="$STUB_BIN:$PATH" STUB_INTERNAL_OPEN=1 bash ./install.sh --yes ) > "$WORK/t6.log" 2>&1
rc=$?
[ "$rc" != "0" ] && ok "内部接口裸奔时拒绝完成安装（退出码 $rc）" || bad "内部接口未受保护却仍报安装完成"
grep -q '服务间接口未受保护' "$WORK/t6.log" && ok "给出明确错误原因" || bad "未给出未受保护的原因"

# =============================================================== T7
head2 "T7 LLM 鉴权失败场景（应明确告警但不阻断安装）"
B7="$WORK/b7"; make_bundle "$B7"
( cd "$B7" && PATH="$STUB_BIN:$PATH" STUB_LLM_CODE=401 bash ./install.sh --yes ) > "$WORK/t7.log" 2>&1
rc=$?
[ "$rc" = "0" ] && ok "告警不阻断安装（设计如此：允许先装后配模型）" || bad "告警不应导致失败，实际退出码 $rc"
grep -q '鉴权失败' "$WORK/t7.log" && ok "提示 LLM 鉴权失败" || bad "未提示鉴权失败"
grep -q 'LLM 端点可用' "$WORK/t7.log" && bad "401 竟被报告为可用" || ok "未把 401 误报为可用"

# =============================================================== 汇总
head2 "汇总"
printf '  通过 %d / 失败 %d\n' "$PASS" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  # 直接把日志打出来，便于一次运行就定位问题（无需重跑）
  for f in "$WORK"/t*.log; do
    [ -f "$f" ] || continue
    printf '\n----- %s (末 30 行) -----\n' "$(basename "$f")"
    tail -n 30 "$f"
  done
  exit 1
fi
exit 0

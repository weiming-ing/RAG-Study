#!/usr/bin/env python
"""环境变量初始化 / 规范化（P0 安全整改配套脚本）

作用：在 .env、docker/.env、backend/.env 中补齐并规范化安全相关配置。

  - 生成 INTERNAL_API_TOKEN（Java /api/internal/** 的服务间接口令牌）
  - 补齐 DB_USERNAME / DB_PASSWORD（Java 引擎直连 MySQL 使用）
  - 写入 CORS_ALLOW_ORIGINS（替代原先的通配来源）
  - 写入 HTTP_TOOL_ALLOWED_HOSTS / HTTP_TOOL_ALLOW_PRIVATE（Agent 出站白名单）
  - 修正 Qdrant 端口变量名（6333=REST，6334=gRPC；原先两者名字写反了）
  - 使 backend/.env 的 JWT_SECRET_KEY 与根 .env 的 JWT_SECRET 完全一致

特性：
  - 幂等：已有值不会被覆盖（端口名修正与 JWT 对齐除外，这两项为强制修正）
  - 安全：写入前备份为 <文件>.bak-<时间戳>，保持 UTF-8 无 BOM，不打印任何密钥值
  - 只关心"键是否存在/是否一致"，不读取也不回显其它密钥内容

用法：
    python deploy/setup-env.py            # 就地更新
    python deploy/setup-env.py --dry-run  # 只报告将要做的修改
"""

from __future__ import annotations

import argparse
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_CORS = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:8001,http://127.0.0.1:8001"
)

# 需要强制修正的键（不是"缺失才补"，而是"值不对就改"）
FORCED_FIXES = {
    "QDRANT_HTTP_PORT": "6333",
    "QDRANT_GRPC_PORT": "6334",
}


class EnvFile:
    """极简 .env 读写：保留原有顺序与换行风格，只做键值 upsert。"""

    def __init__(self, path: Path):
        self.path = path
        raw = path.read_text(encoding="utf-8")
        self.newline = "\r\n" if "\r\n" in raw else "\n"
        self.lines = raw.splitlines()

    def get(self, key: str):
        prefix = f"{key}="
        for line in self.lines:
            if line.strip().startswith("#"):
                continue
            if line.startswith(prefix):
                return line[len(prefix):]
        return None

    def upsert(self, key: str, value: str, force: bool = False) -> str:
        """写入键值。返回 'updated' / 'added' / 'kept'。"""
        prefix = f"{key}="
        for i, line in enumerate(self.lines):
            if line.strip().startswith("#"):
                continue
            if line.startswith(prefix):
                if line == f"{prefix}{value}":
                    return "kept"
                if not force and line[len(prefix):]:
                    return "kept"
                self.lines[i] = f"{prefix}{value}"
                return "updated"
        self.lines.append(f"{key}={value}")
        return "added"

    def save(self, dry_run: bool = False) -> Path | None:
        if dry_run:
            return None
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = self.path.with_name(f"{self.path.name}.bak-{stamp}")
        shutil.copy2(self.path, backup)
        # 显式使用 utf-8（不加 BOM），newline="" 以避免二次转换
        text = self.newline.join(self.lines) + self.newline
        with self.path.open("w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return backup


def report(name: str, results: dict) -> None:
    changed = {k: v for k, v in results.items() if v in ("updated", "added")}
    if changed:
        detail = ", ".join(f"{k}({v})" for k, v in sorted(changed.items()))
        print(f"  {name}: {detail}")
    else:
        print(f"  {name}: 无需修改")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只报告，不写文件")
    args = parser.parse_args()

    root_env = REPO_ROOT / ".env"
    if not root_env.exists():
        print(f"[ERROR] 未找到 {root_env}，请先复制 .env.example 为 .env")
        return 1

    root = EnvFile(root_env)
    # 复用已有口令/密钥，绝不改写它们
    mysql_pwd = root.get("MYSQL_ROOT_PASSWORD") or ""
    root_jwt = root.get("JWT_SECRET") or ""
    token = root.get("INTERNAL_API_TOKEN") or secrets.token_urlsafe(36)

    print(f"仓库根目录: {REPO_ROOT}")
    print(f"JWT_SECRET 长度: {len(root_jwt)}  (需 >= 32)")
    if len(root_jwt) < 32:
        print("[WARN] JWT_SECRET 缺失或过短，请手动生成：")
        print('       python -c "import secrets;print(secrets.token_urlsafe(48))"')
    if not mysql_pwd:
        print("[WARN] MYSQL_ROOT_PASSWORD 为空，DB_PASSWORD 将写入空值")

    files: list[tuple[Path, dict]] = [
        (root_env, {
            "DB_USERNAME": "root",
            "DB_PASSWORD": mysql_pwd,
            "INTERNAL_API_TOKEN": token,
            "CORS_ALLOW_ORIGINS": DEFAULT_CORS,
            "HTTP_TOOL_ALLOWED_HOSTS": "",
            "HTTP_TOOL_ALLOW_PRIVATE": "false",
            **FORCED_FIXES,
        }),
        (REPO_ROOT / "docker" / ".env", {
            "DB_USERNAME": "root",
            "DB_PASSWORD": mysql_pwd,
            "INTERNAL_API_TOKEN": token,
            "CORS_ALLOW_ORIGINS": DEFAULT_CORS,
            "HTTP_TOOL_ALLOWED_HOSTS": "",
            "HTTP_TOOL_ALLOW_PRIVATE": "false",
            **FORCED_FIXES,
        }),
        (REPO_ROOT / "backend" / ".env", {
            # 与根 .env 对齐；Python 侧优先读 JWT_SECRET，此处保持两者一致以防万一
            "JWT_SECRET_KEY": root_jwt,
            "INTERNAL_API_TOKEN": token,
            "CORS_ALLOW_ORIGINS": DEFAULT_CORS,
            "HTTP_TOOL_ALLOWED_HOSTS": "",
            "HTTP_TOOL_ALLOW_PRIVATE": "false",
        }),
    ]

    for path, updates in files:
        if not path.exists():
            print(f"  {path.relative_to(REPO_ROOT)}: 不存在，跳过")
            continue
        env = EnvFile(path)
        force_keys = set(FORCED_FIXES)
        if path == REPO_ROOT / "backend" / ".env":
            # 必须与根 .env 的 JWT_SECRET 对齐，否则 Java 签发的令牌无法校验
            force_keys.add("JWT_SECRET_KEY")
        results = {}
        for key, value in updates.items():
            results[key] = env.upsert(key, value, force=key in force_keys)
        backup = env.save(dry_run=args.dry_run)
        report(str(path.relative_to(REPO_ROOT)), results)
        if backup:
            print(f"      备份 -> {backup.name}")

    print("\n完成。请用以下命令确认一致性（不会显示密钥内容）：")
    print("  python deploy/setup-env.py --dry-run")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
"""生成授权签名密钥对（厂商侧，一次性操作）

产生 Ed25519 密钥对：
  - 私钥：deploy/license/keys/private.pem  —— **只能留在厂商侧**，请离线备份；
          泄露即等于任何人都能签发授权。
  - 公钥：打印到屏幕 —— 粘贴到 backend/services/license_service.py 的
          PRODUCT_PUBLIC_KEY_PEM 常量中（不要放 .env，否则客户可换成自己的公钥自签）。

私钥目录已加入 .gitignore，不会被提交。

用法：
    python deploy/license/gen-keypair.py
    python deploy/license/gen-keypair.py --force     # 覆盖已有私钥；已签发的授权将全部失效
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:  # noqa: BLE001
    print("[ERROR] 缺少 cryptography 库。请先安装：pip install cryptography")
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
KEY_DIR = REPO_ROOT / "deploy" / "license" / "keys"
PRIVATE_KEY = KEY_DIR / "private.pem"


def main() -> int:
    ap = argparse.ArgumentParser(description="生成授权签名密钥对")
    ap.add_argument("--force", action="store_true", help="覆盖已有私钥（危险）")
    args = ap.parse_args()

    if PRIVATE_KEY.exists() and not args.force:
        print(f"[ERROR] 私钥已存在：{PRIVATE_KEY}")
        print("        如需重新生成（会让已签发的授权全部失效），加 --force")
        return 1

    KEY_DIR.mkdir(parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    PRIVATE_KEY.write_bytes(private_pem)
    try:
        PRIVATE_KEY.chmod(0o600)
    except OSError:
        pass  # Windows 上可能无效，不影响功能

    print("=" * 70)
    print("密钥对已生成")
    print("=" * 70)
    print(f"  私钥：{PRIVATE_KEY}")
    print("        —— 务必离线备份，切勿提交到版本库或随产品交付")
    print()
    print("  公钥：请把下面整个常量块粘贴替换到")
    print("        backend/services/license_service.py 的 PRODUCT_PUBLIC_KEY_PEM")
    print()
    print('PRODUCT_PUBLIC_KEY_PEM = """\\')
    print(public_pem, end="")
    print('"""')
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())

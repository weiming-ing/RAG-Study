#!/usr/bin/env python
"""签发授权文件（厂商侧）

读取 deploy/license/keys/private.pem，生成客户可用的 license.json。

用法：
    # 绑定客户机器、一年期、文档上限 5000
    python deploy/license/issue-license.py \
        --customer "某某集团有限公司" \
        --days 365 \
        --fingerprint <客户在管理台/接口读出的指纹> \
        --max-documents 5000 \
        --out license.json

    # 内部开发用：不绑定机器、十年期、不限容量
    python deploy/license/issue-license.py --customer "内部开发" --days 3650 --out license.json

    # 指定到期日（按自然日期续期更直观）
    python deploy/license/issue-license.py --customer "XX" --expires 2027-12-31 --out license.json

参数说明：
    --limits 中的 0 表示不限。--features 留空表示不限制功能。
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:  # noqa: BLE001
    print("[ERROR] 缺少 cryptography 库。请先安装：pip install cryptography")
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PRIVATE_KEY = REPO_ROOT / "deploy" / "license" / "keys" / "private.pem"


def b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def main() -> int:
    ap = argparse.ArgumentParser(description="签发 RAG 助手授权文件")
    ap.add_argument("--customer", required=True, help="客户名称（用于对账，会写入授权内容）")
    ap.add_argument("--license-id", default="", help="授权编号，便于内部对账；默认自动生成")
    ap.add_argument("--days", type=int, default=365, help="有效天数（默认 365）")
    ap.add_argument("--expires", default="", help="到期日 YYYY-MM-DD；指定后忽略 --days")
    ap.add_argument("--fingerprint", default="", help="机器指纹；留空表示不绑定机器")
    ap.add_argument("--max-documents", type=int, default=0, help="文档数上限，0=不限")
    ap.add_argument("--max-users", type=int, default=0, help="用户数上限，0=不限（暂仅上报，未强制）")
    ap.add_argument("--max-knowledge-bases", type=int, default=0, help="知识库数上限，0=不限（暂仅上报）")
    ap.add_argument("--features", default="", help="允许的功能，逗号分隔，如 ocr,agent；留空=不限")
    ap.add_argument("--out", default="license.json", help="输出文件名（默认 license.json）")
    args = ap.parse_args()

    if not PRIVATE_KEY.exists():
        print(f"[ERROR] 未找到私钥：{PRIVATE_KEY}")
        print("        请先运行：python deploy/license/gen-keypair.py")
        return 1

    issued = datetime.now(timezone.utc)
    if args.expires:
        try:
            expires = datetime.strptime(args.expires, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            ) + timedelta(days=1)  # 含到期日当天
        except ValueError:
            print("[ERROR] --expires 格式应为 YYYY-MM-DD")
            return 1
    else:
        expires = issued + timedelta(days=args.days)

    if expires <= issued:
        print("[ERROR] 到期时间早于当前时间")
        return 1

    payload = {
        "format": "rag-license/v1",
        "licenseId": args.license_id or f"LIC-{issued.strftime('%Y%m%d')}-{args.customer[:6]}",
        "customer": args.customer,
        "product": "rag-assistant",
        "issuedAt": issued.replace(microsecond=0).isoformat(),
        "expiresAt": expires.replace(microsecond=0).isoformat(),
        "machineFingerprint": args.fingerprint.strip(),
        "limits": {
            "maxDocuments": args.max_documents,
            "maxUsers": args.max_users,
            "maxKnowledgeBases": args.max_knowledge_bases,
        },
        "features": [f.strip() for f in args.features.split(",") if f.strip()],
    }

    # 签名对象是 payload 的 base64url 文本本身 —— 保证"签的字节 = 验的字节"
    payload_b64 = b64e(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    private_key = serialization.load_pem_private_key(PRIVATE_KEY.read_bytes(), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        print("[ERROR] 私钥类型不是 Ed25519，请重新生成密钥对")
        return 1
    signature_b64 = b64e(private_key.sign(payload_b64.encode("ascii")))

    license_doc = {
        "format": "rag-license/v1",
        "alg": "Ed25519",
        "payload": payload_b64,
        "signature": signature_b64,
    }

    out_path = Path(args.out)
    out_path.write_text(
        json.dumps(license_doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("=" * 70)
    print("授权已签发")
    print("=" * 70)
    print(f"  输出文件   ：{out_path.resolve()}")
    print(f"  授权编号   ：{payload['licenseId']}")
    print(f"  客户       ：{args.customer}")
    print(f"  生效       ：{payload['issuedAt']}")
    print(f"  到期       ：{payload['expiresAt']}（剩余 {max(0, (expires - issued).days)} 天）")
    print(f"  机器绑定   ：{'是 ' + args.fingerprint[:16] + '…' if args.fingerprint else '否（可复制到任意环境，谨慎使用）'}")
    print(f"  文档上限   ：{args.max_documents or '不限'}")
    print(f"  功能限制   ：{payload['features'] or '不限'}")
    print()
    print("  交付方式：把该文件放到产品根目录并命名为 license.json，")
    print("            容器部署时由 LICENSE_FILE 指定路径（见 deploy/offline/README.md）。")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
"""授权校验功能测试（只读，不写任何文件）

覆盖场景：
  1  正常授权                                   2  过期
  3  尚未生效                                    4  签名被篡改（改内容）
  5  用别的私钥签名                              6  机器指纹不匹配
  7  机器指纹匹配                                8  未配置产品公钥
  9  文件不存在                                 10  文件内容损坏
  11 容量上限（不限 / 未超 / 已超）              12 功能开关
  13 真实 license.json 与内置公钥是否匹配（若存在）

测试在内存中生成临时密钥对，不依赖 deploy/license/keys/ 下的真实私钥，
因此任何人都能运行，也便于放进 CI。

用法：
    python deploy/license/test-license.py
退出码：0 = 全部通过；1 = 存在失败
"""

from __future__ import annotations

import base64
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from services import license_service as ls  # noqa: E402

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:  # noqa: BLE001
    print("[ERROR] 缺少 cryptography 库")
    sys.exit(2)

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def keypair():
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return priv, pub


def make_license(payload: dict, priv) -> tuple:
    """返回 (payload_b64, signature_b64)。"""
    payload_b64 = b64e(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return payload_b64, b64e(priv.sign(payload_b64.encode("ascii")))


def base_payload(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    payload = {
        "format": "rag-license/v1",
        "licenseId": "LIC-TEST",
        "customer": "测试客户",
        "product": "rag-assistant",
        "issuedAt": now.isoformat(),
        "expiresAt": (now + timedelta(days=30)).isoformat(),
        "machineFingerprint": "",
        "limits": {"maxDocuments": 0, "maxUsers": 0, "maxKnowledgeBases": 0},
        "features": [],
    }
    payload.update(overrides)
    return payload


def main() -> int:
    print("=" * 70)
    print("授权校验功能测试")
    print("=" * 70)

    priv, pub = keypair()
    other_priv, _ = keypair()
    now = datetime.now(timezone.utc)

    # 1 正常
    p, s = make_license(base_payload(), priv)
    r = ls.verify_license_bytes(p, s, pub, now=now)
    check("正常授权通过", r.valid and r.reason == "ok", f"reason={r.reason}")
    check("剩余天数合理", r.days_remaining is not None and 28 <= r.days_remaining <= 30,
          f"days={r.days_remaining}")

    # 2 过期
    p, s = make_license(base_payload(expiresAt=(now - timedelta(days=1)).isoformat()), priv)
    r = ls.verify_license_bytes(p, s, pub, now=now)
    check("过期授权被拒", not r.valid and r.reason == "expired", f"reason={r.reason}")

    # 3 尚未生效
    p, s = make_license(base_payload(notBefore=(now + timedelta(days=1)).isoformat()), priv)
    r = ls.verify_license_bytes(p, s, pub, now=now)
    check("未生效授权被拒", not r.valid and r.reason == "not_yet_valid", f"reason={r.reason}")

    # 4 内容被篡改（签名不变）
    p, s = make_license(base_payload(), priv)
    tampered = b64e(json.dumps(base_payload(customer="攻击者"), ensure_ascii=False,
                               separators=(",", ":")).encode("utf-8"))
    r = ls.verify_license_bytes(tampered, s, pub, now=now)
    check("内容被篡改被拒", not r.valid and r.reason == "bad_signature", f"reason={r.reason}")

    # 5 用别的私钥签
    p, s = make_license(base_payload(), other_priv)
    r = ls.verify_license_bytes(p, s, pub, now=now)
    check("他人私钥签发被拒", not r.valid and r.reason == "bad_signature", f"reason={r.reason}")

    # 6 指纹不匹配
    p, s = make_license(base_payload(machineFingerprint="deadbeef" * 8), priv)
    r = ls.verify_license_bytes(p, s, pub, fingerprint="cafebabe" * 8, now=now)
    check("机器指纹不匹配被拒", not r.valid and r.reason == "machine_mismatch", f"reason={r.reason}")

    # 7 指纹匹配（大小写不敏感）
    fp = "A1B2C3D4" * 8
    p, s = make_license(base_payload(machineFingerprint=fp), priv)
    r = ls.verify_license_bytes(p, s, pub, fingerprint=fp.lower(), now=now)
    check("机器指纹匹配通过", r.valid, f"reason={r.reason}")

    # 8 未配置公钥
    p, s = make_license(base_payload(), priv)
    r = ls.verify_license_bytes(p, s, "", now=now)
    check("未配置公钥时拒绝（fail closed）", not r.valid and r.reason == "no_public_key",
          f"reason={r.reason}")

    # 9 文件不存在
    r = ls.verify_license_file(REPO_ROOT / "definitely-missing-license.json", pub)
    check("授权文件缺失被拒", not r.valid and r.reason == "missing", f"reason={r.reason}")

    # 10 内容损坏（结构不对 / base64 非法）
    r = ls.verify_license_bytes("not-base64!!", "also-bad!", pub, now=now)
    check("损坏内容被拒", not r.valid and r.reason in ("malformed", "bad_signature"),
          f"reason={r.reason}")

    # 11 容量上限
    svc = ls.LicenseService(base_dir=REPO_ROOT, public_key_pem=pub)
    svc._cached = ls.LicenseStatus(valid=True, reason="ok", payload={"limits": {"maxDocuments": 100}})
    svc._cached_at = time.monotonic()
    ok1, _ = svc.check_limit("maxDocuments", 99, 1)
    ok2, msg2 = svc.check_limit("maxDocuments", 100, 1)
    check("未超上限时允许", ok1)
    check("超上限时拒绝并给出说明", (not ok2) and "上限" in msg2, f"msg={msg2}")

    svc._cached = ls.LicenseStatus(valid=True, reason="ok", payload={"limits": {"maxDocuments": 0}})
    svc._cached_at = time.monotonic()
    ok3, _ = svc.check_limit("maxDocuments", 10 ** 6, 1)
    check("上限为 0 表示不限", ok3)

    # 12 功能开关
    svc._cached = ls.LicenseStatus(valid=True, reason="ok", payload={"features": ["ocr"]})
    svc._cached_at = time.monotonic()
    check("已声明功能可用", svc.allows_feature("ocr"))
    check("未声明功能不可用", not svc.allows_feature("agent"))
    svc._cached = ls.LicenseStatus(valid=True, reason="ok", payload={"features": []})
    svc._cached_at = time.monotonic()
    check("未声明 features 视为不限", svc.allows_feature("agent"))

    # 13 拦截策略（授权无效时）
    from middleware.license_middleware import should_block  # noqa: E402

    must_block = [
        ("/api/chat", "POST"), ("/api/chat/stream", "POST"),
        ("/api/agent/chat", "POST"),
        ("/api/knowledge/upload", "POST"),
        ("/api/knowledge/0/documents", "POST"),
        ("/api/knowledge/documents/1", "DELETE"),
    ]
    must_allow = [
        ("/api/chat/history", "GET"), ("/api/license", "GET"),
        ("/api/knowledge/documents", "GET"),          # 数据始终可查看
        ("/api/conversations/grouped", "GET"),        # 数据始终可导出
        ("/api/auth/login", "POST"),                  # 要能登录才能看状态
        ("/api/upload", "OPTIONS"),                   # 预检
        ("/", "GET"),                                 # 静态前端
        ("/admin/", "GET"),
    ]
    bad_block = [f"{m} {p}" for p, m in must_block if not should_block(p, m)]
    bad_allow = [f"{m} {p}" for p, m in must_allow if should_block(p, m)]
    check("授权失效时拦截问答与入库", not bad_block, f"未拦截: {bad_block}")
    check("授权失效时仍允许登录/查看/导出数据", not bad_allow, f"误拦截: {bad_allow}")

    # 14 真实授权文件 vs 内置公钥
    real = REPO_ROOT / "license.json"
    embedded = ls.PRODUCT_PUBLIC_KEY_PEM.strip()
    if real.exists():
        check("内置产品公钥已配置", bool(embedded),
              "PRODUCT_PUBLIC_KEY_PEM 为空，无法校验真实授权")
        if embedded:
            r = ls.verify_license_file(real, ls.PRODUCT_PUBLIC_KEY_PEM)
            detail = f"reason={r.reason} file={real.name}"
            check("真实 license.json 校验通过", r.valid, detail)
            if r.valid:
                print(f"         客户={r.payload.get('customer')} "
                      f"到期={r.payload.get('expiresAt')} 剩余={r.days_remaining} 天 "
                      f"机器绑定={'是' if r.payload.get('machineFingerprint') else '否'}")
    else:
        print(f"  [SKIP] 未找到 {real.name}（当前环境尚未放置授权文件）")

    print("=" * 70)
    print(f"汇总：通过 {PASS} / 失败 {FAIL}")
    print("=" * 70)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

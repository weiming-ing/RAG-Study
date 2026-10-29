"""
离线授权（License）校验服务

设计要点：
  - 非对称签名（Ed25519）：厂商持私钥签发，产品内置公钥校验，客户无法伪造。
  - 完全离线：不联网、不回连，适合无外网的私有化环境。
  - 可选机器绑定：签发时填入机器指纹，防止同一份授权被复制到多套环境。
  - 可选容量上限：按文档/用户/知识库数量限制，0 表示不限。

签名对象是 license 文件中 payload 字段的 base64url 文本本身，而不是解码后的 JSON
—— 这样无需任何 JSON 规范化约定，即可保证"签的字节 = 验的字节"，避免不同实现
因键顺序或空白差异导致验签失败。

【重要局限，不要当成 DRM】
产品以源码形式交付到客户内网，任何纯离线校验都能被有决心的客户通过改代码绕过。
它的作用是阻止"一份授权随手复制到多套环境"这类常规越界，而不是防破解。
真正需要强管控时，应配合合同条款与现场交付流程。
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    CRYPTO_AVAILABLE = True
except Exception:  # noqa: BLE001
    CRYPTO_AVAILABLE = False


# ---------------------------------------------------------------------------
# 产品公钥
# ---------------------------------------------------------------------------
# 必须内置在代码里，不能放到 .env：否则客户只要换成自己的公钥就能自签一份授权。
# 生成方式：python deploy/license/gen-keypair.py（会打印可直接粘贴到这里的公钥）。
# 留空表示"未配置"——此时所有授权都判为无效（fail closed），这是有意为之。
PRODUCT_PUBLIC_KEY_PEM = """\
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAiEdwZ3Vx5SLNk5yHMWPscRj/WN8YRtSjjuzEZ5vZ6Gs=
-----END PUBLIC KEY-----
"""

# 授权文件的候选路径：LICENSE_FILE 环境变量优先，其次仓库根，最后 deploy 目录（便于开发）
_LICENSE_CANDIDATES = ("license.json", "deploy/license/license.json")

# 状态原因码 → 面向客户的中文说明与处理建议
REASON_MESSAGES = {
    "ok": "授权有效",
    "no_public_key": "产品公钥未配置：请先运行 deploy/license/gen-keypair.py 并把公钥填入 license_service.py",
    "missing": "未找到授权文件：请向供应商获取 license.json，并放到产品根目录",
    "unreadable": "授权文件无法读取：请检查文件权限",
    "malformed": "授权文件格式不正确：请确认使用的是供应商签发的原始文件，未被编辑",
    "bad_signature": "授权文件签名校验失败：文件可能被修改过，请向供应商重新获取",
    "expired": "授权已过期：请联系供应商续期",
    "not_yet_valid": "授权尚未生效：请检查服务器系统时间是否正确",
    "machine_mismatch": "授权与当前机器不匹配：该授权是为其它机器签发的，请联系供应商重新签发",
    "crypto_unavailable": "运行环境缺少加密库（cryptography），无法校验授权",
}


@dataclass
class LicenseStatus:
    """授权校验结果。"""

    valid: bool
    reason: str = "missing"
    payload: dict = field(default_factory=dict)
    file: str = ""
    days_remaining: Optional[int] = None

    @property
    def message(self) -> str:
        return REASON_MESSAGES.get(self.reason, self.reason)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "reason": self.reason,
            "message": self.message,
            "file": self.file,
            "customer": self.payload.get("customer", ""),
            "licenseId": self.payload.get("licenseId", ""),
            "expiresAt": self.payload.get("expiresAt", ""),
            "daysRemaining": self.days_remaining,
            "machineBound": bool(self.payload.get("machineFingerprint")),
            "limits": self.payload.get("limits", {}),
            "features": self.payload.get("features", []),
            "fingerprint": machine_fingerprint(),
        }


# ---------------------------------------------------------------------------
# 机器指纹
# ---------------------------------------------------------------------------
def license_machine_id() -> str:
    """返回机器标识原始值。

    优先级：LICENSE_MACHINE_ID 环境变量 > /etc/machine-id > 主机名+MAC。

    容器部署注意：容器内的 /etc/machine-id 往往是容器自己的，重建后会变化。
    因此 docker-compose 交付时应由 install.sh 从宿主机取出 machine-id 并以
    LICENSE_MACHINE_ID 注入，指纹才能跨容器重建保持稳定。
    """
    explicit = os.getenv("LICENSE_MACHINE_ID", "").strip()
    if explicit:
        return explicit

    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            value = Path(path).read_text(encoding="utf-8").strip()
            if value:
                return value
        except OSError:
            pass

    return f"{socket.gethostname()}|{uuid.getnode():012x}"


def machine_fingerprint() -> str:
    """机器指纹：对机器标识取哈希，便于客户安全地把它读给供应商。"""
    return hashlib.sha256(("rag-assistant|" + license_machine_id()).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 核心校验（纯函数，便于单元测试与复用）
# ---------------------------------------------------------------------------
def _b64d(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _parse_time(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def verify_license_bytes(
    payload_b64: str,
    signature_b64: str,
    public_key_pem: str,
    fingerprint: Optional[str] = None,
    now: Optional[datetime] = None,
) -> LicenseStatus:
    """校验授权内容。任何一步不通过都返回带原因码的无效结果（不抛异常）。"""
    if not CRYPTO_AVAILABLE:
        return LicenseStatus(valid=False, reason="crypto_unavailable")
    if not public_key_pem or not public_key_pem.strip():
        return LicenseStatus(valid=False, reason="no_public_key")

    try:
        public_key = load_pem_public_key(public_key_pem.encode("utf-8"))
        if not isinstance(public_key, Ed25519PublicKey):
            return LicenseStatus(valid=False, reason="no_public_key")
    except Exception:  # noqa: BLE001
        return LicenseStatus(valid=False, reason="no_public_key")

    # 校验签名：签的是 payload 的 base64url 文本本身
    try:
        public_key.verify(_b64d(signature_b64), payload_b64.encode("ascii"))
    except InvalidSignature:
        return LicenseStatus(valid=False, reason="bad_signature")
    except Exception:  # noqa: BLE001
        return LicenseStatus(valid=False, reason="malformed")

    # 签名通过后才解析内容
    try:
        payload = json.loads(_b64d(payload_b64).decode("utf-8"))
    except Exception:  # noqa: BLE001
        return LicenseStatus(valid=False, reason="malformed")

    if not isinstance(payload, dict):
        return LicenseStatus(valid=False, reason="malformed")

    moment = now or datetime.now(timezone.utc)

    not_before = _parse_time(payload.get("notBefore"))
    if not_before and moment < not_before:
        return LicenseStatus(valid=False, reason="not_yet_valid", payload=payload)

    expires_at = _parse_time(payload.get("expiresAt"))
    if expires_at:
        if moment >= expires_at:
            return LicenseStatus(
                valid=False, reason="expired", payload=payload, days_remaining=0
            )
        days = max(0, (expires_at - moment).days)
    else:
        days = None

    bound = (payload.get("machineFingerprint") or "").strip()
    if bound:
        if not fingerprint:
            fingerprint = machine_fingerprint()
        if bound.lower() != fingerprint.lower():
            return LicenseStatus(
                valid=False, reason="machine_mismatch", payload=payload, days_remaining=days
            )

    return LicenseStatus(valid=True, reason="ok", payload=payload, days_remaining=days)


def verify_license_file(
    path,
    public_key_pem: str,
    fingerprint: Optional[str] = None,
    now: Optional[datetime] = None,
) -> LicenseStatus:
    """从文件读取并校验授权。"""
    file_path = Path(path)
    status = LicenseStatus(valid=False, reason="missing", file=str(file_path))

    try:
        raw = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return status
    except OSError:
        status.reason = "unreadable"
        return status

    try:
        doc = json.loads(raw)
        payload_b64 = doc["payload"]
        signature_b64 = doc["signature"]
    except Exception:  # noqa: BLE001
        status.reason = "malformed"
        return status

    result = verify_license_bytes(
        payload_b64, signature_b64, public_key_pem, fingerprint=fingerprint, now=now
    )
    result.file = str(file_path)
    return result


# ---------------------------------------------------------------------------
# 服务封装
# ---------------------------------------------------------------------------
class LicenseService:
    """授权服务：解析候选路径、缓存校验结果、提供功能与容量判定。"""

    #: 校验结果缓存时长（秒）。避免每个请求都读文件并验签。
    CACHE_TTL_SECONDS = 60

    def __init__(self, base_dir: Path = None, public_key_pem: str = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent.parent
        self._public_key = public_key_pem if public_key_pem is not None else PRODUCT_PUBLIC_KEY_PEM
        self._cached: Optional[LicenseStatus] = None
        self._cached_at = 0.0

    # -- 路径解析 ---------------------------------------------------------
    def candidate_paths(self) -> list:
        """返回按优先级排列的候选授权文件路径。"""
        paths = []
        explicit = os.getenv("LICENSE_FILE", "").strip()
        if explicit:
            paths.append(Path(explicit))
        for rel in _LICENSE_CANDIDATES:
            paths.append(self.base_dir / rel)
        return paths

    def resolve_path(self) -> Optional[Path]:
        for p in self.candidate_paths():
            if p.is_file():
                return p
        return None

    # -- 校验 -------------------------------------------------------------
    def status(self, force: bool = False) -> LicenseStatus:
        """返回当前授权状态（带缓存）。"""
        import time as _time

        now_monotonic = _time.monotonic()
        if (
            not force
            and self._cached is not None
            and now_monotonic - self._cached_at < self.CACHE_TTL_SECONDS
        ):
            return self._cached

        path = self.resolve_path()
        if path is None:
            result = LicenseStatus(valid=False, reason="missing")
            result.file = str(self.candidate_paths()[0])
        else:
            result = verify_license_file(path, self._public_key)

        self._cached = result
        self._cached_at = now_monotonic
        return result

    def invalidate(self) -> None:
        self._cached = None
        self._cached_at = 0.0

    # -- 功能与容量 -------------------------------------------------------
    def allows_feature(self, feature: str) -> bool:
        """未声明 features 时视为不限制（向后兼容早期授权文件）。"""
        status = self.status()
        if not status.valid:
            return False
        features = status.payload.get("features")
        if not features:
            return True
        return feature in features

    def check_limit(self, key: str, current: int, incoming: int = 1) -> tuple:
        """检查容量上限。返回 (是否允许, 说明)。

        上限为 0 或未配置表示不限。
        """
        status = self.status()
        if not status.valid:
            return False, status.message
        limit = (status.payload.get("limits") or {}).get(key, 0) or 0
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 0
        if limit <= 0:
            return True, ""
        if current + incoming > limit:
            return False, f"已达授权容量上限（{key}={limit}，当前 {current}），如需扩容请联系供应商"
        return True, ""


license_service = LicenseService()

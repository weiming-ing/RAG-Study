#!/usr/bin/env python
"""读取本机机器指纹（客户侧 / 交付现场使用）

把输出发给供应商，即可获得绑定本机的授权文件。

用法（在部署机器上执行，不要求服务已启动）：
    python deploy/license/machine_fingerprint.py

容器部署注意：
    容器内的 /etc/machine-id 往往是容器自己的，重建后会变化，导致授权失效。
    正确做法是由宿主机取出 machine-id 并注入环境变量：
        LICENSE_MACHINE_ID=$(cat /etc/machine-id)
    或在 docker-compose 中把宿主机的 /etc/machine-id 只读挂载进容器。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

try:
    from services.license_service import (  # noqa: E402
        license_machine_id,
        machine_fingerprint,
    )
except Exception as exc:  # noqa: BLE001
    print(f"[ERROR] 无法导入 license_service：{type(exc).__name__}: {exc}")
    print("        请确认 cryptography 已安装，且当前目录是产品根目录。")
    sys.exit(2)


def main() -> int:
    mid = license_machine_id()
    fp = machine_fingerprint()

    print("=" * 70)
    print("本机机器指纹")
    print("=" * 70)
    print(f"  指纹（发给供应商）：{fp}")
    print(f"  机器标识原文      ：{mid}")
    print()
    print("  供应商据此签发后，把返回的 license.json 放到产品根目录；")
    print("  容器部署请用 LICENSE_FILE 指定其路径，并确保容器内的")
    print("  LICENSE_MACHINE_ID 与上面「机器标识原文」一致，否则指纹会不匹配。")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())

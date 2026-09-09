"""
知识库种子脚本

创建企业知识库并上传 6 个企业制度文档。
用法（确保 Java 后端 :8002 和 Python 后端 :8001 均已启动）：
  python seed_kb.py
"""

import os
import sys
import httpx
from pathlib import Path

JAVA_BACKEND = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")
PYTHON_BACKEND = os.getenv("PYTHON_BACKEND_URL", "http://localhost:8001")
DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "documents"

KB_NAME = "企业知识库"
KB_DESCRIPTION = "存放企业制度文档，包括 IT 设备、财务报销、考勤、人事、保密等管理规范"

ADMIN_USERNAME = os.getenv("TEST_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("TEST_PASSWORD", "admin123")


def login():
    """通过 Python 后端的 /api/auth/login 获取 JWT token"""
    resp = httpx.post(
        f"{PYTHON_BACKEND}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        timeout=10.0,
    )
    if resp.status_code != 200:
        print(f"登录失败: {resp.text}")
        sys.exit(1)

    data = resp.json()
    if not data.get("success"):
        print(f"登录失败: {data}")
        sys.exit(1)

    token = data["data"]["access_token"]
    print(f"登录成功: {ADMIN_USERNAME}")
    return token


def main():
    timeout = httpx.Timeout(300.0, connect=10.0)

    try:
        resp = httpx.get(f"{JAVA_BACKEND}/actuator/health", timeout=5.0)
        if resp.status_code != 200:
            print(f"Java 后端未就绪 (status={resp.status_code})")
            sys.exit(1)
    except Exception as e:
        print(f"Java 后端未启动: {e}")
        print("请先启动 rag-engine (mvn spring-boot:run)")
        sys.exit(1)

    print("Java 后端已连接\n")

    token = login()
    auth_headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(timeout=timeout) as client:
        print(f"\n创建知识库: {KB_NAME}")
        create_resp = client.post(
            f"{JAVA_BACKEND}/api/internal/knowledge-bases",
            headers=auth_headers,
            json={"name": KB_NAME, "description": KB_DESCRIPTION, "category": "企业制度", "isPublic": 1},
        )
        if create_resp.status_code != 200:
            print(f"创建知识库失败: {create_resp.text}")
            sys.exit(1)

        create_data = create_resp.json()
        if create_data.get("code") != 0:
            print(f"创建知识库失败: {create_data.get('message', '未知错误')}")
            sys.exit(1)

        kb_id = create_data["data"]["id"]
        print(f"知识库创建成功: id={kb_id}\n")

        md_files = sorted(DOCS_DIR.glob("*.md"))
        if not md_files:
            print(f"在 {DOCS_DIR} 下未找到 .md 文件")
            sys.exit(1)

        print(f"找到 {len(md_files)} 个文件，开始上传...\n")
        success = 0
        fail = 0

        for fpath in md_files:
            filename = fpath.name
            display_name = filename.split("_", 1)[1] if "_" in filename else filename
            size = fpath.stat().st_size
            print(f"上传中: {display_name} ({size} bytes)...", end=" ", flush=True)

            try:
                with open(fpath, "rb") as f:
                    upload_resp = client.post(
                        f"{JAVA_BACKEND}/api/knowledge/{kb_id}/documents/upload",
                        headers=auth_headers,
                        files={"file": (filename, f, "text/markdown")},
                        data={"tags": "企业制度"},
                    )

                if upload_resp.status_code == 200:
                    result = upload_resp.json()
                    if result.get("code") == 0 or result.get("success") is not False:
                        doc = result.get("data", {})
                        print(f"成功 (id={doc.get('id', '?')})")
                        success += 1
                    else:
                        print(f"失败: {result.get('message', '未知错误')}")
                        fail += 1
                else:
                    print(f"HTTP {upload_resp.status_code}: {upload_resp.text[:200]}")
                    fail += 1
            except Exception as e:
                print(f"异常: {e}")
                fail += 1

        print(f"\n{'='*40}")
        print(f"完成: {success} 成功, {fail} 失败")
        print(f"知识库ID: {kb_id}")
        print(f"知识库名称: {KB_NAME}")
        print(f"{'='*40}")

        if success > 0:
            print(f"\n管理页面: http://localhost:5173/kb/{kb_id}/config")


if __name__ == "__main__":
    main()
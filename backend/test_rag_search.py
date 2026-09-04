"""
测试 RAG 检索功能 — 验证企业知识库文档能否被正确检索
"""

import os
import httpx
import json
import sys

PYTHON_BACKEND = os.getenv("PYTHON_BACKEND_URL", "http://localhost:8001")
KB_ID = 16

ADMIN_USERNAME = os.getenv("TEST_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("TEST_PASSWORD", "admin123")


def login():
    resp = httpx.post(
        f"{PYTHON_BACKEND}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        timeout=10.0,
    )
    data = resp.json()
    if not data.get("success"):
        print(f"登录失败: {data}")
        return None
    return data["data"]["access_token"]


def search_knowledge(query: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}
    resp = httpx.get(
        f"{PYTHON_BACKEND}/api/knowledge/search",
        headers=headers,
        params={"q": query},
        timeout=20.0,
    )
    if resp.status_code != 200:
        print(f"检索失败: {resp.text}")
        return None
    return resp.json()


def main():
    # 解决 Windows 控制台 GBK 编码问题
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("=" * 70)
    print("RAG 检索测试 — 企业知识库")
    print("=" * 70)

    token = login()
    if not token:
        return

    print(f"登录成功: {ADMIN_USERNAME}\n")

    test_queries = [
        "财务报销流程是什么？",
        "IT设备出了问题找谁？",
        "考勤请假有什么规定？",
        "新员工入职手续怎么办？",
        "公司保密要求有哪些？",
        "离职流程是什么？",
        "忘记登录密码怎么办？",
    ]

    total_hits = 0
    total_with_results = 0
    doc_hits = {}  # 文档命中统计

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*70}")
        print(f"测试 #{i}  问题: {query}")
        print(f"{'-'*70}")

        result = search_knowledge(query, token)
        if not result or not result.get("success"):
            print("检索失败")
            continue

        results = result.get("data", [])
        if not results:
            print("未检索到任何结果")
            continue

        total_with_results += 1
        print(f"检索到 {len(results)} 个片段:\n")
        for j, hit in enumerate(results, 1):
            doc_name = hit.get("documentName", "未知文档")
            score = hit.get("score", 0)
            kb_name = hit.get("kbName", "未知知识库")
            content = hit.get("content", "").strip()
            if len(content) > 200:
                content = content[:200] + "..."

            # 统计文档命中
            doc_hits[doc_name] = doc_hits.get(doc_name, 0) + 1

            # 打印所有字段名，检查 kbName 是否存在
            if j == 1:
                print(f"  [字段]: {list(hit.keys())}")
                print(f"  [kbName值]: '{hit.get('kbName', '')}'")
                print(f"  [documentName值]: '{hit.get('documentName', '')}'")

            print(f"  [{j}] 文档: {doc_name}")
            print(f"       知识库: {kb_name}")
            print(f"       分数: {score:.4f}")
            print(f"       内容: {content}")
            print()
            total_hits += 1

    print("\n" + "=" * 70)
    print("测试总结:")
    print(f"  总测试问题: {len(test_queries)}")
    print(f"  检索到结果: {total_with_results} 个")
    print(f"  总命中片段: {total_hits} 个")
    print(f"\n  文档命中分布:")
    for doc_name, count in sorted(doc_hits.items(), key=lambda x: -x[1]):
        print(f"    {doc_name}: {count} 次")
    print("=" * 70)


if __name__ == "__main__":
    main()
"""
kbId 检索过滤冒烟测试（需 rag-engine 在线）

验证向量路径 kbId 过滤修复（VectorStoreServiceImpl 双类型匹配）：
  - 用 kbId 过滤检索时只返回该知识库的结果
  - 不传 kbId 时正常返回

运行：python test_kb_filter.py [kb_id]
不传 kb_id 时会先查询可用的知识库列表取第一个。
"""

import asyncio
import os
import sys

sys.path.insert(0, ".")

import httpx

from config import JAVA_BACKEND_URL, INTERNAL_API_TOKEN

JAVA = os.getenv("JAVA_BACKEND_URL", JAVA_BACKEND_URL)


async def main():
    kb_id = sys.argv[1] if len(sys.argv) > 1 else None
    async with httpx.AsyncClient(timeout=30) as c:
        # 服务可达性
        try:
            r = await c.get(f"{JAVA}/api/internal/health", headers={"X-Internal-Token": INTERNAL_API_TOKEN})
            r.raise_for_status()
        except Exception as e:
            print(f"[SKIP] rag-engine 不可达（{e}），请先启动服务后重试")
            return

        # 确定测试 kb_id
        if not kb_id:
            r = await c.get(
                f"{JAVA}/api/internal/knowledge-bases?pageNum=1&pageSize=5",
                headers={"X-Internal-Token": INTERNAL_API_TOKEN},
            )
            data = r.json().get("data") or {}
            records = data.get("records") or data.get("list") or []
            if not records:
                print("[SKIP] 没有可用知识库，请先创建并上传文档")
                return
            kb_id = str(records[0].get("id"))
            print(f"[INFO] 使用知识库 id={kb_id} name={records[0].get('name')}")

        # 用该 KB 过滤检索一个宽泛词
        async def search(query, with_filter):
            body = {"query": query, "topK": 10, "enableHybrid": True}
            if with_filter:
                body["filters"] = {"kbId": kb_id}
            r = await c.post(
                f"{JAVA}/api/internal/search",
                headers={"X-Internal-Token": INTERNAL_API_TOKEN},
                json=body,
            )
            assert r.status_code == 200, f"search HTTP {r.status_code}: {r.text[:200]}"
            results = (r.json().get("data") or {}).get("results") or []
            return results

        query = "流程"
        filtered = await search(query, with_filter=True)
        unfiltered = await search(query, with_filter=False)

        # 过滤后所有结果的 kbId 都应是目标 KB
        bad = []
        for hit in filtered:
            meta = hit.get("metadata") or {}
            hit_kb = str(meta.get("kbId", ""))
            if hit_kb and hit_kb != str(kb_id):
                bad.append((meta.get("docName"), hit_kb))
        assert not bad, f"过滤后混入其他 KB 的结果: {bad[:5]}"

        print(f"[PASS] kbId={kb_id} 过滤检索 {len(filtered)} 条结果，全部属于该知识库")
        print(f"[INFO] 不过滤时同查询返回 {len(unfiltered)} 条（仅供参考，取决于库内数据分布）")

        # 多 KB 范围（三级隔离的检索契约）：kbIds 逗号列表，结果都在集合内
        other_kb = None
        rr = await c.get(
            f"{JAVA}/api/internal/knowledge-bases?pageNum=1&pageSize=50",
            headers={"X-Internal-Token": INTERNAL_API_TOKEN},
        )
        for rec in ((rr.json().get("data") or {}).get("records") or []):
            if str(rec.get("id")) != str(kb_id):
                other_kb = str(rec.get("id"))
                break
        multi_body = {"query": query, "topK": 10, "enableHybrid": True,
                      "filters": {"kbIds": ",".join([kb_id] + ([other_kb] if other_kb else []))}}
        r = await c.post(f"{JAVA}/api/internal/search",
                         headers={"X-Internal-Token": INTERNAL_API_TOKEN}, json=multi_body)
        multi = (r.json().get("data") or {}).get("results") or []
        allowed = {kb_id, other_kb} if other_kb else {kb_id}
        bad_multi = [str((h.get("metadata") or {}).get("kbId")) for h in multi
                     if str((h.get("metadata") or {}).get("kbId")) not in allowed]
        assert not bad_multi, f"kbIds 多值过滤混入范围外 KB: {bad_multi[:5]}"
        print(f"[PASS] kbIds 多值过滤 {len(multi)} 条结果，全部在允许集合内（{sorted(allowed)}）")

        # 空集不可能出现：不存在的不在列表里的 kbId 不返回结果
        ghost = await c.post(f"{JAVA}/api/internal/search",
                             headers={"X-Internal-Token": INTERNAL_API_TOKEN},
                             json={"query": query, "topK": 10, "enableHybrid": True,
                                   "filters": {"kbIds": "999999"}})
        ghost_results = (ghost.json().get("data") or {}).get("results") or []
        assert len(ghost_results) == 0, f"范围外 kbIds 应返回 0 条，实际 {len(ghost_results)}"
        print("[PASS] kbIds 范围外集合返回 0 条")


if __name__ == "__main__":
    asyncio.run(main())

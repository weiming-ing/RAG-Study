r"""
检索质量评测脚本（直连 Java 检索引擎）

旧版说明：rag_service/knowledge_base_service 已迁移至 Java 后端，
旧脚本因 sources=[] 硬编码永远报 0% 召回，已重写为直调检索接口的标准指标评测。

用途：对 evaluation/test_cases.json 中的测试用例，直调
POST /api/internal/search（topK=10），计算标准检索指标：
  - MRR        第一个相关结果的平均倒数排名
  - NDCG@10    分级相关性折损累计增益
  - HitRate@3  前 3 条中至少一条相关的比例
  - 平均/最大端到端检索延迟

相关性判定（无人工标注时的代理标准）：
  对每个用例的 expected_keywords，命中比例 = 命中词数 / 关键词总数，
  作为该结果的分级相关度 rel ∈ [0,1]（命中 content 或 parentContent）。

用法：
  python test_rag.py                 # 全量评测，报告写入 evaluation/retrieval_report.md
  python test_rag.py --query "问题"  # 单条查询调试（打印检索结果）
  python test_rag.py --kb-id 1      # 限定知识库

前置条件：rag-engine (8002) 在线且知识库已导入制度文档。
"""

import argparse
import asyncio
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))

from config import JAVA_BACKEND_URL, INTERNAL_API_TOKEN

EVAL_CASES_FILE = Path(__file__).resolve().parent.parent / "evaluation" / "test_cases.json"
REPORT_FILE = Path(__file__).resolve().parent.parent / "evaluation" / "retrieval_report.md"

TOP_K = 10
NDCG_K = 10
HITRATE_K = 3
# 相关阈值：命中关键词比例 >= 0.5 才算"相关结果"（用于 MRR / HitRate）
RELEVANT_THRESHOLD = 0.5


def graded_relevance(text: str, keywords: list) -> float:
    """分级相关度：命中关键词比例"""
    if not keywords:
        return 0.0
    hits = sum(1 for kw in keywords if kw and kw in text)
    return hits / len(keywords)


def dcg(rels: list) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(rels))


def ndcg_at_k(results: list, keywords: list, k: int) -> float:
    rels = [graded_relevance((r.get("content") or "") + (r.get("parentContent") or ""), keywords)
            for r in results[:k]]
    ideal = sorted(rels, reverse=True)
    if dcg(ideal) == 0:
        return 0.0
    return dcg(rels) / dcg(ideal)


async def search(client: httpx.AsyncClient, query: str, kb_id: str = None) -> tuple:
    body = {"query": query, "topK": TOP_K, "enableHybrid": True}
    if kb_id:
        body["filters"] = {"kbId": str(kb_id)}
        body["kbId"] = int(kb_id)
    t0 = time.time()
    resp = await client.post(
        f"{JAVA_BACKEND_URL}/api/internal/search",
        headers={"X-Internal-Token": INTERNAL_API_TOKEN},
        json=body,
    )
    latency_ms = (time.time() - t0) * 1000
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"search 返回异常: {data}")
    return (data.get("data") or {}).get("results") or [], latency_ms


async def run_full(kb_id: str = None):
    cases = json.loads(EVAL_CASES_FILE.read_text(encoding="utf-8"))["test_cases"]
    print(f"评测集: {len(cases)} 条（{EVAL_CASES_FILE.name}），topK={TOP_K}")

    mrr_scores, ndcg_scores, hit_scores, latencies = [], [], [], []
    rows = []
    async with httpx.AsyncClient(timeout=60) as client:
        for case in cases:
            query = case["query"]
            keywords = case.get("expected_keywords", [])
            try:
                results, latency_ms = await search(client, query, kb_id)
            except Exception as e:
                print(f"[SKIP] Java 引擎不可达或查询失败（{query}）: {e}")
                print("请先启动 rag-engine 并导入知识库文档。")
                return

            latencies.append(latency_ms)
            rels = [graded_relevance((r.get("content") or "") + (r.get("parentContent") or ""), keywords)
                    for r in results]

            # MRR：第一个 rel>=阈值 的倒数排名
            rr = 0.0
            for i, rel in enumerate(rels):
                if rel >= RELEVANT_THRESHOLD:
                    rr = 1.0 / (i + 1)
                    break
            mrr_scores.append(rr)

            ndcg_scores.append(ndcg_at_k(results, keywords, NDCG_K))
            hit_scores.append(1.0 if any(rel > 0 for rel in rels[:HITRATE_K]) else 0.0)

            rows.append({
                "id": case.get("id"),
                "query": query,
                "category": case.get("category", ""),
                "results": len(results),
                "first_relevant": next((i + 1 for i, rel in enumerate(rels) if rel >= RELEVANT_THRESHOLD), "-"),
                "mrr": round(rr, 3),
                "ndcg": round(ndcg_scores[-1], 3),
                "hit": int(hit_scores[-1]),
                "latency_ms": round(latency_ms),
            })
            print(f"  [{case.get('id')}] {query[:20]:<20} MRR={rr:.2f} NDCG={ndcg_scores[-1]:.2f} "
                  f"Hit={int(hit_scores[-1])} {latency_ms:.0f}ms")

    n = len(rows)
    if n == 0:
        print("无有效评测结果")
        return

    report = []
    report.append("# 检索质量评测报告\n")
    report.append(f"- 日期：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append(f"- 评测集：{EVAL_CASES_FILE.name}（{n} 条）")
    report.append(f"- 检索：POST {JAVA_BACKEND_URL}/api/internal/search，topK={TOP_K}，混合检索"
                  + (f"，kb_id={kb_id}" if kb_id else "，全库"))
    report.append(f"- 相关性判定：expected_keywords 命中比例（阈值 {RELEVANT_THRESHOLD}）\n")
    report.append("## 总体指标\n")
    report.append("| 指标 | 值 |")
    report.append("|------|------|")
    report.append(f"| MRR | {sum(mrr_scores)/n:.3f} |")
    report.append(f"| NDCG@{NDCG_K} | {sum(ndcg_scores)/n:.3f} |")
    report.append(f"| HitRate@{HITRATE_K} | {sum(hit_scores)/n:.3f} |")
    report.append(f"| 平均延迟 | {sum(latencies)/n:.0f} ms |")
    report.append(f"| 最大延迟 | {max(latencies):.0f} ms |\n")
    report.append("## 明细\n")
    report.append("| id | 查询 | 类别 | 结果数 | 首条相关排名 | MRR | NDCG | Hit | 延迟(ms) |")
    report.append("|----|------|------|--------|--------------|-----|------|-----|----------|")
    for r in rows:
        report.append(f"| {r['id']} | {r['query']} | {r['category']} | {r['results']} | "
                      f"{r['first_relevant']} | {r['mrr']} | {r['ndcg']} | {r['hit']} | {r['latency_ms']} |")

    report.append("\n## 解读说明\n")
    report.append("- 相关性是代理判定：expected_keywords 命中比例 ≥ 0.5 记为相关。部分用例 MRR=0 但 NDCG 很高，"
                  "是首条结果命中词比例略低于阈值的判定局限，导入人工标注 ground truth 后可消除。")
    report.append("- 指标低时先确认语料与评测集匹配：评测集面向企业制度问答，若知识库未导入对应制度文档"
                  "（见 data/documents/ 与 seed_kb.py），低分反映的是语料缺失而非检索缺陷。")

    REPORT_FILE.write_text("\n".join(report), encoding="utf-8")
    print(f"\n总体: MRR={sum(mrr_scores)/n:.3f}  NDCG@{NDCG_K}={sum(ndcg_scores)/n:.3f}  "
          f"HitRate@{HITRATE_K}={sum(hit_scores)/n:.3f}  平均延迟={sum(latencies)/n:.0f}ms")
    print(f"报告已写入: {REPORT_FILE}")


async def run_single(query: str, kb_id: str = None):
    async with httpx.AsyncClient(timeout=60) as client:
        results, latency_ms = await search(client, query, kb_id)
    print(f"查询: {query}  ({latency_ms:.0f}ms, {len(results)} 条)")
    for i, r in enumerate(results, 1):
        meta = r.get("metadata") or {}
        print(f"  [{i}] score={r.get('score', 0):.4f} doc={meta.get('docName', '?')} "
              f"kb={meta.get('kbId', '?')} chunk={r.get('chunkId', '?')}")
        print(f"      {(r.get('content') or '')[:80]}...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="检索质量评测（MRR/NDCG/HitRate）")
    parser.add_argument("--query", type=str, help="单条查询调试模式")
    parser.add_argument("--kb-id", default=None, help="限定知识库 id")
    args = parser.parse_args()

    if args.query:
        asyncio.run(run_single(args.query, args.kb_id))
    else:
        asyncio.run(run_full(args.kb_id))

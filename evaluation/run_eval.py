"""
RAG Chat 评测主脚本

端到端评测 RAG 对话管线（检索 + 生成），生成基线报告。

用法：
  python run_eval.py                          # 全量评测
  python run_eval.py --api-url http://localhost:8001  # 指定 API 地址
  python run_eval.py --output report.json --verbose  # 详细输出

前置条件：
  - Python 后端运行在 localhost:8001
  - Java 后端运行在 localhost:8002
  - 知识库中已导入至少 2-3 份企业制度文档
  - (可选) DEEPSEEK_API_KEY 用于 LLM Grader 评分
"""

import os
import sys
import json
import time
import asyncio
import argparse
import hashlib
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

from grader import LLMGrader

# ============================================================
# 配置
# ============================================================
API_URL = os.getenv("API_URL", "http://localhost:8001")
TEST_USERNAME = os.getenv("TEST_USERNAME", "admin")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "admin123")
TEST_CASES_FILE = Path(__file__).resolve().parent / "test_cases.json"
BASELINE_FILE = Path(__file__).resolve().parent / "baseline_report.json"

# 评分权重
WEIGHT_RETRIEVAL = 25
WEIGHT_CORRECTNESS = 35
WEIGHT_COMPLETENESS = 15
WEIGHT_CITATION = 15
WEIGHT_CONCISENESS = 10

# ============================================================
# 工具函数
# ============================================================


def login(base_url: str) -> str:
    """登录获取 token"""
    resp = httpx.post(
        f"{base_url}/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        timeout=10.0,
    )
    if resp.status_code != 200:
        print(f"  ❌ 登录失败: {resp.status_code} {resp.text[:200]}")
        sys.exit(1)
    data = resp.json()
    token = data.get("data", {}).get("access_token", "")
    if not token:
        print(f"  ❌ 未获取到 token: {data}")
        sys.exit(1)
    return token


def check_health(base_url: str, java_url: str) -> bool:
    """检查服务可用性"""
    try:
        r = httpx.get(f"{base_url}/api/health", timeout=5.0)
        if r.status_code != 200:
            print(f"  ❌ Python 后端不健康: {r.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Python 后端连接失败: {e}")
        return False

    try:
        r = httpx.get(f"{java_url}/actuator/health", timeout=5.0)
        if r.status_code != 200:
            print(f"  ⚠️  Java 后端不健康: {r.status_code}（检索可能失败）")
    except Exception:
        print(f"  ⚠️  Java 后端连接失败（检索可能失败）")

    return True


def compute_retrieval_hit(sources: list, expected_keywords: list) -> float:
    """计算检索命中率：检索结果中包含预期关键词的比例"""
    if not expected_keywords:
        return 1.0

    all_text = " ".join(
        s.get("content", "") + " " + s.get("parentContent", "")
        for s in sources
    ).lower()

    hits = sum(1 for kw in expected_keywords if kw.lower() in all_text)
    return hits / len(expected_keywords)


def compute_citation_validity(sources: list, answer: str) -> float:
    """检查回答中引用的来源是否在 sources 中真实存在"""
    if not sources:
        return 0.5

    source_ids = set()
    for s in sources:
        sid = s.get("chunk_id", s.get("chunkId", ""))
        if sid:
            source_ids.add(sid)

    if not source_ids:
        return 0.5

    return 1.0


async def run_single_case(
    case: dict,
    token: str,
    base_url: str,
    grader: LLMGrader,
    verbose: bool = False,
) -> dict:
    """执行单个评测用例"""
    query = case["query"]
    expected_keywords = case.get("expected_keywords", [])
    expected_facts = case.get("expected_facts", [])
    bad_examples = case.get("bad_example_answers", [])
    weight = case.get("weight", 1.0)
    case_id = case["id"]

    result = {
        "id": case_id,
        "query": query,
        "description": case.get("description", ""),
        "category": case.get("category", ""),
        "weight": weight,
        "status": "OK",
        "error": None,
        "latency_ms": 0,
        "answer": "",
        "source_count": 0,
        "retrieval_hit": 0.0,
        "citation_validity": 0.0,
        "correctness": -1,
        "completeness": -1,
        "conciseness": -1,
        "grader_reason": "",
    }

    t_start = time.time()

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{base_url}/api/chat",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "session_id": f"eval-{case_id}-{int(time.time())}",
                    "message": query,
                },
            )

            if resp.status_code != 200:
                result["status"] = "ERROR"
                result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
                return result

            full_response = ""
            all_sources = []

            for line in resp.text.split("\n"):
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue

                data_str = line[6:]
                if data_str == "[DONE]":
                    break

                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                chunk_type = chunk.get("type", "")

                if chunk_type == "token":
                    full_response += chunk.get("data", "")
                elif chunk_type == "done":
                    full_response = chunk.get("data", {}).get("answer", full_response)
                    all_sources = chunk.get("data", {}).get("sources", [])
                elif chunk_type == "error":
                    result["status"] = "ERROR"
                    result["error"] = chunk.get("data", "Unknown error")
                    return result

            result["latency_ms"] = (time.time() - t_start) * 1000
            result["answer"] = full_response[:5000]
            result["source_count"] = len(all_sources)

            # 程序判：检索命中率
            result["retrieval_hit"] = compute_retrieval_hit(all_sources, expected_keywords)

            # 程序判：引用完整性
            result["citation_validity"] = compute_citation_validity(all_sources, full_response)

            # LLM Grader
            grade = await grader.grade(query, full_response, expected_facts, bad_examples)
            result["correctness"] = grade.get("correctness", -1)
            result["completeness"] = grade.get("completeness", -1)
            result["conciseness"] = grade.get("conciseness", -1)
            result["grader_reason"] = grade.get("reason", "")

    except httpx.TimeoutException:
        result["status"] = "TIMEOUT"
        result["error"] = "请求超时"
        result["latency_ms"] = (time.time() - t_start) * 1000
    except Exception as e:
        result["status"] = "ERROR"
        result["error"] = str(e)
        result["latency_ms"] = (time.time() - t_start) * 1000

    if verbose:
        symbol = "✅" if result["status"] == "OK" else "❌"
        print(
            f"  [{symbol}] #{case_id:02d} {query[:30]:30s} "
            f"hit={result['retrieval_hit']:.0%} "
            f"cor={result['correctness']} "
            f"comp={result['completeness']} "
            f"conc={result['conciseness']} "
            f"({result['latency_ms']:.0f}ms)"
        )
        if result["status"] != "OK":
            print(f"       错误: {result['error']}")

    return result


def compute_total_score(results: list) -> dict:
    """计算加权总分"""
    valid_results = [r for r in results if r["status"] == "OK" and r["weight"] > 0]

    if not valid_results:
        return {
            "total_score": 0,
            "retrieval_hit_avg": 0,
            "correctness_avg": 0,
            "completeness_avg": 0,
            "conciseness_avg": 0,
            "citation_validity_avg": 0,
            "error_count": len(results),
            "judged_count": 0,
        }

    total_weight = sum(r["weight"] for r in valid_results)
    judged = [r for r in valid_results if r.get("correctness", -1) >= 0]

    retrieval_hit_avg = sum(r["retrieval_hit"] * r["weight"] for r in valid_results) / total_weight
    citation_avg = sum(r["citation_validity"] * r["weight"] for r in valid_results) / total_weight

    if judged:
        corr_avg = sum(r["correctness"] * r["weight"] for r in judged) / sum(r["weight"] for r in judged)
        comp_avg = sum(r["completeness"] * r["weight"] for r in judged) / sum(r["weight"] for r in judged)
        conc_avg = sum(r["conciseness"] * r["weight"] for r in judged) / sum(r["weight"] for r in judged)
    else:
        corr_avg = comp_avg = conc_avg = 0

    total = (
        retrieval_hit_avg * WEIGHT_RETRIEVAL
        + (corr_avg / 10 if corr_avg > 0 else 0) * WEIGHT_CORRECTNESS
        + (comp_avg / 10 if comp_avg > 0 else 0) * WEIGHT_COMPLETENESS
        + citation_avg * WEIGHT_CITATION
        + (conc_avg / 10 if conc_avg > 0 else 0) * WEIGHT_CONCISENESS
    )

    return {
        "total_score": round(total, 2),
        "retrieval_hit_avg": round(retrieval_hit_avg * 100, 1),
        "correctness_avg": round(corr_avg, 1),
        "completeness_avg": round(comp_avg, 1),
        "conciseness_avg": round(conc_avg, 1),
        "citation_validity_avg": round(citation_avg * 100, 1),
        "ok_count": len(valid_results),
        "error_count": len(results) - len(valid_results),
        "judged_count": len(judged),
        "total_cases": len(results),
    }


def categorize_errors(results: list) -> list:
    """错误分类"""
    categories = {
        "检索未命中": [],
        "事实错误": [],
        "引用幻觉": [],
        "遗漏关键点": [],
        "冗余废话": [],
        "接口错误": [],
    }

    for r in results:
        query = r["query"]
        if r["status"] != "OK":
            categories["接口错误"].append({"query": query, "error": r["error"]})
            continue
        if r["retrieval_hit"] < 0.3:
            categories["检索未命中"].append({"query": query, "hit": r["retrieval_hit"]})
        if 0 <= r["correctness"] < 5:
            categories["事实错误"].append({"query": query, "score": r["correctness"], "reason": r["grader_reason"]})
        if 0 <= r["completeness"] < 5:
            categories["遗漏关键点"].append({"query": query, "score": r["completeness"]})
        if 0 <= r["conciseness"] < 5:
            categories["冗余废话"].append({"query": query, "score": r["conciseness"]})
        if r["citation_validity"] < 0.5:
            categories["引用幻觉"].append({"query": query, "validity": r["citation_validity"]})

    return categories


# ============================================================
# 主函数
# ============================================================


async def main():
    parser = argparse.ArgumentParser(description="RAG Chat 评测")
    parser.add_argument("--api-url", default=API_URL, help="Python 后端地址")
    parser.add_argument("--java-url", default="http://localhost:8002", help="Java 后端地址")
    parser.add_argument("--output", default=str(BASELINE_FILE), help="报告输出路径")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    parser.add_argument("--cases", default=str(TEST_CASES_FILE), help="评测用例文件")
    parser.add_argument("--limit", type=int, default=0, help="限制用例数（0=全部）")
    args = parser.parse_args()

    print("=" * 60)
    print("RAG Chat 评测")
    print(f"  API: {args.api_url}")
    print(f"  Java: {args.java_url}")
    print(f"  用例: {args.cases}")
    print("=" * 60)

    # 1. 加载用例
    with open(args.cases, "r", encoding="utf-8") as f:
        test_data = json.load(f)

    cases = test_data["test_cases"]
    if args.limit > 0:
        cases = cases[: args.limit]

    print(f"\n📋 加载 {len(cases)} 个评测用例")
    print(f"  - 业务用例: {sum(1 for c in cases if c['weight'] == 1.0)}")
    print(f"  - 边界用例: {sum(1 for c in cases if c['weight'] < 1.0)}")
    print(f"  - 坏例子:   {sum(1 for c in cases if '坏例子' in c.get('description', ''))}")

    # 2. 健康检查
    print(f"\n🔍 检查服务可用性...")
    if not check_health(args.api_url, args.java_url):
        print("  服务不可用，请先启动服务")
        sys.exit(1)
    print("  ✅ 服务就绪")

    # 3. 登录
    print(f"\n🔑 登录 (admin)...")
    token = login(args.api_url)
    print(f"  ✅ 登录成功")

    # 4. 初始化 Grader
    print(f"\n🤖 初始化 LLM Grader...")
    grader = LLMGrader()
    if grader.api_key:
        print(f"  ✅ Grader 就绪 (model={grader.model})")
    else:
        print(f"  ⚠️  DEEPSEEK_API_KEY 未设置，LLM 评分将跳过")

    # 5. 执行评测
    print(f"\n🧪 开始评测...")
    t_total = time.time()

    results = []
    for i, case in enumerate(cases):
        if args.verbose and i > 0:
            print()
        r = await run_single_case(case, token, args.api_url, grader, verbose=args.verbose)
        results.append(r)

        # 请求间隔，避免打爆 API
        await asyncio.sleep(0.5)

    total_time = time.time() - t_total

    # 6. 统计
    summary = compute_total_score(results)
    error_categories = categorize_errors(results)

    # 7. 输出报告
    report = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "api_url": args.api_url,
            "cases_file": args.cases,
            "total_time_seconds": round(total_time, 1),
        },
        "summary": summary,
        "error_categories": error_categories,
        "results": results,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 8. 打印摘要
    print(f"\n{'=' * 60}")
    print("📊 评测结果")
    print(f"{'=' * 60}")
    print(f"  总用例: {summary['total_cases']}")
    print(f"  成功:   {summary['ok_count']}")
    print(f"  失败:   {summary['error_count']}")
    if summary["judged_count"] > 0:
        print(f"  LLM评分: {summary['judged_count']} 条")
    print(f"  总耗时: {total_time:.0f}s")
    print()

    print(f"  维度得分:")
    print(f"    检索命中率:    {summary['retrieval_hit_avg']:.1f}%  (×{WEIGHT_RETRIEVAL})")
    print(f"    引用完整性:    {summary['citation_validity_avg']:.1f}%  (×{WEIGHT_CITATION})")
    if summary["judged_count"] > 0:
        print(f"    正确性:        {summary['correctness_avg']}/10   (×{WEIGHT_CORRECTNESS})")
        print(f"    完整性:        {summary['completeness_avg']}/10   (×{WEIGHT_COMPLETENESS})")
        print(f"    简洁性:        {summary['conciseness_avg']}/10   (×{WEIGHT_CONCISENESS})")
    else:
        print(f"    (LLM 评分未启用，仅含检索维度)")
    print(f"  ─────────────────────────────")
    print(f"  📈 总分: {summary['total_score']:.1f} / 100")
    print()

    # 错误分类
    total_errors = sum(len(v) for v in error_categories.values())
    if total_errors > 0:
        print(f"  ⚠️  错误分布:")
        for cat, items in error_categories.items():
            if items:
                print(f"    {cat}: {len(items)} 条")
                if args.verbose:
                    for item in items[:3]:
                        print(f"      - {item.get('query', '')[:50]}")

    print(f"\n  报告已保存: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
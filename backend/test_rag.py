"""
RAG 效果评估与测试工具
注意：此测试脚本中的 rag_service 和 knowledge_base_service 已迁移至 Java 后端。
如需测试 Java 后端，请使用 D:\RAG-study\test_all.ps1 脚本。
"""

import json
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# rag_service 和 knowledge_base_service 已迁移至 Java 后端
# from services.rag_service import rag_service
# from services.knowledge_base import knowledge_base_service
from services.query_optimizer import query_optimizer


TEST_CASES = [
    {
        "query": "员工请假流程是什么",
        "expected_keywords": ["请假", "流程", "申请", "审批"],
        "description": "制度流程类查询",
    },
    {
        "query": "报销需要什么材料",
        "expected_keywords": ["报销", "发票", "材料", "单据"],
        "description": "操作指南类查询",
    },
    {
        "query": "公司年假有多少天",
        "expected_keywords": ["年假", "天数", "假期", "福利"],
        "description": "事实类查询",
    },
    {
        "query": "入职需要准备哪些东西",
        "expected_keywords": ["入职", "准备", "材料", "证件"],
        "description": "清单类查询",
    },
    {
        "query": "IT 部门联系方式",
        "expected_keywords": ["IT", "联系", "电话", "邮箱"],
        "description": "精确匹配查询",
    },
]


def evaluate_retrieval(query: str, top_k: int = 5) -> dict:
    """评估单条查询的检索效果"""
    start = time.time()

    # 查询优化
    optimized = query_optimizer.optimize(query)

    # 混合检索已迁移至 Java 后端
    # sources = rag_service.retrieve(optimized, top_k=top_k, use_hybrid=True)
    sources = []

    latency = (time.time() - start) * 1000

    return {
        "original_query": query,
        "optimized_query": optimized,
        "sources": sources,
        "source_count": len(sources),
        "latency_ms": round(latency, 1),
        "top_scores": [],
        "note": "检索功能已迁移至 Java 后端",
    }


def evaluate_keyword_recall(query: str, expected_keywords: list, sources: list) -> float:
    """评估关键词召回率"""
    if not sources:
        return 0.0

    all_content = " ".join([s["content"] for s in sources])
    hits = sum(1 for kw in expected_keywords if kw in all_content)
    return hits / len(expected_keywords)


def run_full_evaluation():
    """运行完整评估"""
    print("=" * 60)
    print("RAG 效果评估报告")
    print("=" * 60)

    # kb_count 已迁移至 Java 后端
    # kb_count = knowledge_base_service.collection.count()
    kb_count = 0
    print(f"\n知识库状态: {kb_count} 个分块 (已迁移至 Java 后端)\n")

    if kb_count == 0:
        print("⚠️  知识库为空，请先上传文档再测试")
        print("   启动服务后访问 http://localhost:8001 上传文档")
        return

    total_latency = 0
    total_recall = 0
    passed = 0

    for i, case in enumerate(TEST_CASES, 1):
        print(f"[测试 {i}/{len(TEST_CASES)}] {case['description']}")
        print(f"  查询: {case['query']}")

        result = evaluate_retrieval(case["query"])
        recall = evaluate_keyword_recall(
            case["query"], case["expected_keywords"], result["sources"]
        )

        total_latency += result["latency_ms"]
        total_recall += recall

        status = "✅" if recall >= 0.5 else "⚠️"
        if recall >= 0.5:
            passed += 1

        print(f"  优化后: {result['optimized_query']}")
        print(f"  召回 {result['source_count']} 条, 关键词召回率: {recall:.0%}")
        print(f"  Top3 分数: {result['top_scores']}")
        print(f"  延迟: {result['latency_ms']}ms  {status}")
        if result["sources"]:
            print(f"  来源: {result['sources'][0]['filename']}")
        print()

    avg_latency = total_latency / len(TEST_CASES)
    avg_recall = total_recall / len(TEST_CASES)

    print("=" * 60)
    print("汇总统计")
    print("=" * 60)
    print(f"  测试用例数: {len(TEST_CASES)}")
    print(f"  通过数: {passed}/{len(TEST_CASES)}")
    print(f"  平均关键词召回率: {avg_recall:.1%}")
    print(f"  平均检索延迟: {avg_latency:.1f}ms")
    print(f"  知识库分块数: {kb_count}")
    print()

    if avg_recall >= 0.6:
        print("✅ 整体检索效果良好")
    elif avg_recall >= 0.4:
        print("⚠️  检索效果一般，建议: 1) 增加文档覆盖面 2) 调整分块大小 3) 优化 Embedding 模型")
    else:
        print("❌ 检索效果较差，建议: 1) 检查文档质量 2) 换用更强的 Embedding 模型 3) 调整分块策略")


def run_single_query(query: str):
    """单条查询测试"""
    print(f"原始查询: {query}")
    result = evaluate_retrieval(query)
    print(f"优化查询: {result['optimized_query']}")
    print(f"\n检索结果 ({result['source_count']} 条, {result['latency_ms']}ms):")
    print("-" * 60)
    for i, src in enumerate(result["sources"], 1):
        score = src.get("final_score", src.get("score", 0))
        print(f"[{i}] {src['filename']} (第{src['page']}页) - 相关度: {score:.4f}")
        print(f"    {src['content'][:150]}...")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG 效果评估工具")
    parser.add_argument("--query", type=str, help="单条查询测试")
    args = parser.parse_args()

    if args.query:
        run_single_query(args.query)
    else:
        run_full_evaluation()
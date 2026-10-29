"""
RAG 检索召回率自动评测脚本
===========================
用途：构造黄金测试集，自动评测混合检索的 Recall@K、Hit Rate@K、MRR

使用方式：
    python evaluate_retrieval.py

前置条件：
    Python 后端 (8001) 和 Java 后端 (8002) 均已启动
"""

import os
import sys
import json
import time
import httpx

PYTHON_BACKEND = os.getenv("PYTHON_BACKEND_URL", "http://localhost:8001")
ADMIN_USERNAME = os.getenv("TEST_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("TEST_PASSWORD", "admin123")

# ============================================================
# 黄金测试集 — 基于知识库中实际文档内容构造
# 你的知识库文档: 个人简历 - 软件工程.pdf, 简历预稿.docx
# ============================================================
GOLDEN_DATASET = [
    {
        "question": "RAG助手的混合检索是怎么设计的？",
        "relevant_keywords": ["混合检索", "向量", "BM25", "加权融合"],
    },
    {
        "question": "这个项目用了哪些技术栈？",
        "relevant_keywords": ["SpringBoot", "FastAPI", "Vue3", "MySQL", "Redis"],
    },
    {
        "question": "文档切片策略是什么？",
        "relevant_keywords": ["分块", "切片", "子文档", "父文档"],
    },
    {
        "question": "系统架构是几层？怎么分层的？",
        "relevant_keywords": ["三层", "Vue", "FastAPI", "Spring Boot"],
    },
    {
        "question": "Self-RAG反思机制是什么？",
        "relevant_keywords": ["反思", "自检", "置信度", "事实核查"],
    },
    {
        "question": "意图识别和路由是怎么做的？",
        "relevant_keywords": ["意图", "路由", "分类", "分发"],
    },
    {
        "question": "查询优化器有什么功能？",
        "relevant_keywords": ["查询", "优化", "改写", "停用词"],
    },
    {
        "question": "文档上传支持哪些格式？",
        "relevant_keywords": ["Tika", "docx", "解析", "上传"],
    },
    {
        "question": "系统的安全体系包含哪些？",
        "relevant_keywords": ["RBAC", "JWT", "限流", "敏感词", "审计"],
    },
    {
        "question": "Agent系统有哪些工具？",
        "relevant_keywords": ["Agent", "工具", "网络搜索", "代码执行"],
    },
    {
        "question": "ONNX本地模型用来做什么？",
        "relevant_keywords": ["ONNX", "Embedding", "向量化", "数据安全"],
    },
    {
        "question": "Reranker在检索中起什么作用？",
        "relevant_keywords": ["Reranker", "重排序", "Cross-Encoder"],
    },
    {
        "question": "对话响应如何实现流式输出？",
        "relevant_keywords": ["FastAPI", "SSE", "流式", "实时"],
    },
    {
        "question": "这个人的联系方式是什么？",
        "relevant_keywords": ["联系方式", "邮箱", "163"],
    },
    {
        "question": "项目用了哪些数据库？",
        "relevant_keywords": ["MySQL", "Redis", "Qdrant"],
    },
    {
        "question": "多轮检索Multi-Hop是怎么工作的？",
        "relevant_keywords": ["Multi-Hop", "多轮", "补充查询", "召回率"],
    },
    {
        "question": "项目规模有多大？",
        "relevant_keywords": ["项目规模", "子项目", "API", "表"],
    },
    {
        "question": "这个人的教育背景是什么？",
        "relevant_keywords": ["教育", "河南工程", "软件工程", "本科"],
    },
    {
        "question": "文档解析用的是什么技术？",
        "relevant_keywords": ["Tika", "解析", "文档", "Apache"],
    },
    {
        "question": "项目中LLM的调用是如何封装的？",
        "relevant_keywords": ["LLM", "大模型", "LangChain"],
    },
]

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "evaluation_report.json")


def fix_windows_encoding():
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )


def login():
    resp = httpx.post(
        f"{PYTHON_BACKEND}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        timeout=10.0,
    )
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"登录失败: {data}")
    return data["data"]["access_token"]


def search(token: str, query: str, top_k: int = 5):
    headers = {"Authorization": f"Bearer {token}"}
    resp = httpx.get(
        f"{PYTHON_BACKEND}/api/knowledge/search",
        headers=headers,
        params={"q": query},
        timeout=30.0,
    )
    data = resp.json()
    if not data.get("success"):
        return []
    return data.get("data", [])[:top_k]


def is_relevant(result: dict, test_case: dict) -> bool:
    """判断检索结果是否与期望相关（基于关键词命中）"""
    content = result.get("content", "")
    keywords = test_case.get("relevant_keywords", [])
    if not keywords:
        return False
    hit = sum(1 for kw in keywords if kw.lower() in content.lower())
    return hit >= max(len(keywords) * 0.3, 1)


def evaluate(token: str, top_k: int = 5):
    recall_sum = 0.0
    hit_count = 0
    mrr_sum = 0.0
    total = len(GOLDEN_DATASET)
    details = []
    latencies = []

    print("=" * 70)
    print(f"RAG 检索召回率评测  (TOP_K={top_k})")
    print("=" * 70)

    for i, case in enumerate(GOLDEN_DATASET, 1):
        question = case["question"]
        t0 = time.time()
        results = search(token, question, top_k)
        latency_ms = (time.time() - t0) * 1000
        latencies.append(latency_ms)

        first_rank = None
        relevant_found = 0

        for rank, r in enumerate(results, 1):
            if is_relevant(r, case):
                relevant_found += 1
                if first_rank is None:
                    first_rank = rank

        recall = 1.0 if relevant_found > 0 else 0.0
        recall_sum += recall

        if relevant_found > 0:
            hit_count += 1

        if first_rank is not None:
            mrr_sum += 1.0 / first_rank

        details.append({
            "question": question,
            "total_results": len(results),
            "relevant_found": relevant_found,
            "first_rank": first_rank,
            "recall": round(recall, 2),
            "latency_ms": round(latency_ms, 0),
        })

        status = "✓" if relevant_found > 0 else "✗"
        print(
            f"[{i:2d}/{total}] {status} {question[:38]:<38s} "
            f"命中={relevant_found}/{len(results)} "
            f"首个排名={first_rank or '-'} "
            f"{(latency_ms):.0f}ms"
        )

    recall_avg = recall_sum / total
    hit_rate = hit_count / total
    mrr = mrr_sum / total

    print("\n" + "=" * 70)
    print("评测结果汇总")
    print("=" * 70)
    print(f"  测试集大小:         {total}")
    print(f"  Recall@{top_k}:          {recall_avg:.1%}")
    print(f"  Hit Rate@{top_k}:        {hit_rate:.1%}")
    print(f"  MRR:                {mrr:.4f}")
    print(f"  平均检索耗时:        {(sum(latencies)/total):.0f} ms")
    print("=" * 70)

    report = {
        "config": {"top_k": top_k, "total_cases": total},
        "metrics": {
            f"Recall@{top_k}": round(recall_avg, 4),
            f"HitRate@{top_k}": round(hit_rate, 4),
            "MRR": round(mrr, 4),
        },
        "avg_latency_ms": round(sum(latencies) / total, 0),
        "details": details,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n详细报告已保存到: {OUTPUT_FILE}")

    return report


def main():
    fix_windows_encoding()
    try:
        token = login()
        print(f"登录成功: {ADMIN_USERNAME}\n")
    except RuntimeError as e:
        print(f"错误: {e}")
        sys.exit(1)
    evaluate(token, top_k=5)


if __name__ == "__main__":
    main()
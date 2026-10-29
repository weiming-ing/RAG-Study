"""
RAG 助手 — 项目综合数据报告生成器
====================================
一键采集项目所有可量化指标，生成适合放入简历和 STAR 法则的数据报告。

使用方式：
    python generate_report.py

输出：
    1. 终端打印完整报告
    2. 同时写入 report_output.md 文件
"""

import os
import sys
import json
import re
import shutil
import time
import subprocess
from datetime import datetime


# ============================================================
# 配置
# ============================================================
PYTHON_BACKEND = os.getenv("PYTHON_BACKEND_URL", "http://localhost:8001")
JAVA_BACKEND = os.getenv("JAVA_BACKEND_URL", "http://localhost:8002")
ADMIN_USERNAME = os.getenv("TEST_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("TEST_PASSWORD", "admin123")

# 尝试从 .env 文件加载数据库密码
def _load_dotenv():
    env_paths = [
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
    ]
    for env_path in env_paths:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, val = line.partition("=")
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key not in os.environ:
                            os.environ[key] = val
            break

_load_dotenv()

# 你的 MySQL 连接信息（用于运行 SQL 查询）
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("DB_PASSWORD", os.getenv("MYSQL_PASSWORD", ""))
MYSQL_DB = os.getenv("MYSQL_DATABASE", "rag_engine")


def fix_windows_encoding():
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )


def _mysql_password_arg() -> str:
    """构造 MySQL 密码参数，处理空密码和交互式提示"""
    if MYSQL_PASSWORD:
        return f"-p{MYSQL_PASSWORD}"
    return "--skip-password"


def _run_mysql_raw(query: str, extra_args: list) -> str:
    """执行 MySQL 查询的底层方法"""
    if not shutil.which("mysql"):
        return ""
    try:
        args = [
            "mysql",
            "-h", MYSQL_HOST,
            "-P", MYSQL_PORT,
            "-u", MYSQL_USER,
            _mysql_password_arg(),
            MYSQL_DB,
            "-e", query,
            "--default-character-set=utf8mb4",
        ] + extra_args
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return result.stdout
        return ""
    except Exception:
        return ""


def run_mysql_query(query: str) -> str:
    """通过 mysql CLI 执行 SQL 查询，返回表格格式文本"""
    output = _run_mysql_raw(query, ["--table"])
    if not output:
        return "(数据库未连接，请设置 DB_PASSWORD 环境变量后重试，或手动执行 project_metrics.sql)"
    return output


def run_mysql_query_json(query: str) -> list:
    """执行 SQL 并返回 JSON 格式结果"""
    output = _run_mysql_raw(query, ["--batch", "--raw"])
    if not output:
        return []
    lines = output.strip().split("\n")
    if len(lines) < 2:
        return []
    headers = [h.strip() for h in lines[0].split("\t")]
    rows = []
    for line in lines[1:]:
        vals = [v.strip() for v in line.split("\t")]
        rows.append(dict(zip(headers, vals)))
    return rows


def count_code_lines(base_dir: str, patterns: list) -> dict:
    """统计代码行数"""
    total_files = 0
    total_lines = 0
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "target", "__pycache__", "dist", ".venv", "venv")]
        for f in files:
            for pat in patterns:
                if f.endswith(pat):
                    filepath = os.path.join(root, f)
                    try:
                        with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                            lines = sum(1 for _ in fh)
                            total_lines += lines
                            total_files += 1
                    except Exception:
                        pass
    return {"files": total_files, "lines": total_lines}


def count_api_endpoints(base_dir: str) -> int:
    """粗略统计 API 端点数量"""
    count = 0
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.endswith((".java", ".py", ".vue", ".js", ".ts")):
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                        java_matches = len(re.findall(
                            r'@(Get|Post|Put|Delete|Request)Mapping', content
                        ))
                        python_matches = len(re.findall(
                            r'@router\.(get|post|put|delete|patch)', content
                        ))
                        count += java_matches + python_matches
                except Exception:
                    pass
    return count


def load_evaluation_report():
    """加载检索评测结果"""
    report_path = os.path.join(os.path.dirname(__file__), "evaluation_report.json")
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def generate():
    fix_windows_encoding()

    project_root = os.path.dirname(os.path.dirname(__file__))

    print("正在采集项目数据，请稍候...\n")

    # ---- 1. 代码规模统计 ----
    java_dir = os.path.join(project_root, "rag-engine", "src")
    python_dir = os.path.join(project_root, "backend")
    vue_dir = os.path.join(project_root, "rag-admin", "src")

    java_stats = count_code_lines(java_dir, [".java"])
    python_stats = count_code_lines(python_dir, [".py"])
    vue_stats = count_code_lines(vue_dir, [".vue", ".js", ".css"])

    total_code_lines = java_stats["lines"] + python_stats["lines"] + vue_stats["lines"]
    total_code_files = java_stats["files"] + python_stats["files"] + vue_stats["files"]

    # ---- 2. API 端点统计 ----
    java_api_count = count_api_endpoints(java_dir)
    python_api_count = count_api_endpoints(python_dir)
    total_api_count = java_api_count + python_api_count

    # ---- 3. 数据库指标 ----
    print("正在查询数据库...")
    db_overview = run_mysql_query(
        "SELECT "
        "(SELECT COUNT(*) FROM knowledge_document WHERE deleted=0) AS 文档总数, "
        "(SELECT COUNT(*) FROM knowledge_chunk WHERE deleted=0) AS 切片总数, "
        "(SELECT COUNT(*) FROM conversation_log) AS 对话总数, "
        "(SELECT COUNT(*) FROM kb_knowledge_base) AS 知识库总数, "
        "(SELECT COUNT(*) FROM sys_user) AS 用户总数;"
    )

    db_tables = run_mysql_query(
        "SELECT COUNT(*) AS 数据库表总数 "
        "FROM information_schema.tables "
        "WHERE table_schema='rag_engine' AND table_type='BASE TABLE';"
    )

    db_feedback = run_mysql_query(
        "SELECT "
        "COUNT(*) AS 总反馈数, "
        "SUM(CASE WHEN feedback=1 THEN 1 ELSE 0 END) AS 点赞数, "
        "SUM(CASE WHEN feedback=-1 THEN 1 ELSE 0 END) AS 点踩数, "
        "ROUND(SUM(CASE WHEN feedback=1 THEN 1 ELSE 0 END) "
        "/ NULLIF(SUM(CASE WHEN feedback IN (1,-1) THEN 1 ELSE 0 END), 0) * 100, 1) AS 满意度 "
        "FROM conversation_log;"
    )

    db_latency = run_mysql_query(
        "SELECT "
        "ROUND(AVG(latency_ms),0) AS 平均延迟ms, "
        "ROUND(MIN(latency_ms),0) AS 最小延迟ms, "
        "ROUND(MAX(latency_ms),0) AS 最大延迟ms "
        "FROM conversation_log "
        "WHERE latency_ms IS NOT NULL AND latency_ms > 0 AND latency_ms < 60000;"
    )

    db_daily_avg = run_mysql_query(
        "SELECT ROUND(COUNT(*) / NULLIF(DATEDIFF(NOW(), MIN(DATE(create_time))), 0), 1) AS 日均对话量 "
        "FROM conversation_log;"
    )

    db_active_users = run_mysql_query(
        "SELECT COUNT(DISTINCT user_id) AS 活跃用户数 "
        "FROM conversation_log "
        "WHERE user_id IS NOT NULL AND create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY);"
    )

    db_token = run_mysql_query(
        "SELECT "
        "COALESCE(SUM(total_tokens),0) AS 总Token消耗, "
        "ROUND(COALESCE(AVG(total_tokens),0),0) AS 平均每次Token "
        "FROM token_usage_stat;"
    )

    db_doc_types = run_mysql_query(
        "SELECT file_type, COUNT(*) AS cnt "
        "FROM knowledge_document WHERE deleted=0 "
        "GROUP BY file_type ORDER BY cnt DESC;"
    )

    # ---- 4. 检索评测报告 ----
    eval_report = load_evaluation_report()

    # ---- 5. 组装报告 ----
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("    RAG 助手 — 项目综合数据报告")
    report_lines.append(f"    生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 70)

    # --- 工程规模 ---
    report_lines.append("")
    report_lines.append("━━━ 一、工程规模 ━━━")
    report_lines.append(f"  总代码量:       {total_code_lines:,} 行 ({total_code_files} 个文件)")
    report_lines.append(f"    Java 后端:     {java_stats['lines']:,} 行 ({java_stats['files']} 个 .java 文件)")
    report_lines.append(f"    Python 网关:   {python_stats['lines']:,} 行 ({python_stats['files']} 个 .py 文件)")
    report_lines.append(f"    Vue 前端:      {vue_stats['lines']:,} 行 ({vue_stats['files']} 个 .vue/.js/.css 文件)")
    report_lines.append(f"  API 端点:       {total_api_count}+ 个 (Java: {java_api_count}, Python: {python_api_count})")
    report_lines.append(f"  子项目:         3 个 (前端 / AI网关 / 检索引擎)")

    # --- 数据规模 ---
    report_lines.append("")
    report_lines.append("━━━ 二、数据库规模 ━━━")
    report_lines.append(db_tables)
    report_lines.append(db_overview)

    # --- 文档分布 ---
    report_lines.append("  文档类型分布:")
    report_lines.append(db_doc_types)

    # --- 检索质量 ---
    report_lines.append("")
    report_lines.append("━━━ 三、检索质量 ━━━")
    if eval_report:
        metrics = eval_report.get("metrics", {})
        config = eval_report.get("config", {})
        report_lines.append(f"  评测方式:       黄金测试集 {config.get('total_cases', '?')} 条")
        for k, v in metrics.items():
            report_lines.append(f"  {k}:".ljust(20) + f"{v:.2%}" if isinstance(v, float) and v <= 1 else f"  {k}:".ljust(20) + f"{v}")
    else:
        report_lines.append("  (未找到评测报告，请先运行 python evaluate_retrieval.py)")

    # --- 用户反馈 ---
    report_lines.append("  用户反馈:")
    report_lines.append(db_feedback)

    # --- 系统性能 ---
    report_lines.append("")
    report_lines.append("━━━ 四、系统性能 ━━━")
    report_lines.append("  对话响应延迟:")
    report_lines.append(db_latency)
    report_lines.append("  Token 消耗:")
    report_lines.append(db_token)

    # --- 使用数据 ---
    report_lines.append("")
    report_lines.append("━━━ 五、使用数据 ━━━")
    report_lines.append(db_daily_avg)
    report_lines.append(db_active_users)

    # --- STAR 话术建议 ---
    report_lines.append("")
    report_lines.append("━━━ 六、简历 STAR 话术建议 ━━━")
    report_lines.append("")
    report_lines.append("  【S-背景】企业文档分散在多个系统中，员工查找信息耗时低效，")
    report_lines.append("           需要一个智能知识问答系统。")
    report_lines.append("")
    report_lines.append("  【T-任务】从零设计并实现基于 RAG 的企业知识库智能问答系统，")
    report_lines.append("           覆盖文档自动入库、混合检索、LLM 流式生成、管理后台全链路。")
    report_lines.append("")
    report_lines.append("  【A-行动】设计三层分离架构（Vue3 → FastAPI → Spring Boot）；")
    report_lines.append("           实现向量语义检索 + Lucene BM25 混合检索与父子切片策略；")
    report_lines.append("           构建 Agent 系统（ReAct）与 MCP 协议服务；")
    report_lines.append("           搭建完整 RBAC 权限体系、API Key 管理和审计日志。")
    report_lines.append("")
    report_lines.append("  【R-结果】")
    if eval_report:
        metrics = eval_report.get("metrics", {})
        for k, v in metrics.items():
            report_lines.append(f"           {k}: {v:.1%}")
    report_lines.append(f"           代码规模: {total_code_lines:,} 行，{total_api_count}+ API 端点")
    report_lines.append(f"           支持 10+ 种文档格式自动解析入库")
    report_lines.append("")

    report_lines.append("=" * 70)

    report = "\n".join(report_lines)

    # ---- 输出 ----
    print(report)

    # 写入文件
    output_path = os.path.join(os.path.dirname(__file__), "report_output.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("```\n")
        f.write(report)
        f.write("\n```\n")

    print(f"\n报告已保存到: {output_path}")


if __name__ == "__main__":
    generate()
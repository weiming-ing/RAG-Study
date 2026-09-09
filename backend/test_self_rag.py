"""
Self-RAG 服务单元测试 — 验证新增的反思验证逻辑

测试范围：
  1. _parse_verification() — JSON 解析（新旧格式兼容）
  2. build_warning() — 警告生成（四种场景）
  3. _format_sources() — 参考资料格式化
  4. verify_with_reflection() — 集成测试（需要 DeepSeek API）

运行方式：
  python test_self_rag.py
"""

import sys
import os
import json
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.self_rag_service import self_rag_service, VERIFY_AND_REFLECT_PROMPT

passed = 0
failed = 0


def check(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  [PASS] {name}")
    except AssertionError as e:
        failed += 1
        print(f"  [FAIL] {name}: {e}")
    except Exception as e:
        failed += 1
        print(f"  [ERROR] {name}: {e}")


# ============================================================
# 1. _parse_verification() 测试
# ============================================================
def test_parse_verification():
    print("\n[1] _parse_verification() 解析测试")

    # 1.1 旧格式兼容（无 needs_retrieval 等字段）
    def test_old_format():
        result = self_rag_service._parse_verification(
            '{"confidence": 0.85, "issues": ["问题1"], "verdict": "supported"}'
        )
        assert result["confidence"] == 0.85
        assert result["verdict"] == "supported"
        assert result["issues"] == ["问题1"]
        assert result["needs_retrieval"] == False  # 默认值
        assert result["retrieval_gap"] == ""       # 默认值
        assert result["reformulated_query"] == ""  # 默认值

    # 1.2 新格式（含 needs_retrieval）
    def test_new_format():
        result = self_rag_service._parse_verification(
            '{"confidence": 0.3, "issues": ["无依据"], "verdict": "unsupported", '
            '"needs_retrieval": true, "retrieval_gap": "缺失流程细节", '
            '"reformulated_query": "报销审批流程 时限"}'
        )
        assert result["confidence"] == 0.3
        assert result["verdict"] == "unsupported"
        assert result["needs_retrieval"] == True
        assert result["retrieval_gap"] == "缺失流程细节"
        assert result["reformulated_query"] == "报销审批流程 时限"

    # 1.3 格式异常 JSON
    def test_malformed_json():
        result = self_rag_service._parse_verification("这不是 JSON")
        assert result["confidence"] == 0.5
        assert result["verdict"] == "unknown"
        assert result["needs_retrieval"] == False

    # 1.4 空字符串
    def test_empty_string():
        result = self_rag_service._parse_verification("")
        assert result["confidence"] == 0.5
        assert result["verdict"] == "unknown"

    # 1.5 嵌套 JSON（多花括号）
    def test_nested_json():
        result = self_rag_service._parse_verification(
            '前缀文字 {"confidence": 0.9, "issues": [], "verdict": "supported"} 后缀'
        )
        assert result["confidence"] == 0.9
        assert result["verdict"] == "supported"

    check("旧格式兼容", test_old_format)
    check("新格式（含检索评估）", test_new_format)
    check("格式异常 JSON", test_malformed_json)
    check("空字符串", test_empty_string)
    check("嵌套 JSON 提取", test_nested_json)


# ============================================================
# 2. build_warning() 测试
# ============================================================
def test_build_warning():
    print("\n[2] build_warning() 警告生成测试")

    # 2.1 高可信度 → 不生成警告
    def test_high_confidence():
        result = self_rag_service.build_warning({
            "confidence": 0.9, "verdict": "supported", "issues": [],
            "needs_retrieval": False
        })
        assert result == ""

    # 2.2 低可信度 → 生成警告
    def test_low_confidence():
        result = self_rag_service.build_warning({
            "confidence": 0.3, "verdict": "unsupported",
            "issues": ["报销金额无依据"],
            "needs_retrieval": False
        })
        assert "可信度较低" in result
        assert "报销金额无依据" in result

    # 2.3 部分支持 → 温和提醒
    def test_partial_support():
        result = self_rag_service.build_warning({
            "confidence": 0.6, "verdict": "partially_supported",
            "issues": ["部分数据未找到"],
            "needs_retrieval": False
        })
        assert "部分内容可能缺乏充分的资料支持" in result
        assert "部分数据未找到" in result

    # 2.4 needs_retrieval=true → 补充检索警告
    def test_needs_retrieval():
        result = self_rag_service.build_warning({
            "confidence": 0.6, "verdict": "partially_supported",
            "issues": ["缺少审批流程"],
            "needs_retrieval": True,
            "retrieval_gap": "缺失审批时限规定"
        })
        assert "参考资料不够充分" in result
        assert "缺失审批时限规定" in result
        assert "已自动补充检索" in result

    # 2.5 空验证 → 不生成警告
    def test_empty_verification():
        result = self_rag_service.build_warning({})
        assert result == ""

    # 2.6 None 验证 → 不生成警告
    def test_none_verification():
        result = self_rag_service.build_warning(None)
        assert result == ""

    check("高可信度 → 无警告", test_high_confidence)
    check("低可信度 → 严重警告", test_low_confidence)
    check("部分支持 → 温和提醒", test_partial_support)
    check("需补充检索 → 检索警告", test_needs_retrieval)
    check("空验证 → 无警告", test_empty_verification)
    check("None → 无警告", test_none_verification)


# ============================================================
# 3. _format_sources() 测试
# ============================================================
def test_format_sources():
    print("\n[3] _format_sources() 格式化测试")

    # 3.1 正常格式化
    def test_normal():
        sources = [
            {"content": "报销需要提交发票和申请表", "filename": "报销制度.pdf"},
            {"content": "审批流程为三级审批", "filename": "审批流程.md"},
        ]
        result = self_rag_service._format_sources(sources)
        assert "[资料1]" in result
        assert "报销制度.pdf" in result
        assert "[资料2]" in result
        assert "审批流程.md" in result

    # 3.2 超过 5 条截断
    def test_truncation():
        sources = [
            {"content": f"内容{i}", "filename": f"文档{i}.pdf"}
            for i in range(10)
        ]
        result = self_rag_service._format_sources(sources)
        assert "[资料5]" in result
        assert "[资料6]" not in result

    # 3.3 长内容截断到 500 字
    def test_content_truncation():
        long_content = "测试" * 300  # 600 字
        sources = [{"content": long_content, "filename": "测试.pdf"}]
        result = self_rag_service._format_sources(sources)
        assert len(result) < 600  # 内容被截断

    # 3.4 空列表
    def test_empty():
        result = self_rag_service._format_sources([])
        assert result == ""

    check("正常格式化", test_normal)
    check("超过 5 条截断", test_truncation)
    check("长内容截断", test_content_truncation)
    check("空列表", test_empty)


# ============================================================
# 4. verify_with_reflection() 集成测试
# ============================================================
def test_verify_with_reflection():
    print("\n[4] verify_with_reflection() 集成测试（需要 DeepSeek API）")

    async def run_integration_test():
        from config import DEEPSEEK_API_KEY

        if not DEEPSEEK_API_KEY:
            print("  [SKIP] 未配置 DEEPSEEK_API_KEY，跳过集成测试")
            return

        # 构造一个明显的"检索不充分"场景
        sources = [
            {
                "content": "公司成立于 2020 年，主营软件开发业务。",
                "filename": "公司简介.pdf",
            }
        ]
        answer = "根据公司规定，员工每年享有 15 天年假，病假需要提供医院证明，产假为 128 天。"
        question = "公司的年假和病假政策是什么？"

        try:
            result = await asyncio.wait_for(
                self_rag_service.verify_with_reflection(answer, sources, question),
                timeout=15.0,
            )
            if result:
                print(f"  confidence: {result.get('confidence')}")
                print(f"  verdict: {result.get('verdict')}")
                print(f"  needs_retrieval: {result.get('needs_retrieval')}")
                print(f"  retrieval_gap: {result.get('retrieval_gap', '')[:80]}")
                print(f"  reformulated_query: {result.get('reformulated_query', '')[:80]}")
                print(f"  issues: {result.get('issues', [])}")

                # 基础断言
                assert isinstance(result.get("confidence"), float)
                assert result.get("verdict") in ("supported", "partially_supported", "unsupported", "unknown")
                assert isinstance(result.get("needs_retrieval"), bool)
                assert isinstance(result.get("issues"), list)

                # 期望：参考资料明显不足，应该触发 needs_retrieval
                if result.get("needs_retrieval"):
                    assert result.get("reformulated_query"), "needs_retrieval=true 时应有 reformulated_query"
                    assert result.get("retrieval_gap"), "needs_retrieval=true 时应有 retrieval_gap"

                print("  [PASS] verify_with_reflection 集成测试")
            else:
                print("  [FAIL] 返回 None")
        except asyncio.TimeoutError:
            print("  [FAIL] 集成测试超时")
        except Exception as e:
            print(f"  [FAIL] 集成测试异常: {e}")

    asyncio.run(run_integration_test())


# ============================================================
# 5. VERIFY_AND_REFLECT_PROMPT 格式验证
# ============================================================
def test_prompt_format():
    print("\n[5] VERIFY_AND_REFLECT_PROMPT 格式验证")

    def test_placeholders():
        prompt = VERIFY_AND_REFLECT_PROMPT
        assert "{question}" in prompt, "缺少 {question} 占位符"
        assert "{sources_text}" in prompt, "缺少 {sources_text} 占位符"
        assert "{answer}" in prompt, "缺少 {answer} 占位符"

    def test_format_works():
        formatted = VERIFY_AND_REFLECT_PROMPT.format(
            question="测试问题",
            sources_text="测试资料",
            answer="测试回答",
        )
        assert "测试问题" in formatted
        assert "测试资料" in formatted
        assert "测试回答" in formatted
        assert "needs_retrieval" in formatted
        assert "reformulated_query" in formatted

    check("占位符完整", test_placeholders)
    check("format 正常工作", test_format_works)


# ============================================================
# 运行
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print(" Self-RAG 服务单元测试")
    print("=" * 60)

    test_parse_verification()
    test_build_warning()
    test_format_sources()
    test_prompt_format()
    test_verify_with_reflection()

    total = passed + failed
    print("\n" + "=" * 60)
    print(f" 测试结果: {passed}/{total} 通过, {failed}/{total} 失败")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
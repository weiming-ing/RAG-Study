"""
LLM Grader — 使用 DeepSeek API 对 RAG 回答质量进行多维度评分。

评分维度：
  - 正确性 (0-10)：核心事实是否正确，有无编造
  - 完整性 (0-10)：是否覆盖了所有关键点
  - 简洁性 (0-10)：是否直击要害，无冗余

使用方式：
  from grader import LLMGrader
  grader = LLMGrader()
  scores = await grader.grade(query, answer, expected_facts, bad_examples)
"""

import os
import json
import asyncio
import httpx

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
GRADER_MODEL = os.getenv("GRADER_MODEL", "deepseek-chat")

GRADER_PROMPT = """你是一个严谨的 RAG 对话质量评估专家。请根据以下信息对 AI 的回答进行评分。

## 用户问题
{query}

## AI 回答
{answer}

## 期望的关键事实
{expected_facts}

## 已知的错误回答示例（不得出现类似内容）
{bad_examples}

## 评分要求
请从以下三个维度分别打分（0-10 分，整数）：

1. **正确性**：回答中的核心事实是否正确？是否存在编造（幻觉）？如果回答包含了已知错误示例中的内容，正确性不得超过 3 分。
2. **完整性**：是否覆盖了所有期望的关键事实？遗漏了重要信息应扣分。
3. **简洁性**：回答是否直击要害？是否存在冗余、重复、无关内容？

请以 JSON 格式返回评分结果：
```json
{{
  "correctness": <0-10>,
  "completeness": <0-10>,
  "conciseness": <0-10>,
  "reason": "<简短评语，说明扣分原因>"
}}
```

只返回 JSON，不要有其他内容。"""


class LLMGrader:
    """LLM 评分器"""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.base_url = base_url or DEEPSEEK_BASE_URL
        self.model = model or GRADER_MODEL

        if not self.api_key:
            print("[Grader] ⚠️  DEEPSEEK_API_KEY 未设置，LLM 评分将跳过（检索命中率仍可评估）")

    async def grade(
        self,
        query: str,
        answer: str,
        expected_facts: list,
        bad_examples: list,
    ) -> dict:
        """对单条回答进行评分，返回 {correctness, completeness, conciseness, reason}"""
        if not self.api_key:
            return {
                "correctness": -1,
                "completeness": -1,
                "conciseness": -1,
                "reason": "DEEPSEEK_API_KEY 未配置，跳过 LLM 评分",
            }

        facts_str = "\n".join(f"- {f}" for f in expected_facts) if expected_facts else "（无）"
        bad_str = "\n".join(f"- {b}" for b in bad_examples) if bad_examples else "（无）"

        prompt = GRADER_PROMPT.format(
            query=query,
            answer=answer[:3000],
            expected_facts=facts_str,
            bad_examples=bad_str,
        )

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                        "max_tokens": 256,
                    },
                )

                if resp.status_code != 200:
                    print(f"[Grader] API 错误: {resp.status_code} {resp.text[:200]}")
                    return {"correctness": -1, "completeness": -1, "conciseness": -1, "reason": f"API error {resp.status_code}"}

                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()

                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                result = json.loads(content)
                result.setdefault("reason", "")
                return result

        except json.JSONDecodeError as e:
            print(f"[Grader] JSON 解析失败: {e}, content={content[:200]}")
            return {"correctness": -1, "completeness": -1, "conciseness": -1, "reason": f"JSON parse error: {e}"}
        except Exception as e:
            print(f"[Grader] 评分异常: {e}")
            return {"correctness": -1, "completeness": -1, "conciseness": -1, "reason": str(e)}


# 单例
grader = LLMGrader()
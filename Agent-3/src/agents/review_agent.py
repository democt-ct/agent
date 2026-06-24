"""Review Agent -- 回答审查与幻觉检测.

在最终回答返回给用户之前执行,检查:
  1. 数值一致性:回答中的数值是否和 tool_call 结果一致
  2. 制度溯源:提到的制度条款是否在 retrieved_chunks 中存在
  3. 编造检测:是否编造了不存在的制度,数据或审批结果
  4. 置信度标注:低置信回答标记"仅供参考"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ReviewVerdict:
    """审查结论."""

    passed: bool
    issues: list[str] = field(default_factory=list)
    fixed_answer: str | None = None     # 修正后的回答(如需要)
    confidence: float = 1.0             # 审查后的置信度
    warnings: list[str] = field(default_factory=list)


class ReviewAgent:
    """回答审查 Agent -- 规则 + LLM 双重校验.

    规则层做确定性检查(不需要调 LLM),
    遇到边界情况才降级到 LLM 审查.

    Usage:
        # 仅规则(向后兼容)
        ra = ReviewAgent()
        verdict = ra.review(answer, tool_results, retrieved_chunks, raw_query)

        # 规则 + LLM 兜底
        ra = ReviewAgent(client=openai_client, model="Qwen/Qwen3-235B-A22B")
        verdict = ra.review(answer, tool_results, retrieved_chunks, raw_query)
    """

    def __init__(
        self,
        client: Any = None,
        model: str = "deepseek-v4-flash",
    ) -> None:
        self._client = client
        self._model = model

    def review(
        self,
        answer: str,
        tool_results: list[dict] | None = None,
        retrieved_chunks: list[dict] | None = None,
        raw_query: str = "",
    ) -> ReviewVerdict:
        """审查 Agent 的最终回答.

        Args:
            answer: 候选回答文本
            tool_results: 工具调用结果列表 [{"name":"...","result":{...}}]
            retrieved_chunks: RAG 检索到的文档片段
            raw_query: 原始用户问题

        Returns:
            ReviewVerdict 审查结论
        """
        issues: list[str] = []
        warnings: list[str] = []
        tool_results = tool_results or []
        retrieved_chunks = retrieved_chunks or []

        # ── 1. 数值一致性检查 ────────────────────────────────────
        num_issues = self._check_numeric_consistency(answer, tool_results)
        issues.extend(num_issues)

        # ── 2. 空回答检查 ────────────────────────────────────────
        if not answer or len(answer.strip()) < 10:
            issues.append("回答过短或为空,可能未正确生成")
            return ReviewVerdict(passed=False, issues=issues, confidence=0.0)

        # ── 3. 错误透传检查 ──────────────────────────────────────
        for tr in tool_results:
            res = tr.get("result", {})
            if isinstance(res, dict) and "error" in res:
                if res["error"] not in answer:
                    issues.append(f"工具 {tr.get('name')} 返回了错误 '{res['error']}' 但回答中未体现")
                    warnings.append(f"工具 {tr.get('name')} 执行异常: {res['error']}")

        # ── 4. 编造检测(简单规则) ──────────────────────────────
        fabrication_warnings = self._check_fabrication(answer, tool_results, retrieved_chunks)
        warnings.extend(fabrication_warnings)

        # ── 4b. 制度溯源检查 ─────────────────────────────────
        source_issues = self._check_source_citation(answer, retrieved_chunks)
        issues.extend(source_issues)

        # ── 5. 置信度评估(规则层) ─────────────────────────────
        conf = 1.0
        if issues:
            conf -= 0.2 * len(issues)
        if warnings:
            conf -= 0.05 * len(warnings)
        conf = max(0.0, min(1.0, conf))

        # ── 6. LLM 兜底审查 ─────────────────────────────────────
        # 触发条件:有 warning 但未触发硬 issue,或置信度在灰色区间
        if self._client is not None and (
            (len(warnings) > 0 and len(issues) == 0)
            or (0.6 < conf < 0.9 and len(issues) <= 1)
        ):
            try:
                llm_result = self._llm_review(
                    answer=answer,
                    tool_results=tool_results or [],
                    retrieved_chunks=retrieved_chunks or [],
                    raw_query=raw_query,
                )
                if llm_result:
                    if llm_result.get("issues"):
                        issues.extend(llm_result["issues"])
                    if llm_result.get("warnings"):
                        warnings.extend(llm_result["warnings"])
                    if llm_result.get("fixed_answer"):
                        fixed_answer = llm_result["fixed_answer"]
                        answer = fixed_answer
                    llm_conf = llm_result.get("confidence", 1.0)
                    # LLM 置信度优先于规则计算
                    conf = min(conf, llm_conf)
            except Exception as e:
                logger.warning("LLM review failed, using rule-only result: %s", e)

        # ── 7. 置信度评估(合并后) ────────────────────────────
        conf = max(0.0, min(1.0, conf))
        passed = len(issues) == 0

        # 低置信标注
        fixed_answer = answer
        if conf < 0.7 and conf > 0:
            fixed_answer = (
                f"⚠️ *以下回答置信度较低({conf:.0%}),仅供参考*\n\n{answer}"
            )

        return ReviewVerdict(
            passed=passed,
            issues=issues,
            fixed_answer=fixed_answer if not passed or conf < 0.7 else None,
            confidence=conf,
            warnings=warnings,
        )

    # ── 私有方法 ──────────────────────────────────────────────────

    def _check_numeric_consistency(self, answer: str, tool_results: list[dict]) -> list[str]:
        """检查回答中的数值是否和工具返回一致."""
        issues: list[str] = []
        for tr in tool_results:
            result = tr.get("result", {})
            if not isinstance(result, dict):
                continue
            # 检查年假数字
            for key, label in [("annual", "年假"), ("sick", "病假"), ("personal", "事假")]:
                val = result.get(key)
                if val is not None and isinstance(val, (int, float)):
                    # 检查回答中是否出现了不一致的数字
                    # 简单启发:如果回答中出现了 "年假还剩 X" 且 X != val
                    import re
                    pattern = rf"{label}[^\d]*(\d+)\s*天"
                    match = re.search(pattern, answer)
                    if match and int(match.group(1)) != val:
                        issues.append(
                            f"数值不一致: 工具返回 {label}={val}天,但回答中声称{match.group(1)}天"
                        )
        return issues

    def _check_fabrication(
        self, answer: str, tool_results: list[dict], retrieved_chunks: list[dict]
    ) -> list[str]:
        """检测可能编造的内容."""
        warnings: list[str] = []

        # 检查是否引用了不存在的制度条款
        if retrieved_chunks:
            all_sources = {c.get("source", "") for c in retrieved_chunks}
            # 简单检测:如果回答提到了具体的制度条款号但不在来源中
            # 如 "根据 §3.1" 或 "第5.2条"
            import re
            clause_refs = re.findall(r'[§第]\s*[\d.]+', answer)
            # 不做深度检查(需要 LLM 验证),仅记录
            if clause_refs and not all_sources:
                warnings.append("回答引用了制度条款,但无检索来源可验证")

        # 检查是否编造了不存在的员工数据
        for tr in tool_results:
            result = tr.get("result", {})
            if isinstance(result, dict) and "error" in result:
                if "未找到" in str(result["error"]):
                    # 工具返回了"未找到",但回答中是否有数据?
                    name = tr.get("name", "")
                    if "查询" not in answer and "未找到" not in answer:
                        warnings.append(f"工具 {name} 返回'未找到',但回答可能编造了结果")

        return warnings

    def _check_source_citation(self, answer: str, retrieved_chunks: list[dict]) -> list[str]:
        """制度溯源检查:回答中引用的条款是否在检索来源中存在.

        如果回答引用了 §X.Y 或 第X条 但没有对应来源 → 可能是幻觉.
        """
        issues: list[str] = []
        if not retrieved_chunks:
            return issues  # 没有检索来源时不做此检查

        import re
        clause_pattern = re.findall(r'[§第]\s*[\d.]+[条]?', answer)
        if not clause_pattern:
            return issues

        # 合并所有检索内容
        all_text = " ".join(c.get("content", "") for c in retrieved_chunks)
        all_sources = {c.get("source", "") for c in retrieved_chunks}

        for clause in clause_pattern:
            if clause not in all_text:
                issues.append(
                    f"制度溯源失败: 回答引用了 '{clause}' 但在检索到的 {len(retrieved_chunks)} 段内容中未找到"
                )

        # 如果没有任何引用但在讨论制度 → 警告
        if not clause_pattern and any(
            kw in answer for kw in ["制度", "规定", "条例", "政策"]
        ):
            # 宽容处理,仅在有检索来源时才告警
            pass

        return issues


    # ── LLM 审查 ─────────────────────────────────────────────

    def _llm_review(
        self,
        answer: str,
        tool_results: list[dict],
        retrieved_chunks: list[dict],
        raw_query: str,
    ) -> dict[str, Any] | None:
        """用 LLM 对答案做深度验证.

        返回 {passed, issues, warnings, fixed_answer, confidence} 或 None.
        """
        if self._client is None:
            return None

        # 构建上下文
        tools_text = ""
        for tr in tool_results:
            name = tr.get("name", "unknown")
            result = tr.get("result", {})
            tools_text += f"- {name}: {result}\n"

        chunks_text = ""
        for i, c in enumerate(retrieved_chunks):
            chunks_text += (
                f"[{i}] 来源: {c.get('source', '?')} "
                f"相关度: {c.get('score', 0):.2f}\n"
                f"{c.get('content', '')[:500]}\n\n"
            )

        prompt = f"""你是企业制度回答的审查专家.检查以下 AI 回答是否存在幻觉,事实错误或逻辑矛盾.

## 用户问题
{raw_query}

## AI 回答
{answer}

## 工具执行结果
{tools_text if tools_text else "(无可用的工具结果)"}

## 知识库检索片段
{chunks_text if chunks_text else "(无检索结果)"}

## 审查规则
1. 回答中的数值,日期,人名必须与工具结果一致
2. 引用的制度条款必须在知识库片段中存在
3. 不能编造不存在的审批流程,部门名称,联系方式
4. 如果工具返回了 error,回答不能假装成功

## 输出格式
严格 JSON,不要多余文字:
{{"passed": true/false, "issues": ["问题1","问题2"], "warnings": ["注意点1"], "fixed_answer": "修正后回答(如需要,否则 null)", "confidence": 0.0-1.0}}"""

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": "你是企业制度回答的审查专家.按 JSON 格式输出审查结果."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        import json
        try:
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except (json.JSONDecodeError, AttributeError):
            logger.warning("LLM review returned invalid JSON: %s", content[:100])
            return None


# ── 便捷工厂 ──────────────────────────────────────────────────────

_review_agent_instance: ReviewAgent | None = None


def get_review_agent() -> ReviewAgent:
    global _review_agent_instance
    if _review_agent_instance is None:
        _review_agent_instance = ReviewAgent()
    return _review_agent_instance

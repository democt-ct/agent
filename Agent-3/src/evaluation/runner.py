"""EvalRunner -- orchestrates test case execution and computes metrics.

Design:
- Stateless: takes orchestrator + agent_instances in constructor, test cases in run().
- Each case runs independently; one failure does not abort the run.
- Metrics computed from accumulated EvalResult list.
"""

from __future__ import annotations

import time
from typing import Any

from src.agents.base_agent import BaseAgent
from src.agents.orchestrator import Orchestrator
from src.config import config
from src.evaluation.models import EvalReport, EvalResult, TestCase
from src.protocol.types import AgentRequest


class EvalRunner:
    """Run a test suite through the multi-agent system and produce a report.

    Usage:
        runner = EvalRunner(orchestrator, agent_instances)
        report = runner.run(test_cases)                     # full: route + agent
        report = runner.run(test_cases, retrieval_only=True) # fast: route + retrieval
    """

    def __init__(
        self,
        orchestrator: Orchestrator,
        agent_instances: dict[str, BaseAgent],
    ) -> None:
        self._orchestrator = orchestrator
        self._agents = agent_instances

    def run(self, cases: list[TestCase], retrieval_only: bool = False, use_llm: bool = True, rewrite: bool = True) -> EvalReport:
        """Execute all test cases and return an aggregate report.

        Args:
            cases: List of TestCase objects loaded by TestLoader.

        Returns:
            EvalReport with per-result details and summary statistics.
        """
        results: list[EvalResult] = []
        errors: list[str] = []

        for case in cases:
            try:
                result = self._run_one(case, retrieval_only=retrieval_only, use_llm=use_llm, rewrite=rewrite)
                results.append(result)
            except Exception as e:
                errors.append(f"{case.id}: {e}")
                # Synthesise a failure result so the count stays accurate
                results.append(EvalResult(
                    case_id=case.id,
                    query=case.query,
                    category=case.category,
                    expected_agent=case.expected_agent,
                    actual_agent="error",
                    routing_correct=False,
                    routing_method="error",
                    expected_tools=case.expected_tools,
                    actual_tools=[],
                    tools_correct=False,
                    error=str(e),
                ))

        return self._build_report(results, errors)

    # ── Per-case execution ───────────────────────────────────────

    def _run_one(self, case: TestCase, retrieval_only: bool = False, use_llm: bool = True, rewrite: bool = True) -> EvalResult:
        """Route + execute one test case, compare against expectations.

        retrieval_only=True: skip Agent.run(), evaluate routing + retrieval only.
        use_llm=False: skip LLM routing fallback, keyword-only.
        rewrite=False: skip query rewriting, use original query for retrieval.
        """
        t0 = time.time()

        # 1. Route
        route = self._orchestrator.route(case.query, use_llm=use_llm)
        primary = route.get("primary", "fallback")
        secondary = route.get("secondary")

        # 2. Routing correctness
        routing_correct = primary == case.expected_agent
        if case.expected_secondary and secondary:
            routing_correct = (
                primary == case.expected_agent
                and secondary == case.expected_secondary
            )

        agent = self._agents.get(primary)
        answer = ""
        actual_tools: list[str] = []
        tokens_used = 0
        retrieved_sources: list[str] = []
        retrieval_correct = True

        if retrieval_only:
            # ── 快速模式:只 RAG 检索,不跑 Agent ──────────
            tools_correct = True  # retrieval_only 不评估工具
            if agent is not None and primary != "fallback":
                try:
                    chunks = agent.kb.query(case.query, top_k=10, rewrite=rewrite)
                    retrieved_sources = list(set(
                        c.get("source", "") for c in chunks
                    ))
                    if case.expected_sources:
                        retrieval_correct = all(
                            src in retrieved_sources for src in case.expected_sources
                        )
                except Exception:
                    pass
        else:
            # ── 全量模式:跑完整 Agent ────────────────────
            if agent is not None and primary != "fallback":
                req = AgentRequest(
                    query=case.query,
                    agent_name=primary,
                    conversation_history=[],
                    max_tool_calls=config.max_tool_calls_low,
                    temperature=config.llm_temperature,
                )
                try:
                    resp = agent.run(req)
                    answer = resp.answer
                    actual_tools = [tc.get("name", "") for tc in resp.tool_calls]
                    tokens_used = resp.tokens_used
                except Exception as exc:
                    answer = f"[agent error: {exc}]"

            # Tool accuracy
            tools_correct = self._eval_tools(case.expected_tools, actual_tools)

            # Retrieval accuracy
            if agent is not None and primary != "fallback" and resp is not None:
                try:
                    retrieved_sources = list(set(
                        c.get("source", "") for c in resp.retrieved_chunks
                    ))
                except Exception:
                    pass
                if case.expected_sources:
                    retrieval_correct = all(
                        src in retrieved_sources for src in case.expected_sources
                    )

        elapsed_ms = int((time.time() - t0) * 1000)

        return EvalResult(
            case_id=case.id,
            query=case.query,
            category=case.category,
            expected_agent=case.expected_agent,
            actual_agent=primary,
            routing_correct=routing_correct,
            routing_method=route.get("method", ""),
            routing_confidence=route.get("confidence", 0.0),
            expected_tools=case.expected_tools,
            actual_tools=actual_tools,
            tools_correct=tools_correct,
            expected_sources=case.expected_sources,
            retrieved_sources=retrieved_sources,
            retrieval_correct=retrieval_correct,
            answer=answer[:500],
            processing_time_ms=elapsed_ms,
            tokens_used=tokens_used,
        )

    # ── Scoring helpers ───────────────────────────────────────────

    @staticmethod
    def _eval_tools(expected: list[str], actual: list[str]) -> bool:
        """True if all expected tool names appear in the actual tool calls."""
        if not expected:
            return True  # no tool expectation → always correct
        actual_set = set(actual)
        return all(t in actual_set for t in expected)

    # ── Report builder ────────────────────────────────────────────

    def _build_report(
        self,
        results: list[EvalResult],
        errors: list[str],
    ) -> EvalReport:
        total = len(results)
        passed = sum(1 for r in results if r.routing_correct and r.tools_correct)

        routing_correct_count = sum(1 for r in results if r.routing_correct)
        routing_accuracy = routing_correct_count / max(total, 1)

        # Tool accuracy: only count cases that have expected_tools
        tool_cases = [r for r in results if r.expected_tools]
        tool_correct_count = sum(1 for r in tool_cases if r.tools_correct)
        tool_accuracy = tool_correct_count / max(len(tool_cases), 1)

        # Retrieval accuracy: only count cases that have expected_sources
        retrieval_cases = [r for r in results if r.expected_sources]
        retrieval_correct_count = sum(1 for r in retrieval_cases if r.retrieval_correct)
        retrieval_accuracy = retrieval_correct_count / max(len(retrieval_cases), 1)

        avg_time = sum(r.processing_time_ms for r in results) / max(total, 1)
        avg_tokens = sum(r.tokens_used for r in results) / max(total, 1)

        # Per-category breakdown
        by_category: dict[str, dict[str, Any]] = {}
        for r in results:
            cat = r.category or "uncategorised"
            if cat not in by_category:
                by_category[cat] = {"total": 0, "routing_ok": 0, "tools_ok": 0, "tool_total": 0, "retrieval_ok": 0, "retrieval_total": 0}
            stats = by_category[cat]
            stats["total"] += 1
            if r.routing_correct:
                stats["routing_ok"] += 1
            if r.expected_tools:
                stats["tool_total"] += 1
                if r.tools_correct:
                    stats["tools_ok"] += 1
            if r.expected_sources:
                stats["retrieval_total"] += 1
                if r.retrieval_correct:
                    stats["retrieval_ok"] += 1

        for cat, stats in by_category.items():
            stats["routing_accuracy"] = stats["routing_ok"] / max(stats["total"], 1)
            stats["tool_accuracy"] = stats["tools_ok"] / max(stats["tool_total"], 1)
            stats["retrieval_accuracy"] = stats["retrieval_ok"] / max(stats["retrieval_total"], 1)

        return EvalReport(
            total=total,
            passed=passed,
            routing_accuracy=routing_accuracy,
            tool_accuracy=tool_accuracy,
            retrieval_accuracy=retrieval_accuracy,
            avg_time_ms=avg_time,
            avg_tokens=avg_tokens,
            by_category=by_category,
            results=results,
            errors=errors,
        )

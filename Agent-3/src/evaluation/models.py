"""Pydantic models for the evaluation framework.

TestCase  -- input: query + expected outcomes.
EvalResult -- output: actual outcomes vs expected.
EvalReport -- aggregate: per-category accuracy + overall summary.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TestCase(BaseModel):
    """A single evaluation test case.

    Fields:
        id:            Unique identifier (e.g. "eval_001").
        query:         The user's natural-language question.
        expected_agent: Which agent should handle this query  (hr_agent | it_agent | legal_agent | fallback).
        expected_secondary: Optional secondary agent for cross-domain queries.
        expected_tools: Optional list of tool names the agent should invoke.
        golden_answer:  Optional reference answer (for manual comparison, not scored automatically).
        category:       Domain category (hr | it | legal | cross | fallback).
    """

    id: str
    query: str
    expected_agent: str
    expected_secondary: str | None = None
    expected_tools: list[str] = Field(default_factory=list)
    expected_sources: list[str] = Field(default_factory=list)
    golden_answer: str | None = None
    category: str = ""


class EvalResult(BaseModel):
    """Result of running one TestCase through the system."""

    case_id: str
    query: str
    category: str

    # Routing
    expected_agent: str
    actual_agent: str
    routing_correct: bool
    routing_method: str = ""
    routing_confidence: float = 0.0

    # Tool calls
    expected_tools: list[str] = Field(default_factory=list)
    actual_tools: list[str] = Field(default_factory=list)
    tools_correct: bool = True  # True when no tools expected, or all expected tools were called

    # Retrieval
    expected_sources: list[str] = Field(default_factory=list)
    retrieved_sources: list[str] = Field(default_factory=list)
    retrieval_correct: bool = False

    # Metadata
    answer: str = ""
    processing_time_ms: int = 0
    tokens_used: int = 0
    error: str | None = None


class EvalReport(BaseModel):
    """Aggregate evaluation report."""

    total: int = 0
    passed: int = 0
    routing_accuracy: float = 0.0
    tool_accuracy: float = 0.0
    retrieval_accuracy: float = 0.0
    avg_time_ms: float = 0.0
    avg_tokens: float = 0.0
    by_category: dict[str, dict[str, Any]] = Field(default_factory=dict)
    results: list[EvalResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def print_summary(self) -> str:
        """Return a formatted summary string suitable for terminal output."""
        lines: list[str] = []
        w = 62
        lines.append("=" * w)
        lines.append("  📊  Evaluation Report".ljust(w))
        lines.append("=" * w)
        lines.append(f"  Total cases:       {self.total}")
        lines.append(f"  Passed:            {self.passed}  ({self.passed / max(self.total, 1):.1%})")
        lines.append(f"  Routing accuracy:    {self.routing_accuracy:.1%}")
        lines.append(f"  Tool accuracy:       {self.tool_accuracy:.1%}")
        lines.append(f"  Retrieval accuracy:  {self.retrieval_accuracy:.1%}")
        lines.append(f"  Avg time:          {self.avg_time_ms:.0f} ms")
        lines.append(f"  Avg tokens:        {self.avg_tokens:.0f}")
        lines.append("-" * w)

        if self.by_category:
            lines.append(f"  {'Category':<14} {'Cases':>6} {'Routing':>10} {'Tools':>10}")
            lines.append("  " + "-" * 42)
            for cat, stats in sorted(self.by_category.items()):
                n = stats.get("total", 0)
                ra = stats.get("routing_accuracy", 0.0)
                tool_total = stats.get("tool_total", 0)
                if tool_total > 0:
                    ta_str = f"{stats.get('tool_accuracy', 0.0):.1%}"
                else:
                    ta_str = "N/A"
                lines.append(f"  {cat:<14} {n:>6} {ra:>9.1%} {ta_str:>10}")
            lines.append("-" * w)

        if self.errors:
            lines.append(f"  ⚠️  Errors: {len(self.errors)}")
            for err in self.errors[:5]:
                lines.append(f"     - {err[:80]}")
            if len(self.errors) > 5:
                lines.append(f"     ... and {len(self.errors) - 5} more")

        lines.append("=" * w)
        return "\n".join(lines)

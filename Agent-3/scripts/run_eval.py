#!/usr/bin/env python
"""Evaluation CLI — run test sets against the multi-agent system.

Usage:
    python scripts/run_eval.py                          # default test set
    python scripts/run_eval.py data/eval/custom.jsonl   # custom test set
    python scripts/run_eval.py --routing-only            # skip agent execution (fast)

Environment:
    TRACE_ENABLED=true   → also record traces during eval
"""

from __future__ import annotations

import logging
import os
import sys
import time

# Ensure project root is on the import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_eval")


def _init_system() -> dict:
    """Lightweight init: LLM client + Orchestrator + Agent instances (routing only)."""
    from src.llm_client import get_client
    client = get_client()

    from src.agents.orchestrator import Orchestrator
    orchestrator = Orchestrator(client)
    logger.info("Orchestrator ready")

    # Agent instances (needed for tool-accuracy eval; skip KB loading for speed)
    from src.agents.base_agent import BaseAgent
    from src.rag.embedder import Embedder
    from src.rag.knowledge_base import KnowledgeBase
    from src.tools.hr_tools import HR_TOOLS
    from src.tools.it_tools import IT_TOOLS
    from src.tools.legal_tools import LEGAL_TOOLS
    from src.tools.finance_tools import FINANCE_TOOLS
    from src.config import config as cfg

    embedder = Embedder()
    tool_map = {
        "HR_TOOLS": HR_TOOLS,
        "IT_TOOLS": IT_TOOLS,
        "LEGAL_TOOLS": LEGAL_TOOLS,
        "FINANCE_TOOLS": FINANCE_TOOLS,
    }
    agents: dict = {}

    for kb_spec in cfg.kb_registry:
        kb = KnowledgeBase(kb_spec["name"], kb_spec["dir"], embedder=embedder)
        if kb.is_index_stale():
            kb.build_index()
        else:
            kb.load_index()
        tools_list = tool_map[kb_spec["tools_import"]]
        agent = BaseAgent(
            name=kb_spec["agent_name"],
            tools=tools_list,
            kb=kb,
            client=client,
            model=cfg.llm_model,
        )
        agents[kb_spec["agent_key"]] = agent
        logger.info("Agent ready: %s", kb_spec["agent_key"])

    return {"orchestrator": orchestrator, "agents": agents}


def main() -> None:
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run evaluation against the multi-agent system")
    parser.add_argument(
        "test_set",
        nargs="?",
        default="data/eval/test_set.jsonl",
        help="Path to test set (JSONL or JSON). Default: data/eval/test_set.jsonl",
    )
    parser.add_argument(
        "--routing-only",
        action="store_true",
        help="Only evaluate routing accuracy (skip agent execution, much faster)",
    )
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Evaluate routing + RAG retrieval accuracy, skip LLM agent execution (fast)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write full JSON report. If not set, prints summary only.",
    )
    args = parser.parse_args()

    # ── Load test cases ─────────────────────────────────────────
    from src.evaluation.loader import TestLoader

    loader = TestLoader(args.test_set)
    cases = loader.load()
    if not cases:
        print("❌ No test cases loaded.")
        sys.exit(1)
    print(f"📋 Loaded {len(cases)} test cases from {args.test_set}")

    # ── Init system ─────────────────────────────────────────────
    if args.routing_only:
        # Routing only: only need orchestrator, no agents / KBs
        from src.llm_client import get_client
        from src.agents.orchestrator import Orchestrator

        client = get_client()
        orchestrator = Orchestrator(client)
        agents: dict = {}

        # Run routing eval directly
        from src.evaluation.models import EvalReport, EvalResult

        results = []
        for case in cases:
            t0 = time.time()
            route = orchestrator.route(case.query)
            elapsed_ms = int((time.time() - t0) * 1000)
            primary = route.get("primary", "fallback")
            routing_correct = primary == case.expected_agent
            results.append(EvalResult(
                case_id=case.id,
                query=case.query,
                category=case.category,
                expected_agent=case.expected_agent,
                actual_agent=primary,
                routing_correct=routing_correct,
                routing_method=route.get("method", ""),
                routing_confidence=route.get("confidence", 0.0),
                expected_tools=case.expected_tools,
                actual_tools=[],
                tools_correct=True,  # not evaluated
                processing_time_ms=elapsed_ms,
            ))

        from src.evaluation.runner import EvalRunner
        report = EvalRunner._build_report(EvalRunner.__new__(EvalRunner), results, [])
    elif args.retrieval_only:
        # Retrieval only: routing + RAG retrieval, skip LLM agent execution
        print("🚀 Initialising agents (loading KBs, no LLM calls)...")
        system = _init_system()

        from src.evaluation.runner import EvalRunner

        runner = EvalRunner(system["orchestrator"], system["agents"])
        print("🏃 Running retrieval evaluation...")
        report = runner.run(cases, retrieval_only=True)

        for agent in system["agents"].values():
            try:
                agent.kb.stop_watch()
            except Exception:
                pass
    else:
        # Full eval: routing + agent execution
        print("🚀 Initialising agents (this may take a moment)...")
        system = _init_system()

        from src.evaluation.runner import EvalRunner

        runner = EvalRunner(system["orchestrator"], system["agents"])
        print("🏃 Running evaluation...")
        report = runner.run(cases)

        # Clean up file watchers
        for agent in system["agents"].values():
            try:
                agent.kb.stop_watch()
            except Exception:
                pass

    # ── Output ───────────────────────────────────────────────────
    print()
    print(report.print_summary())

    if args.output:
        import json
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
        print(f"\n📄 Full report written to {args.output}")

    # Exit code: 0 if all passed, 1 otherwise
    if report.passed < report.total:
        sys.exit(1)


if __name__ == "__main__":
    main()

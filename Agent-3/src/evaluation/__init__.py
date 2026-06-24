"""Evaluation module -- automated accuracy testing for the multi-agent system.

Usage:
    from src.evaluation import EvalRunner, TestLoader

    loader = TestLoader("data/eval/test_set.jsonl")
    runner = EvalRunner(orchestrator, agent_instances)
    report = runner.run(loader.load())
    report.print_summary()
"""

from src.evaluation.models import EvalReport, EvalResult, TestCase
from src.evaluation.loader import TestLoader
from src.evaluation.runner import EvalRunner

__all__ = ["EvalRunner", "TestLoader", "TestCase", "EvalResult", "EvalReport"]

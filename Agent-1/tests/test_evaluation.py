"""
Agent 回答质量评估集 —— 完整性测试。

用例数据本身的定义已迁移到 ``app/config/evaluation_cases.py``（生产可发布的
单一数据源，被 HTTP 接口、命令行运行器、前端控制台共享）。本文件保留：

  1. ``EVALUATION_CASES`` 的向后兼容 re-export（``scripts/run_evaluation.py``
     历史上从 ``tests.test_evaluation`` 导入，保留以避免破坏既有调用方）。
  2. 用例数据完整性测试（字段齐全、权重合法、患者编号存在、可 JSON 导出）。

用法:
  python -m pytest tests/test_evaluation.py -v
"""

import json
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.evaluation_cases import EVALUATION_CASES  # noqa: E402,F401


class TestEvaluationSet:
    """Verify the evaluation set is well-formed."""

    def test_all_cases_have_ids(self):
        for case in EVALUATION_CASES:
            assert case.get("id"), f"Missing id in case: {case}"

    def test_all_cases_have_questions(self):
        for case in EVALUATION_CASES:
            assert case.get("question"), f"Missing question in {case.get('id')}"

    def test_all_cases_have_expected_intents(self):
        for case in EVALUATION_CASES:
            assert case.get("expected_intents"), f"Missing expected_intents in {case.get('id')}"

    def test_all_cases_have_keywords(self):
        for case in EVALUATION_CASES:
            assert "expected_keywords" in case, f"Missing expected_keywords in {case.get('id')}"
            assert "forbidden_keywords" in case, f"Missing forbidden_keywords in {case.get('id')}"

    def test_all_cases_have_scoring(self):
        """Every case must carry a scoring block (single source of truth for the UI)."""
        for case in EVALUATION_CASES:
            sc = case.get("scoring")
            assert sc is not None, f"Missing scoring in {case.get('id')}"
            for key in ("intent_weight", "keyword_weight", "safety_weight"):
                assert key in sc, f"Missing {key} in scoring of {case.get('id')}"
            total = sc["intent_weight"] + sc["keyword_weight"] + sc["safety_weight"]
            assert abs(total - 1.0) < 1e-6, (
                f"Scoring weights in {case.get('id')} sum to {total}, expected 1.0"
            )

    def test_evaluation_set_count(self):
        """Verify we have a meaningful evaluation set size."""
        assert len(EVALUATION_CASES) >= 15, f"Only {len(EVALUATION_CASES)} cases, need at least 15"

    def test_evaluation_set_diversity(self):
        """Verify coverage of different scenarios."""
        intents_covered = set()
        for case in EVALUATION_CASES:
            for intent in case["expected_intents"]:
                intents_covered.add(intent)
        assert "general_medical_question" in intents_covered
        assert "visit_records_query" in intents_covered or "medical_records_query" in intents_covered

    def test_patient_codes_exist_in_seed_data(self):
        """Verify referenced patients exist in seed data."""
        from scripts.seed_patients import PATIENTS
        seed_codes = {p["patient_code"] for p in PATIENTS}
        referenced = {c["patient_code"] for c in EVALUATION_CASES if c.get("patient_code")}
        missing = referenced - seed_codes
        assert not missing, f"Patient codes not in seed data: {missing}"

    def test_evaluation_json_export(self, tmp_path):
        """Verify evaluation set can be exported as JSON for external tools."""
        export = tmp_path / "evaluation_set.json"
        with open(export, "w", encoding="utf-8") as f:
            json.dump(EVALUATION_CASES, f, ensure_ascii=False, indent=2)
        assert export.exists()
        with open(export, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert len(loaded) == len(EVALUATION_CASES)

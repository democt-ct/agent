"""质量评估用例 HTTP 接口。

本路由将 ``app/config/evaluation_cases.py:EVALUATION_CASES``（评估用例的单一
数据源）通过 HTTP 暴露给质量评估控制台 ``app/static/evaluate.html``，
避免前端硬编码副本。

接口:
  - GET /api/v1/evaluation/cases   返回完整评估用例集
"""

from typing import Any, Dict, List

from fastapi import APIRouter

from app.config.evaluation_cases import EVALUATION_CASES

router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])


@router.get(
    "/cases",
    summary="获取质量评估用例集",
    description=(
        "返回完整的质量评估用例集。该接口是评估用例的【单一数据源】—— "
        "质量评估控制台、命令行运行器均从此处（或其底层 "
        "`app/config/evaluation_cases.py:EVALUATION_CASES`）获取用例，"
        "禁止在前端硬编码副本。"
    ),
)
def list_evaluation_cases() -> Dict[str, Any]:
    """返回评估用例集 + 聚合统计信息。"""
    categories: Dict[str, int] = {}
    for case in EVALUATION_CASES:
        prefix = case["id"].split("-")[0]
        categories[prefix] = categories.get(prefix, 0) + 1

    return {
        "count": len(EVALUATION_CASES),
        "categories": categories,
        "cases": _serialize_cases(EVALUATION_CASES),
    }


def _serialize_cases(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Serialize cases to JSON-safe dicts (patient_code may be None)."""
    return [
        {
            "id": c["id"],
            "patient_code": c.get("patient_code"),
            "question": c["question"],
            "expected_intents": c.get("expected_intents", []),
            "expected_keywords": c.get("expected_keywords", []),
            "forbidden_keywords": c.get("forbidden_keywords", []),
            "evaluation_hint": c.get("evaluation_hint", ""),
            "scoring": c.get(
                "scoring",
                {"intent_weight": 0.3, "keyword_weight": 0.4, "safety_weight": 0.3, "safety_notes": ""},
            ),
        }
        for c in cases
    ]

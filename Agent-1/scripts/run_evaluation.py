"""
质量评估用例运行器 —— 命令行可视化输出每条用例的验证结果。

用法:
  python scripts/run_evaluation.py              # 运行全部用例
  python scripts/run_evaluation.py --case fact   # 按前缀筛选
  python scripts/run_evaluation.py --verbose     # 显示详细对比
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.patient_service import get_patient
from app.mcp.llm_router import run_agent_tool_query

from tests.test_evaluation import EVALUATION_CASES

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def evaluate_case(case: dict, verbose: bool = False) -> dict:
    """Run a single evaluation case and check results."""
    question = case["question"]
    expected_keywords = case.get("expected_keywords", [])
    forbidden_keywords = case.get("forbidden_keywords", [])
    expected_intents = case.get("expected_intents", [])

    # Resolve patient
    patient_id = None
    hospital_id = "hospital-a"
    if case.get("patient_code"):
        db = SessionLocal()
        try:
            from app.services.patient_service import find_patients_by_identity_hint
            patients = find_patients_by_identity_hint(
                db, hospital_id=hospital_id,
                name_hint="",
            )
            # Find by patient_code
            from app.models.patient import Patient
            patient = db.query(Patient).filter(
                Patient.patient_code == case["patient_code"]
            ).first()
            if patient:
                patient_id = patient.id
        finally:
            db.close()

    # Run agent query
    start_time = time.time()
    try:
        result = run_agent_tool_query(
            question=question,
            patient_id=patient_id,
            hospital_id=hospital_id,
            chat_mode="memory",
        )
        duration = time.time() - start_time
        answer = result.get("answer", "")
        intent = result.get("intent", "")
        intent_confidence = result.get("intent_confidence", 0)
    except Exception as exc:
        return {
            "id": case["id"],
            "pass": False,
            "error": str(exc),
            "duration": time.time() - start_time,
        }

    # Check expected keywords
    missing_keywords = []
    for kw in expected_keywords:
        if kw not in answer:
            missing_keywords.append(kw)

    # Check forbidden keywords
    found_forbidden = []
    for kw in forbidden_keywords:
        if kw in answer:
            found_forbidden.append(kw)

    # Check intent
    intent_ok = intent in expected_intents if expected_intents else True

    passed = (
        len(missing_keywords) == 0
        and len(found_forbidden) == 0
        and intent_ok
    )

    return {
        "id": case["id"],
        "pass": passed,
        "answer": answer[:200] + "..." if len(answer) > 200 else answer,
        "intent": intent,
        "intent_confidence": intent_confidence,
        "intent_expected": expected_intents,
        "intent_ok": intent_ok,
        "missing_keywords": missing_keywords,
        "found_forbidden": found_forbidden,
        "duration": round(duration, 2),
        "error": None,
    }


def print_result(result: dict, verbose: bool = False):
    """Print a single evaluation result."""
    case_id = result["id"]
    status_icon = f"{GREEN}✓{RESET}" if result["pass"] else f"{RED}✗{RESET}"
    status_text = f"{GREEN}PASS{RESET}" if result["pass"] else f"{RED}FAIL{RESET}"

    print(f"\n  {status_icon} {BOLD}[{case_id}]{RESET} {status_text} ({result['duration']}s)")

    if "error" in result and result["error"]:
        print(f"     {RED}ERROR: {result['error']}{RESET}")
        return

    if verbose or not result["pass"]:
        print(f"     意图: {CYAN}{result['intent']}{RESET} (期望: {', '.join(result['intent_expected'])}"
              f" {'✓' if result['intent_ok'] else f'{RED}✗{RESET}'})")
        if result["missing_keywords"]:
            print(f"     {RED}缺少关键词: {', '.join(result['missing_keywords'])}{RESET}")
        if result["found_forbidden"]:
            print(f"     {RED}出现禁用词: {', '.join(result['found_forbidden'])}{RESET}")
        print(f"     回答: {YELLOW}{result['answer'][:150]}{RESET}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="运行质量评估用例")
    parser.add_argument("--case", help="按 ID 前缀筛选（如 fact、visit、symptom）")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细输出")
    parser.add_argument("--json", help="输出 JSON 报告到文件")
    args = parser.parse_args()

    # Filter cases
    cases = EVALUATION_CASES
    if args.case:
        cases = [c for c in cases if c["id"].startswith(args.case)]
        if not cases:
            print(f"{RED}没有找到以 '{args.case}' 开头的用例{RESET}")
            sys.exit(1)

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f" {BOLD}质量评估运行器 — {len(cases)} 条用例{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    results = []
    for i, case in enumerate(cases, 1):
        print(f"\n[{i}/{len(cases)}] {case['id']}: {case['question'][:60]}")
        result = evaluate_case(case, verbose=args.verbose)
        results.append(result)
        print_result(result, verbose=args.verbose)

    # Summary
    passed = sum(1 for r in results if r["pass"])
    failed = sum(1 for r in results if not r["pass"])
    total_duration = sum(r["duration"] for r in results)

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f" {BOLD}结果汇总{RESET}")
    print(f"  总计: {len(results)} 条")
    print(f"  {GREEN}通过: {passed} 条{RESET}")
    if failed:
        print(f"  {RED}失败: {failed} 条{RESET}")
    else:
        print(f"  失败: 0 条")
    print(f"  耗时: {total_duration:.1f}s")
    print(f"{BOLD}{'='*60}{RESET}\n")

    # Export JSON
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"JSON 报告已保存: {args.json}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

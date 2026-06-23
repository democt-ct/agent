import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx


ROOT_DIR = Path(__file__).resolve().parents[1]
FASTAPI_DIR = ROOT_DIR / "fastapi"
if str(FASTAPI_DIR) not in sys.path:
    sys.path.insert(0, str(FASTAPI_DIR))

import core  # noqa: E402


def pretty(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def summarize_curated_groups(candidate_groups: Dict[str, Any]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for group_name in core.CURATED_GROUP_NAMES:
        items = candidate_groups.get(group_name, []) if isinstance(candidate_groups, dict) else []
        result[group_name] = len(items) if isinstance(items, list) else 0
    return result


def preview_curated_groups(candidate_groups: Dict[str, Any], limit: int = 3) -> Dict[str, List[str]]:
    preview: Dict[str, List[str]] = {}
    for group_name in core.CURATED_GROUP_NAMES:
        items = candidate_groups.get(group_name, []) if isinstance(candidate_groups, dict) else []
        if not isinstance(items, list) or not items:
            continue
        preview[group_name] = [str(item.get("name") or "").strip() for item in items[:limit] if str(item.get("name") or "").strip()]
    return preview


async def run_pipeline(args: argparse.Namespace) -> None:
    request_context = {
        "destination": args.destination,
        "trip_days": args.trip_days,
        "budget_min": args.budget_min,
        "budget_max": args.budget_max,
        "interests": [item.strip() for item in args.interests.split(",") if item.strip()],
        "preferred_pace": args.preferred_pace,
        "distance_tolerance": args.distance_tolerance,
        "location_scope": args.location_scope,
        "user_original_text": args.message,
        "raw_input": args.message,
    }

    print("\n=== Request Context ===")
    print(
        pretty(
            {
                "destination": request_context["destination"],
                "trip_days": request_context["trip_days"],
                "interests": request_context["interests"],
                "preferred_pace": request_context["preferred_pace"],
            }
        )
    )

    curated = await core.build_llm_curated_city_candidates(request_context)
    candidate_groups = curated.get("candidate_groups") if isinstance(curated.get("candidate_groups"), dict) else {}
    curated_summary = {
        "destination": curated.get("destination"),
        "source": curated.get("source"),
        "warnings": curated.get("warnings") or [],
        "parse_success": curated.get("parse_success"),
        "raw_output_length": curated.get("raw_output_length"),
        "extracted_task_count": curated.get("extracted_task_count"),
        "group_counts": summarize_curated_groups(candidate_groups),
    }

    print("\n=== LLM Curator Summary ===")
    print(pretty(curated_summary))
    print("\n=== LLM Curator Preview ===")
    print(pretty(preview_curated_groups(candidate_groups)))

    if args.show_curated or args.verbose:
        print("\n=== LLM Curator candidate_groups ===")
        print(pretty(candidate_groups))

    tasks = core.build_curated_grounding_tasks(curated)
    print("\n=== Extracted Grounding Tasks ===")
    print(f"task_count={len(tasks)}")
    print(pretty(tasks[: args.task_preview]))

    grounded_results: List[Dict[str, Any]] = []
    grounded_candidates: List[Dict[str, Any]] = []
    if tasks:
        timeout = httpx.Timeout(core.WEB_FETCH_TIMEOUT_SECONDS, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for index, task in enumerate(tasks[: args.task_limit], start=1):
                result = await core.search_amap_poi(client, task)
                grounded_results.append(result)
                grounded_candidates.extend(result.get("data") or [])
                if args.verbose:
                    print(f"\n=== AMap Result {index}/{min(len(tasks), args.task_limit)} ===")
                    print(
                        pretty(
                            {
                                "query": {
                                    "city": task.get("city"),
                                    "keyword": task.get("keyword"),
                                    "groundingName": task.get("groundingName"),
                                    "category": task.get("category"),
                                    "source": task.get("source"),
                                },
                                "resultCount": len(result.get("data") or []),
                                "warnings": result.get("warnings") or [],
                                "preview": [
                                    {
                                        "name": item.get("name"),
                                        "category": item.get("category"),
                                        "plannerCategory": item.get("plannerCategory"),
                                        "groundingConfidence": item.get("groundingConfidence"),
                                        "eligible_for_main_itinerary": item.get("eligible_for_main_itinerary"),
                                        "eligible_reason": item.get("eligible_reason"),
                                    }
                                    for item in (result.get("data") or [])[: args.poi_preview]
                                ],
                            }
                        )
                    )

    print("\n=== Grounding Summary ===")
    print(
        pretty(
            {
                "grounding_task_count": len(tasks),
                "grounding_success_candidate_count": len(grounded_candidates),
                "with_location_count": len([item for item in grounded_candidates if item.get("location")]),
                "eligible_count": len([item for item in grounded_candidates if item.get("eligible_for_main_itinerary")]),
                "eligible_preview": [
                    {
                        "name": item.get("name"),
                        "category": item.get("category"),
                        "groundingConfidence": item.get("groundingConfidence"),
                        "eligible_reason": item.get("eligible_reason"),
                    }
                    for item in grounded_candidates
                    if item.get("eligible_for_main_itinerary")
                ][:8],
            }
        )
    )

    if args.full:
        query_plan = await core.build_candidate_query_plan(request_context)
        candidate_pool = await core.build_amap_candidate_pool(request_context, query_plan=query_plan, web_context=None)
        planner_output = core.build_planner_output(request_context, candidate_pool, query_plan=query_plan, selection_hints={})
        print("\n=== Full Pipeline Summary ===")
        print(
            pretty(
                {
                    "candidate_pool_count": len(candidate_pool.get("candidates") or []),
                    "candidate_pool_warnings": candidate_pool.get("warnings") or [],
                    "eligible_count": len(
                        [item for item in (candidate_pool.get("candidates") or []) if item.get("eligible_for_main_itinerary")]
                    ),
                    "day_item_counts": [
                        len(day.get("items") or [])
                        for day in planner_output.get("itinerary", {}).get("days", [])
                    ],
                    "day_names": [
                        {
                            "day": day.get("day"),
                            "theme": day.get("theme"),
                            "items": [item.get("name") for item in (day.get("items") or [])],
                        }
                        for day in planner_output.get("itinerary", {}).get("days", [])
                    ],
                    "planner_warnings": planner_output.get("warnings") or [],
                    "resolved_places_count": len(planner_output.get("resolvedPlaces") or []),
                }
            )
        )
        if args.show_days or args.verbose:
            print("\n=== Planner Days ===")
            print(pretty(planner_output.get("itinerary", {}).get("days", [])))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test LLM curator output and AMap POI grounding pipeline.")
    parser.add_argument("--destination", default="绵阳")
    parser.add_argument("--trip-days", type=int, default=2)
    parser.add_argument("--message", default="我想去绵阳玩两天，想看城市代表景点，也想逛逛和吃点本地特色。")
    parser.add_argument("--interests", default="城市漫游,本地美食,代表景点")
    parser.add_argument("--preferred-pace", default="balanced")
    parser.add_argument("--distance-tolerance", default="adaptive")
    parser.add_argument("--location-scope", default="nearby")
    parser.add_argument("--budget-min", type=int, default=0)
    parser.add_argument("--budget-max", type=int, default=0)
    parser.add_argument("--task-limit", type=int, default=8)
    parser.add_argument("--task-preview", type=int, default=8)
    parser.add_argument("--poi-preview", type=int, default=3)
    parser.add_argument("--show-curated", action="store_true")
    parser.add_argument("--show-days", action="store_true")
    parser.add_argument("--full", action="store_true", help="Also run candidate_pool and planner_output.")
    parser.add_argument("--verbose", action="store_true", help="Print detailed AMap results and full planner days.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(run_pipeline(args))


if __name__ == "__main__":
    main()

import importlib
from typing import Any, Dict, List


def _legacy():
    return importlib.import_module("core")


async def plan_amap_route(client, points: List[Dict[str, float]]) -> Dict[str, Any]:
    return await _legacy().plan_amap_route(client, points)


async def enrich_planner_output_with_routes(planner_output: Dict[str, Any]) -> Dict[str, Any]:
    return await _legacy().enrich_planner_output_with_routes(planner_output)

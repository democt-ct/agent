import importlib
from typing import Any, Dict, Optional


def _legacy():
    return importlib.import_module("core")


def build_candidate_query_plan(requirement_payload: Dict[str, Any], web_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return _legacy().build_candidate_query_plan(requirement_payload, web_context=web_context)


async def build_amap_candidate_pool(requirement_payload: Dict[str, Any], query_plan: Optional[Dict[str, Any]] = None, web_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return await _legacy().build_amap_candidate_pool(requirement_payload, query_plan=query_plan, web_context=web_context)


async def review_candidate_pool_selection(requirement_payload: Dict[str, Any], candidate_pool: Dict[str, Any]) -> Dict[str, Any]:
    return await _legacy().review_candidate_pool_selection(requirement_payload, candidate_pool)


def build_planner_output(requirement_payload: Dict[str, Any], candidate_pool: Dict[str, Any], query_plan: Optional[Dict[str, Any]] = None, selection_hints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return _legacy().build_planner_output(requirement_payload, candidate_pool, query_plan=query_plan, selection_hints=selection_hints)


async def generate_itinerary(*args, **kwargs) -> Dict[str, Any]:
    return await _legacy().generate_itinerary(*args, **kwargs)

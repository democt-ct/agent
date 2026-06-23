import importlib
from typing import Any, Dict, List, Optional


def _legacy():
    return importlib.import_module("core")


def build_session_title(message: str) -> str:
    return _legacy().build_session_title(message)


def build_preference_follow_up_question(payload: Dict[str, Any]) -> str:
    return _legacy().build_preference_follow_up_question(payload)


def build_assistant_reply(requirement=None, itinerary=None, follow_up_questions=None, is_replan: bool = False) -> str:
    return _legacy().build_assistant_reply(requirement=requirement, itinerary=itinerary, follow_up_questions=follow_up_questions, is_replan=is_replan)


def build_planning_blocked_message(warnings: List[str]) -> str:
    return _legacy().build_planning_blocked_message(warnings)


async def interpret_requirement(text: str, existing_requirement=None) -> Dict[str, Any]:
    return await _legacy().interpret_requirement(text, existing_requirement)


async def summarize_assistant_reply(*args, **kwargs) -> str:
    return await _legacy().summarize_assistant_reply(*args, **kwargs)

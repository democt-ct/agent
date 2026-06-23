import importlib
from typing import Any, Dict, List, Optional


def _legacy():
    return importlib.import_module("core")


def should_auto_web_search(text: str, requirement: Optional[Dict[str, Any]] = None) -> bool:
    return _legacy().should_auto_web_search(text, requirement)


def has_web_context_intent(text: str) -> bool:
    return _legacy().has_web_context_intent(text)


async def collect_web_context(*args, **kwargs) -> Dict[str, Any]:
    return await _legacy().collect_web_context(*args, **kwargs)


def compact_web_context_for_prompt(web_context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return _legacy().compact_web_context_for_prompt(web_context)

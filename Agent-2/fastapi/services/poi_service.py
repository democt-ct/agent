import importlib
from typing import Any, Dict, Optional


def _legacy():
    return importlib.import_module("core")


def parse_amap_location(value: Any) -> Optional[Dict[str, float]]:
    return _legacy().parse_amap_location(value)


def parse_amap_polyline(value: Any):
    return _legacy().parse_amap_polyline(value)


def normalize_amap_poi_candidate(poi: Dict[str, Any], category: Optional[str]):
    return _legacy().normalize_amap_poi_candidate(poi, category)


async def search_amap_poi(*args, **kwargs):
    return await _legacy().search_amap_poi(*args, **kwargs)

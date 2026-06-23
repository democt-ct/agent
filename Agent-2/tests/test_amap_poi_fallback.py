import asyncio
from pathlib import Path
import sys

FASTAPI_DIR = Path(__file__).resolve().parents[1] / "fastapi"
if str(FASTAPI_DIR) not in sys.path:
    sys.path.insert(0, str(FASTAPI_DIR))

import core  # noqa: E402


async def _run_fallback_search() -> dict:
    async def fake_httpx(_client, _url, _params):
        return {"pois": []}

    async def fake_curl(_url, _params):
        return {
            "pois": [
                {
                    "id": "kw-1",
                    "name": "kuanzhai",
                    "cityname": "chengdu",
                    "adname": "qingyang",
                    "location": "104.057,30.669",
                    "address": "chengdu qingyang",
                    "type": "landmark",
                    "typecode": "110000",
                }
            ]
        }

    original_httpx = core._fetch_amap_json_with_httpx
    original_curl = core._fetch_amap_json_with_curl
    original_key = core._get_amap_web_service_key
    core._fetch_amap_json_with_httpx = fake_httpx
    core._fetch_amap_json_with_curl = fake_curl
    core._get_amap_web_service_key = lambda: "test_key"
    try:
        return await core.search_amap_poi(
            None,
            {
                "city": "chengdu",
                "keyword": "kuanzhai",
                "category": "landmark",
                "search_mode": "region",
                "limit": 5,
            },
        )
    finally:
        core._fetch_amap_json_with_httpx = original_httpx
        core._fetch_amap_json_with_curl = original_curl
        core._get_amap_web_service_key = original_key


async def _run_no_match_resolve() -> dict:
    async def fake_empty_httpx(_client, _url, _params):
        return {"pois": []}

    async def fake_empty_curl(_url, _params):
        return {"pois": []}

    original_httpx = core._fetch_amap_json_with_httpx
    original_curl = core._fetch_amap_json_with_curl
    original_key = core._get_amap_web_service_key
    core._fetch_amap_json_with_httpx = fake_empty_httpx
    core._fetch_amap_json_with_curl = fake_empty_curl
    core._get_amap_web_service_key = lambda: "test_key"
    try:
        return await core.api_poi_resolve(
            {
                "keyword": "missing-place",
                "city": "chengdu",
                "limit": 5,
            }
        )
    finally:
        core._fetch_amap_json_with_httpx = original_httpx
        core._fetch_amap_json_with_curl = original_curl
        core._get_amap_web_service_key = original_key


def test_fallback_search_returns_items():
    result = asyncio.run(_run_fallback_search())
    assert result["data"]
    assert result["data"][0]["name"] == "kuanzhai"
    assert result["data"][0]["source"] == "amap_poi"
    assert result["warnings"] == []


def test_no_match_resolve_stays_invalid():
    result = asyncio.run(_run_no_match_resolve())
    assert result["status"] == "invalid"
    assert result["reason"] == "no poi match"
    assert result["alternatives"] == []


if __name__ == "__main__":
    test_fallback_search_returns_items()
    test_no_match_resolve_stays_invalid()
    print("amap_poi_fallback_ok")

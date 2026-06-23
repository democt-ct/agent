from pathlib import Path
import sys


FASTAPI_DIR = Path(__file__).resolve().parents[1] / "fastapi"
if str(FASTAPI_DIR) not in sys.path:
    sys.path.insert(0, str(FASTAPI_DIR))

import core as travel_core  # noqa: E402


def test_validator_removes_duplicate_address_between_day_one_and_day_two():
    itinerary = {
        "city": "绵阳",
        "days": [
            {
                "day_index": 1,
                "items": [
                    {
                        "slot": "上午",
                        "text": "Museum",
                        "selected_places": [
                            {
                                "poi_id": "poi-day-1",
                                "name": "博物馆",
                                "city": "绵阳",
                                "address": "绵阳市涪城区主街123号",
                                "location": {"lng": 104.1, "lat": 31.1},
                                "grounding_status": "grounded",
                                "place_kind": "museum",
                            }
                        ],
                    }
                ],
                "manual_order_poi_ids": ["poi-day-1"],
            },
            {
                "day_index": 2,
                "items": [
                    {
                        "slot": "下午",
                        "text": "美术馆",
                        "selected_places": [
                            {
                                "poi_id": "poi-day-2",
                                "name": "美术馆",
                                "city": "绵阳",
                                "address": "绵阳市涪城区主街123号",
                                "location": {"lng": 104.2, "lat": 31.2},
                                "grounding_status": "grounded",
                                "place_kind": "museum",
                            }
                        ],
                    }
                ],
                "manual_order_poi_ids": ["poi-day-2"],
            },
        ],
        "candidate_backups": [],
    }

    warnings = travel_core._validate_and_repair_itinerary(
        itinerary,
        {"city": "绵阳", "trip_style": "moderate"},
    )

    assert len(itinerary["days"][0]["items"]) == 1
    assert itinerary["days"][1]["items"] == []
    assert itinerary["days"][1]["manual_order_poi_ids"] == []
    assert any("地址重复" in item for item in warnings)
    assert any(
        check.get("code") == "duplicate_address_day_1_2"
        for check in itinerary["validator_result"]["checks"]
    )

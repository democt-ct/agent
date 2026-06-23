import asyncio
from pathlib import Path
import sys

FASTAPI_DIR = Path(__file__).resolve().parents[1] / "fastapi"
if str(FASTAPI_DIR) not in sys.path:
    sys.path.insert(0, str(FASTAPI_DIR))

import app as travel_app  # noqa: E402
import core as travel_core  # noqa: E402


def make_candidate(**overrides):
    base = {
        "id": "cand",
        "name": "瓒婄帇妤?,
        "city": "缁甸槼",
        "category": "landmark",
        "location": {"lng": 104.76, "lat": 31.46},
        "address": "缁甸槼甯傛丢鍩庡尯",
        "source": "amap_poi",
        "sourceOrigin": "llm_curator",
        "sourceInterest": "curated",
        "groundingConfidence": 0.72,
        "classicnessScore": 0.88,
        "contentSignalScore": 0.8,
        "mentionCount": 2,
        "signalCount": 1,
        "llmCurated": True,
        "webDerived": False,
    }
    base.update(overrides)
    return travel_app.enhance_candidate_for_itinerary(base, {"destination": base["city"], "interests": ["褰撳湴鐗硅壊缇庨", "citywalk"]})


def test_non_travel_filter_blocks_generic_mall_and_chain_food():
    mall = make_candidate(
        id="mall",
        name="涓囪揪骞垮満",
        category="mall",
        sourceOrigin="generic_amap",
        llmCurated=False,
        webDerived=False,
        classicnessScore=0.2,
        contentSignalScore=0.1,
        groundingConfidence=0.55,
    )
    chain_food = make_candidate(
        id="chain",
        name="鑲痉鍩?,
        category="food",
        sourceOrigin="generic_amap",
        llmCurated=False,
        webDerived=False,
        classicnessScore=0.1,
        contentSignalScore=0.1,
        groundingConfidence=0.55,
    )
    assert travel_app.non_travel_poi_filter(mall)["filtered"] is True
    assert travel_app.non_travel_poi_filter(chain_food)["filtered"] is True
    assert mall["candidateTier"] == "weak"
    assert chain_food["candidateTier"] == "weak"


def test_enhance_candidate_strong_curated_core_and_rejects_generic_amap():
    curated = make_candidate(
        id="core",
        name="瓒婄帇妤?,
        category="landmark",
        sourceOrigin="llm_curator",
        llmCurated=True,
        classicnessScore=0.93,
        groundingConfidence=0.82,
    )
    generic = make_candidate(
        id="generic",
        name="鏅€氳喘鐗╀腑蹇?,
        category="mall",
        sourceOrigin="generic_amap",
        llmCurated=False,
        webDerived=False,
        classicnessScore=0.18,
        contentSignalScore=0.08,
        groundingConfidence=0.44,
    )
    assert curated["candidateTier"] == "core"
    assert curated["eligible_for_main_itinerary"] is True
    assert generic["candidateTier"] in {"supplemental", "weak"}
    assert generic["eligible_for_main_itinerary"] is False
    assert generic["sourcePriorityBand"] == "P4"


def test_planner_prefers_representative_scenic_and_local_food_over_generic_noise():
    candidates = [
        make_candidate(
            id="core1",
            name="瓒婄帇妤?,
            category="landmark",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.95,
            groundingConfidence=0.84,
            location={"lng": 104.76, "lat": 31.46},
        ),
        make_candidate(
            id="scenic1",
            name="瀵屼箰灞?,
            category="park",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.89,
            groundingConfidence=0.8,
            location={"lng": 104.8, "lat": 31.49},
        ),
        make_candidate(
            id="walk1",
            name="椹宸?,
            category="citywalk",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.84,
            groundingConfidence=0.8,
            location={"lng": 104.763, "lat": 31.459},
        ),
        make_candidate(
            id="food1",
            name="椹宸风編椋熻",
            category="food",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.86,
            groundingConfidence=0.78,
            location={"lng": 104.801, "lat": 31.489},
        ),
        make_candidate(
            id="food2",
            name="鏈湴鑰佸瓧鍙峰皬鍚冭",
            category="food",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.82,
            groundingConfidence=0.76,
            location={"lng": 104.761, "lat": 31.461},
        ),
        make_candidate(
            id="night1",
            name="涓夋睙澶滄櫙",
            category="nightview",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.8,
            groundingConfidence=0.73,
            location={"lng": 104.764, "lat": 31.458},
        ),
        make_candidate(
            id="mall",
            name="涓囪揪骞垮満",
            category="mall",
            sourceOrigin="generic_amap",
            llmCurated=False,
            webDerived=False,
            classicnessScore=0.18,
            contentSignalScore=0.08,
            groundingConfidence=0.52,
            location={"lng": 104.83, "lat": 31.47},
        ),
    ]
    requirement_payload = {
        "destination": "缁甸槼",
        "trip_days": 2,
        "interests": ["褰撳湴鐗硅壊缇庨", "citywalk"],
        "preferred_pace": "relaxed",
    }
    selected = travel_app.select_planner_items(
        requirement_payload,
        candidates,
        query_plan={"categories": [{"category": "landmark", "priority": 5}, {"category": "food", "priority": 5}, {"category": "citywalk", "priority": 4}]},
        selection_hints={"preferredCategories": ["food", "citywalk", "landmark"]},
    )
    assert any(item["category"] in {"landmark", "park", "citywalk", "nightview"} and item["eligible_for_main_itinerary"] for item in selected)
    assert any(item["category"] == "food" and item["eligible_for_main_itinerary"] for item in selected)
    assert all(item.get("name") != "涓囪揪骞垮満" for item in selected)
    assert all("鑲痉鍩? not in str(item.get("name") or "") for item in selected)


def test_citywalk_trip_keeps_walk_area_and_local_food():
    candidates = [
        make_candidate(
            id="cw1",
            name="鐜夋灄璺?,
            city="鎴愰兘",
            category="citywalk",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.86,
            groundingConfidence=0.8,
            address="鎴愰兘甯傛渚尯",
            location={"lng": 104.06, "lat": 30.64},
        ),
        make_candidate(
            id="cw2",
            name="瀹界獎宸峰瓙",
            city="鎴愰兘",
            category="landmark",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.94,
            groundingConfidence=0.82,
            address="鎴愰兘甯傞潚缇婂尯",
            location={"lng": 104.04, "lat": 30.67},
        ),
        make_candidate(
            id="food1",
            name="濂庢槦妤艰",
            city="鎴愰兘",
            category="food",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.9,
            groundingConfidence=0.78,
            address="鎴愰兘甯傞潚缇婂尯",
            location={"lng": 104.05, "lat": 30.65},
        ),
        make_candidate(
            id="food2",
            name="鏈湴鑰佸瓧鍙风編椋熻",
            city="鎴愰兘",
            category="food",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.84,
            groundingConfidence=0.74,
            location={"lng": 104.08, "lat": 30.63},
        ),
        make_candidate(
            id="night1",
            name="涔濈溂妗?,
            city="鎴愰兘",
            category="nightview",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.82,
            groundingConfidence=0.72,
            address="鎴愰兘甯傞敠姹熷尯",
            location={"lng": 104.07, "lat": 30.62},
        ),
        make_candidate(
            id="mall",
            name="鏅€氳喘鐗╀腑蹇?,
            city="鎴愰兘",
            category="mall",
            sourceOrigin="generic_amap",
            llmCurated=False,
            webDerived=False,
            classicnessScore=0.15,
            contentSignalScore=0.05,
            groundingConfidence=0.5,
            location={"lng": 104.09, "lat": 30.69},
        ),
    ]
    selected = travel_app.select_planner_items(
        {"destination": "鎴愰兘", "trip_days": 2, "interests": ["citywalk", "褰撳湴缇庨"], "preferred_pace": "relaxed"},
        candidates,
        query_plan={"categories": [{"category": "citywalk", "priority": 5}, {"category": "food", "priority": 5}, {"category": "nightview", "priority": 4}]},
        selection_hints={"preferredCategories": ["citywalk", "food", "nightview"]},
    )
    assert any(item["category"] == "citywalk" and item["eligible_for_main_itinerary"] for item in selected)
    assert any(item["category"] == "food" and item["eligible_for_main_itinerary"] for item in selected)
    assert all(item.get("name") != "鏅€氳喘鐗╀腑蹇? for item in selected)


def test_query_plan_falls_back_when_curator_returns_empty():
    async def fake_curator(_request_context):
        return {
            "destination": "鏌愪釜鍐烽棬灏忓煄甯?,
            "candidate_groups": {group: [] for group in travel_app.CURATED_GROUP_NAMES},
            "avoid_rules": [],
            "warnings": ["llm_curator_failed_or_invalid_json"],
            "source": "fallback",
        }

    original = travel_app.build_llm_curated_city_candidates
    travel_app.build_llm_curated_city_candidates = fake_curator
    try:
        plan = asyncio.run(
            travel_app.build_candidate_query_plan(
                {"destination": "鏌愪釜鍐烽棬灏忓煄甯?, "trip_days": 1, "interests": ["鍘嗗彶"], "raw_input": "鏌愪釜鍐烽棬灏忓煄甯備竴鏃ユ父"},
                web_context=None,
            )
        )
    finally:
        travel_app.build_llm_curated_city_candidates = original
    assert plan["source"] == "fallback"
    assert plan["fallbackStrategy"]["curatorFirst"] is False
    assert plan["fallbackStrategy"]["webRecommended"] is True
    assert plan["fallbackStrategy"]["genericFallbackRecommended"] is True


def test_query_plan_keeps_curator_first_and_skips_fallback_when_curated_pool_is_sufficient():
    async def fake_curator(_request_context):
        groups = {}
        for index, group in enumerate(travel_app.CURATED_GROUP_NAMES):
            items = []
            if index < 4:
                items = [
                    {"name": f"{group}_a", "grounding_query": f"{group}_a", "category": "landmark", "uncertainty": "low"},
                    {"name": f"{group}_b", "grounding_query": f"{group}_b", "category": "food", "uncertainty": "low"},
                ]
            groups[group] = items
        return {
            "destination": "缁甸槼",
            "candidate_groups": groups,
            "avoid_rules": [],
            "warnings": [],
            "source": "llm",
        }

    original = travel_app.build_llm_curated_city_candidates
    travel_app.build_llm_curated_city_candidates = fake_curator
    try:
        plan = asyncio.run(
            travel_app.build_candidate_query_plan(
                {"destination": "缁甸槼", "trip_days": 2, "interests": ["citywalk"], "raw_input": "缁甸槼 citywalk"},
                web_context=None,
            )
        )
    finally:
        travel_app.build_llm_curated_city_candidates = original
    assert plan["fallbackStrategy"]["curatorFirst"] is True
    assert plan["fallbackStrategy"]["webRecommended"] is False
    assert plan["fallbackStrategy"]["genericFallbackRecommended"] is False


def test_candidate_pool_retries_curator_when_short_on_candidates():
    call_count = {"curator": 0}

    async def fake_curator(_request_context):
        call_count["curator"] += 1
        groups = {}
        for index, group in enumerate(travel_app.CURATED_GROUP_NAMES):
            if index == 0 and call_count["curator"] == 1:
                groups[group] = [
                    {"name": "Initial scenic", "grounding_query": "Initial scenic", "category": "landmark", "uncertainty": "low"}
                ]
            elif index == 0 and call_count["curator"] == 2:
                groups[group] = [
                    {"name": f"Retry scenic {i}", "grounding_query": f"Retry scenic {i}", "category": "landmark", "uncertainty": "low"}
                    for i in range(1, 5)
                ]
            else:
                groups[group] = []
        return {
            "destination": "缁甸槼",
            "candidate_groups": groups,
            "avoid_rules": [],
            "warnings": [],
            "source": "llm",
        }

    async def fake_search_amap_poi(_client, task):
        keyword = str(task.get("keyword") or "")
        data = []
        if "Initial scenic" in keyword:
            data = [
                {
                    "id": "initial_poi",
                    "name": "Initial scenic",
                    "cityname": "缁甸槼",
                    "location": "104.76,31.46",
                    "address": "缁甸槼",
                    "type": "landmark",
                    "typecode": "landmark",
                    "adname": "娑煄鍖?,
                }
            ]
        elif "Retry scenic" in keyword:
            data = [
                {
                    "id": f"retry_{keyword[-1]}",
                    "name": keyword,
                    "cityname": "缁甸槼",
                    "location": "104.77,31.47",
                    "address": "缁甸槼",
                    "type": "landmark",
                    "typecode": "landmark",
                    "adname": "娑煄鍖?,
                }
            ]
        return {"tool": "poi_search", "query": task, "data": data, "warnings": []}

    query_plan = {
        "destination": "缁甸槼",
        "categories": [{"category": "landmark", "priority": 5}],
        "generalKeywords": ["缁甸槼"],
        "avoidCategories": [],
        "source": "llm",
        "curatedCandidatePool": {
            "destination": "缁甸槼",
            "candidate_groups": {
                group: ([{"name": "Initial scenic", "grounding_query": "Initial scenic", "category": "landmark", "uncertainty": "low"}] if index == 0 else [])
                for index, group in enumerate(travel_app.CURATED_GROUP_NAMES)
            },
            "source": "llm",
            "warnings": [],
        },
        "curatedGroundingTasks": [
            {"tool": "searchPOI", "city": "缁甸槼", "keyword": "Initial scenic", "category": "landmark", "priority": 10, "source": "llm_curator"}
        ],
        "fallbackStrategy": {"webRecommended": True, "genericFallbackRecommended": True, "curatorFirst": True},
    }

    original_curator = travel_app.build_llm_curated_city_candidates
    original_search = travel_app.search_amap_poi
    travel_app.build_llm_curated_city_candidates = fake_curator
    travel_app.search_amap_poi = fake_search_amap_poi
    try:
        candidate_pool = asyncio.run(
            travel_app.build_amap_candidate_pool(
                {"destination": "缁甸槼", "trip_days": 1, "interests": ["citywalk"], "raw_input": "缁甸槼 citywalk"},
                query_plan=query_plan,
                web_context={"placeNames": []},
            )
        )
    finally:
        travel_app.build_llm_curated_city_candidates = original_curator
        travel_app.search_amap_poi = original_search

    assert call_count["curator"] == 1
    assert candidate_pool["fallbackStrategy"]["curatorRetryUsed"] is True
    assert len(candidate_pool["candidates"]) >= 1


def test_resolved_places_and_planner_output_include_snake_case_aliases():
    days = [
        {
            "day": 1,
            "items": [
                {
                    "candidateId": "cand_1",
                    "name": "Test Scenic",
                    "category": "landmark",
                    "candidateTier": "core",
                    "qualityFlags": {"representative_walk": True},
                    "scoreBreakdown": {"finalCandidateScore": 88.0},
                    "whySelected": "Strong curated fit",
                    "whyChosen": "Strong curated fit",
                    "whyNotDuplicate": "Unique entity",
                    "sourceSummary": "llm curated",
                    "roleInDay": "anchor",
                    "eligible_for_main_itinerary": True,
                    "eligible_reason": "core classicness and grounding ok",
                    "groundingConfidence": 0.82,
                    "classicnessScore": 0.9,
                    "foodLocalityScore": 0,
                    "walkQualityScore": 12,
                    "protectionApplied": False,
                    "fallbackApplied": False,
                }
            ],
        }
    ]
    resolved = travel_app.build_resolved_places_from_days(days)
    assert resolved[0]["why_selected"] == "Strong curated fit"
    assert resolved[0]["quality_flags"] == {"representative_walk": True}
    assert resolved[0]["score_breakdown"] == {"finalCandidateScore": 88.0}
    assert resolved[0]["candidate_tier"] == "core"
    assert resolved[0]["role_in_day"] == "anchor"

    planner = travel_app.build_planner_output(
        {"destination": "缁甸槼", "trip_days": 1, "interests": []},
        {"candidates": [], "warnings": []},
    )
    assert planner["day_plan"] == planner["dayPlan"]
    assert planner["resolved_places"] == planner["resolvedPlaces"]
    assert planner["route_span_meters"] == planner["routeSpanMeters"]
    assert planner["map_data"] == planner["mapData"]
    assert planner["map_markers"] == planner["mapMarkers"]
    assert planner["selection_reasons"] == planner["selectionReasons"]
    assert planner["fallback_strategy"] == planner["fallbackStrategy"]


def test_destination_matched_duplicate_poi_ranks_first():
    requirement_payload = {"destination": "鎴愰兘", "trip_days": 1, "interests": ["citywalk"]}
    destination_match = make_candidate(
        id="poi_a",
        name="椹宸?,
        city="鎴愰兘",
        category="citywalk",
        sourceOrigin="web_search",
        llmCurated=False,
        webDerived=True,
        classicnessScore=0.7,
        groundingConfidence=0.66,
        address="鎴愰兘甯傚競涓績",
    )
    other_city = make_candidate(
        id="poi_b",
        name="椹宸?,
        city="缁甸槼",
        category="citywalk",
        sourceOrigin="web_search",
        llmCurated=False,
        webDerived=True,
        classicnessScore=0.7,
        groundingConfidence=0.66,
        address="缁甸槼甯傛丢鍩庡尯",
    )
    selected = travel_app.select_planner_items(
        requirement_payload,
        [other_city, destination_match],
        query_plan={"categories": [{"category": "citywalk", "priority": 4}]},
        selection_hints={"preferredCategories": ["citywalk"]},
    )
    assert selected[0]["city"] == "鎴愰兘"



def test_planner_output_keeps_grounded_partial_day_without_hotel():
    candidates = [
        make_candidate(
            id="anchor",
            name="Partial Anchor",
            city="Mianyang",
            category="landmark",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.92,
            groundingConfidence=0.84,
            location={"lng": 104.76, "lat": 31.46},
            address="Mianyang center",
        ),
        make_candidate(
            id="walk",
            name="Partial Walk",
            city="Mianyang",
            category="citywalk",
            sourceOrigin="web_search",
            llmCurated=False,
            webDerived=True,
            classicnessScore=0.78,
            groundingConfidence=0.72,
            location={"lng": 104.762, "lat": 31.458},
            address="Mianyang old street",
        ),
        make_candidate(
            id="food",
            name="Partial Food",
            city="Mianyang",
            category="food",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.85,
            groundingConfidence=0.78,
            location={"lng": 104.764, "lat": 31.459},
            address="Mianyang food street",
        ),
    ]
    planner = travel_app.build_planner_output(
        {"destination": "Mianyang", "trip_days": 1, "interests": ["citywalk"]},
        {"candidates": candidates, "warnings": [], "fallbackStrategy": {}},
        query_plan={"categories": [{"category": "landmark", "priority": 5}, {"category": "food", "priority": 5}, {"category": "citywalk", "priority": 4}]},
        selection_hints={"preferredCategories": ["landmark", "food", "citywalk"]},
    )
    day_items = planner["itinerary"]["days"][0]["items"]
    assert len(day_items) >= 3
    assert len(planner["mapMarkers"]) >= 3


def test_ensure_planner_eligibility_blocks_supplemental_and_hotel_from_main_itinerary():
    supplemental = travel_app.ensurePlannerEligibility(
        {
            "id": "supplemental_1",
            "name": "游客服务中心",
            "category": "landmark",
            "plannerCategory": "supplemental",
            "candidateTier": "supplemental",
            "location": {"lng": 104.76, "lat": 31.46},
            "groundingConfidence": 0.82,
            "classicnessScore": 0.72,
        },
        {"destination": "Mianyang"},
    )
    hotel = travel_app.ensurePlannerEligibility(
        {
            "id": "hotel_1",
            "name": "中心酒店",
            "category": "hotel",
            "candidateTier": "core",
            "location": {"lng": 104.761, "lat": 31.461},
            "groundingConfidence": 0.9,
            "classicnessScore": 0.82,
        },
        {"destination": "Mianyang"},
    )
    assert supplemental["eligible_for_main_itinerary"] is False
    assert hotel["eligible_for_main_itinerary"] is False


def test_normalize_planner_category_demotes_service_like_pois():
    assert travel_app.normalizePlannerCategory({"type": "游客中心"}) == "supplemental"
    assert travel_app.normalizePlannerCategory({"type": "景区售票处"}) == "supplemental"
    assert travel_app.normalizePlannerCategory({"type": "停车场"}) == "supplemental"
    assert travel_app.normalizePlannerCategory({"type": "古街景区"}) == "scenic"


def test_planner_output_meal_slots_require_food_and_hotel_is_removed_from_day_items():
    candidates = [
        make_candidate(
            id="anchor_meal",
            name="Main Anchor",
            city="Mianyang",
            category="landmark",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.9,
            groundingConfidence=0.84,
            location={"lng": 104.76, "lat": 31.46},
            address="Main district",
        ),
        make_candidate(
            id="scenic_lunch_like",
            name="Food Street Scenic Label",
            city="Mianyang",
            category="landmark",
            plannerCategory="scenic",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.82,
            groundingConfidence=0.8,
            location={"lng": 104.761, "lat": 31.461},
            address="Main district",
        ),
        make_candidate(
            id="food_ok",
            name="Local Noodles",
            city="Mianyang",
            category="food",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.84,
            groundingConfidence=0.78,
            location={"lng": 104.762, "lat": 31.462},
            address="Main district",
        ),
        make_candidate(
            id="hotel_hidden",
            name="Route End Hotel",
            city="Mianyang",
            category="hotel",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.86,
            groundingConfidence=0.82,
            location={"lng": 104.763, "lat": 31.463},
            address="Main district",
        ),
    ]


    planner = travel_app.build_planner_output(
        {"destination": "Mianyang", "trip_days": 1, "interests": ["citywalk"]},
        {"candidates": candidates, "warnings": [], "fallbackStrategy": {}},
        query_plan={"categories": [{"category": "landmark", "priority": 5}, {"category": "food", "priority": 5}]},
        selection_hints={"preferredCategories": ["landmark", "food"]},
    )
    day_items = planner["itinerary"]["days"][0]["items"]
    assert all(item["category"] != "hotel" for item in day_items)
    assert all(marker["category"] != "hotel" for marker in planner["mapMarkers"])
    assert all(item["category"] == "food" for item in day_items if item.get("role") == "meal" or item.get("timeSlot") == "lunch")


def test_planner_output_avoids_far_cross_region_mix_for_same_day():
    candidates = [
        make_candidate(
            id="anchor_region_a",
            name="City Museum",
            city="Mianyang",
            category="landmark",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.92,
            groundingConfidence=0.84,
            location={"lng": 104.76, "lat": 31.46},
            address="涪城区中心",
            regionCluster="涪城区",
        ),
        make_candidate(
            id="food_region_a",
            name="Old Street Food",
            city="Mianyang",
            category="food",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.83,
            groundingConfidence=0.78,
            location={"lng": 104.762, "lat": 31.461},
            address="涪城区老街",
            regionCluster="涪城区",
        ),
        make_candidate(
            id="walk_region_a",
            name="River Walk",
            city="Mianyang",
            category="citywalk",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.8,
            groundingConfidence=0.76,
            location={"lng": 104.764, "lat": 31.459},
            address="涪城区江边",
            regionCluster="涪城区",
        ),
        make_candidate(
            id="far_region_b",
            name="Far County Scenic",
            city="Mianyang",
            category="landmark",
            sourceOrigin="llm_curator",
            llmCurated=True,
            classicnessScore=0.9,
            groundingConfidence=0.82,
            location={"lng": 104.32, "lat": 32.1},
            address="平武县景区",
            regionCluster="平武县",
        ),
    ]
    planner = travel_app.build_planner_output(
        {"destination": "Mianyang", "trip_days": 1, "interests": ["轻松", "citywalk"], "preferred_pace": "relaxed"},
        {"candidates": candidates, "warnings": [], "fallbackStrategy": {}},
        query_plan={"categories": [{"category": "landmark", "priority": 5}, {"category": "food", "priority": 5}, {"category": "citywalk", "priority": 4}]},
        selection_hints={"preferredCategories": ["landmark", "food", "citywalk"]},
    )
    names = [item["name"] for item in planner["itinerary"]["days"][0]["items"]]
    assert "Far County Scenic" not in names


def test_amap_poi_search_falls_back_to_curl_when_httpx_returns_empty():
    async def fake_httpx(_client, _url, _params):
        return {"pois": []}

    async def fake_curl(_url, _params):
        return {
            "pois": [
                {
                    "id": "kw-1",
                    "name": "宽窄巷子",
                    "cityname": "成都",
                    "adname": "青羊区",
                    "location": "104.057,30.669",
                    "address": "成都市青羊区窄巷子",
                    "type": "风景名胜",
                    "typecode": "110000",
                }
            ]
        }

    original_httpx = travel_core._fetch_amap_json_with_httpx
    original_curl = travel_core._fetch_amap_json_with_curl
    original_key = travel_core._get_amap_web_service_key
    travel_core._fetch_amap_json_with_httpx = fake_httpx
    travel_core._fetch_amap_json_with_curl = fake_curl
    travel_core._get_amap_web_service_key = lambda: "test_key"
    try:
        result = asyncio.run(
            travel_core.search_amap_poi(
                None,
                {
                    "city": "成都",
                    "keyword": "宽窄巷子",
                    "category": "landmark",
                    "search_mode": "region",
                    "limit": 5,
                },
            )
        )
    finally:
        travel_core._fetch_amap_json_with_httpx = original_httpx
        travel_core._fetch_amap_json_with_curl = original_curl
        travel_core._get_amap_web_service_key = original_key

    assert result["data"]
    assert result["data"][0]["name"] == "宽窄巷子"
    assert result["data"][0]["source"] == "amap_poi"
    assert result["warnings"] == []


def test_amap_poi_resolve_keeps_no_match_when_both_sources_are_empty():
    async def fake_empty_httpx(_client, _url, _params):
        return {"pois": []}

    async def fake_empty_curl(_url, _params):
        return {"pois": []}

    original_httpx = travel_core._fetch_amap_json_with_httpx
    original_curl = travel_core._fetch_amap_json_with_curl
    original_key = travel_core._get_amap_web_service_key
    travel_core._fetch_amap_json_with_httpx = fake_empty_httpx
    travel_core._fetch_amap_json_with_curl = fake_empty_curl
    travel_core._get_amap_web_service_key = lambda: "test_key"
    try:
        result = asyncio.run(
            travel_core.api_poi_resolve(
                {
                    "keyword": "不存在的地点",
                    "city": "成都",
                    "limit": 5,
                }
            )
        )
    finally:
        travel_core._fetch_amap_json_with_httpx = original_httpx
        travel_core._fetch_amap_json_with_curl = original_curl
        travel_core._get_amap_web_service_key = original_key

    assert result["status"] == "invalid"
    assert result["reason"] == "no poi match"
    assert result["alternatives"] == []

if __name__ == "__main__":
    test_non_travel_filter_blocks_generic_mall_and_chain_food()
    test_enhance_candidate_strong_curated_core_and_rejects_generic_amap()
    test_planner_prefers_representative_scenic_and_local_food_over_generic_noise()
    test_citywalk_trip_keeps_walk_area_and_local_food()
    test_query_plan_falls_back_when_curator_returns_empty()
    test_destination_matched_duplicate_poi_ranks_first()
    test_amap_poi_search_falls_back_to_curl_when_httpx_returns_empty()
    test_amap_poi_resolve_keeps_no_match_when_both_sources_are_empty()
    print("pipeline_smoke_ok")

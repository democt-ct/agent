# Findings

## Candidate Flow

- The project already contains `build_llm_curated_city_candidates()`, `build_curated_grounding_tasks()`, `build_candidate_query_plan()`, `build_amap_candidate_pool()`, `non_travel_poi_filter()`, `enhance_candidate_for_itinerary()`, `select_planner_items()`, and `build_planner_output()`.
- There are two `build_candidate_query_plan()` definitions in `fastapi/app.py`; the later one is the active one and currently still emits a generic LLM query plan.
- `build_amap_candidate_pool()` currently runs curated tasks, then generic AMap fallback, then web follow-up, then more generic AMap. That is the opposite of the requested priority order.

## Filtering / Scoring

- `non_travel_poi_filter()` already has blacklist and chain-food logic, but it is still too permissive for generic malls and other low-travel POIs.
- `enhance_candidate_for_itinerary()` already computes `candidateTier`, `eligible_for_main_itinerary`, `qualityFlags`, and score breakdown fields, so it is a good place to tighten thresholds rather than invent a new candidate schema.
- `select_planner_items()` currently still allows non-eligible located items to backfill the selection pool, which can leak weak POIs into the itinerary.

## Planner / Output

- `build_planner_output()` already emits `dayPlan`, `mapData`, `mapMarkers`, `routeSpanMeters`, `warnings`, and `selectionReasons`.
- The output can likely be extended to expose the requested `resolvedPlaces` and score/debug fields without changing the frontend contract heavily.


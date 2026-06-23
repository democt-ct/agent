# Task Plan

## Goal
Refactor the travel planning pipeline so that high-quality LLM-curated city candidates become the primary source, AMap POI becomes a grounding verifier, generic POI/web discovery become fallback only, and the day planner only schedules eligible high-quality places.

## Phases

1. [in_progress] Map current candidate/query/planner flow in `fastapi/app.py` and identify the smallest set of functions to patch.
2. [pending] Implement curator-first candidate generation, grounding task normalization, stronger non-travel POI filtering, and scoring/eligibility updates.
3. [pending] Tighten day-level planner selection so it prefers eligible core/scenic/walk/food candidates and avoids weak/generic POIs.
4. [pending] Add scenario-based verification for the requested cases and fix any regressions.

## Decisions

- Keep the change concentrated in `fastapi/app.py` and only adjust wrappers if needed.
- Preserve current frontend and API shape where possible, but enrich candidate and planner outputs with the requested debugging fields.
- Use LLM curator output as the primary candidate source, with generic AMap and web search as fallback paths only.

## Findings

- `fastapi/services/planner_service.py` and `fastapi/services/poi_service.py` are thin wrappers around `fastapi/app.py`, so most logic changes can stay in one file.
- The app already has curator, grounding, scoring, and planner helpers, but the old query-plan path still mixes generic POI and web-discovery tasks too early.
- `build_amap_candidate_pool()` is currently the main place where curated, web, and generic AMap candidates are blended.

## Errors Encountered

| Error | Attempt | Resolution |
|---|---:|---|
| PowerShell profile load warning | 1 | Non-fatal; continue with `-NoProfile` style reads when needed. |


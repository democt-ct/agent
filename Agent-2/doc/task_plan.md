# Task Plan

## Goal
Improve the current mixed location-search pipeline so it:
- triggers lightweight web search more often for recommendation-style travel requests
- turns web-extracted place names into stronger POI follow-up queries
- builds a base-plus-preference query plan instead of treating categories evenly
- scores and deduplicates candidates more aggressively
- lets the planner pick by time slot and template instead of taking the top results blindly

## Phases

### Phase 1: Trigger and query-plan tuning
- [in_progress] Loosen web-search triggering for recommendation-style travel prompts
- [pending] Make query plans base-category-first, then expand by preferences and web context

### Phase 2: Candidate pool strengthening
- [pending] Improve web-place extraction to POI follow-up mapping
- [pending] Add stronger candidate scoring, dedupe, and category balancing

### Phase 3: Planner selection
- [pending] Ensure planner selects by slot/template rather than first-N candidates
- [pending] Add minimal verification for output shape and scoring behavior

## Findings
- `fastapi/app.py` currently decides whether to collect web context in `has_web_context_intent()` and `collect_web_context()`.
- `src/services/llm/candidatePlanner.ts` already builds a category query plan from requirement + optional web context, but the fallback is still broad and evenly distributed.
- `src/services/candidates/candidatePoolBuilder.ts` already performs `searchWeb` + `searchPOI` and also adds extra POI queries from extracted web place names.
- `src/services/planning/dynamicItineraryPlanner.ts` already uses slot affinity, proximity, and repeat penalties, so the main gain is to make candidate quality better and tweak the fallback / template mix.

## Errors Encountered
- None yet.


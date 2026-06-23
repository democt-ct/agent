# Findings

## Current search flow
- Web context is collected in `fastapi/app.py` when the input matches a conservative intent list, or when forced.
- Candidate pool building happens in `src/services/candidates/candidatePoolBuilder.ts`.
- The candidate pool already mixes:
  - `searchWeb`
  - `searchPOI`
  - extra POI lookups from extracted web place names
  - static pool candidates for special cases
- Planner selection happens in `src/services/planning/dynamicItineraryPlanner.ts`.

## Weak points observed
- Web-trigger intent is narrow, so many travel recommendation prompts skip web context.
- Query planning is still broad by default, even when the user intent is clearly food / cafe / nightview / walking-heavy.
- Candidate dedupe exists, but it mostly merges by source id, name+city, or rounded location. It can still keep near-duplicates across sources.
- Planner already has slot logic, but better upstream candidate quality is needed to make slot selection feel intentional.

## Useful files
- `fastapi/app.py`
- `src/services/llm/candidatePlanner.ts`
- `src/services/candidates/candidatePoolBuilder.ts`
- `src/services/candidates/candidateNormalizer.ts`
- `src/services/planning/dynamicItineraryPlanner.ts`
- `src/services/planning/travelPlanningPipeline.ts`


# Map, Weather, And Routing Integration Plan

## Goal

Add map, weather, and route-planning capabilities to the travel itinerary assistant without rewriting the current architecture.

The integration should support:

- Weather-aware itinerary suggestions.
- Location-aware itinerary activities.
- Route and travel-time estimation between activities.
- Future provider replacement, for example AMap, Baidu Maps, Google Maps, OpenWeather, QWeather.
- LLM usage with grounded tool results, not hallucinated map/weather data.

## Current Architecture Fit

The existing project already has:

- Session memory: `sessions`
- Requirement memory: `trip_requirements`
- Itinerary versions: `itinerary_drafts`
- Conversation memory: `conversation_messages`
- LLM services: `src/services/llm/*`
- Replanning service: `src/services/replanner.ts`
- Conversation orchestration: `src/services/conversationPlanner.ts`

The new capabilities should be added as provider-backed services used by itinerary generation/replanning.

## Recommended Providers

### China-first MVP

Use AMap / Gaode first if the main use case is China travel.

Capabilities:

- Geocoding: address/name to coordinates.
- POI search: attractions, restaurants, hotels.
- Directions: walking, driving, public transport.
- Distance and duration between points.

Weather options:

- AMap weather for simple city weather.
- QWeather / Caiyun for better forecast quality.

### International Later

Add provider abstraction so Google Maps, Mapbox, OpenWeather can be swapped in later.

## Proposed Service Layer

Add provider-neutral interfaces first:

```text
src/services/location/
  types.ts
  geocodingService.ts
  poiService.ts
  routingService.ts
  weatherService.ts
  providers/
    amapProvider.ts
```

### Core Types

```ts
export interface GeoPoint {
  lat: number;
  lng: number;
}

export interface PlaceCandidate {
  name: string;
  address?: string;
  city?: string;
  point?: GeoPoint;
  provider: string;
  providerId?: string;
}

export interface RouteSegment {
  from: PlaceCandidate;
  to: PlaceCandidate;
  mode: "walk" | "drive" | "transit";
  distanceMeters: number;
  durationMinutes: number;
  provider: string;
}

export interface WeatherForecast {
  city: string;
  date: string;
  condition: string;
  minTempC?: number;
  maxTempC?: number;
  precipitationProbability?: number;
  source: string;
}
```

## Data Model Plan

### MVP: No Migration Required

Store map/weather/routing results inside:

- `itinerary_drafts.itinerary_json`
- `conversation_messages.metadata_json`

This is enough for MVP and avoids schema churn.

Example itinerary enrichment:

```json
{
  "days": [
    {
      "day": 1,
      "theme": "西湖轻松游",
      "items": [
        {
          "time": "上午",
          "name": "西湖",
          "location": {
            "lat": 30.259,
            "lng": 120.130,
            "provider": "amap"
          },
          "weather_note": "预计多云，适合户外散步",
          "route_to_next": {
            "mode": "walk",
            "duration_minutes": 18,
            "distance_meters": 1300
          }
        }
      ]
    }
  ]
}
```

### Later Migration

Add normalized tables only after the shape stabilizes:

- `places`
- `itinerary_item_locations`
- `route_segments`
- `weather_snapshots`

## API Plan

Add internal endpoints first for testing:

```http
GET /tools/geocode?city=杭州&query=西湖
GET /tools/weather?city=杭州&date=2026-05-01
POST /tools/route
```

Then use these services internally from:

```http
POST /sessions/:sessionId/chat
POST /sessions/:sessionId/itineraries
POST /sessions/:sessionId/replan
```

## Agent Flow

### New Itinerary

1. User says travel request.
2. Requirement parser extracts destination and days.
3. Weather service fetches forecast if dates are known.
4. POI service resolves key activity locations.
5. Routing service estimates travel time between activities.
6. LLM receives structured context:
   - requirement
   - weather forecast
   - POI candidates
   - route constraints
7. Generated itinerary includes route/weather fields.

### Replanning

1. User says "第二天轻松一点" or "下雨改室内".
2. Conversation planner loads latest requirement and itinerary.
3. Weather/routing services refresh only affected day/location.
4. Replanner asks LLM to modify only relevant parts.
5. New itinerary version is saved.

## Minimal Implementation Phases

### Phase 1: Provider Config

Files:

- `src/services/location/types.ts`
- `src/services/location/providers/amapProvider.ts`
- `src/services/location/locationConfig.ts`

Add env vars:

```text
AMAP_API_KEY=
WEATHER_PROVIDER=amap
MAP_PROVIDER=amap
```

### Phase 2: Weather MVP

Implement:

- `getWeatherForecast(city, dateRange)`
- Store weather summary in itinerary JSON.
- Add prompt context: "weather_context".

Done criteria:

- "第三天下雨，改室内" can use actual weather context when available.

### Phase 3: Geocoding And POI MVP

Implement:

- `searchPlaces(city, query)`
- Resolve activity names to coordinates.
- Store `location` on itinerary items.

Done criteria:

- Generated itinerary items contain provider-backed coordinates when possible.

### Phase 4: Route MVP

Implement:

- `estimateRoute(from, to, mode)`
- Enrich consecutive itinerary items with route duration/distance.
- Add UI display: "步行约 18 分钟".

Done criteria:

- "轻松一点" can reduce long transfers and excessive cross-area movement.

### Phase 5: Agent Context Integration

Modify:

- `src/services/llm/itineraryAgent.ts`
- `src/services/replanner.ts`
- `src/services/conversationPlanner.ts`

Add:

- `travelContextBuilder.ts`

Purpose:

- Build grounded context from map/weather/routing services before LLM call.
- Keep LLM prompt clean and deterministic.

## Key Design Decision

Do not let the LLM invent weather, coordinates, or travel times.

The LLM should receive facts from provider services and decide how to use them in itinerary planning.

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| API key unavailable | Feature fails in local dev | Add graceful fallback and warnings |
| Provider rate limits | Slow or failed planning | Cache provider results in itinerary JSON first |
| POI ambiguity | Wrong location selected | Keep candidates and allow later clarification |
| Weather date missing | Cannot fetch forecast | Use city seasonal note or ask follow-up |
| Route mode mismatch | Bad travel-time estimate | Start with walking/driving only, transit later |

## Recommended Next Step

Start with Phase 1 + Phase 2:

1. Add location/weather config.
2. Implement AMap weather provider.
3. Add weather context into itinerary generation/replanning.
4. Display weather notes in current itinerary.

This gives visible user value with the smallest implementation surface.

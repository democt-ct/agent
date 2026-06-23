import { AMAP_CONFIG } from "../../config/llm";
import type {
  ConfirmedItineraryPlace,
  GeoPoint,
  ItineraryPlaceCandidate,
  ItineraryRoutePlan,
  RejectedItineraryPlace,
  ResolvedSpotCandidate,
  RouteSegment,
  SpotScoreBreakdown,
  StructuredPayload
} from "../../types";

interface AmapPoi {
  id?: string;
  name?: string;
  type?: string;
  typecode?: string;
  cityname?: string;
  adname?: string;
  address?: string;
  location?: string;
}

interface AmapPlaceTextResponse {
  status?: string;
  pois?: AmapPoi[];
  info?: string;
}

interface AmapDirectionStep {
  polyline?: string;
}

interface AmapDirectionPath {
  distance?: string;
  duration?: string;
  steps?: AmapDirectionStep[];
}

interface AmapDirectionResponse {
  status?: string;
  route?: {
    paths?: AmapDirectionPath[];
  };
}

function getAmapServerKey(): string {
  return AMAP_CONFIG.webServiceKey || AMAP_CONFIG.browserKey;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeText(value: string | undefined): string {
  return (value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[·\-\s_（）()【】\[\]]/g, "");
}

function normalizeCityText(value: string | undefined): string {
  return (value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[·\-\s_（）()【】\[\]市]/g, "");
}

function normalizeDay(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function getItems(day: Record<string, unknown>): Record<string, unknown>[] {
  const raw = day.items ?? day.activities ?? day.places;
  return Array.isArray(raw) ? raw.filter(isRecord) : [];
}

function parseLocation(value: string | undefined): GeoPoint | null {
  if (!value) {
    return null;
  }
  const [lngRaw, latRaw] = value.split(",");
  const lng = Number(lngRaw);
  const lat = Number(latRaw);
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
    return null;
  }
  return { lng, lat };
}

function pointToAmap(point: GeoPoint): string {
  return `${point.lng},${point.lat}`;
}

function parsePolyline(value: string | undefined): GeoPoint[] {
  if (!value) {
    return [];
  }
  return value
    .split(";")
    .map(parseLocation)
    .filter((point): point is GeoPoint => Boolean(point));
}

function distanceMeters(a: GeoPoint, b: GeoPoint): number {
  const earthRadius = 6371000;
  const toRad = (degree: number) => (degree * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * earthRadius * Math.asin(Math.sqrt(h));
}

function inferTypeHint(name: string, note?: string): string | undefined {
  const text = `${name} ${note ?? ""}`;
  if (/酒店|民宿|住宿|入住/u.test(text)) return "hotel";
  if (/餐|饭|火锅|小吃|美食|咖啡|茶馆|夜市/u.test(text)) return "food";
  if (/博物馆|纪念馆|展览|科技馆/u.test(text)) return "museum";
  if (/公园|山|湖|湿地|自然|风景|景区|古镇|寺|庙/u.test(text)) {
    return "scenic";
  }
  if (/商场|购物|步行街|街区/u.test(text)) return "shopping";
  return undefined;
}

function scoreNameMatch(query: string, poiName: string): number {
  const queryText = normalizeText(query);
  const poiText = normalizeText(poiName);
  if (!queryText || !poiText) return 0;
  if (queryText === poiText) return 1;
  if (poiText.includes(queryText)) return 0.86;
  if (queryText.includes(poiText)) return 0.72;

  let overlap = 0;
  for (const char of new Set([...queryText])) {
    if (poiText.includes(char)) overlap += 1;
  }
  return Math.min(overlap / Math.max(queryText.length, poiText.length), 0.65);
}

function scoreCityMatch(targetCity: string | undefined, poi: AmapPoi): number {
  if (!targetCity) return 0.5;
  const target = normalizeText(targetCity.replace(/市$/u, ""));
  const city = normalizeText(poi.cityname?.replace(/市$/u, ""));
  const district = normalizeText(poi.adname);
  if (!target) return 0.5;
  if (city === target || district === target) return 1;
  if (city.includes(target) || target.includes(city)) return 0.82;
  if (district.includes(target)) return 0.72;
  return 0;
}

function scoreTypeMatch(typeHint: string | undefined, poi: AmapPoi): number {
  if (!typeHint) return 0.6;
  const typeText = `${poi.type ?? ""} ${poi.typecode ?? ""}`;
  const rules: Record<string, RegExp> = {
    hotel: /住宿|酒店|宾馆|旅馆|100/u,
    food: /餐饮|美食|咖啡|050/u,
    museum: /科教文化|博物馆|展览|140/u,
    scenic: /风景名胜|公园|寺庙|110|081/u,
    shopping: /购物|商场|商业街|060/u
  };
  return rules[typeHint]?.test(typeText) ? 1 : 0.35;
}

function scoreDistance(
  point: GeoPoint,
  sameDayConfirmed: ConfirmedItineraryPlace[]
): number {
  if (!sameDayConfirmed.length) return 0.7;
  const minDistance = Math.min(
    ...sameDayConfirmed.map((place) => distanceMeters(point, place.location))
  );
  if (minDistance <= 1500) return 1;
  if (minDistance <= 4000) return 0.82;
  if (minDistance <= 8000) return 0.58;
  if (minDistance <= 15000) return 0.35;
  return 0.12;
}

function scorePoiCandidate(params: {
  candidate: ItineraryPlaceCandidate;
  poi: AmapPoi;
  location: GeoPoint;
  sameDayConfirmed: ConfirmedItineraryPlace[];
}): SpotScoreBreakdown {
  const name = scoreNameMatch(params.candidate.name, params.poi.name ?? "");
  const city = scoreCityMatch(params.candidate.city, params.poi);
  const type = scoreTypeMatch(params.candidate.typeHint, params.poi);
  const distance = scoreDistance(params.location, params.sameDayConfirmed);
  const total = name * 0.42 + city * 0.28 + type * 0.12 + distance * 0.18;

  return {
    name: Number(name.toFixed(3)),
    city: Number(city.toFixed(3)),
    type: Number(type.toFixed(3)),
    distance: Number(distance.toFixed(3)),
    total: Number(total.toFixed(3))
  };
}

function nearestNeighbor(points: ConfirmedItineraryPlace[]): ConfirmedItineraryPlace[] {
  if (points.length <= 2) {
    return points;
  }

  const remaining = points.slice(1);
  const sorted = [points[0]];

  while (remaining.length) {
    const current = sorted[sorted.length - 1];
    let bestIndex = 0;
    let bestDistance = Number.POSITIVE_INFINITY;

    remaining.forEach((candidate, index) => {
      const distance = distanceMeters(current.location, candidate.location);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestIndex = index;
      }
    });

    sorted.push(remaining.splice(bestIndex, 1)[0]);
  }

  return sorted;
}

function sortBySpatialContinuity(
  points: ConfirmedItineraryPlace[]
): ConfirmedItineraryPlace[] {
  const byDay = new Map<number, ConfirmedItineraryPlace[]>();
  for (const point of points) {
    const existing = byDay.get(point.day) ?? [];
    existing.push(point);
    byDay.set(point.day, existing);
  }

  return [...byDay.entries()]
    .sort(([a], [b]) => a - b)
    .flatMap(([, dayPoints]) =>
      nearestNeighbor(dayPoints.sort((a, b) => a.order - b.order))
    );
}

export function extractPlaceCandidates(params: {
  itinerary: Record<string, unknown>;
  requirement: StructuredPayload;
}): ItineraryPlaceCandidate[] {
  const destination = asString(params.requirement.destination);
  const daysRaw = Array.isArray(params.itinerary.days)
    ? params.itinerary.days
    : isRecord(params.itinerary.itinerary) &&
        Array.isArray(params.itinerary.itinerary.days)
      ? params.itinerary.itinerary.days
      : Array.isArray(params.itinerary.items)
        ? [
            {
              day: params.itinerary.day ?? 1,
              theme: params.itinerary.theme,
              items: params.itinerary.items
            }
          ]
      : [];

  const seen = new Set<string>();
  const candidates: ItineraryPlaceCandidate[] = [];

  daysRaw.filter(isRecord).forEach((day, dayIndex) => {
    const dayNumber = normalizeDay(day.day, dayIndex + 1);
    getItems(day).forEach((item, itemIndex) => {
      const name =
        asString(item.name) ||
        asString(item.place) ||
        asString(item.location) ||
        asString(item.title);
      if (!name) {
        return;
      }

      const key = `${dayNumber}:${name}`;
      if (seen.has(key)) {
        return;
      }
      seen.add(key);

      candidates.push({
        day: dayNumber,
        order: itemIndex + 1,
        name,
        city: asString(item.city) || destination || AMAP_CONFIG.defaultCity,
        typeHint: asString(item.typeHint) || inferTypeHint(name, asString(item.note)),
        time: asString(item.time),
        note:
          asString(item.note) ||
          asString(item.reason) ||
          asString(item.description)
      });
    });
  });

  return candidates;
}

type SpotResolveResult =
  | { status: "confirmed"; place: ConfirmedItineraryPlace }
  | { status: "ambiguous" | "unresolved"; rejected: RejectedItineraryPlace };

function toResolvedCandidate(params: {
  poi: AmapPoi;
  location: GeoPoint;
  breakdown: SpotScoreBreakdown;
}): ResolvedSpotCandidate {
  return {
    amapPoiId: params.poi.id,
    name: params.poi.name ?? "",
    city: params.poi.cityname ?? "",
    district: params.poi.adname,
    address: params.poi.address ?? "",
    location: params.location,
    amapType: params.poi.type,
    confidence: params.breakdown.total,
    scoreBreakdown: params.breakdown
  };
}

async function resolveSpot(
  candidate: ItineraryPlaceCandidate,
  sameDayConfirmed: ConfirmedItineraryPlace[]
): Promise<SpotResolveResult> {
  const key = getAmapServerKey();
  if (!key) {
    return {
      status: "unresolved",
      rejected: {
        ...candidate,
        status: "unresolved",
        reason: "amap key is not configured"
      }
    };
  }

  const url = new URL("https://restapi.amap.com/v3/place/text");
  url.searchParams.set("key", key);
  url.searchParams.set("keywords", candidate.name);
  url.searchParams.set("city", candidate.city || AMAP_CONFIG.defaultCity);
  url.searchParams.set("citylimit", "true");
  url.searchParams.set("offset", "10");
  url.searchParams.set("page", "1");
  url.searchParams.set("extensions", "base");

  const response = await fetch(url.toString());
  if (!response.ok) {
    return {
      status: "unresolved",
      rejected: {
        ...candidate,
        status: "unresolved",
        reason: `poi_search_http_${response.status}`
      }
    };
  }

  const data = (await response.json()) as AmapPlaceTextResponse;
  if (data.status !== "1" || !data.pois?.length) {
    return {
      status: "unresolved",
      rejected: {
        ...candidate,
        status: "unresolved",
        reason: data.info ? `poi_not_found:${data.info}` : "poi_not_found"
      }
    };
  }

  const cityFilteredPois = data.pois.filter((poi) => scoreCityMatch(candidate.city, poi) >= 0.72);
  if (!cityFilteredPois.length) {
    return {
      status: "unresolved",
      rejected: {
        ...candidate,
        status: "unresolved",
        reason: `poi_outside_target_city:${candidate.city || AMAP_CONFIG.defaultCity}`
      }
    };
  }

  const scored = cityFilteredPois
    .map((poi) => {
      const location = parseLocation(poi.location);
      if (!location) return null;
      const scoreBreakdown = scorePoiCandidate({
        candidate,
        poi,
        location,
        sameDayConfirmed
      });
      return {
        poi,
        location,
        scoreBreakdown,
        resolved: toResolvedCandidate({ poi, location, breakdown: scoreBreakdown })
      };
    })
    .filter((item): item is NonNullable<typeof item> => Boolean(item))
    .sort((a, b) => b.scoreBreakdown.total - a.scoreBreakdown.total);

  if (!scored.length) {
    return {
      status: "unresolved",
      rejected: {
        ...candidate,
        status: "unresolved",
        reason: "poi_without_location"
      }
    };
  }

  const best = scored[0];
  const runnerUp = scored[1];
  const confidence = best.scoreBreakdown.total;
  const gap = runnerUp ? confidence - runnerUp.scoreBreakdown.total : 1;
  const cityMatched = best.scoreBreakdown.city >= 0.72;
  const nameMatched = best.scoreBreakdown.name >= 0.72;

  if (!cityMatched || !nameMatched || confidence < 0.72) {
    return {
      status: "unresolved",
      rejected: {
        ...candidate,
        status: "unresolved",
        reason: "low_confidence",
        candidates: scored.slice(0, 5).map((item) => item.resolved)
      }
    };
  }

  if (runnerUp && gap < 0.08) {
    return {
      status: "ambiguous",
      rejected: {
        ...candidate,
        status: "ambiguous",
        reason: "multiple_close_candidates",
        candidates: scored.slice(0, 5).map((item) => item.resolved)
      }
    };
  }

  return {
    status: "confirmed",
    place: {
      ...candidate,
      status: "confirmed",
      id: `${candidate.day}-${candidate.order}-${best.poi.id ?? candidate.name}`,
      address: best.poi.address ?? "",
      location: best.location,
      amapPoiId: best.poi.id,
      amapType: best.poi.type,
      confidence,
      scoreBreakdown: best.scoreBreakdown
    }
  };
}

async function requestSegment(
  from: ConfirmedItineraryPlace,
  to: ConfirmedItineraryPlace,
  mode: "walking" | "driving"
): Promise<RouteSegment | null> {
  const key = getAmapServerKey();
  if (!key) {
    return null;
  }

  const url = new URL(`https://restapi.amap.com/v3/direction/${mode}`);
  url.searchParams.set("key", key);
  url.searchParams.set("origin", pointToAmap(from.location));
  url.searchParams.set("destination", pointToAmap(to.location));

  const response = await fetch(url.toString());
  if (!response.ok) {
    return null;
  }

  const data = (await response.json()) as AmapDirectionResponse;
  const path = data.route?.paths?.[0];
  if (data.status !== "1" || !path) {
    return null;
  }

  const polyline = (path.steps ?? []).flatMap((step) => parsePolyline(step.polyline));
  return {
    fromPlaceId: from.id,
    toPlaceId: to.id,
    distanceMeters: path.distance ? Number(path.distance) : null,
    durationSeconds: path.duration ? Number(path.duration) : null,
    polyline: polyline.length ? polyline : [from.location, to.location],
    provider: "amap",
    mode
  };
}

async function buildSegments(
  points: ConfirmedItineraryPlace[]
): Promise<RouteSegment[]> {
  if (points.length < 2) return [];

  const segmentPromises = points.slice(0, -1).map(async (from, index) => {
    const to = points[index + 1];
    const mode: "walking" | "driving" =
      distanceMeters(from.location, to.location) <= 5000 ? "walking" : "driving";
    const segment =
      (await requestSegment(from, to, mode)) ??
      (await requestSegment(from, to, "driving"));

    return segment ?? {
      fromPlaceId: from.id,
      toPlaceId: to.id,
      distanceMeters: Math.round(distanceMeters(from.location, to.location)),
      durationSeconds: null,
      polyline: [from.location, to.location],
      provider: "amap",
      mode: "straight"
    };
  });

  return Promise.all(segmentPromises);
}

export async function buildItineraryRoutePlan(params: {
  itinerary: Record<string, unknown>;
  requirement: StructuredPayload;
}): Promise<ItineraryRoutePlan> {
  const candidates = extractPlaceCandidates(params);
  const warnings: string[] = [];
  const rejected: ItineraryRoutePlan["rejected_candidates"] = [];

  if (!getAmapServerKey()) {
    return {
      status: "skipped",
      provider: "amap",
      candidates,
      confirmed_points: [],
      rejected_candidates: candidates.map((candidate) => ({
        ...candidate,
        status: "unresolved",
        reason: "amap key is not configured"
      })),
      sorted_place_ids: [],
      segments: [],
      polyline: [],
      warnings: ["AMap Web Service key is not configured; route planning skipped."]
    };
  }

  const confirmed: ConfirmedItineraryPlace[] = [];
  const resolveResults = await Promise.all(
    candidates.map(async (candidate) => {
      const sameDayConfirmed = confirmed.filter((place) => place.day === candidate.day);
      return { candidate, result: await resolveSpot(candidate, sameDayConfirmed) };
    })
  );

  for (const { candidate, result } of resolveResults) {
    if (result.status === "confirmed") {
      confirmed.push(result.place);
    } else {
      rejected.push(result.rejected);
    }
  }

  // Only confirmed points are eligible for spatial sorting and route planning.
  const sorted = sortBySpatialContinuity(confirmed);
  const segments = await buildSegments(sorted);
  const polyline = segments.flatMap((segment) => segment.polyline);

  if (rejected.length) {
    warnings.push(`${rejected.length} place candidate(s) were not confirmed by AMap.`);
  }
  if (confirmed.length < 2) {
    warnings.push("Fewer than two confirmed places; route polyline is incomplete.");
  }

  return {
    status: confirmed.length >= 2 ? "ready" : confirmed.length ? "partial" : "skipped",
    provider: "amap",
    candidates,
    confirmed_points: sorted,
    rejected_candidates: rejected,
    sorted_place_ids: sorted.map((point) => point.id),
    segments,
    polyline,
    warnings
  };
}

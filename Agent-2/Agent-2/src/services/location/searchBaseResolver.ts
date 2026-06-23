import type { Env, GeoPoint, LocationScope, StructuredPayload } from "../../types";

export function normalizeLocationScope(value: unknown): LocationScope {
  const text = String(value ?? "").trim();
  if (text === "surrounding" || text === "nearby" || text === "city_only") {
    return text;
  }
  return "city_only";
}

export function buildSearchKeywordVariants(params: {
  destination: string;
  keyword: string;
  locationScope: LocationScope;
}): string[] {
  const variants = [params.keyword.trim()];
  const stripped = params.keyword.replace(new RegExp(`^${params.destination}\\s*`), "").trim();
  if (!stripped) return variants;
  if (params.locationScope === "nearby") {
    variants.push(`${params.destination}附近 ${stripped}`.trim());
    variants.push(`${params.destination}周边 ${stripped}`.trim());
  }
  if (params.locationScope === "surrounding") {
    variants.push(`${params.destination}周边 ${stripped}`.trim());
    variants.push(`${params.destination}近郊 ${stripped}`.trim());
  }
  return Array.from(new Set(variants)).slice(0, 3);
}

function normalizeGeoPoint(value: unknown): GeoPoint | undefined {
  if (!value || typeof value !== "object") return undefined;
  const lng = Number((value as Record<string, unknown>).lng);
  const lat = Number((value as Record<string, unknown>).lat);
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) return undefined;
  return { lng, lat };
}

export async function resolveSearchBasePayload(params: {
  env?: Env;
  payload: StructuredPayload;
  existingPayload?: StructuredPayload;
  userLocation?: GeoPoint;
}): Promise<StructuredPayload> {
  const next: StructuredPayload = {
    ...params.payload
  };
  const explicitDestination = String(next.destination ?? "").trim();
  const mergedUserLocation = normalizeGeoPoint(params.userLocation ?? next.user_location ?? params.existingPayload?.user_location);

  if (mergedUserLocation) {
    next.user_location = mergedUserLocation;
  }

  next.location_scope = normalizeLocationScope(next.location_scope);

  if (explicitDestination) {
    next.city_source = "user_explicit";
    return next;
  }

  if (!next.city_source) {
    next.city_source = "fallback_question";
  }
  return next;
}

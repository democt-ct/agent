import type { PlaceCandidatePoolItem, StructuredPayload } from "../../types";
import { getBaseMianyangPool } from "./mianyangCandidatePool";

const STATIC_POOL_REGISTRY: Record<string, () => PlaceCandidatePoolItem[]> = {
  "\u7ef5\u9633": getBaseMianyangPool
};

export function shouldUseCityStaticPool(requirement: StructuredPayload): boolean {
  return requirement.enable_city_static_pool === true;
}

export function getOptionalCityStaticPool(requirement: StructuredPayload): PlaceCandidatePoolItem[] {
  if (!shouldUseCityStaticPool(requirement)) return [];
  const destination = String(requirement.destination ?? "").trim();
  const provider = STATIC_POOL_REGISTRY[destination];
  return provider ? provider() : [];
}

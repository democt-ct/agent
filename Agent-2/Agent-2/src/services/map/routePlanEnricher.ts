import type { ItineraryGenerationResult, StructuredPayload } from "../../types";
import { buildItineraryRoutePlan } from "./amapRoutePlanner";

export async function enhanceItineraryWithRoutePlan(params: {
  result: ItineraryGenerationResult;
  requirement: StructuredPayload;
}): Promise<ItineraryGenerationResult> {
  try {
    const routePlan = await buildItineraryRoutePlan({
      itinerary: params.result.itinerary,
      requirement: params.requirement
    });

    return {
      ...params.result,
      itinerary: {
        ...params.result.itinerary,
        route_plan: routePlan
      },
      warnings: [...params.result.warnings, ...routePlan.warnings]
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown route plan error";
    return {
      ...params.result,
      warnings: [...params.result.warnings, `Route planning skipped: ${message}`]
    };
  }
}

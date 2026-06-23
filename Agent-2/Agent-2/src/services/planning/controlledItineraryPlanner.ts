import type {
  DayScheduleSlot,
  ItineraryGenerationResult,
  StructuredPayload
} from "../../types";
import {
  getBaseMianyangPool,
  getExtendedMianyangPool,
  hasPreferenceEnhancement,
  wantsNature
} from "./mianyangCandidatePool";
import { shouldUseCityStaticPool } from "./cityStaticPoolProvider";

export type PlanningMode = "generic_city" | "preference_enhanced";

const DAY_TEMPLATE: DayScheduleSlot[] = [
  {
    slot: "morning",
    timeLabel: "\u4e0a\u5348",
    role: "main_activity",
    categories: ["landmark", "museum", "park", "nature"]
  },
  {
    slot: "lunch",
    timeLabel: "\u4e2d\u5348",
    role: "meal",
    categories: ["food"]
  },
  {
    slot: "afternoon",
    timeLabel: "\u4e0b\u5348",
    role: "relax",
    categories: ["cafe", "mall", "citywalk", "park"]
  },
  {
    slot: "evening",
    timeLabel: "\u665a\u4e0a",
    role: "night",
    categories: ["nightview", "food", "citywalk"]
  }
];

export function enforceControlledItinerary(params: {
  result: ItineraryGenerationResult;
  requirement: StructuredPayload;
}): ItineraryGenerationResult {
  return params.result;
}

export function getMianyangPoolForLlm(requirement: StructuredPayload) {
  if (!shouldUseCityStaticPool(requirement) || requirement.destination !== "\u7ef5\u9633") {
    return null;
  }
  const shouldEnhance = hasPreferenceEnhancement(requirement);
  const allowNature = shouldEnhance && wantsNature(requirement);
  const candidates = (shouldEnhance ? getExtendedMianyangPool() : getBaseMianyangPool()).filter(
    (item) => allowNature || item.zone !== "nearby_nature"
  );

  return {
    mode: shouldEnhance ? "preference_enhanced" : "generic_city",
    generator: "llm_only",
    template: DAY_TEMPLATE.map((slot) => ({
      slot: slot.slot,
      time: slot.timeLabel,
      role: slot.role,
      categories: slot.categories
    })),
    rules: {
      no_backend_itinerary_fallback: true,
      no_free_place_generation: true,
      avoid_duplicate_same_name_or_nearby: true,
      avoid_single_category_stack: true,
      nearby_nature_per_day_limit: allowNature ? 1 : 0
    },
    candidates: candidates.map((item) => ({
      id: item.id,
      name: item.name,
      zone: item.zone,
      tier: item.poolTier,
      category: item.category,
      tags: item.tags
    }))
  };
}

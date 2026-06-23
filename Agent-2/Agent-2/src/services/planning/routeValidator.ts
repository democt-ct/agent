import type {
  CandidatePool,
  CandidateGovernanceSummary,
  PlannedDay,
  PlannerOutput,
  RouteValidationIssue,
  RouteValidationResult
} from "../../types";
import { isGenericQueryTerm, isRealPlaceName, hasValidPoiSource, isGenericDayTheme, isFoodSuitableForMealSlot } from "../candidates/genericTermFilter";

function averageItemsPerDay(days: PlannedDay[]): number {
  if (!days.length) return 0;
  return days.reduce((sum, day) => sum + day.items.length, 0) / days.length;
}

function getCategoryText(day: PlannedDay): string {
  return day.items.map((item) => `${item.name} ${item.category} ${item.reason}`).join(" ");
}

function buildGranularityAudit(params: {
  candidatePool: CandidatePool;
  plannerOutput: PlannerOutput;
}): CandidateGovernanceSummary {
  const days = params.plannerOutput.itinerary.days;
  return {
    planningMode: params.plannerOutput.governanceSummary?.planningMode ?? params.candidatePool.planningMode ?? "city_trip",
    containsInternalPoiInDayItems: days.some((day) => day.items.some((item) => item.granularity === "internal_poi_level")),
    containsServiceLevelInDayItems: days.some((day) => day.items.some((item) => item.granularity === "service_level")),
    dailyMainItemCounts: days.map((day) => ({ day: day.day, count: day.items.length })),
    subStopsCount: days.reduce((sum, day) => sum + day.items.reduce((itemSum, item) => itemSum + (item.subStops?.length ?? 0), 0), 0),
    hasLinkedNightView: days.some((day) => day.items.some((item) => Boolean(item.nightView) || Boolean(item.linkedPoiId))),
    hasFoodWalkMerge: days.some((day) => day.items.some((item) => (item.roles ?? []).includes("walk") && (item.roles ?? []).includes("food")))
  };
}

export function validatePlannedRoute(params: {
  candidatePool: CandidatePool;
  plannerOutput: PlannerOutput;
}): RouteValidationResult {
  const days = params.plannerOutput.itinerary.days;
  const problems: string[] = [];
  const lowQualityItems: RouteValidationIssue[] = [];
  const weak_anchor_days: number[] = [];
  const skipped_slots: Array<{ day: number; slot: string; reason: string }> = [];
  const repaired_day_structure = days.map((day) => ({
    day: day.day,
    theme: day.theme,
    segment_summary: (day.segments ?? []).map((segment) => `${segment.slot}:${segment.strategy}`)
  }));
  const granularityAudit = buildGranularityAudit(params);

  const cityPool = params.plannerOutput.citySignaturePool ?? params.candidatePool.citySignaturePool;
  const coverage = params.plannerOutput.coverageCheck ?? params.candidatePool.coverageCheck;
  if (coverage?.missing_items.length) {
    problems.push(`coverage missing: ${coverage.missing_items.join(", ")}`);
  }

  for (const day of days) {
    if (isGenericDayTheme(day.theme)) {
      problems.push(`Day ${day.day} has generic/fallback theme: "${day.theme}"`);
      lowQualityItems.push({
        name: day.theme,
        problem: "day theme contains internal state or generic words",
        action: "replace"
      });
    }

    for (const item of day.items) {
      if (isGenericQueryTerm(item.name)) {
        problems.push(`Day ${day.day} item "${item.name}" is a generic query term`);
        lowQualityItems.push({
          name: item.name,
          problem: "generic query term used as route item",
          action: "remove"
        });
      }
      if (!isRealPlaceName(item.name)) {
        problems.push(`Day ${day.day} item "${item.name}" is not a valid place name`);
        lowQualityItems.push({
          name: item.name,
          problem: "invalid place name",
          action: "remove"
        });
      }
      if (!hasValidPoiSource({ source: item.source, location: item.location, tags: [], name: item.name, city: "", category: item.category } as any)) {
        problems.push(`Day ${day.day} item "${item.name}" lacks valid POI source`);
        lowQualityItems.push({
          name: item.name,
          problem: "missing valid POI source or location",
          action: "remove"
        });
      }
      if (item.granularity === "service_level" || item.granularity === "internal_poi_level") {
        problems.push(`Day ${day.day} item "${item.name}" has inappropriate granularity: ${item.granularity}`);
        lowQualityItems.push({
          name: item.name,
          problem: `granularity ${item.granularity} should not be main item`,
          action: "remove"
        });
      }
      if (item.category === "food" && !isFoodSuitableForMealSlot({ category: item.category, name: item.name, tags: [] } as any, item.timeSlot)) {
        problems.push(`Day ${day.day} item "${item.name}" is unsuitable for ${item.timeSlot}`);
        lowQualityItems.push({
          name: item.name,
          problem: `food type unsuitable for ${item.timeSlot}`,
          action: "replace"
        });
      }
    }

    const text = getCategoryText(day);
    if (!/(food|mall|citywalk|nightview|park|museum|landmark|nature)/i.test(text) && day.items.length >= 2) {
      problems.push(`Day ${day.day} lacks travel-shaped categories`);
    }
    const first = day.items[0];
    if (!first || (first.score ?? 0) < 45) {
      weak_anchor_days.push(day.day);
    }
    const existingSlots = new Set((day.segments ?? []).map((segment) => segment.slot));
    for (const required of ["afternoon", "evening"] as const) {
      if (!existingSlots.has(required) || !day.items.some((item) => item.timeSlot === required)) {
        skipped_slots.push({ day: day.day, slot: required, reason: "slot not filled with a main itinerary item" });
      }
    }
    if (day.items.length < 3) {
      problems.push(`Day ${day.day} has fewer than 3 playable items`);
    }
  }

  if (granularityAudit.containsInternalPoiInDayItems) {
    problems.push("internal_poi_level leaked into day.items");
    lowQualityItems.push({
      name: "internal_poi_level",
      problem: "internal POIs should stay as subStops in city_trip mode",
      action: "remove"
    });
  }
  if (granularityAudit.containsServiceLevelInDayItems) {
    problems.push("service_level leaked into day.items");
    lowQualityItems.push({
      name: "service_level",
      problem: "service POIs should not be main itinerary items",
      action: "remove"
    });
  }

  const avg = averageItemsPerDay(days);
  const fatigueAssessment =
    avg >= 5 ? "dense" :
    avg >= 4 ? "moderate" :
    "relaxed";
  if (avg >= 5) {
    problems.push("average daily item count is too dense");
  }

  const foodAssessment = days.some((day) =>
    (day.segments ?? []).some((segment) => segment.strategy === "food_cluster" || segment.strategy === "meal_stop")
  )
    ? "food strategy present"
    : "food strategy is weak";

  const missingCitySignatureItems = (cityPool?.must_visit_attractions ?? [])
    .filter((item) =>
      !days.some((day) => day.items.some((planned) => planned.name.includes(item.name) || item.name.includes(planned.name)))
    )
    .slice(0, 6)
    .map((item) => item.name);

  if (missingCitySignatureItems.length) {
    problems.push("some city signature attractions were not represented");
  }
  if (weak_anchor_days.length) {
    problems.push(`weak day anchors: ${weak_anchor_days.join(", ")}`);
  }
  if (skipped_slots.length) {
    problems.push("afternoon or evening slots were skipped");
  }

  return {
    is_valid: problems.length === 0,
    main_problems: problems,
    low_quality_items: lowQualityItems,
    missing_city_signature_items: missingCitySignatureItems,
    weak_anchor_days,
    skipped_slots,
    route_fatigue_assessment: fatigueAssessment,
    food_strategy_assessment: foodAssessment,
    repair_suggestions: [
      coverage?.missing_items.length ? "add missing must-visit, food, or night candidates before planning" : "",
      missingCitySignatureItems.length ? "promote uncovered signature attractions into anchor clusters" : "",
      avg >= 5 ? "reduce daily item density or merge nearby stops" : "",
      granularityAudit.containsInternalPoiInDayItems ? "merge internal POIs back into parent attractions" : "",
      granularityAudit.containsServiceLevelInDayItems ? "drop service POIs from main itinerary" : "",
      lowQualityItems.some((item) => item.problem.includes("generic")) ? "filter generic query terms from candidate pool" : "",
      lowQualityItems.some((item) => item.problem.includes("theme")) ? "generate meaningful day themes" : ""
    ].filter(Boolean),
    repaired_day_structure,
    granularity_audit: granularityAudit
  };
}

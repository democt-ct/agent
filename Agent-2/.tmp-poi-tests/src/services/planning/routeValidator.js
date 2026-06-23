function averageItemsPerDay(days) {
    if (!days.length)
        return 0;
    return days.reduce((sum, day) => sum + day.items.length, 0) / days.length;
}
function getCategoryText(day) {
    return day.items.map((item) => `${item.name} ${item.category} ${item.reason}`).join(" ");
}
function buildGranularityAudit(params) {
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
export function validatePlannedRoute(params) {
    const days = params.plannerOutput.itinerary.days;
    const problems = [];
    const lowQualityItems = [];
    const weak_anchor_days = [];
    const skipped_slots = [];
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
        const text = getCategoryText(day);
        if (!/(food|mall|citywalk|nightview|park|museum|landmark|nature)/i.test(text) && day.items.length >= 2) {
            problems.push(`Day ${day.day} lacks travel-shaped categories`);
        }
        const first = day.items[0];
        if (!first || (first.score ?? 0) < 45) {
            weak_anchor_days.push(day.day);
        }
        const existingSlots = new Set((day.segments ?? []).map((segment) => segment.slot));
        for (const required of ["afternoon", "evening"]) {
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
    const fatigueAssessment = avg >= 5 ? "dense" :
        avg >= 4 ? "moderate" :
            "relaxed";
    if (avg >= 5) {
        problems.push("average daily item count is too dense");
    }
    const foodAssessment = days.some((day) => (day.segments ?? []).some((segment) => segment.strategy === "food_cluster" || segment.strategy === "meal_stop"))
        ? "food strategy present"
        : "food strategy is weak";
    const missingCitySignatureItems = (cityPool?.must_visit_attractions ?? [])
        .filter((item) => !days.some((day) => day.items.some((planned) => planned.name.includes(item.name) || item.name.includes(planned.name))))
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
            granularityAudit.containsServiceLevelInDayItems ? "drop service POIs from main itinerary" : ""
        ].filter(Boolean),
        repaired_day_structure,
        granularity_audit: granularityAudit
    };
}

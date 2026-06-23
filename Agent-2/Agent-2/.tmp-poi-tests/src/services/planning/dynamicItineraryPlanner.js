import { buildTravelPlanningStructure, ensurePlannerEligibility, getPlannerCategory, isPlannerSelectable } from "./anchorClusterPlanner";
import { buildCitySignaturePool, checkCityCoverage } from "./citySignaturePool";
import { resolvePreferenceProfile } from "./profileResolver";
import { getDayOverrideForSlot } from "../replan/replanDirectives";
import { validatePlannedRoute } from "./routeValidator";
const DAY_TEMPLATES = {
    arrival: {
        name: "arrival",
        slots: [
            { slot: "morning", label: "arrival", categories: ["scenic", "walk"] },
            { slot: "lunch", label: "lunch", categories: ["food"] },
            { slot: "afternoon", label: "settle", categories: ["walk", "food"] },
            { slot: "evening", label: "night", categories: ["scenic", "food", "walk"] }
        ]
    },
    balanced: {
        name: "balanced",
        slots: [
            { slot: "morning", label: "main", categories: ["scenic", "walk"] },
            { slot: "lunch", label: "lunch", categories: ["food"] },
            { slot: "afternoon", label: "stroll", categories: ["walk", "food", "scenic"] },
            { slot: "evening", label: "night", categories: ["scenic", "food", "walk"] }
        ]
    },
    foodie: {
        name: "foodie",
        slots: [
            { slot: "morning", label: "start", categories: ["walk", "scenic"] },
            { slot: "lunch", label: "lunch", categories: ["food"] },
            { slot: "afternoon", label: "cafe", categories: ["food", "walk"] },
            { slot: "evening", label: "night", categories: ["scenic", "food", "walk"] }
        ]
    },
    closing: {
        name: "closing",
        slots: [
            { slot: "morning", label: "final-start", categories: ["scenic", "walk"] },
            { slot: "lunch", label: "lunch", categories: ["food"] },
            { slot: "afternoon", label: "final", categories: ["walk", "food", "scenic"] },
            { slot: "evening", label: "return-night", categories: ["scenic", "food"] }
        ]
    },
    nature: {
        name: "nature",
        slots: [
            { slot: "morning", label: "nature", categories: ["scenic", "walk"] },
            { slot: "lunch", label: "lunch", categories: ["food"] },
            { slot: "afternoon", label: "stroll", categories: ["walk", "food", "scenic"] },
            { slot: "evening", label: "night", categories: ["scenic", "food"] }
        ]
    }
};
const SLOT_PRIORITY = {
    morning: ["scenic", "walk"],
    lunch: ["food"],
    afternoon: ["walk", "food", "scenic"],
    evening: ["scenic", "food", "walk"]
};
const INTEREST_CATEGORY_RULES = [
    { category: "food", patterns: [/food|restaurant|eat|meal|\u9910|\u7f8e\u98df|\u5c0f\u5403/i] },
    { category: "cafe", patterns: [/cafe|coffee|\u5496\u5561|\u4e0b\u5348\u8336/i] },
    { category: "mall", patterns: [/mall|shopping|\u5546\u573a|\u8d2d\u7269|\u5546\u5708/i] },
    { category: "citywalk", patterns: [/citywalk|walk|stroll|\u6f2b\u6b65|\u8857\u533a|\u8001\u8857/i] },
    { category: "nightview", patterns: [/night|view|\u591c\u666f|\u591c\u5e02|\u591c\u6e38|\u89c2\u666f/i] },
    { category: "park", patterns: [/park|green|\u516c\u56ed|\u7eff\u5730|\u6563\u6b65/i] },
    { category: "nature", patterns: [/nature|scenic|mountain|lake|\u81ea\u7136|\u98ce\u5149|\u5c71|\u6e56/i] },
    { category: "museum", patterns: [/museum|history|culture|\u535a\u7269\u9986|\u5c55\u89c8|\u5386\u53f2|\u6587\u5316/i] }
];
function normalizeText(value) {
    return value.trim().toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}
function distanceMeters(a, b) {
    const earthRadius = 6371000;
    const toRad = (degree) => (degree * Math.PI) / 180;
    const dLat = toRad(b.lat - a.lat);
    const dLng = toRad(b.lng - a.lng);
    const lat1 = toRad(a.lat);
    const lat2 = toRad(b.lat);
    const h = Math.sin(dLat / 2) ** 2 +
        Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
    return Math.round(2 * earthRadius * Math.asin(Math.sqrt(h)));
}
function getTripDays(requirement) {
    const raw = Number(requirement.trip_days ?? 1);
    if (!Number.isFinite(raw) || raw <= 0)
        return 1;
    return Math.min(Math.max(Math.round(raw), 1), 7);
}
function getInterests(requirement) {
    return Array.isArray(requirement.interests)
        ? requirement.interests.map((item) => String(item).trim()).filter(Boolean)
        : [];
}
function getPace(requirement) {
    return String(requirement.preferredPace ?? requirement.preferred_pace ?? "").trim();
}
function getDistanceTolerance(requirement) {
    return String(requirement.distanceTolerance ?? requirement.distance_tolerance ?? "").trim();
}
function buildCategoryPriorityMap(queryPlan) {
    const map = new Map();
    if (!queryPlan)
        return map;
    for (const item of queryPlan.categories) {
        map.set(item.category, Math.max(map.get(item.category) ?? 0, item.priority));
    }
    return map;
}
function candidatePlannerCategory(candidate) {
    return candidate.plannerCategory ?? getPlannerCategory(candidate);
}
function normalizePlannerCategoryLabel(value) {
    const text = normalizeText(value);
    if (/food|cafe|meal|restaurant|localfood|foodarea/.test(text))
        return "food";
    if (/walk|citywalk|park|mall|shopping|stroll|area/.test(text))
        return "walk";
    if (/scenic|core|culture|history|nature|night|museum|landmark/.test(text))
        return "scenic";
    return "supplemental";
}
function categoryMatchesPlannerChoice(candidateCategory, choice) {
    return candidateCategory === normalizePlannerCategoryLabel(choice);
}
function buildContentSignalBoost(candidate, contentSignals) {
    if (!contentSignals?.length)
        return { bonus: 0, reasons: [] };
    const candidateText = normalizeText(`${candidate.name} ${candidate.description ?? ""} ${candidate.tags.join(" ")}`);
    let bonus = 0;
    const reasons = [];
    if (candidate.source === "content_search") {
        bonus += 3;
        reasons.push("content source");
    }
    for (const signal of contentSignals.slice(0, 8)) {
        const placeMatch = signal.extractedPlaceNames.some((name) => {
            const normalizedName = normalizeText(name);
            return normalizedName && (candidateText.includes(normalizedName) || normalizedName.includes(normalizeText(candidate.name)));
        });
        if (placeMatch) {
            bonus += 8;
            reasons.push("content place match");
        }
        if (signal.categoryHints.includes(candidate.category)) {
            bonus += 3;
            reasons.push("content category hint");
        }
        if (signal.sceneTags.some((tag) => candidateText.includes(normalizeText(tag)))) {
            bonus += 1;
            reasons.push("content scene match");
        }
    }
    return { bonus: Math.min(bonus, 24), reasons: reasons.slice(0, 6) };
}
function getTemplateName(requirement, day, daysCount) {
    const interests = getInterests(requirement);
    const pace = getPace(requirement);
    if (day === 1)
        return "arrival";
    if (day === daysCount)
        return "closing";
    if (interests.some((item) => /food|cafe|shopping|\u7f8e\u98df|\u5496\u5561|\u5546\u573a/i.test(item))) {
        return "foodie";
    }
    if (interests.some((item) => /nature|scenic|\u81ea\u7136|\u666f\u533a|\u5c71|\u6e56/i.test(item))) {
        return "nature";
    }
    if (pace === "relaxed") {
        return "balanced";
    }
    return "balanced";
}
function getDayTemplate(requirement, day, daysCount) {
    return DAY_TEMPLATES[getTemplateName(requirement, day, daysCount)];
}
function buildEffectiveDayTemplate(requirement, day, daysCount) {
    const base = getDayTemplate(requirement, day, daysCount);
    return {
        ...base,
        slots: base.slots.map((slot) => {
            const override = getDayOverrideForSlot(requirement.replan_directives, day, slot.slot);
            const globalAvoid = new Set((requirement.replan_directives?.global?.avoid_categories ?? []).map((item) => normalizePlannerCategoryLabel(String(item))));
            const overridePreferred = (override?.preferred_categories ?? []).map((item) => normalizePlannerCategoryLabel(String(item)));
            const overrideAvoid = new Set((override?.avoid_categories ?? []).map((item) => normalizePlannerCategoryLabel(String(item))));
            const categories = [
                ...overridePreferred,
                ...slot.categories.filter((item) => !globalAvoid.has(item) && !overrideAvoid.has(item))
            ];
            return {
                ...slot,
                categories: Array.from(new Set(categories))
            };
        })
    };
}
function maxItemsPerDay(requirement) {
    if (requirement.replan_directives?.global?.preferred_pace === "relaxed" || requirement.replan_directives?.global?.reduce_transfers) {
        return 3;
    }
    return 4;
}
export function dedupePlannerCandidates(candidates) {
    const result = [];
    const seen = new Set();
    for (const candidate of candidates) {
        const nameCity = `${normalizeText(candidate.city)}:${normalizeText(candidate.name)}`;
        const source = candidate.sourceRef ? `${candidate.source}:${candidate.sourceRef}` : "";
        const location = candidate.location
            ? `${candidate.location.lng.toFixed(4)},${candidate.location.lat.toFixed(4)}`
            : "";
        const key = source || `${nameCity}:${location}`;
        if (seen.has(key) || seen.has(nameCity))
            continue;
        seen.add(key);
        seen.add(nameCity);
        result.push(candidate);
    }
    return result;
}
function interestMatchesCandidate(candidate, requirement) {
    const text = normalizeText(`${candidate.name} ${candidate.description ?? ""} ${candidate.tags.join(" ")}`);
    const interests = getInterests(requirement);
    return interests.some((interest) => text.includes(normalizeText(interest)));
}
function buildSignatureLookup(pool) {
    const map = new Map();
    if (!pool)
        return map;
    const all = [
        ...pool.must_visit_attractions,
        ...pool.famous_foods,
        ...pool.food_areas,
        ...pool.shopping_areas,
        ...pool.night_options,
        ...pool.local_experiences,
        ...pool.backup_day_trips
    ];
    for (const item of all) {
        if (item.candidateId)
            map.set(item.candidateId, item);
    }
    return map;
}
function getUserPreferenceScore(candidate, requirement, profile) {
    const plannerCategory = candidatePlannerCategory(candidate);
    let score = 40;
    if (interestMatchesCandidate(candidate, requirement))
        score += 35;
    if (profile.preference_params.food_priority === "high" && plannerCategory === "food")
        score += 16;
    if (profile.preference_params.famous_spot_priority === "high" && plannerCategory === "scenic")
        score += 16;
    if (profile.preference_params.hidden_gem_priority === "high" && plannerCategory === "walk")
        score += 12;
    if (profile.preference_params.walking_preference === "low" && plannerCategory === "walk")
        score -= 8;
    return Math.max(0, Math.min(100, score));
}
function getQualityScore(candidate, contentSignals) {
    let score = Math.round(candidate.confidence * 70);
    if (candidate.source === "mcp_poi")
        score += 18;
    if (candidate.source === "static_pool")
        score += 10;
    const contentBoost = buildContentSignalBoost(candidate, contentSignals);
    score += Math.min(contentBoost.bonus, 12);
    if (candidate.location)
        score += 6;
    return Math.max(0, Math.min(100, score));
}
function scoreCandidate(candidate, requirement, preferenceProfile, signatureLookup, categoryPriorityMap, contentSignals) {
    const interests = getInterests(requirement);
    const reasons = [];
    const signatureSummary = signatureLookup.get(candidate.id);
    const citySignatureScore = Math.max(0, Math.min(100, signatureSummary?.city_signature_score ?? candidate.citySignatureScore ?? 38));
    const userPreferenceScore = getUserPreferenceScore(candidate, requirement, preferenceProfile);
    const qualityScore = getQualityScore(candidate, contentSignals);
    let routeFitScore = 50;
    let distanceScore = candidate.location ? 72 : 35;
    if (candidate.location) {
        reasons.push("has location");
    }
    else {
        distanceScore -= 14;
    }
    if (candidate.source === "static_pool") {
        reasons.push("curated static pool");
    }
    else if (candidate.source === "mcp_poi") {
        reasons.push("AMap POI");
    }
    else if (candidate.source === "content_search") {
        reasons.push("content recommendation signal");
    }
    else if (candidate.source === "mcp_search") {
        reasons.push("web search");
    }
    const contentBoost = buildContentSignalBoost(candidate, contentSignals);
    if (contentBoost.bonus > 0) {
        routeFitScore += Math.min(8, Math.round(contentBoost.bonus * 0.4));
        reasons.push(...contentBoost.reasons);
    }
    if (interestMatchesCandidate(candidate, requirement)) {
        reasons.push("interest match");
    }
    const plannerCategory = candidatePlannerCategory(candidate);
    if (interests.some((interest) => normalizeText(interest).includes(normalizeText(plannerCategory)))) {
        routeFitScore += 8;
        reasons.push(`category aligned: ${plannerCategory}`);
    }
    if (plannerCategory === "food" || plannerCategory === "scenic") {
        routeFitScore += 4;
    }
    if (getDistanceTolerance(requirement) === "urban_only" && plannerCategory === "walk") {
        distanceScore -= 12;
    }
    const categoryPriority = categoryPriorityMap?.get(candidate.category) ?? 0;
    if (categoryPriority > 0) {
        routeFitScore += categoryPriority * 4;
        reasons.push(`query priority: ${categoryPriority}`);
    }
    if (signatureSummary) {
        reasons.push(`city signature: ${signatureSummary.suggested_role}`);
    }
    const finalScore = citySignatureScore * 0.3 +
        userPreferenceScore * 0.2 +
        qualityScore * 0.2 +
        Math.max(0, Math.min(100, routeFitScore)) * 0.2 +
        Math.max(0, Math.min(100, distanceScore)) * 0.1;
    candidate.citySignatureScore = citySignatureScore;
    candidate.userPreferenceScore = userPreferenceScore;
    candidate.qualityScore = qualityScore;
    candidate.routeFitScore = Math.max(0, Math.min(100, routeFitScore));
    candidate.distanceScore = Math.max(0, Math.min(100, distanceScore));
    candidate.finalScore = Math.round(finalScore);
    return {
        candidate,
        score: Math.round(finalScore),
        reasons
    };
}
function nearbyScore(candidate, dayItems, focusLocation, slot) {
    if (!candidate.location)
        return 0;
    let score = 0;
    if (focusLocation) {
        const distance = distanceMeters(candidate.location, focusLocation);
        if (distance < 1200)
            score += 18;
        else if (distance < 3000)
            score += 12;
        else if (distance < 6000)
            score += 6;
        else if (distance < 10000)
            score -= 2;
        else
            score -= 8;
    }
    const locatedItems = dayItems.filter((item) => item.location);
    if (!locatedItems.length) {
        return slot === "lunch" ? Math.round(score * 0.5) : score;
    }
    const nearest = Math.min(...locatedItems.map((item) => distanceMeters(candidate.location, item.location)));
    if (nearest < 1200)
        score += 10;
    else if (nearest < 3000)
        score += 6;
    else if (nearest < 6000)
        score += 3;
    else if (nearest > 10000)
        score -= 6;
    if (slot === "lunch") {
        return Math.round(score * 0.55);
    }
    return score;
}
function categoryRepeatPenalty(candidate, dayItems, tripCategoryUsage, requirement) {
    const plannerCategory = candidatePlannerCategory(candidate);
    const dayCount = dayItems.filter((item) => normalizePlannerCategoryLabel(item.category) === plannerCategory).length;
    const tripCount = tripCategoryUsage.get(plannerCategory) ?? 0;
    const relaxedMultiplier = requirement.replan_directives?.global?.preferred_pace === "relaxed" ? 1.4 : 1;
    const dailyPenalty = dayCount * (plannerCategory === "food" ? 5 : 12) * relaxedMultiplier;
    const tripPenalty = tripCount * (plannerCategory === "food" ? 2 : 5);
    return dailyPenalty + tripPenalty;
}
function slotAffinity(slot, category) {
    if (slot.categories.includes(category))
        return 20;
    if (SLOT_PRIORITY[slot.slot].includes(category))
        return 10;
    return 0;
}
function evaluateCandidateForSlot(params) {
    const candidate = params.scored.candidate;
    const reasons = [...params.scored.reasons];
    let score = params.scored.score;
    const dayPlan = params.dayPlan;
    const directiveOverride = getDayOverrideForSlot(params.requirement.replan_directives, params.day, params.slot.slot);
    const plannerCategory = candidatePlannerCategory(candidate);
    if (params.selectionHints?.preferredCandidateIds.includes(candidate.id)) {
        score += 30;
        reasons.push("LLM shortlist");
    }
    if (params.selectionHints?.avoidCandidateIds.includes(candidate.id)) {
        score -= 40;
        reasons.push("LLM avoid list");
    }
    if (params.selectionHints?.preferredCategories.some((item) => categoryMatchesPlannerChoice(plannerCategory, String(item)))) {
        score += 10;
        reasons.push("LLM preferred category");
    }
    if (dayPlan?.candidateIds.includes(candidate.id)) {
        score += 18;
        reasons.push("day cluster");
    }
    if (dayPlan?.mainClusterId && dayPlan.candidateIds.includes(candidate.id)) {
        score += 4;
    }
    if (dayPlan?.foodCandidateIds.includes(candidate.id) && params.slot.slot === "lunch") {
        score += 16;
        reasons.push("food hub");
    }
    if (dayPlan?.mainClusterType === "full_cluster" && params.slot.slot !== "lunch") {
        score += 2;
    }
    const contentBoost = buildContentSignalBoost(candidate, params.contentSignals);
    if (contentBoost.bonus > 0) {
        score += Math.round(contentBoost.bonus * 0.5);
        reasons.push(...contentBoost.reasons.slice(0, 2));
    }
    const affinity = slotAffinity(params.slot, plannerCategory);
    score += affinity;
    if (affinity > 0) {
        reasons.push(`slot fit: ${params.slot.slot}`);
    }
    const proximity = nearbyScore(candidate, params.dayItems, dayPlan?.focusLocation, params.slot.slot);
    score += proximity;
    if (proximity > 0) {
        reasons.push("nearby to current day");
    }
    if (directiveOverride?.preferred_categories?.some((item) => categoryMatchesPlannerChoice(plannerCategory, String(item)))) {
        score += 28;
        reasons.push("day override preferred");
    }
    if (directiveOverride?.avoid_categories?.some((item) => categoryMatchesPlannerChoice(plannerCategory, String(item)))) {
        score -= 60;
        reasons.push("day override avoid");
    }
    if (params.slot.categories.includes(plannerCategory) && params.slot.slot === "afternoon" && plannerCategory === "food") {
        score += 4;
    }
    if (params.slot.slot === "evening" && params.slot.categories.includes("food") && plannerCategory === "food") {
        score += 6;
    }
    const repeatPenalty = categoryRepeatPenalty(candidate, params.dayItems, params.tripCategoryUsage, params.requirement);
    score -= repeatPenalty;
    if (repeatPenalty > 0) {
        reasons.push("category balance penalty");
    }
    if (params.slot.slot === "lunch" && plannerCategory !== "food") {
        score -= 4;
    }
    if (params.slot.slot === "evening" && plannerCategory === "scenic") {
        score += 8;
    }
    if (params.slot.slot === "afternoon" && (plannerCategory === "food" || plannerCategory === "walk")) {
        score += 6;
    }
    if (params.slot.slot === "morning" && plannerCategory === "scenic") {
        score += 6;
    }
    return {
        candidate,
        score: Math.round(score),
        reasons
    };
}
function isNearEnough(candidate, dayItems) {
    if (!candidate.location)
        return true;
    const locatedItems = dayItems.filter((item) => item.location);
    if (!locatedItems.length)
        return true;
    const nearest = Math.min(...locatedItems.map((item) => distanceMeters(candidate.location, item.location)));
    return nearest <= 12000;
}
function getSlotPlan(dayPlan, slot) {
    return dayPlan?.slotPlans.find((plan) => plan.slot === slot);
}
function pickForSlot(params) {
    const slotPlan = getSlotPlan(params.dayPlan, params.slot.slot);
    const scopedIds = slotPlan?.candidateIds.length ? slotPlan.candidateIds : params.dayPlan?.candidateIds;
    const globalAvoid = new Set((params.requirement.replan_directives?.global?.avoid_categories ?? []).map((item) => normalizePlannerCategoryLabel(String(item))));
    const dayOverride = getDayOverrideForSlot(params.requirement.replan_directives, params.day, params.slot.slot);
    const scopedCandidates = scopedIds?.length
        ? params.scored.filter((item) => scopedIds.includes(item.candidate.id))
        : params.scored;
    const ranked = (scopedCandidates.length ? scopedCandidates : params.scored)
        .filter((item) => !params.usedIds.has(item.candidate.id))
        .filter((item) => !globalAvoid.has(candidatePlannerCategory(item.candidate)))
        .filter((item) => !(dayOverride?.avoid_categories ?? []).map((value) => normalizePlannerCategoryLabel(String(value))).includes(candidatePlannerCategory(item.candidate)))
        .filter((item) => isNearEnough(item.candidate, params.dayItems))
        .map((item) => evaluateCandidateForSlot({
        scored: item,
        slot: params.slot,
        requirement: params.requirement,
        day: params.day,
        dayItems: params.dayItems,
        tripCategoryUsage: params.tripCategoryUsage,
        selectionHints: params.selectionHints,
        contentSignals: params.contentSignals,
        dayPlan: params.dayPlan
    }))
        .sort((a, b) => {
        const scoreDelta = b.score - a.score;
        if (scoreDelta !== 0)
            return scoreDelta;
        const locationDelta = Number(Boolean(b.candidate.location)) - Number(Boolean(a.candidate.location));
        if (locationDelta !== 0)
            return locationDelta;
        return b.candidate.confidence - a.candidate.confidence;
    });
    if (ranked[0])
        return ranked[0];
    const fallbackByCategory = params.scored
        .filter((item) => !params.usedIds.has(item.candidate.id))
        .filter((item) => params.slot.categories.includes(candidatePlannerCategory(item.candidate)))
        .sort((a, b) => b.score - a.score);
    return fallbackByCategory[0] ?? null;
}
function toPlannedItem(params) {
    const candidate = params.scored.candidate;
    const slotPlan = getSlotPlan(params.dayPlan, params.slot);
    const reasonParts = [slotPlan?.rationale, slotPlan?.transferReason, params.scored.reasons[0]].filter(Boolean);
    return {
        candidateId: candidate.id,
        name: candidate.name,
        category: candidate.category,
        day: params.day,
        order: params.order,
        timeSlot: params.slot,
        reason: reasonParts.join(" "),
        location: candidate.location,
        address: candidate.address,
        durationMinutes: candidate.suggestedDurationMinutes,
        source: candidate.source,
        score: params.scored.score,
        granularity: candidate.granularity,
        subStops: candidate.subStops,
        roles: candidate.roles,
        linkedPoiId: candidate.linkedPoiId,
        nightView: candidate.nightView
    };
}
export function buildMapData(days) {
    const markers = days.flatMap((day) => day.items
        .filter((item) => item.location)
        .map((item) => ({
        id: item.candidateId,
        day: day.day,
        order: item.order,
        name: item.name,
        category: item.category,
        location: item.location
    })));
    const center = markers.length
        ? {
            lng: markers.reduce((sum, marker) => sum + marker.location.lng, 0) / markers.length,
            lat: markers.reduce((sum, marker) => sum + marker.location.lat, 0) / markers.length
        }
        : undefined;
    return {
        markers,
        polylines: [],
        layers: days.map((day) => ({
            day: day.day,
            markerIds: markers.filter((marker) => marker.day === day.day).map((marker) => marker.id),
            polylineIds: []
        })),
        center
    };
}
function fallbackScore(candidate) {
    const finalScore = Number(candidate.finalScore ?? 0);
    const classicnessScore = Number(candidate.classicnessScore ?? candidate.classicness_score ?? 0);
    const groundingConfidence = Number(candidate.groundingConfidence ?? candidate.grounding_confidence ?? 0);
    const confidence = Number(candidate.confidence ?? 0);
    return finalScore * 1000 + classicnessScore * 100 + groundingConfidence * 10 + confidence;
}
function buildFallbackPlannedItem(params) {
    const scoredCandidate = {
        candidate: params.candidate,
        score: Math.round(fallbackScore(params.candidate)),
        reasons: ["fallback_select_without_cluster_used"]
    };
    return toPlannedItem({
        scored: scoredCandidate,
        day: params.day,
        order: params.order,
        slot: params.slot
    });
}
function pickFallbackCandidate(ranked, usedIds, preferredCategories) {
    const unused = ranked.filter((candidate) => !usedIds.has(candidate.id));
    const searchPool = unused.length ? unused : ranked;
    for (const preferredCategory of preferredCategories) {
        const match = searchPool.find((candidate) => candidatePlannerCategory(candidate) === preferredCategory);
        if (match)
            return match;
    }
    return searchPool[0] ?? null;
}
export function fallbackSelectWithoutCluster(params) {
    const warnings = ["fallback_select_without_cluster_used"];
    const selectable = dedupePlannerCandidates(params.candidates.map(ensurePlannerEligibility)).filter(isPlannerSelectable);
    const ranked = [...selectable].sort((a, b) => {
        const scoreDelta = fallbackScore(b) - fallbackScore(a);
        if (scoreDelta !== 0)
            return scoreDelta;
        const classicnessDelta = Number(b.classicnessScore ?? b.classicness_score ?? 0) - Number(a.classicnessScore ?? a.classicness_score ?? 0);
        if (classicnessDelta !== 0)
            return classicnessDelta;
        const groundingDelta = Number(b.groundingConfidence ?? b.grounding_confidence ?? 0) - Number(a.groundingConfidence ?? a.grounding_confidence ?? 0);
        if (groundingDelta !== 0)
            return groundingDelta;
        return Number(b.confidence ?? 0) - Number(a.confidence ?? 0);
    });
    if (!ranked.length) {
        warnings.push("fallback_select_without_cluster_no_candidates");
        return { days: [], warnings };
    }
    const usedIds = new Set();
    let days = [];
    const perDayLimit = 4;
    const slotOrder = [
        { slot: "morning", categories: ["scenic", "walk", "supplemental"] },
        { slot: "lunch", categories: ["food", "scenic", "walk", "supplemental"] },
        { slot: "afternoon", categories: ["walk", "scenic", "food", "supplemental"] },
        { slot: "evening", categories: ["scenic", "food", "walk", "supplemental"] }
    ];
    for (let day = 1; day <= params.tripDays; day += 1) {
        const items = [];
        for (const slot of slotOrder) {
            if (items.length >= perDayLimit)
                break;
            const picked = pickFallbackCandidate(ranked, usedIds, slot.categories);
            if (!picked)
                continue;
            if (!usedIds.has(picked.id))
                usedIds.add(picked.id);
            items.push(buildFallbackPlannedItem({
                candidate: picked,
                day,
                order: items.length + 1,
                slot: slot.slot
            }));
        }
        if (!items.length) {
            const picked = ranked[0];
            if (picked) {
                items.push(buildFallbackPlannedItem({
                    candidate: picked,
                    day,
                    order: 1,
                    slot: "morning"
                }));
            }
        }
        days.push({
            day,
            theme: `fallback day ${day}`,
            items,
            totalFatigueScore: Math.min(100, items.length * 18),
            totalTransferDistanceMeters: 0,
            notes: ["fallback_select_without_cluster_used"]
        });
    }
    return { days, warnings };
}
function buildDayTheme(requirement, day, daysCount) {
    const destination = String(requirement.destination ?? "destination").trim() || "destination";
    const interests = getInterests(requirement);
    if (day === 1)
        return `${destination} arrival`;
    if (day === daysCount)
        return `${destination} closing`;
    if (interests.some((item) => /food|cafe|shopping|restaurant|\u7f8e\u98df|\u5496\u5561|\u5546\u573a/i.test(item))) {
        return `${destination} food and streets`;
    }
    if (interests.some((item) => /night|nightview|\u591c\u666f|\u591c\u5e02|\u591c\u6e38/i.test(item))) {
        return `${destination} night views`;
    }
    if (interests.some((item) => /nature|scenic|\u81ea\u7136|\u666f\u533a|\u5c71|\u6e56/i.test(item))) {
        return `${destination} nature`;
    }
    return `${destination} city classic`;
}
export function planDynamicItinerary(input) {
    const warnings = [...input.candidatePool.warnings];
    const selectionHints = input.candidatePool.selectionHints;
    const categoryPriorityMap = buildCategoryPriorityMap(input.candidatePool.queryPlan);
    const contentSignals = input.candidatePool.contentSignals;
    const preferenceProfile = input.candidatePool.preferenceProfile ?? resolvePreferenceProfile(input.requirement);
    const citySignaturePool = input.candidatePool.citySignaturePool ?? buildCitySignaturePool(String(input.requirement.destination ?? input.candidatePool.destination ?? ""), input.candidatePool, input.requirement);
    const coverageCheck = input.candidatePool.coverageCheck ?? checkCityCoverage({
        ...input.candidatePool,
        preferenceProfile,
        citySignaturePool
    });
    const travelPlan = buildTravelPlanningStructure({
        requirement: input.requirement,
        candidatePool: input.candidatePool
    });
    warnings.push(...travelPlan.warnings);
    if (coverageCheck.missing_items.length) {
        warnings.push(`coverage missing: ${coverageCheck.missing_items.join(", ")}`);
    }
    const candidates = dedupePlannerCandidates(input.candidatePool.candidates.map(ensurePlannerEligibility));
    const signatureLookup = buildSignatureLookup(citySignaturePool);
    const scored = candidates
        .map((candidate) => scoreCandidate(candidate, input.requirement, preferenceProfile, signatureLookup, categoryPriorityMap, contentSignals))
        .sort((a, b) => b.score - a.score);
    if (!scored.length) {
        warnings.push("candidate pool is empty; itinerary cannot be planned");
    }
    const daysCount = getTripDays(input.requirement);
    const perDayLimit = maxItemsPerDay(input.requirement);
    const usedIds = new Set();
    const tripCategoryUsage = new Map();
    let days = [];
    for (let day = 1; day <= daysCount; day += 1) {
        const items = [];
        const template = buildEffectiveDayTemplate(input.requirement, day, daysCount).slots;
        const dayPlan = travelPlan.dayPlans[day - 1];
        for (const slot of template) {
            if (items.length >= perDayLimit)
                break;
            const picked = pickForSlot({
                slot,
                requirement: input.requirement,
                day,
                scored,
                usedIds,
                dayItems: items,
                tripCategoryUsage,
                selectionHints,
                contentSignals,
                dayPlan
            });
            if (!picked) {
                warnings.push(`day ${day} slot ${slot.slot} fallback exhausted`);
                continue;
            }
            usedIds.add(picked.candidate.id);
            tripCategoryUsage.set(candidatePlannerCategory(picked.candidate), (tripCategoryUsage.get(candidatePlannerCategory(picked.candidate)) ?? 0) + 1);
            items.push(toPlannedItem({
                scored: picked,
                day,
                order: items.length + 1,
                slot: slot.slot,
                dayPlan
            }));
        }
        days.push({
            day,
            theme: buildDayTheme(input.requirement, day, daysCount),
            items,
            segments: dayPlan?.slotPlans,
            totalFatigueScore: Math.min(100, items.length * 18 + (dayPlan?.slotPlans.length ?? 0) * 6),
            totalTransferDistanceMeters: (dayPlan?.slotPlans ?? []).reduce((sum, segment) => sum + (segment.transferDistanceMeters ?? 0), 0),
            notes: (dayPlan?.slotPlans ?? []).map((segment) => segment.rationale)
        });
    }
    const totalItems = days.reduce((sum, day) => sum + day.items.length, 0);
    if (totalItems === 0) {
        const fallback = fallbackSelectWithoutCluster({
            candidates,
            tripDays: daysCount
        });
        if (fallback.days.length) {
            warnings.push(...fallback.warnings);
            days = fallback.days;
        }
        else {
            warnings.push(...fallback.warnings);
        }
    }
    const notSelectedSignatureItems = citySignaturePool.must_visit_attractions
        .filter((item) => !days.some((day) => day.items.some((planned) => planned.candidateId === item.candidateId)))
        .slice(0, 8);
    const governanceSummary = {
        ...(input.candidatePool.governanceSummary ?? {
            planningMode: input.candidatePool.planningMode ?? "city_trip"
        }),
        dailyMainItemCounts: days.map((day) => ({ day: day.day, count: day.items.length })),
        subStopsCount: days.reduce((sum, day) => sum + day.items.reduce((itemSum, item) => itemSum + (item.subStops?.length ?? 0), 0), 0),
        hasLinkedNightView: days.some((day) => day.items.some((item) => Boolean(item.nightView) || Boolean(item.linkedPoiId))),
        hasFoodWalkMerge: days.some((day) => day.items.some((item) => (item.roles ?? []).includes("walk") && (item.roles ?? []).includes("food")))
    };
    const baseOutput = {
        itinerary: { days },
        mapData: buildMapData(days),
        warnings,
        sourceRefs: Array.from(new Set(candidates.map((candidate) => candidate.sourceRef).filter((value) => Boolean(value)))),
        preferenceProfile,
        citySignatureSeed: input.candidatePool.citySignatureSeed,
        citySignaturePool,
        coverageCheck,
        notSelectedSignatureItems,
        governanceSummary
    };
    const routeValidation = validatePlannedRoute({
        candidatePool: {
            ...input.candidatePool,
            preferenceProfile,
            citySignaturePool,
            coverageCheck
        },
        plannerOutput: baseOutput
    });
    return {
        ...baseOutput,
        routeValidation
    };
}

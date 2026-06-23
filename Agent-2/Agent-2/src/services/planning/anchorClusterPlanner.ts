import type {
  CandidatePool,
  CandidatePlace,
  DaySlotPlan,
  GeoPoint,
  PlannerCategory,
  PlannerTimeSlot,
  StructuredPayload
} from "../../types";
import { getDayOverrideForSlot } from "../replan/replanDirectives";

export type TravelIntent =
  | "light_trip"
  | "special_ops"
  | "family"
  | "foodie"
  | "photo"
  | "culture"
  | "nature";

export type TravelClusterType = "full_cluster" | "single_anchor" | "food_cluster" | "weak_cluster";
export type TravelClusterRole =
  | "sightseeing_cluster"
  | "food_cluster"
  | "leisure_cluster"
  | "night_cluster"
  | "shopping_cluster";

export interface TravelCluster {
  id: string;
  anchorId: string;
  anchorName: string;
  type: TravelClusterType;
  role?: TravelClusterRole;
  center?: GeoPoint;
  candidateIds: string[];
  categories: PlannerCategory[];
  categoryCounts: Partial<Record<PlannerCategory, number>>;
  score: number;
}

export interface TravelDayPlan {
  day: number;
  intent: TravelIntent;
  mainClusterId?: string;
  auxClusterId?: string;
  mainClusterType?: TravelClusterType;
  focusLocation?: GeoPoint;
  candidateIds: string[];
  foodCandidateIds: string[];
  slotPlans: DaySlotPlan[];
}

export interface TravelPlanningStructure {
  intent: TravelIntent;
  intentReasons: string[];
  clusters: TravelCluster[];
  dayPlans: TravelDayPlan[];
  warnings: string[];
}

interface RankedCandidate {
  candidate: CandidatePlace;
  score: number;
}

function normalizeText(value: string): string {
  return value.trim().toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}

function getQualityFlags(candidate: CandidatePlace): Record<string, unknown> {
  const raw = candidate.qualityFlags ?? candidate.quality_flags;
  return raw && typeof raw === "object" && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {};
}

function hasQualityFlag(candidate: CandidatePlace, flag: string): boolean {
  return Boolean(getQualityFlags(candidate)[flag]);
}

function getCandidateTier(candidate: CandidatePlace): string {
  return String(candidate.candidateTier ?? candidate.candidate_tier ?? "").trim().toLowerCase();
}

function getGroundingConfidence(candidate: CandidatePlace): number {
  return Number(candidate.groundingConfidence ?? candidate.grounding_confidence ?? 0) || 0;
}

function getClassicnessScore(candidate: CandidatePlace): number {
  return Number(candidate.classicnessScore ?? candidate.classicness_score ?? 0) || 0;
}

export function getPlannerCategory(candidate: CandidatePlace): PlannerCategory {
  const explicit = String(candidate.plannerCategory ?? "").trim().toLowerCase();
  if (explicit === "scenic" || explicit === "food" || explicit === "walk" || explicit === "food_walk" || explicit === "supplemental") {
    return explicit;
  }

  const tier = getCandidateTier(candidate);
  const granularity = String(candidate.granularity ?? "").trim().toLowerCase();
  const text = normalizeText(
    `${candidate.name} ${candidate.description ?? ""} ${candidate.tags.join(" ")} ${tier} ${granularity} ${candidate.roles?.join(" ") ?? ""} ${candidate.source}`
  );

  if (granularity === "food_level" || /foodwalk/.test(text)) {
    return (candidate.roles ?? []).includes("walk") ? "food_walk" : "food";
  }
  if (granularity === "district_level") return "walk";
  if (granularity === "attraction_level") return "scenic";
  if (granularity === "internal_poi_level" || granularity === "service_level" || granularity === "city_level") {
    return "supplemental";
  }
  if (tier === "food" || candidate.category === "food" || candidate.category === "cafe" || /localfood|foodarea|foodzone/.test(text)) {
    return "food";
  }
  if (tier === "walk" || candidate.category === "citywalk" || candidate.category === "park" || candidate.category === "mall" || /citywalk|walk|stroll|shopping|area/.test(text)) {
    return "walk";
  }
  if (
    tier === "scenic" ||
    tier === "core" ||
    candidate.category === "landmark" ||
    candidate.category === "museum" ||
    candidate.category === "nightview" ||
    candidate.category === "nature" ||
    /scenic|culturehistory|naturerelax|nightview|nightviewarea|core|history|nature/.test(text)
  ) {
    return "scenic";
  }

  return "supplemental";
}

function normalizePlannerCategoryLabel(value: string): PlannerCategory {
  const text = normalizeText(value);
  if (/food|cafe|meal|restaurant|localfood|foodarea/.test(text)) return "food";
  if (/walk|citywalk|park|mall|shopping|stroll|area/.test(text)) return "walk";
  if (/scenic|core|culture|history|nature|night|museum|landmark/.test(text)) return "scenic";
  return "supplemental";
}

export function ensurePlannerEligibility(candidate: CandidatePlace): CandidatePlace {
  const plannerCategory = getPlannerCategory(candidate);
  const tier = getCandidateTier(candidate);
  const granularity = String(candidate.granularity ?? "").trim().toLowerCase();
  const groundingConfidence = getGroundingConfidence(candidate);
  const classicnessScore = getClassicnessScore(candidate);
  const qualityFlags = getQualityFlags(candidate);
  const explicitEligible = candidate.eligibleForMainItinerary ?? candidate.eligible_for_main_itinerary;
  const trustedCurator =
    candidate.source === "llm_curator" ||
    Boolean(qualityFlags.llm_curated) ||
    Boolean(qualityFlags.high_classicness) ||
    Boolean(qualityFlags.representative_walk) ||
    Boolean(qualityFlags.local_food);
  const tierTrusted = ["core", "scenic", "walk", "food"].includes(tier);
  const inferredEligible =
    explicitEligible ??
    (Boolean(candidate.location) &&
      granularity !== "internal_poi_level" &&
      granularity !== "service_level" &&
      granularity !== "city_level" &&
      (trustedCurator ||
        (tierTrusted && groundingConfidence >= 0.55) ||
        (classicnessScore >= 0.62 && groundingConfidence >= 0.45 && plannerCategory !== "supplemental") ||
        groundingConfidence >= 0.7));

  return {
    ...candidate,
    plannerCategory,
    candidateTier: candidate.candidateTier ?? candidate.candidate_tier ?? tier,
    candidate_tier: candidate.candidate_tier ?? candidate.candidateTier ?? tier,
    groundingConfidence: candidate.groundingConfidence ?? candidate.grounding_confidence ?? groundingConfidence,
    grounding_confidence: candidate.grounding_confidence ?? candidate.groundingConfidence ?? groundingConfidence,
    classicnessScore: candidate.classicnessScore ?? candidate.classicness_score ?? classicnessScore,
    classicness_score: candidate.classicness_score ?? candidate.classicnessScore ?? classicnessScore,
    eligibleForMainItinerary: Boolean(inferredEligible),
    eligible_for_main_itinerary: Boolean(inferredEligible),
    qualityFlags,
    quality_flags: qualityFlags
  };
}

export function isPlannerSelectable(candidate: CandidatePlace): boolean {
  if (!candidate.location) return false;
  if (candidate.granularity === "internal_poi_level" || candidate.granularity === "service_level" || candidate.granularity === "city_level") {
    return candidate.planningMode === "attraction_internal_route" && candidate.granularity === "internal_poi_level";
  }
  const tier = getCandidateTier(candidate);
  const groundingConfidence = getGroundingConfidence(candidate);
  const qualityFlags = getQualityFlags(candidate);
  const trustedCurator =
    candidate.source === "llm_curator" ||
    Boolean(qualityFlags.llm_curated) ||
    Boolean(qualityFlags.high_classicness);
  if (trustedCurator && groundingConfidence >= 0.55) return true;
  if (["core", "scenic", "walk", "food"].includes(tier) && groundingConfidence >= 0.55) return true;
  return !isLowValueMerchant(candidate);
}

export function buildCandidateDebugSummary(candidates: CandidatePlace[]): Record<string, unknown> {
  const total = candidates.length;
  const withLocation = candidates.filter((candidate) => Boolean(candidate.location)).length;
  const noLocation = total - withLocation;
  const lowValueMerchant = candidates.filter((candidate) => isLowValueMerchant(candidate)).length;
  const eligibleForMainItinerary = candidates.filter((candidate) => Boolean(candidate.eligible_for_main_itinerary ?? candidate.eligibleForMainItinerary)).length;

  const groupBy = (selector: (candidate: CandidatePlace) => string): Record<string, number> =>
    candidates.reduce<Record<string, number>>((acc, candidate) => {
      const key = selector(candidate) || "unknown";
      acc[key] = (acc[key] ?? 0) + 1;
      return acc;
    }, {});

  const top10 = [...candidates]
    .sort((a, b) => {
      const scoreA = Number(a.finalScore ?? a.classicnessScore ?? a.classicness_score ?? a.groundingConfidence ?? a.grounding_confidence ?? a.confidence ?? 0);
      const scoreB = Number(b.finalScore ?? b.classicnessScore ?? b.classicness_score ?? b.groundingConfidence ?? b.grounding_confidence ?? b.confidence ?? 0);
      if (scoreB !== scoreA) return scoreB - scoreA;
      return Number((b.groundingConfidence ?? b.grounding_confidence ?? 0)) - Number((a.groundingConfidence ?? a.grounding_confidence ?? 0));
    })
    .slice(0, 10)
    .map((candidate) => ({
      name: candidate.name,
      category: candidate.category,
      plannerCategory: candidate.plannerCategory ?? getPlannerCategory(candidate),
      tier: candidate.candidateTier ?? candidate.candidate_tier ?? "",
      location: candidate.location ?? null,
      score: candidate.finalScore ?? candidate.classicnessScore ?? candidate.classicness_score ?? candidate.confidence,
      groundingConfidence: candidate.groundingConfidence ?? candidate.grounding_confidence ?? null,
      eligible: Boolean(candidate.eligible_for_main_itinerary ?? candidate.eligibleForMainItinerary),
      source: candidate.source,
      quality_flags: candidate.quality_flags ?? candidate.qualityFlags ?? {}
    }));

  return {
    total,
    withLocation,
    noLocation,
    lowValueMerchant,
    eligible_for_main_itinerary: eligibleForMainItinerary,
    byCandidateTier: groupBy((candidate) => candidate.candidateTier ?? candidate.candidate_tier ?? "unknown"),
    byCategory: groupBy((candidate) => candidate.category),
    byPlannerCategory: groupBy((candidate) => candidate.plannerCategory ?? getPlannerCategory(candidate)),
    bySource: groupBy((candidate) => candidate.source),
    top10
  };
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
  return Math.round(2 * earthRadius * Math.asin(Math.sqrt(h)));
}

function getTripDays(requirement: StructuredPayload): number {
  const raw = Number(requirement.trip_days ?? 1);
  if (!Number.isFinite(raw) || raw <= 0) return 1;
  return Math.min(Math.max(Math.round(raw), 1), 7);
}

function getInterests(requirement: StructuredPayload): string[] {
  return Array.isArray(requirement.interests)
    ? requirement.interests.map((item) => String(item).trim()).filter(Boolean)
    : [];
}

function getPace(requirement: StructuredPayload): string {
  return String(requirement.preferredPace ?? requirement.preferred_pace ?? "").trim();
}

function getDistanceTolerance(requirement: StructuredPayload): string {
  return String(requirement.distanceTolerance ?? requirement.distance_tolerance ?? "").trim();
}

function classifyIntent(requirement: StructuredPayload): { intent: TravelIntent; reasons: string[] } {
  const interests = getInterests(requirement);
  const pace = getPace(requirement);
  const tolerance = getDistanceTolerance(requirement);
  const text = normalizeText(
    `${interests.join(" ")} ${Array.isArray(requirement.constraints) ? requirement.constraints.join(" ") : ""}`
  );
  if (requirement.replan_directives?.global?.preferred_categories?.some((item) => item === "food" || item === "cafe")) {
    return { intent: "foodie", reasons: ["directive food preference"] };
  }

  const rules: Array<{ intent: TravelIntent; patterns: RegExp[]; reason: string }> = [
    {
      intent: "foodie",
      patterns: [/food|cafe|restaurant|meal/i, /美食|小吃|餐饮|夜宵/u],
      reason: "food preference"
    },
    {
      intent: "photo",
      patterns: [/photo|photogenic|shoot|insta/i, /拍照|打卡|出片/u],
      reason: "photo preference"
    },
    {
      intent: "family",
      patterns: [/family|kid|children/i, /亲子|带娃|小朋友/u],
      reason: "family preference"
    },
    {
      intent: "culture",
      patterns: [/museum|culture|history/i, /博物馆|展览|文化|人文/u],
      reason: "culture preference"
    },
    {
      intent: "nature",
      patterns: [/nature|scenic|mountain|lake/i, /自然|风景|山|湖|公园/u],
      reason: "nature preference"
    }
  ];

  for (const rule of rules) {
    if (rule.patterns.some((pattern) => pattern.test(text))) {
      return { intent: rule.intent, reasons: [rule.reason] };
    }
  }

  if (pace === "relaxed") {
    return { intent: "light_trip", reasons: ["relaxed pace"] };
  }
  if (pace === "compact" || tolerance === "urban_only") {
    return { intent: "special_ops", reasons: ["compact pace"] };
  }
  return { intent: "special_ops", reasons: ["balanced default"] };
}

function isLowValueMerchant(candidate: CandidatePlace): boolean {
  const text = normalizeText(`${candidate.name} ${candidate.description ?? ""} ${candidate.tags.join(" ")}`);
  return /(?:酒店|宾馆|公寓|写字楼|办公楼|公司|超市|便利店|药店|银行|加油站|停车场|服务区|厕所|工厂|仓库|民宿|网吧|快递|诊所|医院|地产|中介|售票处|游客中心|车站)/u.test(
    text
  );
}

function sourceBonus(candidate: CandidatePlace): number {
  if (candidate.source === "mcp_poi") return 18;
  if (candidate.source === "static_pool") return 12;
  if (candidate.source === "content_search") return 7;
  return 0;
}

function intentBonus(candidate: CandidatePlace, intent: TravelIntent): number {
  const text = normalizeText(`${candidate.name} ${candidate.description ?? ""} ${candidate.tags.join(" ")}`);
  if (intent === "foodie" && /food|restaurant|meal|cafe/i.test(text)) return 12;
  if (intent === "foodie" && /美食|小吃|餐饮|夜宵/u.test(text)) return 12;
  if (intent === "photo" && /photo|photogenic|view/i.test(text)) return 10;
  if (intent === "photo" && /拍照|打卡|出片|夜景/u.test(text)) return 10;
  if (intent === "family" && /park|museum|landmark|family|kid/i.test(text)) return 8;
  if (intent === "family" && /亲子|带娃|小朋友|儿童/u.test(text)) return 8;
  if (intent === "culture" && /museum|culture|history/i.test(text)) return 10;
  if (intent === "culture" && /博物馆|展览|文化|人文/u.test(text)) return 10;
  if (intent === "nature" && /nature|scenic|park|mountain|lake/i.test(text)) return 10;
  if (intent === "nature" && /自然|风景|山|湖|公园/u.test(text)) return 10;
  if (intent === "light_trip" && candidate.category === "cafe") return 6;
  if (intent === "special_ops" && candidate.category === "landmark") return 6;
  return 0;
}

function qualityScore(candidate: CandidatePlace, intent: TravelIntent): number {
  let score = candidate.confidence * 40 + (candidate.citySignatureScore ?? 0) * 0.4;

  if (candidate.location) score += 10;
  else score -= 12;

  score += sourceBonus(candidate);
  score += intentBonus(candidate, intent);

  if (candidate.category === "food" || candidate.category === "cafe") score += 4;
  if (candidate.category === "nightview") score += 3;
  if (candidate.category === "mall") score += 2;

  if (isLowValueMerchant(candidate)) score -= 28;

  return Math.round(score);
}

function isAnchorEligible(candidate: CandidatePlace): boolean {
  if (!candidate.location) return false;
  const plannerCategory = getPlannerCategory(candidate);
  if (isLowValueMerchant(candidate) && !(candidate.source === "llm_curator" || Boolean(getQualityFlags(candidate).llm_curated) || Boolean(getQualityFlags(candidate).high_classicness))) return false;
  if ((candidate.citySignatureScore ?? 0) < 30 && plannerCategory !== "scenic") {
    return false;
  }
  return ["scenic", "walk", "food", "food_walk"].includes(plannerCategory);
}

function isFoodEligible(candidate: CandidatePlace): boolean {
  if (!candidate.location) return false;
  const plannerCategory = getPlannerCategory(candidate);
  if (isLowValueMerchant(candidate) && !(candidate.source === "llm_curator" || Boolean(getQualityFlags(candidate).llm_curated) || Boolean(getQualityFlags(candidate).high_classicness))) return false;
  return plannerCategory === "food" || plannerCategory === "food_walk";
}

function clusterRadius(candidate: CandidatePlace, intent: TravelIntent): number {
  const plannerCategory = getPlannerCategory(candidate);
  if (plannerCategory === "scenic" || intent === "nature") return 6500;
  if (plannerCategory === "walk") return 3200;
  if (plannerCategory === "food_walk") return 2500;
  if (plannerCategory === "food") return 1800;
  return 3000;
}

function foodClusterRadius(candidate: CandidatePlace): number {
  const plannerCategory = getPlannerCategory(candidate);
  if (plannerCategory === "walk" || plannerCategory === "food_walk") return 2200;
  return 1800;
}

function summarizeCategoryCounts(candidates: CandidatePlace[]): Partial<Record<PlannerCategory, number>> {
  return candidates.reduce<Partial<Record<PlannerCategory, number>>>((acc, candidate) => {
    const category = getPlannerCategory(candidate);
    acc[category] = (acc[category] ?? 0) + 1;
    return acc;
  }, {});
}

function averageCenter(candidates: CandidatePlace[]): GeoPoint | undefined {
  const located = candidates.filter((candidate) => candidate.location);
  if (!located.length) return undefined;
  return {
    lng: located.reduce((sum, candidate) => sum + candidate.location!.lng, 0) / located.length,
    lat: located.reduce((sum, candidate) => sum + candidate.location!.lat, 0) / located.length
  };
}

function chooseAnchorClusterType(
  memberCount: number,
  categories: Set<PlannerCategory>,
  categoryCounts: Partial<Record<PlannerCategory, number>>,
  anchor: CandidatePlace
): TravelClusterType {
  const scenic = categories.has("scenic");
  const support = categoryCounts.food ?? 0;

  if (memberCount >= 4 && scenic && support >= 2 && categories.size >= 3 && (anchor.citySignatureScore ?? 0) >= 42) return "full_cluster";
  if (scenic && ((anchor.citySignatureScore ?? 0) >= 50 || anchor.confidence >= 0.8 || memberCount >= 2)) return "single_anchor";
  return "weak_cluster";
}

function canBeDayAnchor(candidate: CandidatePlace, tripDays: number): boolean {
  const signature = candidate.citySignatureScore ?? 0;
  const plannerCategory = getPlannerCategory(candidate);
  if (tripDays <= 2) {
    return signature >= 48 || (plannerCategory === "scenic" && signature >= 40);
  }
  return signature >= 38;
}

function scoreAnchorCandidate(candidate: CandidatePlace, clusterSupportScore: number, routeFitScore: number): number {
  const citySignatureScore = candidate.citySignatureScore ?? 0;
  const plannerCategory = getPlannerCategory(candidate);
  const representativeScore =
    plannerCategory === "scenic" ? 80 :
    plannerCategory === "walk" ? 56 :
    plannerCategory === "food_walk" ? 62 :
    plannerCategory === "food" ? 44 :
    30;
  const userPreferenceScore = candidate.userPreferenceScore ?? 50;
  const weakAnchorPenalty = citySignatureScore < 45 ? 18 : 0;
  const ordinaryBusinessPenalty = isLowValueMerchant(candidate) ? 40 : 0;
  return (
    citySignatureScore * 0.4 +
    representativeScore * 0.2 +
    userPreferenceScore * 0.15 +
    clusterSupportScore * 0.15 +
    routeFitScore * 0.1 -
    weakAnchorPenalty -
    ordinaryBusinessPenalty
  );
}

function inferClusterRole(categories: Set<PlannerCategory>): TravelClusterRole {
  if (categories.has("food")) return "food_cluster";
  if (categories.has("walk")) return "leisure_cluster";
  if (categories.has("scenic")) return "sightseeing_cluster";
  return "sightseeing_cluster";
}

function buildAnchorClusters(params: { candidates: CandidatePlace[]; intent: TravelIntent }): TravelCluster[] {
  const anchors = params.candidates
    .filter(isAnchorEligible)
    .map((candidate) => ({ candidate, score: qualityScore(candidate, params.intent) }))
    .sort((a, b) => {
      const scoreDelta = b.score - a.score;
      if (scoreDelta !== 0) return scoreDelta;
      return b.candidate.confidence - a.candidate.confidence;
    });

  const usedAnchors = new Set<string>();
  const clusters: TravelCluster[] = [];

  for (const anchor of anchors) {
    if (usedAnchors.has(anchor.candidate.id)) continue;
    if (!anchor.candidate.location) continue;

    const radius = clusterRadius(anchor.candidate, params.intent);
    const neighbors = params.candidates
      .filter((candidate) => candidate.id !== anchor.candidate.id)
      .filter((candidate) => candidate.location)
      .map((candidate) => ({
        candidate,
        distance: distanceMeters(anchor.candidate.location!, candidate.location!)
      }))
      .filter((item) => item.distance <= radius)
      .sort((a, b) => {
        const qualityDelta = qualityScore(b.candidate, params.intent) - qualityScore(a.candidate, params.intent);
        if (qualityDelta !== 0) return qualityDelta;
        return a.distance - b.distance;
      })
      .slice(0, 7)
      .map((item) => item.candidate);

    const clusterCandidates = [anchor.candidate, ...neighbors];
    usedAnchors.add(anchor.candidate.id);
    for (const neighbor of neighbors.filter((item) => isAnchorEligible(item) && item.confidence >= 0.82)) {
      usedAnchors.add(neighbor.id);
    }

    const categories = new Set<PlannerCategory>(clusterCandidates.map((candidate) => getPlannerCategory(candidate)));
    const categoryCounts = summarizeCategoryCounts(clusterCandidates);
    const type = chooseAnchorClusterType(clusterCandidates.length, categories, categoryCounts, anchor.candidate);
    const clusterSupportScore = Math.min(100, clusterCandidates.length * 12 + categories.size * 10);
    const routeFitScore = type === "full_cluster" ? 78 : type === "single_anchor" ? 64 : 38;
    const score = scoreAnchorCandidate(anchor.candidate, clusterSupportScore, routeFitScore);

    clusters.push({
      id: `anchor_${anchor.candidate.id}`,
      anchorId: anchor.candidate.id,
      anchorName: anchor.candidate.name,
      type,
      role: inferClusterRole(categories),
      center: averageCenter(clusterCandidates) ?? anchor.candidate.location,
      candidateIds: clusterCandidates.map((candidate) => candidate.id),
      categories: Array.from(categories),
      categoryCounts,
      score
    });
  }

  return clusters;
}

function buildFoodClusters(params: { candidates: CandidatePlace[]; intent: TravelIntent }): TravelCluster[] {
  const anchors = params.candidates
    .filter(isFoodEligible)
    .map((candidate) => ({ candidate, score: qualityScore(candidate, params.intent) }))
    .sort((a, b) => b.score - a.score);

  const usedMembers = new Set<string>();
  const clusters: TravelCluster[] = [];

  for (const anchor of anchors) {
    if (usedMembers.has(anchor.candidate.id)) continue;
    if (!anchor.candidate.location) continue;

    const radius = foodClusterRadius(anchor.candidate);
    const members = params.candidates
      .filter((candidate) => candidate.location && isFoodEligible(candidate))
      .map((candidate) => ({
        candidate,
        distance: distanceMeters(anchor.candidate.location!, candidate.location!)
      }))
      .filter((item) => item.distance <= radius)
      .sort((a, b) => {
        const qualityDelta = qualityScore(b.candidate, params.intent) - qualityScore(a.candidate, params.intent);
        if (qualityDelta !== 0) return qualityDelta;
        return a.distance - b.distance;
      })
      .slice(0, 6)
      .map((item) => item.candidate);

    const categoryCounts = summarizeCategoryCounts(members);
    const supportCount = categoryCounts.food ?? 0;
    const diversity = Object.values(categoryCounts).filter((count) => Number(count) > 0).length;
    if (members.length < 2 || supportCount < 2) continue;

    for (const member of members) usedMembers.add(member.id);

    clusters.push({
      id: `food_${anchor.candidate.id}`,
      anchorId: anchor.candidate.id,
      anchorName: anchor.candidate.name,
      type: supportCount >= 3 || diversity >= 3 ? "food_cluster" : "weak_cluster",
      role: "food_cluster",
      center: averageCenter(members) ?? anchor.candidate.location,
      candidateIds: members.map((candidate) => candidate.id),
      categories: Array.from(new Set(members.map((candidate) => getPlannerCategory(candidate)))),
      categoryCounts,
      score: members.reduce((sum, candidate) => sum + qualityScore(candidate, params.intent), 0) + 12
    });
  }

  return clusters.filter((cluster) => cluster.type === "food_cluster");
}

function buildFoodPool(candidates: CandidatePlace[], intent: TravelIntent): RankedCandidate[] {
  return candidates
    .filter((candidate) => getPlannerCategory(candidate) === "food")
    .map((candidate) => ({ candidate, score: qualityScore(candidate, intent) }))
    .sort((a, b) => b.score - a.score);
}

function pickMainCluster(clusters: TravelCluster[], day: number, daysCount: number): TravelCluster | undefined {
  return [...clusters]
    .map((cluster) => {
      const anchorSignature = cluster.score;
      let score = anchorSignature;
      if (day === 1 && cluster.type === "full_cluster") score += 6;
      if (day === daysCount && cluster.categories.includes("scenic")) {
        score += 6;
      }
      return { cluster, score };
    })
    .sort((a, b) => b.score - a.score)[0]?.cluster;
}

function findClusterById(clusters: TravelCluster[], clusterId?: string): TravelCluster | undefined {
  if (!clusterId) return undefined;
  return clusters.find((cluster) => cluster.id === clusterId);
}

function clusterDistance(a?: TravelCluster, b?: TravelCluster): number {
  if (!a?.center || !b?.center) return Number.POSITIVE_INFINITY;
  return distanceMeters(a.center, b.center);
}

function getClusterCandidates(
  cluster: TravelCluster | undefined,
  candidateLookup: Map<string, CandidatePlace>,
  categories?: PlannerCategory[]
): CandidatePlace[] {
  if (!cluster) return [];
  const scoped = cluster.candidateIds
    .map((candidateId) => candidateLookup.get(candidateId))
    .filter((candidate): candidate is CandidatePlace => Boolean(candidate));
  if (!categories?.length) return scoped;
  return scoped.filter((candidate) => categories.includes(getPlannerCategory(candidate)));
}

function selectCandidateIds(candidates: CandidatePlace[], limit: number): string[] {
  return candidates.slice(0, limit).map((candidate) => candidate.id);
}

function pickNearbyFoodCluster(
  anchorCluster: TravelCluster | undefined,
  foodClusters: TravelCluster[],
  usedClusterIds: Set<string>
): { cluster?: TravelCluster; transferReason?: string; transferDistanceMeters?: number } {
  if (!anchorCluster?.center) return {};

  const ranked = foodClusters
    .filter((cluster) => !usedClusterIds.has(cluster.id))
    .map((cluster) => ({
      cluster,
      distance: cluster.center ? distanceMeters(anchorCluster.center!, cluster.center) : Number.POSITIVE_INFINITY,
      score: cluster.score
    }))
    .filter((item) => item.distance <= 9000)
    .sort((a, b) => {
      const distanceDelta = a.distance - b.distance;
      if (Math.abs(distanceDelta) > 1200) return distanceDelta;
      return b.score - a.score;
    });

  const picked = ranked[0];
  if (!picked) return {};

  return {
    cluster: picked.cluster,
    transferDistanceMeters: picked.distance,
    transferReason:
      picked.distance > 3000
        ? "景点周边餐饮支撑较弱，中午转去更成熟的美食片区，换取更稳定的用餐体验。"
        : "中午接入附近成熟餐饮片区，补足主景点周边的吃饭选择。"
  };
}

function pickNearbySupportCluster(
  anchorCluster: TravelCluster | undefined,
  allClusters: TravelCluster[],
  usedClusterIds: Set<string>,
  categories: PlannerCategory[],
  maxDistanceMeters: number
): TravelCluster | undefined {
  const ranked = allClusters
    .filter((cluster) => !usedClusterIds.has(cluster.id))
    .filter((cluster) => cluster.candidateIds.length > 0)
    .filter((cluster) => categories.some((category) => cluster.categories.includes(category)))
    .map((cluster) => {
      const distance = anchorCluster?.center && cluster.center ? distanceMeters(anchorCluster.center, cluster.center) : 0;
      return {
        cluster,
        distance,
        score: cluster.score + (cluster.type === "food_cluster" ? 6 : 0)
      };
    })
    .filter((item) => item.distance <= maxDistanceMeters)
    .sort((a, b) => {
      const scoreDelta = b.score - a.score;
      if (Math.abs(scoreDelta) > 10) return scoreDelta;
      return a.distance - b.distance;
    });

  return ranked[0]?.cluster;
}

function dedupeIds(ids: string[]): string[] {
  return Array.from(new Set(ids.filter(Boolean)));
}

function buildFallbackCluster(candidates: CandidatePlace[]): TravelCluster | undefined {
  const top = candidates[0];
  if (!top) return undefined;

  const scoped = candidates.slice(0, 4);
  const categories = new Set<PlannerCategory>(scoped.map((candidate) => getPlannerCategory(candidate)));
  return {
    id: `anchor_${top.id}`,
    anchorId: top.id,
    anchorName: top.name,
    type: "single_anchor",
    role: inferClusterRole(categories),
    center: top.location,
    candidateIds: scoped.map((candidate) => candidate.id),
    categories: Array.from(categories),
    categoryCounts: summarizeCategoryCounts(scoped),
    score: scoped.reduce((sum, candidate) => sum + candidate.confidence * 20, 0)
  };
}

function buildSlotPlan(params: {
  slot: PlannerTimeSlot;
  strategy: DaySlotPlan["strategy"];
  cluster?: TravelCluster;
  candidateIds: string[];
  rationale: string;
  transferReason?: string;
  transferDistanceMeters?: number;
}): DaySlotPlan {
  return {
    slot: params.slot,
    strategy: params.strategy,
    segmentType:
      params.slot === "morning" ? "sightseeing" :
      params.slot === "lunch" ? "food" :
      params.strategy === "shopping_cluster" ? "shopping" :
      params.slot === "evening" ? "night" :
      "leisure",
    clusterId: params.cluster?.id,
    clusterType: params.cluster?.type,
    candidateIds: dedupeIds(params.candidateIds),
    rationale: params.rationale,
    transferReason: params.transferReason,
    transferDistanceMeters: params.transferDistanceMeters
  };
}

function assignDayPlans(params: {
  requirement: StructuredPayload;
  clusters: TravelCluster[];
  foodPool: RankedCandidate[];
  candidates: CandidatePlace[];
  daysCount: number;
  intent: TravelIntent;
}): TravelDayPlan[] {
  const candidateLookup = new Map(params.candidates.map((candidate) => [candidate.id, candidate]));
  const anchorClusters = params.clusters
    .filter((cluster) => cluster.type === "full_cluster" || cluster.type === "single_anchor")
    .sort((a, b) => b.score - a.score);
  const foodClusters = params.clusters.filter((cluster) => cluster.type === "food_cluster");
  const supportClusters = params.clusters.filter((cluster) => cluster.type !== "weak_cluster");
  const remainingAnchors = [...anchorClusters];
  const usedClusterIds = new Set<string>();
  const dayPlans: TravelDayPlan[] = [];
  const fallbackCandidates = [...params.candidates].sort((a, b) => b.confidence - a.confidence);

  for (let day = 1; day <= params.daysCount; day += 1) {
    const mainCluster = pickMainCluster(
      (remainingAnchors.length ? remainingAnchors : anchorClusters).filter((cluster) => {
        const anchor = candidateLookup.get(cluster.anchorId);
        return anchor ? canBeDayAnchor(anchor, params.daysCount) : true;
      }),
      day,
      params.daysCount
    );
    if (mainCluster) usedClusterIds.add(mainCluster.id);

    const morningCandidates = getClusterCandidates(mainCluster, candidateLookup, ["scenic", "walk"]);
    const slotPlans: DaySlotPlan[] = [];

    if (mainCluster) {
      slotPlans.push(
        buildSlotPlan({
          slot: "morning",
          strategy: mainCluster.type === "single_anchor" ? "single_anchor" : "anchor_cluster",
          cluster: mainCluster,
          candidateIds: selectCandidateIds(morningCandidates.length ? morningCandidates : getClusterCandidates(mainCluster, candidateLookup), 4),
          rationale:
            mainCluster.type === "single_anchor"
              ? "上午先完成高优先级核心景点，不强行在周边凑满一整天，给后续转场留出空间。"
              : "上午先在成熟景点片区展开，减少来回折返，把最有代表性的游玩内容放在体力最好的时段。"
        })
      );
    }

    const anchorFoodCandidates = getClusterCandidates(mainCluster, candidateLookup, ["food"]);
    const hasStrongLocalMeal = anchorFoodCandidates.length >= 2 || (mainCluster?.categoryCounts.food ?? 0) >= 2;
    const nearbyFood = hasStrongLocalMeal ? undefined : pickNearbyFoodCluster(mainCluster, foodClusters, usedClusterIds);
    const lunchCluster = hasStrongLocalMeal ? mainCluster : nearbyFood?.cluster;
    if (lunchCluster?.id && lunchCluster.id !== mainCluster?.id) usedClusterIds.add(lunchCluster.id);

    const lunchOverride = getDayOverrideForSlot(params.requirement.replan_directives, day, "lunch");
    const lunchCategories: PlannerCategory[] = lunchOverride?.preferred_categories?.length
      ? lunchOverride.preferred_categories.map((value) => normalizePlannerCategoryLabel(value))
      : ["food"];
    const lunchCandidates = lunchCluster
      ? getClusterCandidates(lunchCluster, candidateLookup, lunchCategories)
      : params.foodPool.slice(0, 3).map((item) => item.candidate);
    slotPlans.push(
      buildSlotPlan({
        slot: "lunch",
        strategy: lunchCluster
          ? lunchCluster.type === "food_cluster"
            ? "food_cluster"
            : "meal_stop"
          : "meal_stop",
        cluster: lunchCluster,
        candidateIds: selectCandidateIds(lunchCandidates, 4),
        rationale: hasStrongLocalMeal
          ? "中午尽量留在上午片区内解决，减少折返和排队不确定性。"
          : lunchCluster
            ? "中午切到成熟美食片区，避免在景点周边为了就近而牺牲餐饮质量。"
            : "中午保留为独立用餐停靠点，不把吃饭强行绑定在景点周边。",
        transferReason: nearbyFood?.transferReason,
        transferDistanceMeters: nearbyFood?.transferDistanceMeters
      })
    );

    const preferSameAnchorAfternoon =
      mainCluster?.type === "full_cluster" &&
      (["walk"] as PlannerCategory[]).some((category) =>
        mainCluster.categories.includes(category)
      );
    const afternoonCluster = preferSameAnchorAfternoon
      ? mainCluster
      : pickNearbySupportCluster(mainCluster, supportClusters, usedClusterIds, ["walk"], 8000) ?? mainCluster;
    if (afternoonCluster?.id && afternoonCluster.id !== mainCluster?.id && afternoonCluster.id !== lunchCluster?.id) {
      usedClusterIds.add(afternoonCluster.id);
    }

    const afternoonOverride = getDayOverrideForSlot(params.requirement.replan_directives, day, "afternoon");
    const afternoonCandidates = getClusterCandidates(
      afternoonCluster,
      candidateLookup,
      afternoonOverride?.preferred_categories?.length
        ? afternoonOverride.preferred_categories.map((value) => normalizePlannerCategoryLabel(value))
        : ["walk", "scenic"]
    );
    slotPlans.push(
      buildSlotPlan({
        slot: "afternoon",
        strategy: afternoonCluster?.id === mainCluster?.id ? "anchor_cluster" : "leisure_cluster",
        cluster: afternoonCluster,
        candidateIds: selectCandidateIds(afternoonCandidates.length ? afternoonCandidates : getClusterCandidates(afternoonCluster, candidateLookup), 4),
        rationale:
          afternoonCluster?.id === mainCluster?.id
            ? "下午延续同片区轻松内容，把节奏从打卡切到逛和休息，控制疲劳度。"
            : "下午转到附近更适合休闲逛吃的片区，让整天从高强度观光自然过渡到轻松活动。"
      })
    );

    const eveningCluster =
      pickNearbySupportCluster(
        afternoonCluster ?? mainCluster,
        supportClusters,
        usedClusterIds,
        ["scenic", "food", "walk"],
        9000
      ) ??
      lunchCluster ??
      afternoonCluster ??
      mainCluster;
    if (eveningCluster?.id && !usedClusterIds.has(eveningCluster.id) && eveningCluster.id !== mainCluster?.id) {
      usedClusterIds.add(eveningCluster.id);
    }

    const eveningOverride = getDayOverrideForSlot(params.requirement.replan_directives, day, "evening");
    const eveningCandidates = getClusterCandidates(
      eveningCluster,
      candidateLookup,
      eveningOverride?.preferred_categories?.length
        ? eveningOverride.preferred_categories.map((value) => normalizePlannerCategoryLabel(value))
        : ["scenic", "food", "walk"]
    );
    slotPlans.push(
      buildSlotPlan({
        slot: "evening",
        strategy: "night_cluster",
        cluster: eveningCluster,
        candidateIds: selectCandidateIds(eveningCandidates.length ? eveningCandidates : getClusterCandidates(eveningCluster, candidateLookup), 4),
        rationale: "晚上安排夜景、夜游或轻松收尾片区，避免把高体力景点放在行程末段。"
      })
    );

    const dayCandidateIds = dedupeIds([
      ...slotPlans.flatMap((plan) => plan.candidateIds),
      ...fallbackCandidates.slice(0, 4).map((candidate) => candidate.id)
    ]);
    const auxCluster =
      findClusterById(params.clusters, lunchCluster?.id && lunchCluster.id !== mainCluster?.id ? lunchCluster.id : afternoonCluster?.id);

    dayPlans.push({
      day,
      intent: params.intent,
      mainClusterId: mainCluster?.id,
      auxClusterId: auxCluster?.id,
      mainClusterType: mainCluster?.type,
      focusLocation: mainCluster?.center ?? auxCluster?.center,
      candidateIds: dayCandidateIds,
      foodCandidateIds: slotPlans.find((plan) => plan.slot === "lunch")?.candidateIds ?? [],
      slotPlans
    });

    if (mainCluster) {
      const nextRemaining = remainingAnchors.filter((cluster) => cluster.id !== mainCluster.id);
      remainingAnchors.splice(0, remainingAnchors.length, ...nextRemaining);
    }
  }

  return dayPlans;
}

export function buildTravelPlanningStructure(params: {
  requirement: StructuredPayload;
  candidatePool: CandidatePool;
}): TravelPlanningStructure {
  const daysCount = getTripDays(params.requirement);
  const intentProfile = classifyIntent(params.requirement);
  const preparedCandidates = params.candidatePool.candidates.map(ensurePlannerEligibility);
  const debugSummary = buildCandidateDebugSummary(preparedCandidates);
  console.info("[debugCandidatePool]", debugSummary);
  const eligibleCandidates = preparedCandidates.filter(isPlannerSelectable);
  const warnings: string[] = [...params.candidatePool.warnings];

  if (!eligibleCandidates.length) {
    warnings.push("no planner-selectable candidates survived cluster filtering");
  }

  let clusters = [
    ...buildAnchorClusters({
      candidates: eligibleCandidates,
      intent: intentProfile.intent
    }),
    ...buildFoodClusters({
      candidates: eligibleCandidates,
      intent: intentProfile.intent
    })
  ].sort((a, b) => b.score - a.score);

  if (!clusters.length && eligibleCandidates.length) {
    const fallbackCluster = buildFallbackCluster([...eligibleCandidates].sort((a, b) => b.confidence - a.confidence));
    if (fallbackCluster) clusters = [fallbackCluster];
  }

  if (!clusters.length) {
    warnings.push("cluster builder could not find a stable anchor cluster");
  }

  const foodPool = buildFoodPool(eligibleCandidates, intentProfile.intent);
  if (!foodPool.length) warnings.push("no strong food pool candidates were found");

  const dayPlans = assignDayPlans({
    requirement: params.requirement,
    clusters,
    foodPool,
    candidates: eligibleCandidates,
    daysCount,
    intent: intentProfile.intent
  });

  if (clusters.some((cluster) => cluster.type === "single_anchor")) {
    warnings.push("some landmark candidates are treated as single anchors because nearby support content is limited");
  }

  return {
    intent: intentProfile.intent,
    intentReasons: intentProfile.reasons,
    clusters,
    dayPlans,
    warnings: Array.from(new Set(warnings))
  };
}

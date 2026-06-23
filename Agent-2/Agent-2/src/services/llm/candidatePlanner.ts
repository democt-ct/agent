import type {
  CandidatePool,
  CandidateQueryPlan,
  CandidateSelectionHint,
  CitySignatureSeed,
  Env,
  PlaceCategory,
  StructuredPayload
} from "../../types";
import { getDayOverrideForSlot } from "../replan/replanDirectives";
import { OpenAIResponsesClient } from "./openaiResponsesClient";

const PLACE_CATEGORIES: PlaceCategory[] = [
  "landmark",
  "food",
  "cafe",
  "mall",
  "park",
  "citywalk",
  "nightview",
  "nature",
  "museum"
];

const REQUIRED_CATEGORIES: PlaceCategory[] = [
  "landmark",
  "food",
  "cafe",
  "mall",
  "park",
  "citywalk",
  "nightview"
];

function getDestination(requirement: StructuredPayload): string {
  return String(requirement.destination || "").trim();
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

function inferCategoryFromText(text: string): PlaceCategory {
  if (/food|restaurant|eat|meal|\u7f8e\u98df|\u5c0f\u5403|\u9910\u996e/i.test(text)) return "food";
  if (/cafe|coffee|\u5496\u5561|\u4e0b\u5348\u8336/i.test(text)) return "cafe";
  if (/mall|shopping|\u5546\u573a|\u8d2d\u7269|\u5546\u5708/i.test(text)) return "mall";
  if (/citywalk|walk|stroll|\u6f2b\u6b65|\u8857\u533a|\u8001\u8857/i.test(text)) return "citywalk";
  if (/night|view|\u591c\u666f|\u591c\u5e02|\u591c\u6e38|\u89c2\u666f/i.test(text)) return "nightview";
  if (/park|green|\u516c\u56ed|\u7eff\u5730|\u6563\u6b65/i.test(text)) return "park";
  if (/nature|scenic|mountain|lake|\u81ea\u7136|\u98ce\u5149|\u5c71|\u6e56/i.test(text)) return "nature";
  if (/museum|history|culture|\u535a\u7269\u9986|\u5c55\u89c8|\u5386\u53f2|\u6587\u5316/i.test(text)) return "museum";
  return "landmark";
}

function buildCategoryKeywords(category: PlaceCategory, requirement: StructuredPayload, seed?: CitySignatureSeed): string[] {
  const interests = getInterests(requirement);
  const base: Record<PlaceCategory, string[]> = {
    landmark: ["\u666f\u70b9", "\u5730\u6807", "\u4ee3\u8868\u6027\u5730\u6807", "\u6253\u5361"],
    food: ["\u7f8e\u98df", "\u5f53\u5730\u7f8e\u98df", "\u5c0f\u5403", "\u591c\u5bb5"],
    cafe: ["\u5496\u5561", "\u4e0b\u5348\u8336", "\u72ec\u7acb\u5496\u5561", "\u4e66\u5e97\u5496\u5561"],
    mall: ["\u5546\u573a", "\u8d2d\u7269\u4e2d\u5fc3", "\u5546\u4e1a\u8857", "\u6b65\u884c\u8857"],
    park: ["\u516c\u56ed", "\u7eff\u9053", "\u57ce\u5e02\u516c\u56ed", "\u6ee8\u6c5f\u516c\u56ed"],
    citywalk: ["citywalk", "\u6f2b\u6b65", "\u8001\u8857", "\u8857\u533a", "\u6b65\u884c\u8def\u7ebf"],
    nightview: ["\u591c\u666f", "\u591c\u6e38", "\u89c2\u666f\u53f0", "\u706f\u5149\u79c0", "\u591c\u5e02"],
    nature: ["\u81ea\u7136\u98ce\u5149", "\u98ce\u666f\u533a", "\u5c71\u6c34", "\u516c\u56ed"],
    museum: ["\u535a\u7269\u9986", "\u5c55\u89c8", "\u5386\u53f2\u6587\u5316", "\u6587\u5316\u573a\u9986"]
  };

  const interestKeywords = interests.filter((interest) => {
    const guessed = inferCategoryFromText(interest);
    return guessed === category;
  });

  const seedKeywords = [
    ...(seed?.must_visit_attractions ?? []),
    ...(seed?.famous_foods ?? []),
    ...(seed?.food_areas ?? []),
    ...(seed?.shopping_areas ?? []),
    ...(seed?.night_options ?? []),
    ...(seed?.local_experiences ?? []),
    ...(seed?.backup_day_trips ?? [])
  ]
    .filter((item) => item.category === category)
    .map((item) => item.name);

  // Preference-driven keyword boosters for matched interest categories
  const boosterKeywords: string[] = interestKeywords.length > 0
    ? ({
        food: ["必吃餐厅", "本地人推荐", "网红美食", "老字号"],
        cafe: ["网红咖啡", "特色茶馆", "独立书店"],
        landmark: ["必打卡", "经典景点", "网红打卡地"],
        citywalk: ["文艺街区", "小众路线", "本地人逛的街"],
        nightview: ["夜景打卡", "夜市小吃", "江景"],
        nature: ["小众秘境", "自然风光", "户外徒步"],
        museum: ["必看展览", "文化地标", "艺术馆"]
      } as Record<PlaceCategory, string[]>)[category] ?? []
    : [];

  return Array.from(new Set([...seedKeywords, ...base[category], ...boosterKeywords, ...interestKeywords])).slice(0, 6);
}

function buildQueryPlanFallback(requirement: StructuredPayload, seed?: CitySignatureSeed): CandidateQueryPlan {
  const destination = getDestination(requirement);
  const interests = getInterests(requirement);
  const pace = getPace(requirement);
  const distanceTolerance = getDistanceTolerance(requirement);
  const categories = new Set<PlaceCategory>(["landmark", "food", "cafe", "mall", "park", "citywalk", "nightview"]);

  for (const interest of interests) {
    categories.add(inferCategoryFromText(interest));
  }
  if (pace === "relaxed") {
    categories.add("cafe");
    categories.add("park");
    categories.add("citywalk");
    categories.add("nightview");
  }
  if (distanceTolerance === "urban_only") {
    categories.add("food");
    categories.add("cafe");
    categories.add("mall");
  }
  if (distanceTolerance === "flexible") {
    categories.add("nature");
  }

  const globalPreferred = new Set(requirement.replan_directives?.global?.preferred_categories ?? []);
  const globalAvoid = new Set(requirement.replan_directives?.global?.avoid_categories ?? []);
  const overriddenCategories = new Set<PlaceCategory>();
  for (let day = 1; day <= Number(requirement.trip_days ?? 1); day += 1) {
    for (const slot of ["morning", "lunch", "afternoon", "evening"] as const) {
      const override = getDayOverrideForSlot(requirement.replan_directives, day, slot);
      override?.preferred_categories?.forEach((item) => overriddenCategories.add(item));
      override?.avoid_categories?.forEach((item) => globalAvoid.add(item));
    }
  }
  const orderedCategories = Array.from(categories)
    .filter((category) => !globalAvoid.has(category))
    .sort((a, b) => {
      const aBoost = Number(globalPreferred.has(a) || overriddenCategories.has(a));
      const bBoost = Number(globalPreferred.has(b) || overriddenCategories.has(b));
      if (aBoost !== bBoost) return bBoost - aBoost;
      return 0;
    });

  const planCategories = orderedCategories.slice(0, 9).map((category, index) => ({
    category,
    keywords: buildCategoryKeywords(category, requirement, seed).slice(0, 4),
    priority: Math.max(
      1,
      Math.min(
        5,
        5 - Math.min(index, 4) + (globalPreferred.has(category) || overriddenCategories.has(category) ? 1 : 0)
      )
    ),
    minResults: category === "food" || category === "cafe" ? 3 : 2,
    maxResults: category === "nightview" || category === "mall" ? 4 : 5,
    rationale: "fallback heuristic"
  }));

  return {
    destination,
    summary: "heuristic query plan",
    categories: planCategories,
    generalKeywords: Array.from(
      new Set([
        ...interests.slice(0, 4),
        ...(seed?.must_visit_attractions ?? []).slice(0, 2).map((item) => item.name),
        ...(seed?.food_areas ?? []).slice(0, 2).map((item) => item.name),
        ...(seed?.shopping_areas ?? []).slice(0, 2).map((item) => item.name)
      ])
    ),
    avoidCategories: Array.from(globalAvoid)
  };
}

function buildQueryPlanPrompt(params: {
  requirement: StructuredPayload;
  instruction?: string;
  seed?: CitySignatureSeed;
}): string {
  return JSON.stringify(
    {
      requirement: params.requirement,
      instruction: params.instruction ?? null,
      city_signature_seed: params.seed ?? null,
      rules: [
        "Do not generate final places.",
        "Only generate search categories and keywords.",
        "Cover landmark, food, cafe, mall, park, citywalk, and nightview.",
        "Use 2 to 5 keywords per category.",
        "Make the plan local and practical.",
        "Prefer routes and neighborhoods over generic scenic spots.",
        "If city_signature_seed is provided, query those names and areas before generic category terms.",
        "Important: major shopping or entertainment districts can be key city content, not just backup malls."
      ]
    },
    null,
    2
  );
}

export async function buildCandidateQueryPlan(params: {
  env: Env;
  requirement: StructuredPayload;
  instruction?: string;
  seed?: CitySignatureSeed;
}): Promise<CandidateQueryPlan> {
  const client = new OpenAIResponsesClient(params.env);
  const fallback = buildQueryPlanFallback(params.requirement, params.seed);
  const avoidCategories = new Set(fallback.avoidCategories);
  if (!client.isEnabled()) {
    return fallback;
  }

  try {
    const plan = await client.createStructuredJson<CandidateQueryPlan>({
      system: [
        "You are a travel search planner.",
        "Your job is to convert user requirements into a search plan for real POI and web tools.",
        "Never output final itinerary places.",
        "Never invent location truth.",
        "Use the real destination and current preferences to decide what to query."
      ].join("\n"),
      user: buildQueryPlanPrompt(params),
      schemaName: "candidate_query_plan",
      schema: {
        type: "object",
        additionalProperties: false,
        properties: {
          destination: { type: "string" },
          summary: { type: "string" },
          categories: {
            type: "array",
            minItems: 1,
            items: {
              type: "object",
              additionalProperties: false,
              properties: {
                category: { enum: PLACE_CATEGORIES },
                keywords: { type: "array", items: { type: "string" } },
                priority: { type: "integer", minimum: 1, maximum: 5 },
                minResults: { type: "integer", minimum: 1, maximum: 10 },
                maxResults: { type: "integer", minimum: 1, maximum: 12 },
                rationale: { type: "string" }
              },
              required: ["category", "keywords", "priority", "minResults", "maxResults", "rationale"]
            }
          },
          generalKeywords: { type: "array", items: { type: "string" } },
          avoidCategories: { type: "array", items: { enum: PLACE_CATEGORIES } }
        },
        required: ["destination", "summary", "categories", "generalKeywords", "avoidCategories"]
      }
    });

    return {
      ...plan,
      destination: plan.destination || fallback.destination,
      categories: (plan.categories.length ? plan.categories : fallback.categories)
        .filter((item) => !avoidCategories.has(item.category))
        .map((item) => ({
          ...item,
          priority: fallback.categories.find((entry) => entry.category === item.category)?.priority ?? item.priority
        })),
      generalKeywords: plan.generalKeywords.length ? plan.generalKeywords : fallback.generalKeywords,
      avoidCategories: Array.from(new Set([...(plan.avoidCategories ?? []), ...fallback.avoidCategories]))
    };
  } catch {
    return fallback;
  }
}

function summarizeCandidates(candidatePool: CandidatePool): Array<{
  category: string;
  items: Array<{
    id: string;
    name: string;
    category: PlaceCategory;
    city: string;
    address?: string;
    description?: string;
    confidence: number;
    source: string;
  }>;
}> {
  const grouped = new Map<string, Array<{
    id: string;
    name: string;
    category: PlaceCategory;
    city: string;
    address?: string;
    description?: string;
    confidence: number;
    source: string;
  }>>();

  for (const candidate of candidatePool.candidates) {
    const list = grouped.get(candidate.category) ?? [];
    list.push({
      id: candidate.id,
      name: candidate.name,
      category: candidate.category,
      city: candidate.city,
      address: candidate.address,
      description: candidate.description,
      confidence: candidate.confidence,
      source: candidate.source
    });
    grouped.set(candidate.category, list);
  }

  const snapshot = Array.from(grouped.entries()).map(([category, items]) => ({
    category,
    items: items.slice(0, 4)
  }));

  return snapshot;
}

function buildSelectionPrompt(params: {
  requirement: StructuredPayload;
  queryPlan: CandidateQueryPlan;
  candidatePool: CandidatePool;
}): string {
  return JSON.stringify(
    {
      requirement: params.requirement,
      query_plan: params.queryPlan,
      candidate_pool_snapshot: summarizeCandidates(params.candidatePool),
      rules: [
        "Only choose from candidate_pool_snapshot ids.",
        "Do not invent new places.",
        "Prefer a balanced mix of food, cafe, mall, park, citywalk, landmark, and nightview.",
        "Prefer candidates with location and higher confidence.",
        "Return a shortlist for the planner, not a final itinerary."
      ]
    },
    null,
    2
  );
}

export async function reviewCandidatePoolSelection(params: {
  env: Env;
  requirement: StructuredPayload;
  queryPlan: CandidateQueryPlan;
  candidatePool: CandidatePool;
}): Promise<CandidateSelectionHint> {
  const client = new OpenAIResponsesClient(params.env);
  const fallback: CandidateSelectionHint = {
    preferredCandidateIds: [],
    avoidCandidateIds: [],
    preferredCategories: params.queryPlan.categories.slice(0, 4).map((item) => item.category),
    notes: ["heuristic selection hint"]
  };

  if (!client.isEnabled() || !params.candidatePool.candidates.length) {
    return fallback;
  }

  try {
    const hint = await client.createStructuredJson<CandidateSelectionHint>({
      system: [
        "You are a travel candidate reviewer.",
        "Choose a shortlist from actual candidate ids.",
        "Never invent or replace ids.",
        "Keep the shortlist small and diverse.",
        "Do not output final itinerary."
      ].join("\n"),
      user: buildSelectionPrompt(params),
      schemaName: "candidate_selection_hint",
      schema: {
        type: "object",
        additionalProperties: false,
        properties: {
          preferredCandidateIds: { type: "array", items: { type: "string" } },
          avoidCandidateIds: { type: "array", items: { type: "string" } },
          preferredCategories: { type: "array", items: { enum: PLACE_CATEGORIES } },
          notes: { type: "array", items: { type: "string" } }
        },
        required: ["preferredCandidateIds", "avoidCandidateIds", "preferredCategories", "notes"]
      }
    });

    return {
      preferredCandidateIds: hint.preferredCandidateIds.slice(0, 12),
      avoidCandidateIds: hint.avoidCandidateIds.slice(0, 8),
      preferredCategories: hint.preferredCategories.length
        ? hint.preferredCategories
        : fallback.preferredCategories,
      notes: hint.notes.length ? hint.notes : fallback.notes
    };
  } catch {
    return fallback;
  }
}

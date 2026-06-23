import type {
  CandidatePool,
  CandidatePlace,
  ContentSignal,
  CandidateQueryTask,
  CandidateQueryPlan,
  CitySignatureSeed,
  Env,
  McpToolResult,
  PlaceCandidatePoolItem,
  PlaceCategory,
  StructuredPayload
} from "../../types";
import { McpClient, mcpClient as defaultMcpClient } from "../mcp/mcpClient";
import type { McpWebSearchItem } from "../mcp/mcpTypes";
import {
  buildSearchKeywordVariants,
  normalizeLocationScope
} from "../location/searchBaseResolver";
import {
  dedupeCandidatePlaces,
  normalizeStaticPoolCandidate,
  normalizeToolResultToCandidates
} from "./candidateNormalizer";
import { applyPoiGovernance } from "./poiGranularity";
import {
  buildContentSignals,
  inferContentSignalCategory,
  isValidPlaceName,
  webPlacesToPoiQueries
} from "./contentSignalExtractor";
import { buildCitySignaturePool, checkCityCoverage } from "../planning/citySignaturePool";
import { resolvePreferenceProfile } from "../planning/profileResolver";
import { getOptionalCityStaticPool } from "../planning/cityStaticPoolProvider";
import { filterGenericCandidates, isGenericQueryTerm } from "./genericTermFilter";

function getDestination(requirement: StructuredPayload): string {
  return String(requirement.destination || "").trim();
}

function getLocationScope(requirement: StructuredPayload): "city_only" | "surrounding" | "nearby" {
  return normalizeLocationScope(requirement.location_scope);
}

const REQUIRED_CATEGORIES: PlaceCategory[] = [
  "landmark",
  "food",
  "cafe",
  "mall",
  "park",
  "citywalk",
  "nightview"
];

const BONUS_CATEGORIES: PlaceCategory[] = ["museum", "nature"];

const CITY_SIGNATURE_SEARCH_TEMPLATES = [
  "{city} 必去景点",
  "{city} 旅游攻略 经典路线",
  "{city} 特色美食",
  "{city} 美食街 本地人",
  "{city} 夜景 夜市",
  "{city} 小众景点 本地体验"
];

const CATEGORY_QUERY_BANK: Record<PlaceCategory, string[]> = {
  landmark: ["\u666f\u70b9", "\u5730\u6807", "\u5fc5\u6253\u5361", "\u4ee3\u8868\u6027\u5730\u6807"],
  food: ["\u7f8e\u98df", "\u5f53\u5730\u7f8e\u98df", "\u5c0f\u5403", "\u591c\u5bb5"],
  cafe: ["\u5496\u5561", "\u4e0b\u5348\u8336", "\u7eb8\u4e66\u5e97\u5496\u5561", "\u72ec\u7acb\u5496\u5561"],
  mall: ["\u5546\u573a", "\u8d2d\u7269\u4e2d\u5fc3", "\u5546\u4e1a\u8857", "\u6b65\u884c\u8857"],
  park: ["\u516c\u56ed", "\u7eff\u9053", "\u6ee8\u6c5f\u516c\u56ed", "\u57ce\u5e02\u516c\u56ed"],
  citywalk: ["citywalk", "\u6f2b\u6b65", "\u8001\u8857", "\u8857\u533a", "\u6b65\u884c\u8def\u7ebf"],
  nightview: ["\u591c\u666f", "\u591c\u6e38", "\u89c2\u666f\u53f0", "\u706f\u5149\u79c0", "\u591c\u5e02"],
  nature: ["\u81ea\u7136\u98ce\u5149", "\u98ce\u666f\u533a", "\u5c71\u6c34", "\u516c\u56ed"],
  museum: ["\u535a\u7269\u9986", "\u5c55\u89c8", "\u5386\u53f2\u6587\u5316", "\u6587\u5316\u573a\u9986"]
};

const INTEREST_CATEGORY_PATTERNS: Array<{
  category: PlaceCategory;
  patterns: RegExp[];
}> = [
  { category: "food", patterns: [/\u7f8e\u98df|\u9910\u996e|\u5c0f\u5403|\u706b\u9505|food|restaurant/i] },
  { category: "cafe", patterns: [/\u5496\u5561|\u8336|\u4e0b\u5348\u8336|cafe|coffee/i] },
  { category: "mall", patterns: [/\u8d2d\u7269|\u5546\u573a|\u5546\u5708|mall|shopping/i] },
  { category: "park", patterns: [/\u516c\u56ed|\u7eff\u5730|\u6563\u6b65|park/i] },
  { category: "citywalk", patterns: [/\u6f2b\u6b65|citywalk|city walk|\u8857\u533a|\u8001\u8857/i] },
  { category: "nightview", patterns: [/\u591c\u666f|\u591c\u5e02|\u591c\u6e38|\u89c2\u666f|night/i] },
  { category: "nature", patterns: [/\u81ea\u7136|\u98ce\u5149|\u5c71|\u6e56|\u666f\u533a|scenic|nature/i] },
  { category: "museum", patterns: [/\u535a\u7269\u9986|\u5c55\u89c8|\u5386\u53f2|\u6587\u5316|museum/i] }
];

function normalizeKey(value: string): string {
  return value.trim().toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}

function isDiscoveryOnlyKeyword(keyword: string): boolean {
  return /(特色景点|本地美食|特色小吃|美食街|美食|商圈|商场|住宿|旅游攻略|经典路线|必去景点|小众景点|本地体验|夜景|夜市)/i.test(keyword);
}

function shouldDirectlyAddAmapResult(params: {
  keyword: string;
  queryCategory: PlaceCategory;
  resultName: string;
}): boolean {
  if (isDiscoveryOnlyKeyword(params.keyword)) return false;
  if (!isValidPlaceName(params.resultName)) return false;
  const compactKeyword = normalizeKey(params.keyword);
  const compactName = normalizeKey(params.resultName);
  if (!compactName) return false;
  return compactKeyword.includes(compactName) || compactName.includes(compactKeyword.replace(normalizeKey(params.resultName.split(" ")[0] ?? ""), ""));
}

function buildDiscoveryCandidates(params: {
  city: string;
  query: string;
  queryCategory: PlaceCategory;
  webItems: McpWebSearchItem[];
  poiCandidates: CandidatePlace[];
  contentSignals: ContentSignal[];
}): CandidatePool["discoveryCandidates"] {
  const items: NonNullable<CandidatePool["discoveryCandidates"]> = [];
  for (const signal of params.contentSignals) {
    for (const name of signal.extractedPlaceNames.filter(isValidPlaceName)) {
      items.push({
        name,
        category: signal.categoryHints[0] ?? params.queryCategory,
        source: "web_signal",
        confidence: signal.confidence,
        query: params.query
      });
    }
  }
  for (const poi of params.poiCandidates.slice(0, 8)) {
    if (!isValidPlaceName(poi.name)) continue;
    items.push({
      name: poi.name,
      category: poi.category,
      source: "generic_poi",
      confidence: poi.confidence,
      query: params.query
    });
  }
  const deduped = new Map<string, NonNullable<CandidatePool["discoveryCandidates"]>[number]>();
  for (const item of items) {
    const key = `${item.category}:${normalizeKey(item.name)}`;
    if (!deduped.has(key) || (deduped.get(key)?.confidence ?? 0) < item.confidence) {
      deduped.set(key, item);
    }
  }
  return Array.from(deduped.values()).slice(0, 16);
}

function promoteDiscoveryToCandidatePool(params: {
  city: string;
  discoveryCandidates: NonNullable<CandidatePool["discoveryCandidates"]>;
}): Array<{ keyword: string; category: PlaceCategory; sourceInterest: string; priority: number; rationale: string }> {
  return params.discoveryCandidates
    .filter((item) => isValidPlaceName(item.name))
    .slice(0, 10)
    .map((item) => ({
      keyword: `${params.city} ${item.name}`.trim(),
      category: item.category,
      sourceInterest: item.source,
      priority: Math.max(3, Math.round(item.confidence * 5)),
      rationale: `promoted discovery candidate from ${item.source}`
    }));
}

function getInterestCategories(requirement: StructuredPayload): PlaceCategory[] {
  const interests = Array.isArray(requirement.interests)
    ? requirement.interests.map((item) => String(item).trim()).filter(Boolean)
    : [];
  const categories = new Set<PlaceCategory>();
  for (const interest of interests) {
    const matched = INTEREST_CATEGORY_PATTERNS.find((item) =>
      item.patterns.some((pattern) => pattern.test(interest))
    );
    if (matched) categories.add(matched.category);
  }
  const pace = String(requirement.preferredPace ?? requirement.preferred_pace ?? "").trim();
  const distanceTolerance = String(requirement.distanceTolerance ?? requirement.distance_tolerance ?? "").trim();
  if (pace === "relaxed") {
    categories.add("cafe");
    categories.add("park");
    categories.add("citywalk");
    categories.add("nightview");
  }
  if (pace === "compact") {
    categories.add("landmark");
    categories.add("food");
    categories.add("mall");
  }
  if (distanceTolerance === "urban_only") {
    categories.add("food");
    categories.add("cafe");
    categories.add("mall");
    categories.add("citywalk");
  }
  if (distanceTolerance === "flexible") {
    categories.add("park");
    categories.add("nature");
  }
  return Array.from(categories);
}

function buildQueryPlan(requirement: StructuredPayload): Array<{
  keyword: string;
  category: PlaceCategory;
  sourceInterest?: string;
}> {
  const destination = getDestination(requirement);
  const interests = Array.isArray(requirement.interests)
    ? requirement.interests.map((item) => String(item).trim()).filter(Boolean)
    : [];
  const preferenceCategories = getInterestCategories(requirement);
  const categoryOrder = [
    ...REQUIRED_CATEGORIES.filter((category) => preferenceCategories.includes(category)),
    ...REQUIRED_CATEGORIES.filter((category) => !preferenceCategories.includes(category)),
    ...BONUS_CATEGORIES.filter((category) => preferenceCategories.includes(category)),
    ...BONUS_CATEGORIES.filter((category) => !preferenceCategories.includes(category))
  ];
  const plan: Array<{ keyword: string; category: PlaceCategory; sourceInterest?: string }> = [];
  const seen = new Set<string>();

  for (const category of categoryOrder) {
    const categoryKeywords = CATEGORY_QUERY_BANK[category] ?? [];
    const primaryKeywords = categoryKeywords.slice(0, 2);
    const bonusKeywords = categoryKeywords.slice(2, 4);
    const interestMatches = interests.filter((interest) =>
      INTEREST_CATEGORY_PATTERNS.some(
        (entry) => entry.category === category && entry.patterns.some((pattern) => pattern.test(interest))
      )
    );
    const keywords = [...primaryKeywords, ...bonusKeywords, ...interestMatches];

    for (const keyword of keywords) {
      const normalized = normalizeKey(`${destination} ${keyword}`);
      const key = `${category}:${normalized}`;
      if (seen.has(key)) continue;
      seen.add(key);
      plan.push({
        keyword: `${destination} ${keyword}`.trim(),
        category,
        sourceInterest: interestMatches[0] || category
      });
    }
  }

  if (!plan.length) {
    for (const category of REQUIRED_CATEGORIES) {
      const keyword = CATEGORY_QUERY_BANK[category][0];
      plan.push({
        keyword: `${destination} ${keyword}`.trim(),
        category,
        sourceInterest: "default"
      });
    }
  }

  return plan.slice(0, 16);
}

function buildSearchPlan(params: {
  requirement: StructuredPayload;
  queryPlan?: CandidateQueryPlan;
  citySignatureSeed?: CitySignatureSeed;
}): Array<{
  keyword: string;
  category: PlaceCategory;
  sourceInterest?: string;
  priority: number;
  minResults: number;
  maxResults: number;
  rationale?: string;
}> {
  if (!params.queryPlan) {
    const fallbackPlan = buildQueryPlan(params.requirement).map((item, index) => ({
      ...item,
      priority: Math.max(1, 5 - Math.min(index, 4)),
      minResults: 2,
      maxResults: 5
    }));
    const seedTasks = (params.citySignatureSeed
        ? [
          ...params.citySignatureSeed.must_visit_attractions,
          ...params.citySignatureSeed.famous_foods,
          ...params.citySignatureSeed.food_areas,
          ...params.citySignatureSeed.shopping_areas,
          ...params.citySignatureSeed.night_options,
          ...params.citySignatureSeed.local_experiences,
          ...params.citySignatureSeed.backup_day_trips
        ].slice(0, 10).map((item, index) => ({
          keyword: `${getDestination(params.requirement)} ${item.name}`.trim(),
          category: item.category,
          sourceInterest: item.reason,
          priority: Math.max(3, 5 - Math.floor(index / 2)),
          minResults: 1,
          maxResults: 4,
          rationale: "city signature seed"
        }))
      : []);
    return [...seedTasks, ...fallbackPlan].slice(0, 18);
  }

  const seen = new Set<string>();
  const searchPlan: Array<{
    keyword: string;
    category: PlaceCategory;
    sourceInterest?: string;
    priority: number;
    minResults: number;
    maxResults: number;
    rationale?: string;
  }> = [];

  for (const item of params.queryPlan.categories) {
    for (const keyword of item.keywords.slice(0, 4)) {
      const key = `${item.category}:${keyword.trim().toLowerCase()}`;
      if (seen.has(key)) continue;
      seen.add(key);
      searchPlan.push({
        keyword: `${params.queryPlan.destination} ${keyword}`.trim(),
        category: item.category,
        sourceInterest: item.rationale,
        priority: item.priority,
        minResults: item.minResults,
        maxResults: item.maxResults,
        rationale: item.rationale
      });
    }
  }

  if (params.citySignatureSeed) {
    for (const seedItem of [
      ...params.citySignatureSeed.must_visit_attractions,
      ...params.citySignatureSeed.famous_foods,
      ...params.citySignatureSeed.food_areas,
      ...params.citySignatureSeed.shopping_areas,
      ...params.citySignatureSeed.night_options,
      ...params.citySignatureSeed.local_experiences,
      ...params.citySignatureSeed.backup_day_trips
    ].slice(0, 12)) {
      const keyword = `${params.queryPlan.destination} ${seedItem.name}`.trim();
      const key = `seed:${seedItem.category}:${keyword.toLowerCase()}`;
      if (seen.has(key)) continue;
      seen.add(key);
      searchPlan.push({
        keyword,
        category: seedItem.category,
        sourceInterest: seedItem.reason,
        priority: Math.max(3, Math.round(seedItem.confidence * 5)),
        minResults: 1,
        maxResults: 4,
        rationale: "city signature seed"
      });
    }
  }

  for (const keyword of params.queryPlan.generalKeywords.slice(0, 4)) {
    const category = inferFallbackCategory(keyword);
    const key = `general:${keyword.trim().toLowerCase()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    searchPlan.push({
      keyword: `${params.queryPlan.destination} ${keyword}`.trim(),
      category,
      sourceInterest: "general_keyword",
      priority: 2,
      minResults: 2,
      maxResults: 4,
      rationale: "general keyword"
    });
  }

  return searchPlan.slice(0, 18);
}

function inferFallbackCategory(keyword: string): PlaceCategory {
  if (/food|restaurant|eat|meal|\u7f8e\u98df|\u5c0f\u5403|\u9910\u996e/i.test(keyword)) return "food";
  if (/cafe|coffee|\u5496\u5561|\u4e0b\u5348\u8336/i.test(keyword)) return "cafe";
  if (/mall|shopping|\u5546\u573a|\u8d2d\u7269|\u5546\u5708/i.test(keyword)) return "mall";
  if (/citywalk|walk|stroll|\u6f2b\u6b65|\u8857\u533a|\u8001\u8857/i.test(keyword)) return "citywalk";
  if (/night|view|\u591c\u666f|\u591c\u5e02|\u591c\u6e38|\u89c2\u666f/i.test(keyword)) return "nightview";
  if (/park|green|\u516c\u56ed|\u7eff\u5730|\u6563\u6b65/i.test(keyword)) return "park";
  if (/nature|scenic|mountain|lake|\u81ea\u7136|\u98ce\u5149|\u5c71|\u6e56/i.test(keyword)) return "nature";
  if (/museum|history|culture|\u535a\u7269\u9986|\u5c55\u89c8|\u5386\u53f2|\u6587\u5316/i.test(keyword)) return "museum";
  return "landmark";
}

function mapMissingCoverageToCategory(item: string): PlaceCategory | null {
  if (item === "must_visit_attractions") return "landmark";
  if (item === "famous_foods_or_food_areas") return "food";
  if (item === "night_options") return "nightview";
  if (item === "local_experiences") return "citywalk";
  return null;
}

export async function buildCandidatePool(params: {
  requirement: StructuredPayload;
  staticCandidates?: PlaceCandidatePoolItem[];
  mcpClient?: McpClient;
  env?: Env;
  queryPlan?: CandidateQueryPlan;
  citySignatureSeed?: CitySignatureSeed;
}): Promise<CandidatePool> {
  const destination = getDestination(params.requirement);
  const client = params.mcpClient ?? (params.env ? new McpClient(params.env) : defaultMcpClient);
  const warnings: string[] = [];
  const toolResults: McpToolResult[] = [];
  const queryTasks: CandidateQueryTask[] = [];
  const candidates: CandidatePlace[] = [];
  const discoveryCandidates: NonNullable<CandidatePool["discoveryCandidates"]> = [];
  const contentSignals: ContentSignal[] = [];
  const preferenceProfile = resolvePreferenceProfile(params.requirement);
  const locationScope = getLocationScope(params.requirement);

  console.info("[candidatePool] parsedRequirement", params.requirement);

  if (!destination) {
    return {
      destination,
      candidates: [],
      toolResults,
      queryTasks,
      warnings: ["destination is required to build candidate pool"]
    };
  }

  const staticPool = params.staticCandidates ?? getOptionalCityStaticPool(params.requirement);
  candidates.push(...staticPool.map(normalizeStaticPoolCandidate));

  const searchPlan = buildSearchPlan({
    requirement: params.requirement,
    queryPlan: params.queryPlan,
    citySignatureSeed: params.citySignatureSeed
  });
  const queryResults = await Promise.all(
    searchPlan.map(async (query) => {
      const webTask: CandidateQueryTask = {
        tool: "searchWeb",
        city: destination,
        keyword: query.keyword,
        category: query.category,
        sourceInterest: query.sourceInterest,
        priority: query.priority,
        plannedMinResults: query.minResults,
        plannedMaxResults: query.maxResults,
        rationale: query.rationale,
        status: "pending"
      };
      const poiTask: CandidateQueryTask = {
        tool: "searchPOI",
        city: destination,
        keyword: query.keyword,
        category: query.category,
        sourceInterest: query.sourceInterest,
        priority: query.priority,
        plannedMinResults: query.minResults,
        plannedMaxResults: query.maxResults,
        rationale: query.rationale,
        status: "pending"
      };
      queryTasks.push(webTask, poiTask);
      const keywordVariants = buildSearchKeywordVariants({
        destination,
        keyword: query.keyword,
        locationScope
      });
      console.info("[candidatePool] tool params", {
        searchWeb: { query: keywordVariants[0], city: destination },
        searchPOI: {
          city: locationScope === "city_only" ? destination : undefined,
          keyword: keywordVariants[0],
          category: query.category
        }
      });
      const [webResult, poiResult] = await Promise.all([
        client.searchWeb(keywordVariants[0], destination),
        Promise.any(
          keywordVariants.map((keywordVariant) =>
            client.searchPOI(
              locationScope === "city_only" ? destination : undefined,
              keywordVariant,
              query.category
            )
          )
        ).catch(() => client.searchPOI(destination, query.keyword, query.category))
      ]);
      return { webTask, poiTask, webResult, poiResult, category: query.category, keyword: query.keyword };
    })
  );

  for (const { webTask, poiTask, webResult, poiResult, category, keyword } of queryResults) {
    toolResults.push(webResult, poiResult);
    webTask.status = webResult.warnings.length ? "failed" : "ok";
    webTask.resultCount = Array.isArray(webResult.data) ? webResult.data.length : 0;
    webTask.warnings = webResult.warnings;
    poiTask.status = poiResult.warnings.length ? "failed" : "ok";
    poiTask.resultCount = Array.isArray(poiResult.data) ? poiResult.data.length : 0;
    poiTask.warnings = poiResult.warnings;
    warnings.push(...webResult.warnings, ...poiResult.warnings);
    const webCandidates = normalizeToolResultToCandidates(webResult, destination, category);
    const poiCandidates = normalizeToolResultToCandidates(poiResult, destination, category);
    candidates.push(...webCandidates.filter((item) => !isDiscoveryOnlyKeyword(keyword)));
    candidates.push(
      ...poiCandidates.filter((item) =>
        shouldDirectlyAddAmapResult({
          keyword,
          queryCategory: category,
          resultName: item.name
        })
      )
    );

    if (webResult.tool === "web_search" && Array.isArray(webResult.data) && webResult.data.length) {
      const webItems = webResult.data as McpWebSearchItem[];
      const nextSignals = buildContentSignals({
        city: destination,
        query: webTask.keyword,
        items: webItems,
        category
      });
      contentSignals.push(...nextSignals);
      discoveryCandidates.push(
        ...buildDiscoveryCandidates({
          city: destination,
          query: keyword,
          queryCategory: category,
          webItems,
          poiCandidates,
          contentSignals: nextSignals
        }) ?? []
      );
    }
  }

  const extraPoiQueryMap = new Map<
    string,
    {
      keyword: string;
      category: PlaceCategory;
      sourceInterest: string;
      priority: number;
      rationale: string;
    }
  >();
  for (const signal of contentSignals) {
    for (const [index, query] of webPlacesToPoiQueries({
      city: destination,
      extractedPlaceNames: signal.extractedPlaceNames.slice(0, 2),
      category: signal.categoryHints[0] ?? inferContentSignalCategory(signal.title),
      query: signal.title
    }).entries()) {
      const key = `${query.category}:${normalizeKey(query.keyword)}`;
      if (extraPoiQueryMap.has(key)) continue;
      extraPoiQueryMap.set(key, {
        keyword: query.keyword,
        category: query.category,
        sourceInterest: query.sourceInterest,
        priority: Math.max(1, 5 - index),
        rationale: query.rationale
      });
    }
  }
  for (const promoted of promoteDiscoveryToCandidatePool({
    city: destination,
    discoveryCandidates
  })) {
    const key = `${promoted.category}:${normalizeKey(promoted.keyword)}`;
    if (extraPoiQueryMap.has(key)) continue;
    extraPoiQueryMap.set(key, promoted);
  }

  const extraPoiQueries = Array.from(extraPoiQueryMap.values()).slice(0, 10);
  if (extraPoiQueries.length) {
    const extraPoiResults = await Promise.all(
      extraPoiQueries.map(async (query) => {
        const poiTask: CandidateQueryTask = {
          tool: "searchPOI",
          city: destination,
          keyword: query.keyword,
          category: query.category,
          sourceInterest: query.sourceInterest,
          priority: query.priority,
          plannedMinResults: 1,
          plannedMaxResults: 4,
          rationale: query.rationale,
          status: "pending"
        };
        queryTasks.push(poiTask);
        const keywordVariants = buildSearchKeywordVariants({
          destination,
          keyword: query.keyword,
          locationScope
        });
        const poiResult = await Promise.any(
          keywordVariants.map((keywordVariant) =>
            client.searchPOI(
              locationScope === "city_only" ? destination : undefined,
              keywordVariant,
              query.category
            )
          )
        ).catch(() => client.searchPOI(destination, query.keyword, query.category));
        return { poiTask, poiResult, category: query.category };
      })
    );

    for (const { poiTask, poiResult, category } of extraPoiResults) {
      toolResults.push(poiResult);
      poiTask.status = poiResult.warnings.length ? "failed" : "ok";
      poiTask.resultCount = Array.isArray(poiResult.data) ? poiResult.data.length : 0;
      poiTask.warnings = poiResult.warnings;
      warnings.push(...poiResult.warnings);
      candidates.push(...normalizeToolResultToCandidates(poiResult, destination, category));
    }
  }

  const dedupedCandidates = dedupeCandidatePlaces(candidates);
  const governedInitial = applyPoiGovernance({
    candidates: dedupedCandidates,
    requirement: params.requirement,
    queryTasks,
    queryPlan: params.queryPlan,
    warnings
  });
  let citySignaturePool = buildCitySignaturePool(destination, {
    destination,
    candidates: governedInitial.candidates,
    toolResults,
    queryTasks,
    queryPlan: params.queryPlan,
    contentSignals,
    warnings: governedInitial.warnings,
    preferenceProfile
  }, params.requirement);
  let coverageCheck = checkCityCoverage({
    destination,
    candidates: governedInitial.candidates,
    toolResults,
    queryTasks,
    queryPlan: params.queryPlan,
    contentSignals,
    warnings: governedInitial.warnings,
    preferenceProfile,
    citySignaturePool
  });

  if (coverageCheck.missing_items.length) {
    const supplementalQueries = coverageCheck.missing_items
      .flatMap((missing) => {
        const category = mapMissingCoverageToCategory(missing);
        if (!category) return [];
        return CITY_SIGNATURE_SEARCH_TEMPLATES
          .filter((template) =>
            (missing === "must_visit_attractions" && /景点|经典路线/.test(template)) ||
            (missing === "famous_foods_or_food_areas" && /美食|美食街/.test(template)) ||
            (missing === "night_options" && /夜景 夜市/.test(template)) ||
            (missing === "local_experiences" && /小众景点 本地体验/.test(template))
          )
          .map((template) => ({
            keyword: template.replace("{city}", destination),
            category
          }));
      })
      .slice(0, 6);

    const supplementalResults = await Promise.all(
      supplementalQueries.map(async (query) => {
        const keywordVariants = buildSearchKeywordVariants({
          destination,
          keyword: query.keyword,
          locationScope
        });
        const [webResult, poiResult] = await Promise.all([
          client.searchWeb(keywordVariants[0], destination),
          Promise.any(
            keywordVariants.map((keywordVariant) =>
              client.searchPOI(
                locationScope === "city_only" ? destination : undefined,
                keywordVariant,
                query.category
              )
            )
          ).catch(() => client.searchPOI(destination, query.keyword, query.category))
        ]);
        return { query, webResult, poiResult };
      })
    );

    for (const { query, webResult, poiResult } of supplementalResults) {
      toolResults.push(webResult, poiResult);
      warnings.push(...webResult.warnings, ...poiResult.warnings);
      candidates.push(...normalizeToolResultToCandidates(webResult, destination, query.category));
      candidates.push(...normalizeToolResultToCandidates(poiResult, destination, query.category));
      if (Array.isArray(webResult.data) && webResult.data.length) {
        contentSignals.push(
          ...buildContentSignals({
            city: destination,
            query: query.keyword,
            items: webResult.data as McpWebSearchItem[],
            category: query.category
          })
        );
      }
    }
  }

  const finalCandidates = dedupeCandidatePlaces(candidates);
  const governedFinal = applyPoiGovernance({
    candidates: finalCandidates,
    requirement: params.requirement,
    queryTasks,
    queryPlan: params.queryPlan,
    warnings
  });

  const genericFilteredCandidates = filterGenericCandidates(governedFinal.candidates);
  const genericCount = governedFinal.candidates.length - genericFilteredCandidates.length;
  if (genericCount > 0) {
    warnings.push(`filtered ${genericCount} generic/invalid candidates`);
    console.info("[candidatePool] filtered generic candidates", {
      before: governedFinal.candidates.length,
      after: genericFilteredCandidates.length,
      filtered: genericCount
    });
  }

  citySignaturePool = buildCitySignaturePool(destination, {
    destination,
    candidates: genericFilteredCandidates,
    discoveryCandidates,
    toolResults,
    queryTasks,
    queryPlan: params.queryPlan,
    contentSignals,
    warnings: governedFinal.warnings,
    preferenceProfile
  }, params.requirement);
  coverageCheck = checkCityCoverage({
    destination,
    candidates: genericFilteredCandidates,
    toolResults,
    queryTasks,
    queryPlan: params.queryPlan,
    contentSignals,
    warnings: governedFinal.warnings,
    preferenceProfile,
    citySignaturePool
  });
  console.info("[candidatePool] candidatePlaces count", {
    raw: candidates.length,
    deduped: governedFinal.candidates.length,
    afterGenericFilter: genericFilteredCandidates.length
  });

  return {
    destination,
    candidates: genericFilteredCandidates,
    toolResults,
    queryTasks,
    queryPlan: params.queryPlan ?? {
      destination,
      summary: "heuristic query plan",
      categories: buildQueryPlan(params.requirement).map((item, index) => ({
        category: item.category,
        keywords: [item.keyword],
        priority: Math.max(1, 5 - Math.min(index, 4)),
        minResults: 2,
        maxResults: 5,
        rationale: item.sourceInterest ?? "fallback"
      })),
      generalKeywords: [],
      avoidCategories: []
    },
    contentSignals,
    preferenceProfile,
    citySignatureSeed: params.citySignatureSeed,
    citySignaturePool,
    coverageCheck,
    planningMode: governedFinal.planningMode,
    groundingDiagnostics: governedFinal.groundingDiagnostics,
    governanceSummary: governedFinal.governanceSummary,
    warnings: governedFinal.warnings
  };
}

import type {
  CandidatePlace,
  GeoPoint,
  McpToolResult,
  PlaceCandidatePoolItem,
  PlaceCategory
} from "../../types";
import type { McpPoiItem, McpWebSearchItem } from "../mcp/mcpTypes";

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 80);
}

function normalizeText(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]/gu, "");
}

function roundLocation(point?: GeoPoint): string {
  if (!point) return "";
  return `${point.lng.toFixed(4)},${point.lat.toFixed(4)}`;
}

function inferContentTags(text: string): string[] {
  const tags: string[] = [];
  if (/逛吃|美食|小吃|餐厅|food|eat|meal|restaurant/i.test(text)) tags.push("foodie");
  if (/拍照|打卡|出片|photo|photogenic|insta/i.test(text)) tags.push("photo");
  if (/夜景|夜游|夜市|night|evening|灯光/i.test(text)) tags.push("nightview");
  if (/约会|情侣|date|romantic/i.test(text)) tags.push("date");
  if (/亲子|孩子|family|kid|kids/i.test(text)) tags.push("family");
  if (/咖啡|下午茶|coffee|cafe/i.test(text)) tags.push("cafe");
  if (/商场|购物|shopping|mall/i.test(text)) tags.push("shopping");
  if (/citywalk|漫步|漫游|walk|stroll|老街|街区/i.test(text)) tags.push("citywalk");
  if (/自然|公园|山|湖|scenic|nature|徒步/i.test(text)) tags.push("nature");
  return Array.from(new Set(tags));
}

function inferCategoryFromText(text: string): PlaceCategory {
  if (/\u9910\u996e|\u7f8e\u98df|\u5c0f\u5403|\u706b\u9505|food|restaurant/i.test(text)) return "food";
  if (/\u5496\u5561|\u8336|\u996e\u54c1|cafe|coffee/i.test(text)) return "cafe";
  if (/\u591c\u666f|\u591c\u5e02|\u591c\u6e38|\u89c2\u666f|night/i.test(text)) return "nightview";
  if (/\u516c\u56ed|\u7eff\u5730|park/i.test(text)) return "park";
  if (/\u6f2b\u6b65|\u8857\u533a|citywalk|city walk|\u6b65\u884c|\u8001\u8857/i.test(text)) return "citywalk";
  if (/\u535a\u7269\u9986|\u5c55\u89c8|museum/i.test(text)) return "museum";
  if (/\u8d2d\u7269|\u5546\u573a|\u5546\u5708|mall|shopping/i.test(text)) return "mall";
  if (/\u98ce\u666f|\u666f\u533a|\u540d\u80dc|\u81ea\u7136|scenic|nature/i.test(text)) return "nature";
  return "landmark";
}

function suggestedDurationForCategory(category: PlaceCategory): number {
  switch (category) {
    case "food":
      return 75;
    case "cafe":
      return 60;
    case "nightview":
      return 90;
    case "mall":
      return 90;
    case "museum":
      return 120;
    case "nature":
      return 150;
    case "park":
    case "citywalk":
      return 100;
    default:
      return 90;
  }
}

function buildOriginQueryTag(result: McpToolResult): string | undefined {
  const city = String(result.query.city ?? "").trim();
  const keyword = String(result.query.keyword ?? result.query.query ?? "").trim();
  const category = String(result.query.category ?? "").trim();
  const raw = [result.tool, city, keyword, category].filter(Boolean).join("_");
  return raw ? `origin_query:${slugify(raw)}` : undefined;
}

export function normalizePoiCandidate(item: McpPoiItem): CandidatePlace {
  const category = item.category ?? inferCategoryFromText(`${item.name} ${item.rawType ?? ""}`);
  return {
    id: `poi_${item.id}`,
    name: item.name,
    city: item.city,
    category,
    location: item.location,
    address: item.address,
    source: "mcp_poi",
    sourceRef: item.id,
    tags: [category, item.district, item.rawType].filter((tag): tag is string => Boolean(tag)),
    description: item.rawType,
    suggestedDurationMinutes: suggestedDurationForCategory(category),
    confidence: item.location ? 0.86 : 0.68
  };
}

export function normalizeWebCandidate(
  item: McpWebSearchItem,
  city: string,
  category?: PlaceCategory
): CandidatePlace {
  const text = `${item.title} ${item.snippet ?? ""}`;
  const resolvedCategory = category ?? inferCategoryFromText(text);
  const contentTags = inferContentTags(text);
  return {
    id: `web_${slugify(item.url || item.title)}`,
    name: item.title,
    city,
    category: resolvedCategory,
    source: "content_search",
    sourceRef: item.url,
    tags: [resolvedCategory, "content_search", ...contentTags],
    description: item.snippet,
    suggestedDurationMinutes: suggestedDurationForCategory(resolvedCategory),
    confidence: 0.42
  };
}

export function normalizeStaticPoolCandidate(item: PlaceCandidatePoolItem): CandidatePlace {
  return {
    id: `static_${item.id}`,
    name: item.name,
    city: item.city,
    category: item.category,
    location: item.location,
    source: "static_pool",
    sourceRef: item.id,
    tags: item.tags,
    suggestedDurationMinutes: item.suggestedDurationMinutes,
    confidence: item.location ? 0.72 : 0.55
  };
}

export function normalizeToolResultToCandidates(
  result: McpToolResult,
  fallbackCity: string,
  category?: PlaceCategory
): CandidatePlace[] {
  const originQueryTag = buildOriginQueryTag(result);
  if (result.tool === "poi_search") {
    return (result.data as McpPoiItem[]).map((item, index) => {
      const candidate = normalizePoiCandidate(item);
      return {
        ...candidate,
        confidence: Math.max(0.55, candidate.confidence - index * 0.015),
        tags: Array.from(new Set([
          ...candidate.tags,
          originQueryTag,
          category ? `query_category:${category}` : "",
          item.category ? `poi_category:${item.category}` : ""
        ].filter((tag): tag is string => Boolean(tag)))),
        queryCategories: category ? [category] : item.category ? [item.category] : []
      };
    });
  }
  if (result.tool === "place_details") {
    const item = result.data as McpPoiItem | null;
    return item ? [normalizePoiCandidate(item)] : [];
  }
  if (result.tool === "web_search") {
    return (result.data as McpWebSearchItem[]).map((item, index) => {
      const candidate = normalizeWebCandidate(item, fallbackCity, category);
      return {
        ...candidate,
        confidence: Math.max(0.25, candidate.confidence - index * 0.03),
        tags: Array.from(new Set([
          ...candidate.tags,
          originQueryTag,
          category ? `query_category:${category}` : ""
        ].filter((tag): tag is string => Boolean(tag)))),
        queryCategories: category ? [category] : []
      };
    });
  }
  return [];
}

export function dedupeCandidatePlaces(candidates: CandidatePlace[]): CandidatePlace[] {
  const byKey = new Map<string, CandidatePlace>();

  for (const candidate of candidates) {
    const sourceId = candidate.sourceRef ? `${candidate.source}:${candidate.sourceRef}` : "";
    const nameCityKey = `${normalizeText(candidate.city)}:${normalizeText(candidate.name)}`;
    const locationKey = candidate.location
      ? `${normalizeText(candidate.city)}:${roundLocation(candidate.location)}`
      : "";
    const keys = [sourceId, nameCityKey, locationKey].filter(Boolean);
    const existing = keys.map((key) => byKey.get(key)).find(Boolean);

    if (!existing) {
      for (const key of keys) byKey.set(key, candidate);
      continue;
    }

    const merged: CandidatePlace = {
      ...existing,
      location: existing.location ?? candidate.location,
      address: existing.address ?? candidate.address,
      description: existing.description ?? candidate.description,
      confidence: Math.max(existing.confidence, candidate.confidence),
      tags: Array.from(new Set([...existing.tags, ...candidate.tags])),
      queryCategories: Array.from(new Set([...(existing.queryCategories ?? []), ...(candidate.queryCategories ?? [])])),
      subStops: Array.from(new Set([...(existing.subStops ?? []), ...(candidate.subStops ?? [])])),
      roles: Array.from(new Set([...(existing.roles ?? []), ...(candidate.roles ?? [])])),
      mergedAliases: Array.from(new Set([...(existing.mergedAliases ?? []), ...(candidate.mergedAliases ?? [])]))
    };
    for (const key of keys) byKey.set(key, merged);
  }

  return Array.from(new Set(byKey.values()));
}

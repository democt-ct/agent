import type { ContentSignal, PlaceCategory } from "../../types";
import type { McpWebSearchItem } from "../mcp/mcpTypes";

function normalizeText(value: string): string {
  return value.trim().toLowerCase();
}

function simpleHash(value: string): string {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash.toString(36);
}

function inferCategoryFromText(text: string): PlaceCategory {
  if (/food|restaurant|eat|meal|餐饮|美食|小吃/i.test(text)) return "food";
  if (/cafe|coffee|咖啡|下午茶/i.test(text)) return "cafe";
  if (/mall|shopping|商场|购物|商圈/i.test(text)) return "mall";
  if (/citywalk|walk|stroll|漫步|街区|老街/i.test(text)) return "citywalk";
  if (/night|view|夜景|夜市|夜游|观景/i.test(text)) return "nightview";
  if (/park|green|公园|绿地|散步/i.test(text)) return "park";
  if (/nature|scenic|mountain|lake|自然|风光|山|湖/i.test(text)) return "nature";
  if (/museum|history|culture|博物馆|展览|历史|文化/i.test(text)) return "museum";
  return "landmark";
}

const GENERIC_PLACE_TERMS = [
  "特色景点",
  "本地美食",
  "热门景点",
  "旅游攻略",
  "美食推荐",
  "必去路线",
  "经典路线",
  "商圈",
  "住宿",
  "景点",
  "美食",
  "特色",
  "打卡",
  "路线"
];

const INVALID_NAME_PATTERNS = [
  /看到|这座|这里|如果|可以|适合|推荐|攻略|路线|特色|上午|下午|晚上|同学|晒出|浸润|摇碎|体验|打卡|玩法|第一次/i,
  /[,.;:!?，。；：！？]/,
  /的.{4,}/,
  /(大学同学|青石板|银杏叶|茶香|蜜蜡)/i
];

export function isValidPlaceName(name: string): boolean {
  const value = name.trim();
  if (!value) return false;
  if (value.length > 20) return false;
  if (/^[\d\s\W_]+$/.test(value)) return false;
  if (GENERIC_PLACE_TERMS.some((term) => value.includes(term) || term.includes(value))) return false;
  if (INVALID_NAME_PATTERNS.some((pattern) => pattern.test(value))) return false;
  const chineseChars = (value.match(/[\u4e00-\u9fff]/g) ?? []).length;
  if (chineseChars > 15) return false;
  if (/\s{2,}/.test(value)) return false;
  return true;
}

function extractSceneTags(text: string): string[] {
  const lowered = text.toLowerCase();
  const tags: string[] = [];
  const rules: Array<[string, RegExp]> = [
    ["foodie", /food|eat|meal|restaurant|美食|小吃|餐饮/i],
    ["photo", /photo|photogenic|insta|拍照|出片|打卡/i],
    ["nightview", /night|evening|夜景|夜游|夜市|灯光/i],
    ["date", /date|romantic|约会|情侣/i],
    ["family", /family|kid|kids|亲子|儿童|家庭/i],
    ["cafe", /coffee|cafe|咖啡|下午茶/i],
    ["shopping", /shopping|mall|商场|购物|逛街/i],
    ["citywalk", /citywalk|walk|stroll|漫步|老街|街区/i],
    ["nature", /scenic|nature|mountain|lake|自然|风景|山|湖/i]
  ];

  for (const [tag, pattern] of rules) {
    if (pattern.test(lowered)) tags.push(tag);
  }
  return Array.from(new Set(tags));
}

export function extractPlaceNamesFromWeb(text: string): string[] {
  const candidates = new Set<string>();
  const normalized = text.replace(/\s+/g, " ").trim();
  const segments = normalized
    .split(/[、,，;；:：|/\\()\[\]{}<>《》“”"'`·\-—]/g)
    .map((item) => item.trim())
    .filter(Boolean);

  for (const segment of segments) {
    if (segment.length < 2 || segment.length > 20) continue;
    if (/^(top|best|day|part|chapter|vol\.?|no\.?)$/i.test(segment)) continue;
    if (/^[\d\s\W_]+$/.test(segment)) continue;
    if (isValidPlaceName(segment)) candidates.add(segment);
  }

  const patterns = [
    /([A-Za-z\u4e00-\u9fff]{2,20}?)(?:景点|美食|小吃|咖啡|商场|公园|夜景|夜游|博物馆|展览|街区|老街|打卡)/g,
    /["'“”]?([A-Za-z\u4e00-\u9fff]{2,20})["'“”]?(?:的)?(?:推荐|攻略|打卡|必去)/g
  ];

  for (const pattern of patterns) {
    for (const match of normalized.matchAll(pattern)) {
      const value = (match[1] || "").trim();
      if (value.length >= 2 && value.length <= 20 && !/^[\d\s\W_]+$/.test(value) && isValidPlaceName(value)) {
        candidates.add(value);
      }
    }
  }

  return Array.from(candidates).slice(0, 5);
}

export function webPlacesToPoiQueries(params: {
  city: string;
  extractedPlaceNames: string[];
  category?: PlaceCategory;
  query: string;
}): Array<{ keyword: string; category: PlaceCategory; sourceInterest: string; rationale: string }> {
  return params.extractedPlaceNames
    .filter(isValidPlaceName)
    .map((placeName) => ({
      keyword: `${params.city} ${placeName}`.trim(),
      category: params.category ?? inferCategoryFromText(`${params.query} ${placeName}`),
      sourceInterest: "content_signal",
      rationale: `validated web place name from ${params.query}`
    }));
}

function inferCategoryHints(sceneTags: string[], text: string): PlaceCategory[] {
  const hints = new Set<PlaceCategory>();
  const lowered = normalizeText(text);

  if (sceneTags.includes("foodie")) hints.add("food");
  if (sceneTags.includes("cafe")) hints.add("cafe");
  if (sceneTags.includes("shopping")) hints.add("mall");
  if (sceneTags.includes("citywalk")) hints.add("citywalk");
  if (sceneTags.includes("nightview")) hints.add("nightview");
  if (sceneTags.includes("family")) hints.add("park");
  if (sceneTags.includes("nature")) hints.add("nature");

  if (/museum|history|culture|博物馆|展览|历史|文化/i.test(lowered)) {
    hints.add("museum");
  }

  if (!hints.size) {
    hints.add(inferCategoryFromText(lowered));
  }

  return Array.from(hints);
}

export function buildContentSignals(params: {
  city: string;
  query: string;
  items: McpWebSearchItem[];
  category?: PlaceCategory;
}): ContentSignal[] {
  const signals: ContentSignal[] = [];

  params.items.forEach((item, index) => {
    const text = `${item.title} ${item.snippet ?? ""}`.trim();
    const sceneTags = extractSceneTags(text);
    const placeNames = extractPlaceNamesFromWeb(text);
    const categoryHints = Array.from(
      new Set<PlaceCategory>([
        ...(params.category ? [params.category] : []),
        ...inferCategoryHints(sceneTags, text)
      ])
    );
    const confidence = Math.max(
      0.3,
      0.9 - index * 0.08 - (placeNames.length ? 0 : 0.12) - (sceneTags.length ? 0 : 0.1)
    );

    signals.push({
      id: `content-${index}-${simpleHash(item.url || item.title || text)}`,
      source: "web_search",
      city: params.city,
      query: params.query,
      title: item.title,
      snippet: item.snippet,
      url: item.url,
      extractedPlaceNames: placeNames,
      sceneTags,
      styleTags: sceneTags,
      categoryHints,
      confidence
    });
  });

  return signals;
}

export function inferContentSignalCategory(text: string): PlaceCategory {
  return inferCategoryFromText(text);
}

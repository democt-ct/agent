import type { CandidatePlace, PlannedItem, PlaceCategory } from "../../types";

const GENERIC_QUERY_TERMS = new Set([
  "特色景点",
  "本地美食",
  "热门景点",
  "旅游攻略",
  "美食推荐",
  "必去路线",
  "经典路线",
  "必去景点",
  "小众景点",
  "本地体验",
  "美食街",
  "特色小吃",
  "特色美食",
  "网红打卡",
  "网红景点",
  "拍照圣地",
  "约会圣地",
  "亲子游",
  "周末去哪",
  "一日游",
  "两日游",
  "三日游",
  "几日游",
  "旅游行程",
  "旅行攻略",
  "自驾游",
  "穷游",
  "背包游",
  "度假",
  "民宿推荐",
  "酒店推荐",
  "住宿推荐",
  "门票",
  "开放时间",
  "怎么去",
  "交通",
  "地址",
  "电话",
  "营业时间"
]);

const GENERIC_CATEGORY_TERMS = new Set([
  "景点",
  "美食",
  "小吃",
  "咖啡",
  "商场",
  "购物",
  "公园",
  "绿地",
  "散步",
  "夜景",
  "夜市",
  "夜游",
  "观景",
  "自然",
  "风光",
  "山水",
  "风景",
  "博物馆",
  "展览",
  "历史文化",
  "文化",
  "商圈",
  "步行街",
  "老街",
  "街区",
  "打卡",
  "路线",
  "特色",
  "住宿",
  "酒店",
  "民宿",
  "餐饮",
  "餐厅",
  "饭店",
  "火锅",
  "烧烤",
  "串串",
  "酒吧",
  "夜宵",
  "下午茶",
  "茶馆"
]);

const INTERNAL_STATE_WORDS = new Set([
  "closing",
  "fallback",
  "unknown",
  "default",
  "cluster",
  "supplemental",
  "pending",
  "loading",
  "placeholder",
  "test",
  "demo",
  "sample",
  "example",
  "mock",
  "dummy",
  "temp",
  "tmp"
]);

const REVIEW_SENTENCE_PATTERNS = [
  /推荐大家去/,
  /强烈推荐/,
  /一定要去/,
  /不去后悔/,
  /值得打卡/,
  /必去/,
  /必吃/,
  /必玩/,
  /超级好吃/,
  /非常好吃/,
  /环境很好/,
  /服务很好/,
  /性价比高/,
  /下次还来/,
  /强烈安利/,
  /种草/,
  /拔草/,
  /踩雷/,
  /避雷/,
  /攻略分享/,
  /经验分享/,
  /游记/,
  /行程安排/,
  /路线规划/,
  /省钱攻略/,
  /住宿攻略/,
  /交通攻略/,
  /美食攻略/
];

const QUERY_KEYWORD_PATTERNS = [
  /怎么去/,
  /如何到达/,
  /在哪里/,
  /地址在哪/,
  /营业时间/,
  /开放时间/,
  /门票多少钱/,
  /门票价格/,
  /值得去吗/,
  /好玩吗/,
  /好吃吗/,
  /怎么样/,
  /好不好/,
  /有没有/,
  /有没有推荐/,
  /有没有好的/,
  /有没有好吃的/,
  /有没有好玩的/
];

function normalizeForComparison(value: string): string {
  return value.trim().toLowerCase().replace(/[^\u4e00-\u9fffa-z0-9]/g, "");
}

export function isGenericQueryTerm(name: string): boolean {
  const normalized = normalizeForComparison(name);
  if (!normalized) return false;

  if (GENERIC_QUERY_TERMS.has(normalized)) return true;
  if (GENERIC_CATEGORY_TERMS.has(normalized)) return true;
  if (INTERNAL_STATE_WORDS.has(normalized)) return true;

  for (const term of GENERIC_QUERY_TERMS) {
    if (normalized.includes(normalizeForComparison(term)) || normalizeForComparison(term).includes(normalized)) {
      return true;
    }
  }

  for (const term of GENERIC_CATEGORY_TERMS) {
    if (normalized.includes(normalizeForComparison(term)) || normalizeForComparison(term).includes(normalized)) {
      return true;
    }
  }

  if (REVIEW_SENTENCE_PATTERNS.some((pattern) => pattern.test(name))) return true;
  if (QUERY_KEYWORD_PATTERNS.some((pattern) => pattern.test(name))) return true;

  if (normalized.length <= 2 && !/[\u4e00-\u9fff]/.test(normalized)) return true;

  return false;
}

export function isRealPlaceName(name: string): boolean {
  if (!name || name.length < 2) return false;
  if (name.length > 30) return false;

  if (isGenericQueryTerm(name)) return false;

  if (/^[\d\s\W_]+$/.test(name)) return false;
  if (/\s{2,}/.test(name)) return false;

  const chineseChars = (name.match(/[\u4e00-\u9fff]/g) ?? []).length;
  if (chineseChars > 18) return false;

  return true;
}

export function hasValidPoiSource(candidate: CandidatePlace): boolean {
  if (candidate.source === "static_pool" || candidate.source === "llm_curator") return true;
  if (candidate.source === "mcp_poi") return true;
  if (candidate.location) return true;
  if (candidate.source === "content_search" && candidate.tags.some((tag) => tag.startsWith("poi_verified:"))) return true;
  return false;
}

export function isFoodSuitableForMealSlot(
  candidate: CandidatePlace,
  mealSlot: "morning" | "lunch" | "afternoon" | "evening"
): boolean {
  if (candidate.category !== "food" && candidate.category !== "cafe") return true;

  const nameLower = candidate.name.toLowerCase();
  const tagsLower = candidate.tags.join(" ").toLowerCase();
  const text = `${nameLower} ${tagsLower}`;

  if (mealSlot === "morning") {
    if (/火锅|串串|烧烤|酒吧|夜宵|麻辣烫|冒菜|烤肉|烤鱼|小龙虾/.test(text)) return false;
    if (/夜市|大排档|宵夜|深夜/.test(text)) return false;
  }

  return true;
}

export function isGenericDayTheme(theme: string): boolean {
  if (!theme) return true;
  const normalized = normalizeForComparison(theme);

  for (const word of INTERNAL_STATE_WORDS) {
    if (normalized.includes(word)) return true;
  }

  if (/fallback|unknown|default|cluster/i.test(theme)) return true;

  return false;
}

export function validateRouteItem(item: PlannedItem): {
  isValid: boolean;
  issues: string[];
} {
  const issues: string[] = [];

  if (isGenericQueryTerm(item.name)) {
    issues.push(`generic term used as route item: "${item.name}"`);
  }

  if (!isRealPlaceName(item.name)) {
    issues.push(`invalid place name: "${item.name}"`);
  }

  if (!item.location && item.source !== "static_pool" && item.source !== "llm_curator") {
    issues.push(`missing location for item: "${item.name}"`);
  }

  if (item.granularity === "service_level") {
    issues.push(`service-level POI used as main item: "${item.name}"`);
  }

  if (item.granularity === "internal_poi_level") {
    issues.push(`internal POI used as main item: "${item.name}"`);
  }

  return {
    isValid: issues.length === 0,
    issues
  };
}

export function validateCandidateForPool(candidate: CandidatePlace): {
  isValid: boolean;
  issues: string[];
} {
  const issues: string[] = [];

  if (isGenericQueryTerm(candidate.name)) {
    issues.push(`generic term in candidate pool: "${candidate.name}"`);
  }

  if (!isRealPlaceName(candidate.name)) {
    issues.push(`invalid candidate name: "${candidate.name}"`);
  }

  if (!hasValidPoiSource(candidate)) {
    issues.push(`candidate lacks valid POI source: "${candidate.name}" (source: ${candidate.source})`);
  }

  if (!candidate.location && candidate.source !== "static_pool" && candidate.source !== "llm_curator") {
    issues.push(`candidate missing location: "${candidate.name}"`);
  }

  if (candidate.granularity === "service_level") {
    issues.push(`service-level candidate: "${candidate.name}"`);
  }

  return {
    isValid: issues.length === 0,
    issues
  };
}

export function filterGenericCandidates(candidates: CandidatePlace[]): CandidatePlace[] {
  return candidates.filter((candidate) => {
    const validation = validateCandidateForPool(candidate);
    return validation.isValid;
  });
}

export function filterGenericItems(items: PlannedItem[]): PlannedItem[] {
  return items.filter((item) => {
    const validation = validateRouteItem(item);
    return validation.isValid;
  });
}

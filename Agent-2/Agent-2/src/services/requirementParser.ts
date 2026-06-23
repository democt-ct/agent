import type { StructuredPayload } from "../types";

const INTEREST_KEYWORDS = [
  "拍照",
  "美食",
  "咖啡",
  "亲子",
  "购物",
  "博物馆",
  "自然风光",
  "海边",
  "城市漫游",
  "夜景"
];

const CONSTRAINT_KEYWORDS = [
  "不要太累",
  "预算有限",
  "带老人",
  "带孩子",
  "不想打车",
  "低强度",
  "轻松一点"
];

const CHINESE_DAY_NUMBERS: Record<string, number> = {
  一: 1,
  二: 2,
  两: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 7,
  八: 8,
  九: 9,
  十: 10
};

function extractBudget(text: string): number | null {
  const match = text.match(/预算\s*(\d{3,6})\s*元?/u);
  return match ? Number(match[1]) : null;
}

function extractTripDays(text: string): number | null {
  const digitMatch = text.match(/(\d+)\s*[天日]/u);
  if (digitMatch) {
    return Number(digitMatch[1]);
  }

  const chineseMatch = text.match(/([一二两三四五六七八九十])\s*[天日]/u);
  return chineseMatch ? CHINESE_DAY_NUMBERS[chineseMatch[1]] ?? null : null;
}

function extractOriginCity(text: string): string | undefined {
  const match = text.match(/从([\u4e00-\u9fa5]{2,8})出发/u);
  return match?.[1];
}

function extractInterests(text: string): string[] | undefined {
  const matches = INTEREST_KEYWORDS.filter((keyword) => text.includes(keyword));
  return matches.length > 0 ? matches : undefined;
}

function extractConstraints(text: string): string[] | undefined {
  const matches = CONSTRAINT_KEYWORDS.filter((keyword) => text.includes(keyword));
  return matches.length > 0 ? matches : undefined;
}

function extractTravelersSummary(text: string): string | undefined {
  if (text.includes("带老人") && text.includes("带孩子")) {
    return "family_with_elder_and_child";
  }
  if (text.includes("带老人")) return "with_elder";
  if (text.includes("带孩子") || text.includes("亲子")) {
    return "family_with_child";
  }
  if (text.includes("情侣")) return "couple";
  if (text.includes("朋友")) return "friends";
  return undefined;
}

export function parseRequirement(rawInput: string): StructuredPayload {
  const payload: StructuredPayload = {};
  const budget = extractBudget(rawInput);
  const tripDays = extractTripDays(rawInput);
  const originCity = extractOriginCity(rawInput);
  const interests = extractInterests(rawInput);
  const constraints = extractConstraints(rawInput);
  const travelersSummary = extractTravelersSummary(rawInput);

  if (budget !== null) payload.budget_max = budget;
  if (tripDays !== null) payload.trip_days = tripDays;
  if (originCity) payload.origin_city = originCity;
  if (interests) payload.interests = interests;
  if (constraints) payload.constraints = constraints;
  if (travelersSummary) payload.travelers_summary = travelersSummary;

  return payload;
}

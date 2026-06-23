import type { PlaceCandidatePoolItem, StructuredPayload } from "../../types";

export const MIANYANG_PLACE_POOL: PlaceCandidatePoolItem[] = [
  {
    id: "yuewanglou",
    name: "\u8d8a\u738b\u697c",
    city: "\u7ef5\u9633",
    zone: "urban_core",
    poolTier: "base",
    category: "landmark",
    location: { lng: 104.75404, lat: 31.46159 },
    suggestedDurationMinutes: 90,
    tags: ["landmark", "city_view", "culture", "\u5730\u6807", "\u62cd\u7167\u6253\u5361"]
  },
  {
    id: "majiakou",
    name: "\u9a6c\u5bb6\u5df7",
    city: "\u7ef5\u9633",
    zone: "urban_core",
    poolTier: "base",
    category: "food",
    location: { lng: 104.75052, lat: 31.46216 },
    suggestedDurationMinutes: 75,
    tags: ["food", "local_snack", "walkable", "\u7f8e\u98df", "\u5348\u9910", "\u665a\u9910"]
  },
  {
    id: "fujiang_river_walk",
    name: "\u6daa\u6c5f\u6cbf\u5cb8Citywalk",
    city: "\u7ef5\u9633",
    zone: "urban_core",
    poolTier: "base",
    category: "citywalk",
    location: { lng: 104.7549, lat: 31.4682 },
    suggestedDurationMinutes: 80,
    tags: ["river", "walk", "relaxed", "\u4f11\u95f2", "citywalk", "\u4e0d\u5168\u662f\u666f\u70b9"]
  },
  {
    id: "mianyang_museum",
    name: "\u7ef5\u9633\u535a\u7269\u9986",
    city: "\u7ef5\u9633",
    zone: "urban_core",
    poolTier: "base",
    category: "museum",
    location: { lng: 104.7056, lat: 31.4676 },
    suggestedDurationMinutes: 100,
    tags: ["museum", "culture", "indoor", "\u5730\u6807"]
  },
  {
    id: "sanjiang_bandao",
    name: "\u4e09\u6c5f\u534a\u5c9b\u591c\u666f",
    city: "\u7ef5\u9633",
    zone: "urban_core",
    poolTier: "base",
    category: "nightview",
    location: { lng: 104.7286, lat: 31.4558 },
    suggestedDurationMinutes: 90,
    tags: ["river", "photo", "\u591c\u666f", "\u62cd\u7167\u6253\u5361"]
  },
  {
    id: "kaide_plaza",
    name: "\u51ef\u5fb7\u5e7f\u573a",
    city: "\u7ef5\u9633",
    zone: "urban_core",
    poolTier: "base",
    category: "mall",
    location: { lng: 104.7481, lat: 31.4638 },
    suggestedDurationMinutes: 90,
    tags: ["mall", "shopping", "indoor", "\u5546\u573a", "\u4f11\u95f2"]
  },
  {
    id: "downtown_cafe",
    name: "\u6daa\u57ce\u533a\u5496\u5561\u5c0f\u61a9",
    city: "\u7ef5\u9633",
    zone: "urban_core",
    poolTier: "base",
    category: "cafe",
    location: { lng: 104.7462, lat: 31.4651 },
    suggestedDurationMinutes: 60,
    tags: ["cafe", "relaxed", "\u5496\u5561", "\u8f7b\u677e", "\u4e0d\u5168\u662f\u666f\u70b9"]
  },
  {
    id: "fule_shan",
    name: "\u5bcc\u4e50\u5c71\u516c\u56ed",
    city: "\u7ef5\u9633",
    zone: "urban_edge",
    poolTier: "extended",
    category: "park",
    location: { lng: 104.7798, lat: 31.4642 },
    suggestedDurationMinutes: 120,
    tags: ["park", "light_hike", "history", "\u81ea\u7136\u98ce\u5149", "\u4f11\u95f2"]
  },
  {
    id: "mianyang_science_museum",
    name: "\u7ef5\u9633\u79d1\u6280\u9986",
    city: "\u7ef5\u9633",
    zone: "urban_edge",
    poolTier: "extended",
    category: "museum",
    location: { lng: 104.6904, lat: 31.4748 },
    suggestedDurationMinutes: 100,
    tags: ["science", "indoor", "family", "\u5730\u6807"]
  },
  {
    id: "xishan_park",
    name: "\u897f\u5c71\u516c\u56ed",
    city: "\u7ef5\u9633",
    zone: "urban_edge",
    poolTier: "extended",
    category: "park",
    location: { lng: 104.7167, lat: 31.4753 },
    suggestedDurationMinutes: 110,
    tags: ["park", "relaxed", "green", "\u81ea\u7136\u98ce\u5149", "\u8f7b\u677e"]
  },
  {
    id: "xianhai",
    name: "\u4ed9\u6d77\u98ce\u666f\u533a",
    city: "\u7ef5\u9633",
    zone: "nearby_nature",
    poolTier: "extended",
    category: "nature",
    location: { lng: 104.8568, lat: 31.5382 },
    suggestedDurationMinutes: 180,
    tags: ["lake", "nature", "half_day", "\u81ea\u7136\u98ce\u5149"]
  },
  {
    id: "luofu_mountain",
    name: "\u7f57\u6d6e\u5c71\u98ce\u666f\u533a",
    city: "\u7ef5\u9633",
    zone: "nearby_nature",
    poolTier: "extended",
    category: "nature",
    location: { lng: 104.3939, lat: 31.6748 },
    suggestedDurationMinutes: 240,
    tags: ["mountain", "nature", "far", "\u81ea\u7136\u98ce\u5149"]
  }
];

export function shouldUseMianyangPool(requirement: StructuredPayload): boolean {
  return requirement.destination === "\u7ef5\u9633";
}

export function getBaseMianyangPool(): PlaceCandidatePoolItem[] {
  return MIANYANG_PLACE_POOL.filter((item) => item.poolTier === "base");
}

export function getExtendedMianyangPool(): PlaceCandidatePoolItem[] {
  return MIANYANG_PLACE_POOL;
}

function unique(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}

function normalizeSignalText(text: string): string[] {
  const signals: string[] = [];
  const rules: Array<[string, string[]]> = [
    ["\u7f8e\u98df", ["\u7f8e\u98df", "\u5c0f\u5403", "\u5403", "\u706b\u9505", "\u9910"]],
    ["\u5496\u5561", ["\u5496\u5561", "\u4e0b\u5348\u8336"]],
    ["\u5546\u573a", ["\u5546\u573a", "\u901b\u8857", "\u8d2d\u7269", "\u5546\u4e1a"]],
    ["citywalk", ["citywalk", "\u6f2b\u6b65", "\u6563\u6b65", "\u901b"]],
    ["\u591c\u666f", ["\u591c\u666f", "\u591c\u5e02", "\u665a\u4e0a"]],
    ["\u5730\u6807", ["\u5730\u6807", "\u4eba\u6587", "\u6587\u5316"]],
    ["\u62cd\u7167\u6253\u5361", ["\u62cd\u7167", "\u6253\u5361"]],
    ["\u81ea\u7136\u98ce\u5149", ["\u81ea\u7136", "\u98ce\u666f", "\u5c71", "\u6e56", "\u6237\u5916"]],
    ["\u8f7b\u677e", ["\u8f7b\u677e", "\u4e0d\u7d2f", "\u6162"]],
    ["\u4e0d\u60f3\u592a\u8fdc", ["\u4e0d\u8fdc", "\u5e02\u533a", "\u4ec5\u5e02\u533a"]],
    ["\u4e0d\u5168\u662f\u666f\u70b9", ["\u4e0d\u5168\u662f\u666f\u70b9", "\u4e0d\u8981\u90fd\u662f\u666f\u70b9", "\u522b\u5168\u662f\u666f\u70b9"]]
  ];

  for (const [label, keywords] of rules) {
    if (keywords.some((keyword) => text.includes(keyword))) {
      signals.push(label);
    }
  }
  return signals;
}

export function getPreferenceSignals(requirement: StructuredPayload): string[] {
  const preferences = requirement.user_preferences as
    | { interests?: string[]; preferredPace?: string; distanceTolerance?: string }
    | undefined;
  const rawSignals = [
    ...(requirement.interests ?? []),
    ...(requirement.constraints ?? []),
    ...(preferences?.interests ?? []),
    preferences?.preferredPace === "relaxed" ? "\u8f7b\u677e" : "",
    preferences?.distanceTolerance === "urban_only" ? "\u4e0d\u60f3\u592a\u8fdc" : "",
    preferences?.distanceTolerance === "nearby_ok" ? "\u53ef\u63a5\u53d7\u8fd1\u90ca" : "",
    preferences?.distanceTolerance === "flexible" ? "\u8ddd\u79bb\u7075\u6d3b" : ""
  ].filter(Boolean);

  return unique([...rawSignals, ...normalizeSignalText(rawSignals.join(" "))]);
}

export function hasPreferenceEnhancement(requirement: StructuredPayload): boolean {
  return getPreferenceSignals(requirement).length > 0;
}

export function wantsNature(requirement: StructuredPayload): boolean {
  const preferences = requirement.user_preferences as
    | { distanceTolerance?: string }
    | undefined;
  if (preferences?.distanceTolerance === "urban_only") {
    return false;
  }
  return getPreferenceSignals(requirement).some((signal) =>
    ["\u81ea\u7136\u98ce\u5149", "\u81ea\u7136", "\u98ce\u666f", "\u5c71", "\u6e56", "\u6237\u5916"].includes(signal)
  );
}


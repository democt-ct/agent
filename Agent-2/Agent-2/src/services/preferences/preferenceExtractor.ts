import type {
  DistanceTolerance,
  PreferredPace,
  StructuredPayload,
  UserPreferencePayload
} from "../../types";

const INTEREST_RULES: Array<[string, string[]]> = [
  ["\u7f8e\u98df", ["\u7f8e\u98df", "\u5c0f\u5403", "\u5403", "\u9910", "\u591c\u5bb5"]],
  ["\u5496\u5561", ["\u5496\u5561", "\u4e0b\u5348\u8336"]],
  ["\u5546\u573a", ["\u5546\u573a", "\u901b\u8857", "\u8d2d\u7269", "\u5546\u4e1a"]],
  ["citywalk", ["citywalk", "\u6f2b\u6b65", "\u6563\u6b65", "\u901b"]],
  ["\u5730\u6807", ["\u5730\u6807", "\u4eba\u6587", "\u6587\u5316"]],
  ["\u81ea\u7136\u98ce\u5149", ["\u81ea\u7136", "\u98ce\u666f", "\u5c71", "\u6e56", "\u6237\u5916"]],
  ["\u591c\u666f", ["\u591c\u666f", "\u591c\u5e02", "\u665a\u4e0a"]],
  ["\u62cd\u7167\u6253\u5361", ["\u62cd\u7167", "\u6253\u5361"]],
  ["\u4e0d\u5168\u662f\u666f\u70b9", ["\u4e0d\u5168\u662f\u666f\u70b9", "\u4e0d\u8981\u90fd\u662f\u666f\u70b9", "\u522b\u5168\u662f\u666f\u70b9"]]
];

function unique(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}

function hasAny(text: string, keywords: string[]): boolean {
  return keywords.some((keyword) => text.includes(keyword));
}

export function extractPreferencesFromText(text: string): UserPreferencePayload {
  const preferences: UserPreferencePayload = {};

  if (hasAny(text, ["\u8f7b\u677e", "\u4e0d\u7d2f", "\u6162\u4e00\u70b9", "\u4f11\u95f2"])) {
    preferences.preferredPace = "relaxed";
  } else if (hasAny(text, ["\u7d27\u51d1", "\u591a\u73a9\u51e0\u4e2a", "\u591a\u5b89\u6392"])) {
    preferences.preferredPace = "compact";
  } else if (hasAny(text, ["\u9002\u4e2d", "\u6b63\u5e38\u8282\u594f"])) {
    preferences.preferredPace = "moderate";
  }

  const interests = INTEREST_RULES
    .filter(([, keywords]) => hasAny(text, keywords))
    .map(([interest]) => interest);
  if (interests.length) {
    preferences.interests = unique(interests);
  }

  if (hasAny(text, ["\u4ec5\u5e02\u533a", "\u5e02\u533a", "\u4e0d\u60f3\u592a\u8fdc", "\u522b\u592a\u8fdc"])) {
    preferences.distanceTolerance = "urban_only";
  } else if (hasAny(text, ["\u8fd1\u90ca", "\u5468\u8fb9", "\u53ef\u4ee5\u7a0d\u5fae\u8fdc\u4e00\u70b9"])) {
    preferences.distanceTolerance = "nearby_ok";
  } else if (hasAny(text, ["\u8fdc\u4e00\u70b9\u4e5f\u884c", "\u8ddd\u79bb\u7075\u6d3b"])) {
    preferences.distanceTolerance = "flexible";
  }

  return preferences;
}

export function hasPreferenceSignal(preferences: UserPreferencePayload): boolean {
  return Boolean(
    preferences.preferredPace ||
      preferences.distanceTolerance ||
      preferences.interests?.length
  );
}

export function mergePreferences(
  existing: UserPreferencePayload,
  update: UserPreferencePayload
): UserPreferencePayload {
  return {
    preferredPace: update.preferredPace ?? existing.preferredPace,
    distanceTolerance: update.distanceTolerance ?? existing.distanceTolerance,
    interests: update.interests?.length
      ? unique([...(existing.interests ?? []), ...update.interests])
      : existing.interests
  };
}

export function applyPreferencesToRequirement(params: {
  requirement: StructuredPayload;
  preferences: UserPreferencePayload;
  explicitInput?: StructuredPayload;
}): StructuredPayload {
  const explicit = params.explicitInput ?? {};
  const next: StructuredPayload = { ...params.requirement };

  if (!explicit.interests?.length && params.preferences.interests?.length) {
    next.interests = unique([...(next.interests ?? []), ...params.preferences.interests]);
  }

  const constraints = new Set(next.constraints ?? []);
  if (!explicit.constraints?.length && params.preferences.preferredPace) {
    const labels: Record<PreferredPace, string> = {
      relaxed: "\u8f7b\u677e",
      moderate: "\u9002\u4e2d",
      compact: "\u7d27\u51d1"
    };
    constraints.add(labels[params.preferences.preferredPace]);
  }

  if (!explicit.constraints?.length && params.preferences.distanceTolerance) {
    const labels: Record<DistanceTolerance, string> = {
      urban_only: "\u4ec5\u5e02\u533a",
      nearby_ok: "\u53ef\u63a5\u53d7\u8fd1\u90ca",
      flexible: "\u8ddd\u79bb\u7075\u6d3b"
    };
    constraints.add(labels[params.preferences.distanceTolerance]);
  }

  if (constraints.size) {
    next.constraints = [...constraints];
  }

  next.user_preferences = params.preferences;
  return next;
}


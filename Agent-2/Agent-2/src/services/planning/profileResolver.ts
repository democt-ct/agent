import type {
  PlannerProfileId,
  PreferenceParams,
  ResolvedPreferenceProfile,
  StructuredPayload
} from "../../types";

const PROFILE_PRESETS: Record<PlannerProfileId, PreferenceParams> = {
  light_comfort: {
    fatigue_tolerance: "low",
    food_priority: "medium",
    famous_spot_priority: "medium",
    hidden_gem_priority: "low",
    allow_food_transfer: false,
    max_major_transfers_per_day: 1,
    schedule_density: "low_to_medium",
    walking_preference: "low"
  },
  classic_must_visit: {
    fatigue_tolerance: "medium",
    food_priority: "medium",
    famous_spot_priority: "high",
    hidden_gem_priority: "low",
    allow_food_transfer: false,
    max_major_transfers_per_day: 2,
    schedule_density: "medium",
    walking_preference: "medium"
  },
  food_first: {
    fatigue_tolerance: "medium",
    food_priority: "high",
    famous_spot_priority: "medium",
    hidden_gem_priority: "medium",
    allow_food_transfer: true,
    max_major_transfers_per_day: 2,
    schedule_density: "medium",
    walking_preference: "medium"
  },
  deep_local: {
    fatigue_tolerance: "medium",
    food_priority: "high",
    famous_spot_priority: "medium",
    hidden_gem_priority: "high",
    allow_food_transfer: true,
    max_major_transfers_per_day: 2,
    schedule_density: "medium",
    walking_preference: "medium"
  },
  high_intensity: {
    fatigue_tolerance: "high",
    food_priority: "medium",
    famous_spot_priority: "high",
    hidden_gem_priority: "medium",
    allow_food_transfer: true,
    max_major_transfers_per_day: 3,
    schedule_density: "high",
    walking_preference: "high"
  },
  family_friendly: {
    fatigue_tolerance: "very_low",
    food_priority: "medium",
    famous_spot_priority: "medium",
    hidden_gem_priority: "low",
    allow_food_transfer: false,
    max_major_transfers_per_day: 1,
    schedule_density: "low",
    walking_preference: "low"
  }
};

function getText(payload: StructuredPayload): string {
  return [
    payload.travelers_summary,
    ...(payload.interests ?? []),
    ...(payload.constraints ?? [])
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function mergePreferenceParams(
  primary: PreferenceParams,
  secondary: PreferenceParams
): PreferenceParams {
  const fatigueOrder = ["very_low", "low", "medium", "high"] as const;
  const levelOrder = ["low", "medium", "high"] as const;
  const densityOrder = ["low", "low_to_medium", "medium", "high"] as const;

  const minLevel = <T extends readonly string[]>(values: T, left: T[number], right: T[number]): T[number] =>
    values[Math.min(values.indexOf(left), values.indexOf(right))];
  const maxLevel = <T extends readonly string[]>(values: T, left: T[number], right: T[number]): T[number] =>
    values[Math.max(values.indexOf(left), values.indexOf(right))];

  return {
    fatigue_tolerance: minLevel(fatigueOrder, primary.fatigue_tolerance, secondary.fatigue_tolerance),
    food_priority: maxLevel(levelOrder, primary.food_priority, secondary.food_priority),
    famous_spot_priority: maxLevel(levelOrder, primary.famous_spot_priority, secondary.famous_spot_priority),
    hidden_gem_priority: maxLevel(levelOrder, primary.hidden_gem_priority, secondary.hidden_gem_priority),
    allow_food_transfer: primary.allow_food_transfer || secondary.allow_food_transfer,
    max_major_transfers_per_day: Math.min(
      primary.max_major_transfers_per_day,
      secondary.max_major_transfers_per_day
    ),
    schedule_density: minLevel(densityOrder, primary.schedule_density, secondary.schedule_density),
    walking_preference: minLevel(
      ["low", "medium", "high"] as const,
      primary.walking_preference ?? "medium",
      secondary.walking_preference ?? "medium"
    )
  };
}

export function resolvePreferenceProfile(payload: StructuredPayload): ResolvedPreferenceProfile {
  const text = getText(payload);
  let primary: PlannerProfileId = "light_comfort";
  let secondary: PlannerProfileId = "classic_must_visit";
  const reasons: string[] = [];

  const wantsEasy = /不想太累|轻松|舒适|慢一点|少走|老人|长辈|亲子|带娃/.test(text);
  const wantsFood = /好吃|美食|小吃|本地菜|吃得好|餐厅|夜宵/.test(text);
  const wantsClassic = /必打卡|经典|地标|著名|代表性/.test(text);
  const wantsLocal = /本地|小众|老店|local|citywalk|街区/.test(text);
  const wantsIntense = /高强度|尽量多看|多去几个|打卡越多越好/.test(text);
  const familyLike = /亲子|老人|长辈|带娃|低风险/.test(text);

  if (familyLike) {
    primary = "family_friendly";
    secondary = wantsFood ? "food_first" : "classic_must_visit";
    reasons.push("检测到亲子/老人低疲劳信号");
  } else if (wantsIntense && !wantsEasy) {
    primary = "high_intensity";
    secondary = wantsClassic ? "classic_must_visit" : "food_first";
    reasons.push("检测到高强度多转场诉求");
  } else if (wantsFood && wantsEasy) {
    primary = "light_comfort";
    secondary = "food_first";
    reasons.push("检测到不想太累且重视吃");
  } else if (wantsFood) {
    primary = "food_first";
    secondary = wantsLocal ? "deep_local" : "classic_must_visit";
    reasons.push("检测到美食优先诉求");
  } else if (wantsLocal) {
    primary = "deep_local";
    secondary = wantsEasy ? "light_comfort" : "classic_must_visit";
    reasons.push("检测到本地街区/小众体验诉求");
  } else if (wantsClassic) {
    primary = "classic_must_visit";
    secondary = wantsEasy ? "light_comfort" : "food_first";
    reasons.push("检测到经典地标诉求");
  } else {
    reasons.push("未识别到强偏好，使用舒适+经典默认组合");
  }

  return {
    primary_profile: primary,
    secondary_profile: secondary,
    preference_params: mergePreferenceParams(PROFILE_PRESETS[primary], PROFILE_PRESETS[secondary]),
    reason: reasons.join("；")
  };
}

import type { StructuredPayload, TripRequirement } from "../types";

function getPayload(requirement: TripRequirement): StructuredPayload {
  return JSON.parse(requirement.structured_payload_json) as StructuredPayload;
}

function buildDayTheme(
  day: number,
  tripDays: number,
  interests: string[],
  destination: string
): string {
  if (day === 1) {
    return `${destination}\u5230\u8fbe\u4e0e\u8f7b\u91cf\u719f\u6089`;
  }
  if (day === tripDays) {
    return `${destination}\u6536\u5c3e\u4e0e\u8fd4\u7a0b\u51c6\u5907`;
  }
  if (interests.includes("\u7f8e\u98df")) {
    return `${destination}\u8857\u533a\u6f2b\u6e38\u4e0e\u7f8e\u98df\u5b89\u6392`;
  }
  if (interests.includes("\u62cd\u7167")) {
    return `${destination}\u51fa\u7247\u8def\u7ebf\u4e0e\u666f\u89c2\u6f2b\u6b65`;
  }
  return `${destination}\u7ecf\u5178\u4e00\u65e5\u8def\u7ebf`;
}

function buildItems(theme: string, relaxed: boolean): Array<Record<string, string>> {
  return [
    {
      time: "\u4e0a\u5348",
      name: theme.includes("\u5230\u8fbe")
        ? "\u9152\u5e97\u5165\u4f4f\u4e0e\u5468\u8fb9\u719f\u6089"
        : "\u6838\u5fc3\u7247\u533a\u6b65\u884c\u8def\u7ebf",
      note: relaxed
        ? "\u4ee5\u4f4e\u5f3a\u5ea6\u8282\u594f\u5f00\u59cb\uff0c\u907f\u514d\u5b89\u6392\u8fc7\u6ee1"
        : "\u4f18\u5148\u8986\u76d6\u6838\u5fc3\u533a\u57df"
    },
    {
      time: "\u4e0b\u5348",
      name: theme.includes("\u7f8e\u98df")
        ? "\u8857\u533a\u901b\u5403\u4e0e\u5730\u6807\u6253\u5361"
        : "\u4e3b\u666f\u70b9\u6216\u4ee3\u8868\u6027\u8857\u533a\u6e38\u89c8",
      note: relaxed
        ? "\u9884\u7559\u4f11\u606f\u4e0e\u673a\u52a8\u65f6\u95f4"
        : "\u9002\u5f53\u8865\u5145 1-2 \u4e2a\u5173\u8054\u70b9\u4f4d"
    },
    {
      time: "\u665a\u4e0a",
      name: "\u672c\u5730\u9910\u996e\u4e0e\u591c\u95f4\u6563\u6b65",
      note: relaxed
        ? "\u5c3d\u91cf\u5c31\u8fd1\u5b89\u6392\uff0c\u51cf\u5c11\u6298\u8fd4"
        : "\u53ef\u52a0\u5165\u591c\u666f\u6216\u7279\u8272\u591c\u5e02"
    }
  ];
}

export function generateTemplateItinerary(requirement: TripRequirement): {
  title: string;
  summary: string;
  itinerary: Record<string, unknown>;
  budgetEstimate: Record<string, unknown>;
  warnings: string[];
} {
  const payload = getPayload(requirement);
  const destination = payload.destination ?? "\u76ee\u7684\u5730";
  const tripDays = payload.trip_days ?? 3;
  const interests = payload.interests ?? [];
  const constraints = payload.constraints ?? [];
  const relaxed =
    constraints.includes("\u4e0d\u8981\u592a\u7d2f") ||
    constraints.includes("\u4f4e\u5f3a\u5ea6");

  const days = Array.from({ length: tripDays }, (_, index) => {
    const day = index + 1;
    const theme = buildDayTheme(day, tripDays, interests, destination);

    return {
      day,
      theme,
      items: buildItems(theme, relaxed),
      pace: relaxed ? "relaxed" : "standard"
    };
  });

  return {
    title: `${destination}${tripDays}\u5929\u65c5\u884c\u8349\u6848`,
    summary: relaxed
      ? "\u5f53\u524d\u8349\u6848\u4ee5\u4f4e\u5f3a\u5ea6\u548c\u53ef\u6267\u884c\u6027\u4f18\u5148\uff0c\u9002\u5408\u5148\u8dd1\u901a\u6574\u4f53\u884c\u7a0b\u6846\u67b6\u3002"
      : "\u5f53\u524d\u8349\u6848\u8986\u76d6\u6838\u5fc3\u8def\u7ebf\uff0c\u53ef\u7ee7\u7eed\u7ec6\u5316\u666f\u70b9\u3001\u9152\u5e97\u548c\u4ea4\u901a\u5b89\u6392\u3002",
    itinerary: {
      destination,
      trip_days: tripDays,
      travel_style: relaxed ? "relaxed" : "standard",
      interests,
      constraints,
      days
    },
    budgetEstimate: {
      total: payload.budget_max ?? null,
      currency: "CNY",
      split: {
        transport: payload.budget_max ? Math.round(payload.budget_max * 0.3) : null,
        hotel: payload.budget_max ? Math.round(payload.budget_max * 0.4) : null,
        food: payload.budget_max ? Math.round(payload.budget_max * 0.2) : null,
        misc: payload.budget_max ? Math.round(payload.budget_max * 0.1) : null
      }
    },
    warnings: [
      "\u5f53\u524d\u4e3a\u6a21\u677f\u8349\u6848\uff0c\u5c1a\u672a\u63a5\u5165\u5b9e\u65f6\u4ea4\u901a\u3001\u5929\u6c14\u548c\u8425\u4e1a\u65f6\u95f4\u6821\u9a8c\u3002",
      "\u5982\u9700\u66f4\u9ad8\u8d28\u91cf\u89c4\u5212\uff0c\u4e0b\u4e00\u9636\u6bb5\u53ef\u63a5\u5165 LLM \u505a\u7ed3\u6784\u5316\u89e3\u6790\u548c\u91cd\u89c4\u5212\u3002"
    ]
  };
}

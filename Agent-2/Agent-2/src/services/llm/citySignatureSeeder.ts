import type {
  CitySignatureSeed,
  Env,
  PlaceCategory,
  StructuredPayload
} from "../../types";
import { OpenAIResponsesClient } from "./openaiResponsesClient";
import {
  buildDynamicRecallCitySignature,
  loadCuratedCityKnowledge,
  mergeSignatureSources
} from "../../data/cityCuratedKnowledge";

function getDestination(requirement: StructuredPayload): string {
  return String(requirement.destination || "").trim();
}

function getInterests(requirement: StructuredPayload): string[] {
  return Array.isArray(requirement.interests)
    ? requirement.interests.map((item) => String(item).trim()).filter(Boolean)
    : [];
}

function heuristicSeed(requirement: StructuredPayload): CitySignatureSeed {
  const destination = getDestination(requirement);
  const interests = getInterests(requirement);
  const make = (
    name: string,
    category: PlaceCategory,
    reason: string,
    confidence = 0.45
  ) => ({ name, category, reason, confidence, source: "heuristic_prior" as const });

  return {
    destination,
    must_visit_attractions: [
      make(`${destination} 地标景点`, "landmark", "默认保留城市代表性景点召回入口"),
      make(`${destination} 历史文化地标`, "museum", "默认保留文化代表性内容"),
      make(`${destination} 经典必打卡`, "landmark", "默认保留经典路线支点")
    ],
    famous_foods: [
      make(`${destination} 本地特色美食`, "food", "默认保留城市特色餐饮"),
      make(`${destination} 老店小吃`, "food", "默认保留本地餐饮代表性内容")
    ],
    food_areas: [
      make(`${destination} 美食街`, "food", "默认保留成熟美食片区"),
      make(`${destination} 商圈美食`, "mall", "支持商场/商圈承接吃+逛")
    ],
    shopping_areas: [
      make(`${destination} 核心商圈`, "mall", "默认保留城市级商圈/娱乐休闲片区"),
      make(`${destination} 购物娱乐街区`, "mall", "支持逛街、商场、综合休闲场景")
    ],
    night_options: [
      make(`${destination} 夜景`, "nightview", "默认保留夜游候选"),
      make(`${destination} 夜市`, "nightview", "默认保留夜市候选")
    ],
    local_experiences: [
      make(`${destination} 老街 citywalk`, "citywalk", "默认保留本地街区体验"),
      make(`${destination} 城市公园`, "park", "默认保留休闲片区")
    ],
    backup_day_trips: interests.some((item) => /自然|郊区|山|湖|nature|scenic/i.test(item))
      ? [make(`${destination} 周边自然景区`, "nature", "用户含自然偏好，保留周边一日游备选", 0.4)]
      : []
  };
}

function buildPrompt(requirement: StructuredPayload): string {
  return JSON.stringify(
    {
      destination: getDestination(requirement),
      interests: getInterests(requirement),
      trip_days: requirement.trip_days ?? null,
      constraints: requirement.constraints ?? [],
      rules: [
        "Return city-level signature seeds before POI validation.",
        "Prefer famous attractions, representative foods, food areas, shopping or entertainment districts, night options, and local experiences.",
        "Use place names or neighborhood names that are likely real travel anchors.",
        "Do not output generic chain stores, parking lots, or transit stations."
      ]
    },
    null,
    2
  );
}

export async function buildCitySignatureSeed(params: {
  env: Env;
  requirement: StructuredPayload;
}): Promise<CitySignatureSeed> {
  const fallback = heuristicSeed(params.requirement);
  const curated = loadCuratedCityKnowledge(fallback.destination);
  const dynamicRecall = buildDynamicRecallCitySignature(fallback.destination);
  const mergedFallback = mergeSignatureSources(fallback.destination, curated, dynamicRecall, fallback);
  const client = new OpenAIResponsesClient(params.env);
  if (!client.isEnabled() || !fallback.destination) {
    return mergedFallback;
  }

  try {
    const seed = await client.createStructuredJson<CitySignatureSeed>({
      system: [
        "You are a city signature travel seed planner.",
        "Your job is to output a city-level signature seed set before map verification.",
        "Do not generate a final itinerary.",
        "Prefer famous landmarks, representative food, real food areas, city-core shopping or entertainment districts, night options, and local experiences.",
        "Avoid chains, parking, ticket offices, and generic businesses."
      ].join("\n"),
      user: buildPrompt(params.requirement),
      schemaName: "city_signature_seed",
      schema: {
        type: "object",
        additionalProperties: false,
        properties: {
          destination: { type: "string" },
          must_visit_attractions: { type: "array", items: { $ref: "#/$defs/item" } },
          famous_foods: { type: "array", items: { $ref: "#/$defs/item" } },
          food_areas: { type: "array", items: { $ref: "#/$defs/item" } },
          shopping_areas: { type: "array", items: { $ref: "#/$defs/item" } },
          night_options: { type: "array", items: { $ref: "#/$defs/item" } },
          local_experiences: { type: "array", items: { $ref: "#/$defs/item" } },
          backup_day_trips: { type: "array", items: { $ref: "#/$defs/item" } }
        },
        required: [
          "destination",
          "must_visit_attractions",
          "famous_foods",
          "food_areas",
          "shopping_areas",
          "night_options",
          "local_experiences",
          "backup_day_trips"
        ],
        $defs: {
          item: {
            type: "object",
            additionalProperties: false,
            properties: {
              name: { type: "string" },
              category: {
                enum: ["landmark", "food", "cafe", "mall", "park", "citywalk", "nightview", "nature", "museum"]
              },
              reason: { type: "string" },
              confidence: { type: "number" },
              source: { enum: ["llm_prior", "heuristic_prior"] }
            },
            required: ["name", "category", "reason", "confidence", "source"]
          }
        }
      }
    });

    return mergeSignatureSources(
      seed.destination || fallback.destination,
      curated,
      dynamicRecall,
      fallback,
      seed
    );
  } catch {
    return mergedFallback;
  }
}

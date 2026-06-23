import type { CitySignatureSeed, CitySignatureSeedItem, PlaceCategory } from "../types";
import curatedKnowledgeJson from "./city_curated_knowledge.json";

const CITY_CURATED_KNOWLEDGE = curatedKnowledgeJson as Record<string, Partial<CitySignatureSeed>>;

function normalizeCity(city: string): string {
  return city.trim().toLowerCase();
}

function makeHeuristicItem(
  name: string,
  category: PlaceCategory,
  reason: string,
  confidence = 0.75
): CitySignatureSeedItem {
  return {
    name,
    category,
    reason,
    confidence,
    source: "heuristic_prior"
  };
}

export function loadCuratedCityKnowledge(city: string): Partial<CitySignatureSeed> | null {
  return CITY_CURATED_KNOWLEDGE[normalizeCity(city)] ?? null;
}

export function buildDynamicRecallCitySignature(city: string): Partial<CitySignatureSeed> {
  return {
    must_visit_attractions: [
      makeHeuristicItem(`${city} 城市地标`, "landmark", "动态召回城市地标"),
      makeHeuristicItem(`${city} 历史文化地标`, "museum", "动态召回文化代表点")
    ],
    famous_foods: [
      makeHeuristicItem(`${city} 本地代表菜`, "food", "动态召回城市代表性餐饮"),
      makeHeuristicItem(`${city} 老店小吃`, "food", "动态召回本地小吃")
    ],
    food_areas: [
      makeHeuristicItem(`${city} 成熟美食片区`, "food", "动态召回美食片区")
    ],
    shopping_areas: [
      makeHeuristicItem(`${city} 核心商圈`, "mall", "动态召回商圈娱乐休闲片区")
    ],
    night_options: [
      makeHeuristicItem(`${city} 夜景片区`, "nightview", "动态召回夜游片区")
    ],
    local_experiences: [
      makeHeuristicItem(`${city} 本地街区`, "citywalk", "动态召回本地街区体验")
    ],
    backup_day_trips: []
  };
}

export function mergeSignatureSources(
  destination: string,
  ...sources: Array<Partial<CitySignatureSeed> | null | undefined>
): CitySignatureSeed {
  const mergeList = (key: keyof CitySignatureSeed) => {
    const list = sources.flatMap((source) => (source?.[key] as CitySignatureSeedItem[] | undefined) ?? []);
    const deduped = new Map<string, CitySignatureSeedItem>();
    for (const item of list) {
      const current = deduped.get(item.name);
      if (!current || current.confidence < item.confidence) deduped.set(item.name, item);
    }
    return Array.from(deduped.values()).slice(0, 8);
  };

  return {
    destination,
    must_visit_attractions: mergeList("must_visit_attractions"),
    famous_foods: mergeList("famous_foods"),
    food_areas: mergeList("food_areas"),
    shopping_areas: mergeList("shopping_areas"),
    night_options: mergeList("night_options"),
    local_experiences: mergeList("local_experiences"),
    backup_day_trips: mergeList("backup_day_trips")
  };
}

"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.isCoreRecommendablePoi = isCoreRecommendablePoi;
exports.buildCitySignaturePool = buildCitySignaturePool;
exports.checkCityCoverage = checkCityCoverage;
const profileResolver_1 = require("./profileResolver");
function normalizeText(value) {
    return value.trim().toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}
function scoreContentMention(candidate, signals = []) {
    const candidateKey = normalizeText(candidate.name);
    let score = 0;
    for (const signal of signals) {
        if (signal.extractedPlaceNames.some((name) => normalizeText(name).includes(candidateKey) || candidateKey.includes(normalizeText(name)))) {
            score += 16;
        }
        if (signal.categoryHints.includes(candidate.category))
            score += 4;
    }
    return Math.min(score, 24);
}
function hasTag(candidate, pattern) {
    return pattern.test(`${candidate.name} ${candidate.description ?? ""} ${candidate.tags.join(" ")}`);
}
function isCoreRecommendablePoi(poi) {
    const text = `${poi.name} ${poi.description ?? ""} ${poi.tags.join(" ")}`;
    if (/(停车场|售票处|游客中心|出入口|地铁站|公交站|交通枢纽|ticket|parking|visitor center|station)/i.test(text)) {
        return { can_be_core: false, reason: "交通/配套设施不应作为核心游玩点", suggested_role: "transport" };
    }
    if (/(麦当劳|肯德基|星巴克|瑞幸|便利店|连锁|chain|hotel)/i.test(text) && poi.category !== "mall") {
        return { can_be_core: false, reason: "普通连锁或生活服务点不适合作为核心推荐", suggested_role: "backup" };
    }
    if (poi.category === "food" && !/(老店|本地|小吃|美食|夜市|餐厅|火锅|特色)/i.test(text)) {
        return { can_be_core: false, reason: "普通餐饮缺少本地代表性", suggested_role: "meal_stop" };
    }
    return { can_be_core: true, reason: "可作为核心候选", suggested_role: "core" };
}
function suggestedRole(candidate) {
    if (candidate.category === "food")
        return "meal_stop";
    if (candidate.category === "mall")
        return "shopping_cluster";
    if (candidate.category === "nightview")
        return "night_cluster";
    if (candidate.category === "citywalk" || candidate.category === "park" || candidate.category === "cafe") {
        return "leisure_cluster";
    }
    return candidate.category === "nature" ? "backup_day_trip" : "anchor";
}
function toSummary(candidate, score, reason) {
    return {
        name: candidate.name,
        type: candidate.category,
        city_signature_score: score,
        suggested_role: suggestedRole(candidate),
        reason,
        candidateId: candidate.id
    };
}
function buildCitySignaturePool(city, candidatePool, requirement) {
    const profile = candidatePool.preferenceProfile ?? (0, profileResolver_1.resolvePreferenceProfile)(requirement);
    const signals = candidatePool.contentSignals ?? [];
    const scored = candidatePool.candidates.map((candidate) => {
        const core = isCoreRecommendablePoi(candidate);
        const contentScore = scoreContentMention(candidate, signals);
        const categoryBase = candidate.category === "landmark" || candidate.category === "museum" ? 60 :
            candidate.category === "food" ? 58 :
                candidate.category === "nightview" ? 50 :
                    candidate.category === "mall" ? 42 :
                        candidate.category === "citywalk" || candidate.category === "park" ? 44 :
                            34;
        const famousBoost = /(著名|地标|必打卡|博物馆|古镇|老街|夜市|商圈|购物中心|mall|广场)/i.test(`${candidate.name} ${candidate.description ?? ""}`) ? 10 : 0;
        const profileBoost = profile.preference_params.food_priority === "high" && candidate.category === "food" ? 8 :
            profile.preference_params.hidden_gem_priority === "high" && (candidate.category === "citywalk" || candidate.category === "park" || candidate.category === "cafe") ? 6 :
                profile.preference_params.famous_spot_priority === "high" && (candidate.category === "landmark" || candidate.category === "museum" || candidate.category === "nightview") ? 8 :
                    0;
        const score = Math.round(categoryBase + contentScore + famousBoost + profileBoost + candidate.confidence * 18 + (core.can_be_core ? 0 : -24));
        return { candidate, score, core };
    }).sort((a, b) => b.score - a.score);
    const mustVisit = scored
        .filter((item) => item.core.can_be_core && ["landmark", "museum", "nature", "park"].includes(item.candidate.category))
        .slice(0, 8)
        .map((item) => toSummary(item.candidate, item.score, `${city}代表性景点候选`));
    const famousFoods = scored
        .filter((item) => item.candidate.category === "food")
        .slice(0, 8)
        .map((item) => toSummary(item.candidate, item.score, "优先保留本地餐饮代表项"));
    const foodAreas = scored
        .filter((item) => item.candidate.category === "mall" || hasTag(item.candidate, /(夜市|美食街|商圈|购物中心|步行街)/i))
        .slice(0, 6)
        .map((item) => ({
        ...toSummary(item.candidate, item.score, "可承担成熟美食片区/商圈角色"),
        suggested_role: "food_cluster"
    }));
    const shoppingAreas = scored
        .filter((item) => item.candidate.category === "mall" ||
        hasTag(item.candidate, /(商圈|购物中心|太古里|步行街|商业街|广场|娱乐|综合体)/i))
        .slice(0, 8)
        .map((item) => ({
        ...toSummary(item.candidate, item.score, "城市级商圈/娱乐休闲片区候选"),
        suggested_role: "shopping_cluster"
    }));
    const nightOptions = scored
        .filter((item) => item.candidate.category === "nightview" || hasTag(item.candidate, /(夜景|夜游|夜市|灯光)/i))
        .slice(0, 6)
        .map((item) => toSummary(item.candidate, item.score, "夜间活动候选"));
    const localExperiences = scored
        .filter((item) => ["citywalk", "park", "cafe", "mall", "museum"].includes(item.candidate.category))
        .slice(0, 8)
        .map((item) => toSummary(item.candidate, item.score, "本地体验/休闲片区候选"));
    const backupTrips = scored
        .filter((item) => item.candidate.category === "nature")
        .slice(0, 4)
        .map((item) => ({
        ...toSummary(item.candidate, item.score, "代表性较强但更适合单独安排"),
        suggested_role: "backup_day_trip"
    }));
    const avoidAsCore = scored
        .filter((item) => !item.core.can_be_core)
        .slice(0, 12)
        .map((item) => ({
        ...toSummary(item.candidate, item.score, item.core.reason),
        suggested_role: item.core.suggested_role === "transport" ? "backup" : "backup"
    }));
    return {
        must_visit_attractions: mustVisit,
        famous_foods: famousFoods,
        food_signatures: famousFoods,
        food_areas: foodAreas,
        shopping_areas: shoppingAreas,
        night_options: nightOptions,
        local_experiences: localExperiences,
        backup_day_trips: backupTrips,
        avoid_as_core: avoidAsCore
    };
}
function checkCityCoverage(candidatePool) {
    const pool = candidatePool.citySignaturePool;
    if (!pool) {
        return {
            ok: false,
            has_enough_must_visit: false,
            has_famous_food_or_food_area: false,
            has_night_option: false,
            has_local_experience: false,
            missing_items: ["city_signature_pool"],
            coverage_summary: {
                must_visit_count: 0,
                food_signature_count: 0,
                food_area_count: 0,
                night_option_count: 0,
                local_experience_count: 0
            },
            repair_actions: ["build_or_recall_city_signature_pool"]
        };
    }
    const missing_items = [];
    const hasEnoughMustVisit = pool.must_visit_attractions.length >= 3;
    const hasFood = pool.famous_foods.length >= 2 || pool.food_areas.length >= 1;
    const hasNight = pool.night_options.length >= 1;
    const hasLocal = pool.local_experiences.length >= 1;
    if (!hasEnoughMustVisit)
        missing_items.push("must_visit_attractions");
    if (!hasFood)
        missing_items.push("famous_foods_or_food_areas");
    if (!hasNight)
        missing_items.push("night_options");
    if (!hasLocal)
        missing_items.push("local_experiences");
    const repair_actions = missing_items.map((item) => item === "must_visit_attractions"
        ? "recall_more_must_visit_attractions"
        : item === "famous_foods_or_food_areas"
            ? "recall_food_signatures_or_food_areas"
            : item === "night_options"
                ? "recall_night_options"
                : "recall_local_experiences");
    return {
        ok: missing_items.length === 0,
        has_enough_must_visit: hasEnoughMustVisit,
        has_famous_food_or_food_area: hasFood,
        has_night_option: hasNight,
        has_local_experience: hasLocal,
        missing_items,
        coverage_summary: {
            must_visit_count: pool.must_visit_attractions.length,
            food_signature_count: pool.food_signatures.length,
            food_area_count: pool.food_areas.length,
            shopping_area_count: pool.shopping_areas.length,
            night_option_count: pool.night_options.length,
            local_experience_count: pool.local_experiences.length
        },
        repair_actions
    };
}

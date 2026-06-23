const CATEGORY_PATTERNS = [
    { category: "food", patterns: [/美食|餐饮|小吃|火锅|吃饭|food|restaurant/i] },
    { category: "cafe", patterns: [/咖啡|下午茶|coffee|cafe/i] },
    { category: "mall", patterns: [/商场|购物|逛街|mall|shopping/i] },
    { category: "park", patterns: [/公园|绿地|park/i] },
    { category: "citywalk", patterns: [/citywalk|漫步|老街|街区|散步/i] },
    { category: "nightview", patterns: [/夜景|夜游|夜市|观景|night/i] },
    { category: "nature", patterns: [/自然|风景|山|湖|景区|nature|scenic/i] },
    { category: "museum", patterns: [/博物馆|展览|历史|文化|museum/i] },
    { category: "landmark", patterns: [/景点|地标|打卡| landmark/i] }
];
const SLOT_PATTERNS = [
    { slot: "morning", patterns: [/上午|早上|早晨/] },
    { slot: "lunch", patterns: [/中午|午饭|午餐/] },
    { slot: "afternoon", patterns: [/下午|午后/] },
    { slot: "evening", patterns: [/晚上|夜里|傍晚/] }
];
function uniqueCategories(values) {
    if (!values?.length)
        return undefined;
    return Array.from(new Set(values));
}
function detectCategories(text) {
    const result = [];
    for (const item of CATEGORY_PATTERNS) {
        if (item.patterns.some((pattern) => pattern.test(text))) {
            result.push(item.category);
        }
    }
    return Array.from(new Set(result));
}
function detectSlot(text) {
    return SLOT_PATTERNS.find((item) => item.patterns.some((pattern) => pattern.test(text)))?.slot;
}
function detectDay(text) {
    const digit = text.match(/第?\s*(\d+)\s*天/u);
    if (digit)
        return Number(digit[1]);
    const map = {
        一: 1,
        二: 2,
        两: 2,
        三: 3,
        四: 4,
        五: 5,
        六: 6,
        七: 7
    };
    const chinese = text.match(/第?\s*([一二两三四五六七])\s*天/u);
    return chinese ? map[chinese[1]] : undefined;
}
function detectPreferredPace(text) {
    if (/轻松|不累|慢一点|休闲|宽松/u.test(text))
        return "relaxed";
    if (/紧凑|多安排|高效|赶一点/u.test(text))
        return "compact";
    if (/适中|正常节奏/u.test(text))
        return "moderate";
    return undefined;
}
function detectDistanceTolerance(text) {
    if (/只在市区|仅市区|别太远|不要跑太远|少走路/u.test(text))
        return "urban_only";
    if (/近郊|周边|附近/u.test(text))
        return "nearby_ok";
    if (/远一点也行|距离灵活/u.test(text))
        return "flexible";
    return undefined;
}
function mergeDayOverrides(existing = [], incoming = []) {
    const merged = [...existing];
    for (const item of incoming) {
        const index = merged.findIndex((entry) => entry.day === item.day && entry.slot === item.slot);
        if (index >= 0) {
            merged[index] = {
                ...merged[index],
                ...item,
                preferred_categories: uniqueCategories([
                    ...(merged[index].preferred_categories ?? []),
                    ...(item.preferred_categories ?? [])
                ]),
                avoid_categories: uniqueCategories([
                    ...(merged[index].avoid_categories ?? []),
                    ...(item.avoid_categories ?? [])
                ])
            };
            continue;
        }
        merged.push({
            ...item,
            preferred_categories: uniqueCategories(item.preferred_categories),
            avoid_categories: uniqueCategories(item.avoid_categories)
        });
    }
    return merged;
}
function mergeReplaceTargets(existing = [], incoming = []) {
    return [...existing, ...incoming].slice(-8);
}
export function extractReplanDirectives(text) {
    const normalized = String(text ?? "").trim();
    if (!normalized)
        return undefined;
    const preferredCategories = detectCategories(normalized.match(/(?:多一点|更偏|优先|想要|改成)([^，。！？]+)/u)?.[1] ?? normalized);
    const avoidCategories = detectCategories(normalized.match(/(?:不要|别|少一点|减少|换掉)([^，。！？]+)/u)?.[1] ?? "");
    const day = detectDay(normalized);
    const slot = detectSlot(normalized);
    const preferredPace = detectPreferredPace(normalized);
    const distanceTolerance = detectDistanceTolerance(normalized);
    const replaceTargets = [];
    const dayOverrides = [];
    if (/换成|改成/u.test(normalized) && (preferredCategories.length || avoidCategories.length)) {
        replaceTargets.push({
            day,
            slot,
            from_categories: avoidCategories.length ? avoidCategories : undefined,
            to_categories: preferredCategories.length ? preferredCategories : undefined,
            note: normalized
        });
    }
    if (day || slot) {
        dayOverrides.push({
            day: day ?? 1,
            slot,
            preferred_categories: preferredCategories.length ? preferredCategories : undefined,
            avoid_categories: avoidCategories.length ? avoidCategories : undefined,
            preferred_pace: preferredPace,
            note: normalized
        });
    }
    const global = preferredPace ||
        distanceTolerance ||
        preferredCategories.length ||
        avoidCategories.length ||
        /少走路|减少转场|别太折腾/u.test(normalized)
        ? {
            preferred_pace: preferredPace,
            distance_tolerance: distanceTolerance,
            preferred_categories: preferredCategories.length ? preferredCategories : undefined,
            avoid_categories: avoidCategories.length ? avoidCategories : undefined,
            reduce_transfers: /少走路|减少转场|别太折腾/u.test(normalized) || undefined,
            prefer_nearby: /少走路|别太远|附近|就近/u.test(normalized) || undefined,
            note: normalized
        }
        : undefined;
    if (!global && !dayOverrides.length && !replaceTargets.length) {
        return undefined;
    }
    return {
        global,
        day_overrides: dayOverrides.length ? dayOverrides : undefined,
        replace_targets: replaceTargets.length ? replaceTargets : undefined,
        source_message: normalized
    };
}
export function mergeReplanDirectives(existing, incoming) {
    if (!existing && !incoming)
        return undefined;
    if (!existing)
        return incoming;
    if (!incoming)
        return existing;
    return {
        global: {
            ...existing.global,
            ...incoming.global,
            preferred_categories: uniqueCategories([
                ...(existing.global?.preferred_categories ?? []),
                ...(incoming.global?.preferred_categories ?? [])
            ]),
            avoid_categories: uniqueCategories([
                ...(existing.global?.avoid_categories ?? []),
                ...(incoming.global?.avoid_categories ?? [])
            ])
        },
        day_overrides: mergeDayOverrides(existing.day_overrides, incoming.day_overrides),
        replace_targets: mergeReplaceTargets(existing.replace_targets, incoming.replace_targets),
        source_message: incoming.source_message ?? existing.source_message
    };
}
function mergeInterestCategories(payload, categories) {
    if (!categories?.length)
        return payload.interests;
    return Array.from(new Set([...(payload.interests ?? []), ...categories]));
}
export function applyReplanDirectivesToPayload(payload) {
    const directives = payload.replan_directives;
    if (!directives)
        return payload;
    const next = { ...payload };
    const global = directives.global;
    if (global?.preferred_pace)
        next.preferredPace = global.preferred_pace;
    if (global?.distance_tolerance)
        next.distanceTolerance = global.distance_tolerance;
    if (global?.preferred_categories?.length) {
        next.interests = mergeInterestCategories(next, global.preferred_categories);
    }
    if (global?.avoid_categories?.length) {
        const labels = global.avoid_categories.map((item) => `avoid:${item}`);
        next.constraints = Array.from(new Set([...(next.constraints ?? []), ...labels]));
    }
    return next;
}
export function hasReplanDirectiveSignal(payload) {
    const directives = payload?.replan_directives;
    return Boolean(directives?.global ||
        directives?.day_overrides?.length ||
        directives?.replace_targets?.length);
}
export function summarizeAppliedDirectiveChanges(payload) {
    const directives = payload?.replan_directives;
    if (!directives)
        return [];
    const parts = [];
    if (directives.global?.preferred_pace === "relaxed")
        parts.push("整体节奏更轻松");
    if (directives.global?.distance_tolerance === "urban_only")
        parts.push("优先市区内与近距离转场");
    if (directives.global?.preferred_categories?.length) {
        parts.push(`整体更偏向 ${directives.global.preferred_categories.join("+")}`);
    }
    if (directives.global?.avoid_categories?.length) {
        parts.push(`整体避开 ${directives.global.avoid_categories.join("+")}`);
    }
    for (const item of directives.day_overrides ?? []) {
        const scope = item.slot ? `第${item.day}天${item.slot}` : `第${item.day}天`;
        const changes = [
            item.preferred_categories?.length ? `偏向 ${item.preferred_categories.join("+")}` : "",
            item.avoid_categories?.length ? `避开 ${item.avoid_categories.join("+")}` : "",
            item.preferred_pace === "relaxed" ? "更轻松" : ""
        ].filter(Boolean);
        if (changes.length)
            parts.push(`${scope} ${changes.join("，")}`);
    }
    return parts;
}
export function getDayOverrideForSlot(directives, day, slot) {
    return directives?.day_overrides?.find((item) => item.day === day && item.slot === slot) ??
        directives?.day_overrides?.find((item) => item.day === day && !item.slot);
}

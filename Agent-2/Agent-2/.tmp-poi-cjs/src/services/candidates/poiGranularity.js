"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.inferPlanningMode = inferPlanningMode;
exports.normalizePoiGranularity = normalizePoiGranularity;
exports.applyPoiGovernance = applyPoiGovernance;
function normalizeText(value) {
    return value.trim().toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}
function uniqueStrings(values) {
    return Array.from(new Set(values.map((value) => String(value ?? "").trim()).filter(Boolean)));
}
function includesAny(text, patterns) {
    return patterns.some((pattern) => pattern.test(text));
}
const SERVICE_PATTERNS = [
    /酒店|宾馆|民宿|hospital|school|government|company|office|residential|parking|gas|hotel|inn/i,
    /医院|学校|政府|公司|写字楼|住宅|小区|加油站|汽车服务|便利店|生活服务|营业厅|银行|apartment|community/i
];
const SERVICE_MERCHANT_PATTERNS = [
    /店|餐厅|饭店|火锅|茶府|酒店|宾馆|便利店|商店|商铺|超市|广场店|停车场/i,
    /restaurant|hotel|inn|store|shop|parking|mart|mall|cafe|tea house/i
];
const INTERNAL_FACILITY_PATTERNS = [
    /游客中心|售票处|检票口|入口|出口|停车场|服务中心|卫生间|码头|站点|观景台|游客服务|visitor center|ticket office|entrance|exit/i,
    /亭|碑|桥|塔|阁|墓|鼎|雕塑|小岛|园|殿|门|馆内|遗址点|驿站|gate|bridge|pavilion|tower|dock|viewpoint/i
];
const INTERNAL_CONTEXT_PATTERNS = [
    /景区|公园|博物馆|古镇|老街|步行街|商圈|街区|广场|湖|山|寺|楼|湿地|园区|滨江|河岸|scenic area|park|museum|old street|walking street|district|square|lake|mountain|temple|waterfront/i
];
const ATTRACTION_PATTERNS = [
    /景区|景点|公园|博物馆|纪念馆|寺|庙|古镇|古城|地标|山|湖|楼|塔|广场|湿地|遗址|scenic area|attraction|park|museum|temple|ancient town|landmark|mountain|lake|square/i
];
const DISTRICT_PATTERNS = [
    /街区|商圈|老街|夜市|滨江路|步行街|城市漫游|citywalk|city walk|漫步|古城片区|district|old street|night market|waterfront road|walking street/i
];
const FOOD_AREA_PATTERNS = [
    /美食街|小吃街|夜市|美食城|餐饮街|老字号|食街|food street|snack street|food market/i
];
const WALK_AREA_PATTERNS = [
    /老街|步行街|街区|滨江路|夜市|巷子|河岸|江边|湖畔|citywalk|漫步|街市|old street|walking street|district|waterfront|harbor|riverfront/i
];
const SHOPPING_PATTERNS = [/购物|商场|商圈|mall|shopping/i];
const INTERNAL_ROUTE_PATTERNS = [
    /景区内部|公园内|园区内|内部怎么逛|内部路线|景区内路线|园区内怎么走|inside .*?(scenic area|park|museum)|how to tour inside|internal route|inside route/i
];
const CITY_TRIP_PATTERNS = [
    /玩几天|几日游|两日游|三日游|旅游|行程|city trip|trip plan|攻略/i
];
const SCENIC_QUERY_CATEGORIES = new Set([
    "landmark",
    "park",
    "museum",
    "nature",
    "nightview",
    "citywalk"
]);
const MAIN_ITINERARY_GRANULARITIES = new Set([
    "attraction_level",
    "district_level",
    "food_level"
]);
function getRequirementText(requirement) {
    return String(requirement["raw_input"] ??
        requirement["user_input"] ??
        requirement["query"] ??
        requirement["instruction"] ??
        "").trim();
}
function inferPlanningMode(requirement) {
    const text = getRequirementText(requirement);
    if (includesAny(text, INTERNAL_ROUTE_PATTERNS))
        return "attraction_internal_route";
    if (includesAny(text, CITY_TRIP_PATTERNS))
        return "city_trip";
    return "city_trip";
}
function wantsShopping(requirement) {
    const text = `${getRequirementText(requirement)} ${(requirement.interests ?? []).join(" ")}`;
    return includesAny(text, SHOPPING_PATTERNS);
}
function buildCandidateText(candidate) {
    return [
        candidate.name,
        candidate.address,
        candidate.description,
        candidate.tags.join(" "),
        candidate.city
    ].filter(Boolean).join(" ");
}
function hasParentStructure(candidate) {
    const text = buildCandidateText(candidate);
    return /[-·•()（）]/.test(candidate.name) || includesAny(text, INTERNAL_CONTEXT_PATTERNS);
}
function inferGranularity(candidate, planningMode) {
    const text = buildCandidateText(candidate);
    const normalizedName = normalizeText(candidate.name);
    const normalizedCity = normalizeText(candidate.city);
    if (normalizedName && normalizedCity && normalizedName === normalizedCity) {
        return "city_level";
    }
    if (includesAny(text, SERVICE_PATTERNS)) {
        return "service_level";
    }
    if (includesAny(text, INTERNAL_FACILITY_PATTERNS) &&
        (planningMode === "attraction_internal_route" || hasParentStructure(candidate))) {
        return "internal_poi_level";
    }
    if (candidate.category === "food" || candidate.category === "cafe") {
        return "food_level";
    }
    if (candidate.category === "citywalk" || includesAny(text, DISTRICT_PATTERNS)) {
        return "district_level";
    }
    if (candidate.category === "mall" && !includesAny(text, DISTRICT_PATTERNS)) {
        return "service_level";
    }
    if (candidate.category === "landmark" ||
        candidate.category === "park" ||
        candidate.category === "museum" ||
        candidate.category === "nature" ||
        candidate.category === "nightview" ||
        includesAny(text, ATTRACTION_PATTERNS)) {
        return "attraction_level";
    }
    return "service_level";
}
function inferPlannerCategoryFromGranularity(granularity, candidate) {
    if ((candidate.roles ?? []).includes("food") && (candidate.roles ?? []).includes("walk"))
        return "food_walk";
    if (granularity === "food_level")
        return "food";
    if (granularity === "district_level")
        return "walk";
    if (granularity === "attraction_level")
        return "scenic";
    if (candidate.category === "nightview")
        return "scenic";
    return "supplemental";
}
function extractParentName(candidate, knownParents) {
    const text = buildCandidateText(candidate);
    const matchedParent = knownParents
        .filter((item) => item.id !== candidate.id)
        .find((item) => {
        const key = normalizeText(item.name);
        return key && normalizeText(text).includes(key);
    });
    if (matchedParent)
        return matchedParent.name;
    const direct = candidate.name.match(/(.+?(?:景区|公园|博物馆|纪念馆|古镇|老街|步行街|商圈|街区|广场|湖|山|寺|楼|湿地|园区|Scenic Area|Park|Museum|Old Street|Walking Street|District|Square|Lake|Mountain|Temple))(?:内)?[-·•\s()（）].+/i);
    if (direct?.[1])
        return direct[1].trim();
    const context = text.match(/(.+?(?:景区|公园|博物馆|纪念馆|古镇|老街|步行街|商圈|街区|广场|湖|山|寺|楼|湿地|园区|Scenic Area|Park|Museum|Old Street|Walking Street|District|Square|Lake|Mountain|Temple))(?:内|里面| inside)/i);
    return context?.[1]?.trim();
}
function semanticAreaKey(name) {
    return normalizeText(name.replace(/美食街|小吃街|老街|步行街|夜市|商圈|街区|滨江路|古城|食街|美食城|food street|food market|old street|walking street|district|night market|waterfront/gi, ""));
}
function semanticNightKey(name) {
    return normalizeText(name.replace(/夜景|夜游|观景|night view|night|view|walk|stroll|citywalk/gi, ""));
}
function mergeCandidate(base, incoming) {
    return {
        ...base,
        location: base.location ?? incoming.location,
        address: base.address ?? incoming.address,
        confidence: Math.max(base.confidence, incoming.confidence),
        tags: uniqueStrings([...base.tags, ...incoming.tags]),
        queryCategories: Array.from(new Set([...(base.queryCategories ?? []), ...(incoming.queryCategories ?? [])])),
        roles: uniqueStrings([...(base.roles ?? []), ...(incoming.roles ?? [])]),
        subStops: uniqueStrings([...(base.subStops ?? []), ...(incoming.subStops ?? [])]),
        mergedAliases: uniqueStrings([...(base.mergedAliases ?? []), incoming.name, ...(incoming.mergedAliases ?? [])])
    };
}
function normalizeCandidate(candidate, planningMode, requirement) {
    const granularity = inferGranularity(candidate, planningMode);
    const text = buildCandidateText(candidate);
    const representativeWalk = granularity === "district_level" && includesAny(text, WALK_AREA_PATTERNS);
    const localFood = granularity === "food_level" &&
        (includesAny(text, FOOD_AREA_PATTERNS) || candidate.category === "food" || candidate.category === "cafe");
    const qualityFlags = {
        ...(candidate.qualityFlags ?? candidate.quality_flags ?? {}),
        representative_walk: representativeWalk,
        local_food: localFood
    };
    let eligible = Boolean(candidate.location);
    if (!MAIN_ITINERARY_GRANULARITIES.has(granularity))
        eligible = false;
    if (granularity === "district_level" && !representativeWalk)
        eligible = false;
    if (granularity === "food_level" && !(localFood || candidate.source === "llm_curator"))
        eligible = false;
    if (candidate.category === "mall" && !wantsShopping(requirement))
        eligible = false;
    if (planningMode === "city_trip" && granularity === "internal_poi_level")
        eligible = false;
    if (granularity === "service_level" || granularity === "city_level")
        eligible = false;
    return {
        ...candidate,
        granularity,
        planningMode,
        plannerCategory: inferPlannerCategoryFromGranularity(granularity, candidate),
        eligibleForMainItinerary: eligible,
        eligible_for_main_itinerary: eligible,
        qualityFlags,
        quality_flags: qualityFlags,
        roles: uniqueStrings([
            ...(candidate.roles ?? []),
            granularity === "district_level" ? "walk" : "",
            granularity === "food_level" ? "food" : "",
            candidate.category === "nightview" ? "evening" : ""
        ]),
        role: candidate.category === "nightview" ? "evening" : candidate.role
    };
}
function rejectMerchantAlias(candidate, allCandidates, planningMode) {
    if (planningMode !== "city_trip")
        return candidate;
    const text = buildCandidateText(candidate);
    const queryCategories = candidate.queryCategories ?? [];
    const scenicOnlyTask = queryCategories.length > 0 &&
        queryCategories.every((category) => SCENIC_QUERY_CATEGORIES.has(category)) &&
        !queryCategories.some((category) => category === "food" || category === "cafe");
    const scenicParent = allCandidates.find((item) => {
        if (item.id === candidate.id)
            return false;
        if (!item.location || !candidate.location)
            return false;
        const itemGranularity = item.granularity;
        if (itemGranularity !== "attraction_level" && itemGranularity !== "district_level")
            return false;
        const key = normalizeText(item.name);
        return key && normalizeText(candidate.name).includes(key);
    });
    const shouldReject = scenicOnlyTask &&
        (candidate.granularity === "food_level" || candidate.granularity === "service_level") &&
        includesAny(text, SERVICE_MERCHANT_PATTERNS) &&
        Boolean(scenicParent);
    if (!shouldReject)
        return candidate;
    return {
        ...candidate,
        eligibleForMainItinerary: false,
        eligible_for_main_itinerary: false,
        plannerCategory: "supplemental",
        warning: "merchant_alias_rejected",
        parentName: scenicParent?.name,
        roles: uniqueStrings([...(candidate.roles ?? []), "nearby_tip"])
    };
}
function mergeInternalPois(candidates, planningMode) {
    if (planningMode === "attraction_internal_route") {
        return { candidates, parentInferredByTask: new Map() };
    }
    const mainCandidates = candidates.filter((candidate) => candidate.granularity === "attraction_level" || candidate.granularity === "district_level");
    const merged = new Map();
    const parentInferredByTask = new Map();
    for (const candidate of candidates) {
        if (candidate.granularity !== "internal_poi_level") {
            merged.set(candidate.id, candidate);
            continue;
        }
        const parentName = extractParentName(candidate, mainCandidates);
        if (!parentName) {
            merged.set(candidate.id, {
                ...candidate,
                eligibleForMainItinerary: false,
                eligible_for_main_itinerary: false,
                plannerCategory: "supplemental"
            });
            continue;
        }
        const existingParent = Array.from(merged.values()).find((item) => normalizeText(item.name) === normalizeText(parentName)) ??
            mainCandidates.find((item) => normalizeText(item.name) === normalizeText(parentName));
        const queryKey = (candidate.tags.find((tag) => tag.startsWith("origin_query:")) ?? "").replace("origin_query:", "");
        if (queryKey) {
            const previous = parentInferredByTask.get(queryKey) ?? [];
            parentInferredByTask.set(queryKey, uniqueStrings([...previous, parentName]));
        }
        if (existingParent) {
            merged.set(existingParent.id, {
                ...existingParent,
                sourceOrigin: existingParent.sourceOrigin ?? "amap_inferred_parent",
                warning: existingParent.warning ?? "parent_inferred_from_internal_pois",
                subStops: uniqueStrings([...(existingParent.subStops ?? []), candidate.name]),
                mergedAliases: uniqueStrings([...(existingParent.mergedAliases ?? []), candidate.name])
            });
            continue;
        }
        const parentGranularity = includesAny(parentName, DISTRICT_PATTERNS)
            ? "district_level"
            : "attraction_level";
        const parentCandidate = {
            ...candidate,
            id: `${candidate.id}_parent`,
            name: parentName,
            granularity: parentGranularity,
            plannerCategory: parentGranularity === "district_level" ? "walk" : "scenic",
            eligibleForMainItinerary: true,
            eligible_for_main_itinerary: true,
            sourceOrigin: "amap_inferred_parent",
            warning: "parent_inferred_from_internal_pois",
            parentName,
            subStops: [candidate.name],
            mergedAliases: [candidate.name],
            roles: uniqueStrings([...(candidate.roles ?? []), parentGranularity === "district_level" ? "walk" : "scenic"])
        };
        merged.set(parentCandidate.id, parentCandidate);
    }
    return {
        candidates: Array.from(merged.values()),
        parentInferredByTask
    };
}
function mergeFoodWalkAreas(candidates) {
    const result = [];
    const usedIds = new Set();
    for (const candidate of candidates) {
        if (usedIds.has(candidate.id))
            continue;
        if (candidate.granularity !== "district_level" && candidate.granularity !== "food_level") {
            result.push(candidate);
            continue;
        }
        const areaKey = semanticAreaKey(candidate.name);
        const peer = candidates.find((item) => {
            if (item.id === candidate.id || usedIds.has(item.id))
                return false;
            if (item.granularity !== "district_level" && item.granularity !== "food_level")
                return false;
            const peerKey = semanticAreaKey(item.name);
            return areaKey && peerKey && (areaKey === peerKey || areaKey.includes(peerKey) || peerKey.includes(areaKey));
        });
        if (!peer) {
            result.push(candidate);
            continue;
        }
        usedIds.add(peer.id);
        usedIds.add(candidate.id);
        result.push({
            ...mergeCandidate(candidate, peer),
            granularity: "district_level",
            plannerCategory: "food_walk",
            roles: uniqueStrings([...(candidate.roles ?? []), ...(peer.roles ?? []), "walk", "food"]),
            qualityFlags: {
                ...(candidate.qualityFlags ?? candidate.quality_flags ?? {}),
                ...(peer.qualityFlags ?? peer.quality_flags ?? {}),
                representative_walk: true,
                local_food: true
            },
            quality_flags: {
                ...(candidate.qualityFlags ?? candidate.quality_flags ?? {}),
                ...(peer.qualityFlags ?? peer.quality_flags ?? {}),
                representative_walk: true,
                local_food: true
            },
            sourceOrigin: candidate.sourceOrigin ?? peer.sourceOrigin ?? "merged_food_walk",
            mergedAliases: uniqueStrings([candidate.name, peer.name, ...(candidate.mergedAliases ?? []), ...(peer.mergedAliases ?? [])]),
            role: candidate.role ?? peer.role
        });
    }
    return result;
}
function linkNightViewCandidates(candidates, queryPlan) {
    const linkedByTask = new Map();
    let linkedNightView = false;
    const enriched = [...candidates];
    const existingNight = candidates.some((candidate) => candidate.category === "nightview" && Boolean(candidate.location));
    for (const candidate of candidates) {
        if (candidate.category !== "nightview" || candidate.location)
            continue;
        const target = candidates.find((item) => {
            if (!item.location || item.id === candidate.id)
                return false;
            if (item.granularity !== "attraction_level" && item.granularity !== "district_level")
                return false;
            const itemKey = normalizeText(item.name);
            const candidateKey = normalizeText(candidate.name);
            const itemSemantic = semanticNightKey(item.name);
            const candidateSemantic = semanticNightKey(candidate.name);
            return Boolean((itemKey && candidateKey && (candidateKey.includes(itemKey) || itemKey.includes(candidateKey))) ||
                (itemSemantic && candidateSemantic && (candidateSemantic.includes(itemSemantic) || itemSemantic.includes(candidateSemantic))));
        });
        if (!target)
            continue;
        linkedNightView = true;
        const queryKey = (candidate.tags.find((tag) => tag.startsWith("origin_query:")) ?? "").replace("origin_query:", "");
        if (queryKey)
            linkedByTask.set(queryKey, target.name);
        enriched.push({
            ...candidate,
            id: `${candidate.id}_linked_night`,
            plannerCategory: "scenic",
            granularity: target.granularity,
            linkedPoiId: target.id,
            nightView: true,
            location: target.location,
            address: target.address,
            name: candidate.name,
            roles: uniqueStrings([...(target.roles ?? []), "evening"]),
            role: "evening",
            eligibleForMainItinerary: true,
            eligible_for_main_itinerary: true
        });
    }
    if (!existingNight && queryPlan) {
        const nightTasks = queryPlan.categories.filter((item) => item.category === "nightview");
        for (const task of nightTasks) {
            const target = candidates.find((candidate) => candidate.location &&
                (candidate.granularity === "attraction_level" || candidate.granularity === "district_level") &&
                task.keywords.some((keyword) => {
                    const taskKey = normalizeText(keyword);
                    const candidateKey = normalizeText(candidate.name);
                    const taskSemantic = semanticNightKey(keyword);
                    const candidateSemantic = semanticNightKey(candidate.name);
                    return Boolean((taskKey && candidateKey && (taskKey.includes(candidateKey) || candidateKey.includes(taskKey))) ||
                        (taskSemantic && candidateSemantic && (taskSemantic.includes(candidateSemantic) || candidateSemantic.includes(taskSemantic))));
                }));
            if (!target)
                continue;
            linkedNightView = true;
            linkedByTask.set(`queryplan:${task.keywords[0] ?? "nightview"}`, target.name);
            enriched.push({
                ...target,
                id: `${target.id}_night_link`,
                category: "nightview",
                linkedPoiId: target.id,
                nightView: true,
                roles: uniqueStrings([...(target.roles ?? []), "evening"]),
                role: "evening",
                eligibleForMainItinerary: true,
                eligible_for_main_itinerary: true
            });
            break;
        }
    }
    return { candidates: enriched, linkedByTask, linkedNightView };
}
function buildGroundingDiagnostics(params) {
    return params.queryTasks.map((task) => {
        const taskKey = `poi_search_${normalizeText(task.city)}_${normalizeText(task.keyword)}_${normalizeText(task.category ?? "")}`;
        const related = params.candidates.filter((candidate) => candidate.tags.includes(`origin_query:${taskKey}`));
        return {
            taskName: `${task.tool}:${task.keyword}`,
            primarySelected: uniqueStrings(related
                .filter((candidate) => Boolean(candidate.eligible_for_main_itinerary))
                .slice(0, 3)
                .map((candidate) => candidate.name)),
            parentInferred: params.parentInferredByTask.get(taskKey) ?? [],
            internalSubStopsCount: related.reduce((sum, candidate) => sum + (candidate.subStops?.length ?? 0), 0),
            merchantAliasRejectedCount: related.filter((candidate) => candidate.warning === "merchant_alias_rejected").length,
            keptAsMainCount: related.filter((candidate) => Boolean(candidate.eligible_for_main_itinerary)).length,
            linkedNightViewTarget: params.linkedByTask.get(taskKey),
            mergedAliases: uniqueStrings(related.flatMap((candidate) => candidate.mergedAliases ?? []).slice(0, 8))
        };
    });
}
function normalizePoiGranularity(candidate, requirement) {
    return normalizeCandidate(candidate, inferPlanningMode(requirement), requirement);
}
function applyPoiGovernance(params) {
    const planningMode = inferPlanningMode(params.requirement);
    const normalized = params.candidates.map((candidate) => normalizeCandidate(candidate, planningMode, params.requirement));
    const merchantFiltered = normalized.map((candidate) => rejectMerchantAlias(candidate, normalized, planningMode));
    const mergedInternal = mergeInternalPois(merchantFiltered, planningMode);
    const mergedAreas = mergeFoodWalkAreas(mergedInternal.candidates);
    const linkedNightView = linkNightViewCandidates(mergedAreas, params.queryPlan);
    const groundingDiagnostics = buildGroundingDiagnostics({
        candidates: linkedNightView.candidates,
        queryTasks: params.queryTasks,
        parentInferredByTask: mergedInternal.parentInferredByTask,
        linkedByTask: linkedNightView.linkedByTask
    });
    const warnings = Array.from(new Set([
        ...(params.warnings ?? []),
        planningMode === "city_trip" ? "city_trip_mode_active" : "attraction_internal_route_mode_active",
        linkedNightView.linkedNightView ? "night_view_linked_to_existing_candidate" : "",
        mergedAreas.some((candidate) => (candidate.roles ?? []).includes("walk") && (candidate.roles ?? []).includes("food"))
            ? "food_walk_candidate_merged"
            : ""
    ].filter(Boolean)));
    const governanceSummary = {
        planningMode,
        subStopsCount: linkedNightView.candidates.reduce((sum, candidate) => sum + (candidate.subStops?.length ?? 0), 0),
        hasLinkedNightView: linkedNightView.linkedNightView,
        hasFoodWalkMerge: linkedNightView.candidates.some((candidate) => (candidate.roles ?? []).includes("walk") && (candidate.roles ?? []).includes("food"))
    };
    return {
        candidates: linkedNightView.candidates,
        warnings,
        planningMode,
        groundingDiagnostics,
        governanceSummary
    };
}

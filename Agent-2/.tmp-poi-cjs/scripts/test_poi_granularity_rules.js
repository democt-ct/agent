"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const poiGranularity_1 = require("../src/services/candidates/poiGranularity");
const dynamicItineraryPlanner_1 = require("../src/services/planning/dynamicItineraryPlanner");
function assert(condition, message) {
    if (!condition)
        throw new Error(message);
}
function makeCandidate(params) {
    return {
        source: "mcp_poi",
        tags: [],
        suggestedDurationMinutes: 90,
        confidence: 0.85,
        ...params
    };
}
function buildQueryPlan(destination, categories) {
    return {
        destination,
        summary: "test query plan",
        categories: categories.map((category) => ({
            category,
            keywords: [category],
            priority: 5,
            minResults: 1,
            maxResults: 5,
            rationale: "test"
        })),
        generalKeywords: [],
        avoidCategories: []
    };
}
function govern(params) {
    const queryPlan = buildQueryPlan(String(params.requirement.destination ?? ""), params.categories);
    const queryTasks = params.categories.map((category) => ({
        tool: "searchPOI",
        city: String(params.requirement.destination ?? ""),
        keyword: category,
        category,
        priority: 5
    }));
    const governed = (0, poiGranularity_1.applyPoiGovernance)({
        candidates: params.candidates,
        requirement: params.requirement,
        queryPlan,
        queryTasks,
        warnings: []
    });
    return {
        destination: String(params.requirement.destination ?? ""),
        candidates: governed.candidates,
        toolResults: [],
        queryTasks,
        queryPlan,
        warnings: governed.warnings,
        planningMode: governed.planningMode,
        groundingDiagnostics: governed.groundingDiagnostics,
        governanceSummary: governed.governanceSummary
    };
}
function testCityTripDoesNotLeakInternalPoiIntoMainItinerary() {
    const requirement = {
        destination: "Sample City",
        trip_days: 2,
        interests: ["citywalk", "local food"],
        raw_input: "Sample City two day trip"
    };
    const pool = govern({
        requirement,
        categories: ["landmark", "citywalk", "food", "nightview"],
        candidates: [
            makeCandidate({ id: "park", name: "Central Heritage Park", city: "Sample City", category: "landmark", location: { lng: 120.1, lat: 30.1 } }),
            makeCandidate({ id: "visitor", name: "Central Heritage Park Visitor Center", city: "Sample City", category: "landmark", location: { lng: 120.101, lat: 30.101 } }),
            makeCandidate({ id: "pavilion", name: "Central Heritage Park Viewing Pavilion", city: "Sample City", category: "landmark", location: { lng: 120.102, lat: 30.102 } }),
            makeCandidate({ id: "district", name: "Riverfront Old Street", city: "Sample City", category: "citywalk", location: { lng: 120.11, lat: 30.11 } }),
            makeCandidate({ id: "food", name: "Riverfront Old Street Food Market", city: "Sample City", category: "food", location: { lng: 120.111, lat: 30.111 } }),
            makeCandidate({ id: "museum", name: "City Memory Museum", city: "Sample City", category: "museum", location: { lng: 120.12, lat: 30.12 } })
        ]
    });
    const planner = (0, dynamicItineraryPlanner_1.planDynamicItinerary)({ requirement, candidatePool: pool });
    assert(planner.itinerary.days.every((day) => day.items.every((item) => item.granularity !== "internal_poi_level")), "city_trip should not place internal_poi_level into day.items");
}
function testInternalPoisMergeIntoParentSubStops() {
    const requirement = {
        destination: "Scenic City",
        trip_days: 2,
        raw_input: "Scenic City two day trip"
    };
    const pool = govern({
        requirement,
        categories: ["landmark"],
        candidates: [
            makeCandidate({ id: "gate", name: "Grand Scenic Area East Gate", city: "Scenic City", category: "landmark", location: { lng: 121.1, lat: 31.1 } }),
            makeCandidate({ id: "tower", name: "Grand Scenic Area Observation Tower", city: "Scenic City", category: "landmark", location: { lng: 121.101, lat: 31.101 } })
        ]
    });
    const parent = pool.candidates.find((candidate) => candidate.name === "Grand Scenic Area");
    assert(Boolean(parent), "internal POIs should infer a parent candidate");
    assert((parent?.subStops?.length ?? 0) >= 2, "inferred parent should keep internal POIs as subStops");
}
function testCitywalkAndFoodAreaCanMergeIntoFoodWalk() {
    const requirement = {
        destination: "Walk City",
        trip_days: 2,
        interests: ["citywalk", "food"],
        raw_input: "Walk City two day trip"
    };
    const pool = govern({
        requirement,
        categories: ["citywalk", "food"],
        candidates: [
            makeCandidate({ id: "walk", name: "Harbor Old Street", city: "Walk City", category: "citywalk", location: { lng: 122.1, lat: 32.1 } }),
            makeCandidate({ id: "food", name: "Harbor Old Street Food Street", city: "Walk City", category: "food", location: { lng: 122.101, lat: 32.101 } })
        ]
    });
    assert(pool.candidates.some((candidate) => (candidate.roles ?? []).includes("walk") && (candidate.roles ?? []).includes("food")), "citywalk and food candidates from the same area should merge into a food_walk-style candidate");
}
function testNightViewCanLinkToExistingArea() {
    const requirement = {
        destination: "Night City",
        trip_days: 2,
        raw_input: "Night City two day trip night view"
    };
    const pool = govern({
        requirement,
        categories: ["citywalk", "nightview"],
        candidates: [
            makeCandidate({ id: "riverfront", name: "Riverfront Walk", city: "Night City", category: "citywalk", location: { lng: 123.1, lat: 33.1 } }),
            makeCandidate({ id: "night-name-only", name: "Riverfront Night View", city: "Night City", category: "nightview" })
        ]
    });
    assert(pool.candidates.some((candidate) => Boolean(candidate.linkedPoiId) && candidate.nightView), "night_view should link to an existing candidate when standalone grounding fails");
}
function testMerchantAliasFromScenicTaskIsRejected() {
    const requirement = {
        destination: "Alias City",
        trip_days: 2,
        raw_input: "Alias City two day trip"
    };
    const pool = govern({
        requirement,
        categories: ["landmark"],
        candidates: [
            makeCandidate({ id: "core", name: "Ancient City Wall", city: "Alias City", category: "landmark", location: { lng: 124.1, lat: 34.1 } }),
            makeCandidate({ id: "alias", name: "Ancient City Wall Hotel", city: "Alias City", category: "food", queryCategories: ["landmark"], location: { lng: 124.101, lat: 34.101 } })
        ]
    });
    const alias = pool.candidates.find((candidate) => candidate.id === "alias");
    assert(alias?.eligible_for_main_itinerary === false, "merchant alias should not inherit scenic main-candidate eligibility");
}
function testAttractionInternalRouteAllowsInternalPoiPlanning() {
    const requirement = {
        destination: "Route City",
        trip_days: 1,
        raw_input: "How to tour inside Grand Scenic Area"
    };
    const pool = govern({
        requirement,
        categories: ["landmark"],
        candidates: [
            makeCandidate({ id: "gate", name: "Grand Scenic Area East Gate", city: "Route City", category: "landmark", location: { lng: 125.1, lat: 35.1 } }),
            makeCandidate({ id: "pavilion", name: "Grand Scenic Area Lake Pavilion", city: "Route City", category: "landmark", location: { lng: 125.101, lat: 35.101 } }),
            makeCandidate({ id: "bridge", name: "Grand Scenic Area Stone Bridge", city: "Route City", category: "landmark", location: { lng: 125.102, lat: 35.102 } })
        ]
    });
    const planner = (0, dynamicItineraryPlanner_1.planDynamicItinerary)({ requirement, candidatePool: pool });
    assert(planner.itinerary.days.some((day) => day.items.some((item) => item.granularity === "internal_poi_level")), "attraction_internal_route should allow internal POIs into planned route items");
}
function printGovernanceSnapshot() {
    const requirement = {
        destination: "Demo City",
        trip_days: 2,
        interests: ["citywalk", "food", "night view"],
        raw_input: "Demo City two day trip with night view"
    };
    const pool = govern({
        requirement,
        categories: ["landmark", "citywalk", "food", "nightview"],
        candidates: [
            makeCandidate({ id: "park", name: "Grand Scenic Area Park", city: "Demo City", category: "landmark", location: { lng: 126.1, lat: 36.1 } }),
            makeCandidate({ id: "gate", name: "Grand Scenic Area Park East Gate", city: "Demo City", category: "landmark", location: { lng: 126.101, lat: 36.101 } }),
            makeCandidate({ id: "pavilion", name: "Grand Scenic Area Park Lake Pavilion", city: "Demo City", category: "landmark", location: { lng: 126.102, lat: 36.102 } }),
            makeCandidate({ id: "walk", name: "Harbor Old Street", city: "Demo City", category: "citywalk", location: { lng: 126.11, lat: 36.11 } }),
            makeCandidate({ id: "food", name: "Harbor Old Street Food Street", city: "Demo City", category: "food", location: { lng: 126.111, lat: 36.111 } }),
            makeCandidate({ id: "night", name: "Harbor Old Street Night View", city: "Demo City", category: "nightview" })
        ]
    });
    const planner = (0, dynamicItineraryPlanner_1.planDynamicItinerary)({ requirement, candidatePool: pool });
    const primaryCandidates = pool.candidates
        .filter((candidate) => candidate.eligible_for_main_itinerary)
        .map((candidate) => ({
        id: candidate.id,
        name: candidate.name,
        plannerCategory: candidate.plannerCategory,
        roles: candidate.roles,
        granularity: candidate.granularity,
        linkedPoiId: candidate.linkedPoiId,
        role: candidate.role
    }));
    const mergedAliases = pool.candidates
        .filter((candidate) => (candidate.mergedAliases?.length ?? 0) > 0)
        .map((candidate) => ({ name: candidate.name, mergedAliases: candidate.mergedAliases }));
    const linkedNightViewTarget = pool.groundingDiagnostics?.flatMap((item) => item.linkedNightViewTarget ? [{ taskName: item.taskName, linkedNightViewTarget: item.linkedNightViewTarget }] : []) ?? [];
    const parentInferred = pool.groundingDiagnostics?.flatMap((item) => item.parentInferred.length ? [{ taskName: item.taskName, parentInferred: item.parentInferred }] : []) ?? [];
    const subStops = pool.candidates
        .filter((candidate) => (candidate.subStops?.length ?? 0) > 0)
        .map((candidate) => ({ name: candidate.name, subStops: candidate.subStops }));
    const dayItems = planner.itinerary.days.map((day) => ({
        day: day.day,
        items: day.items.map((item) => ({
            name: item.name,
            category: item.category,
            granularity: item.granularity,
            plannerRole: item.role,
            roles: item.roles,
            linkedPoiId: item.linkedPoiId,
            subStops: item.subStops
        }))
    }));
    console.log("final primary candidates");
    console.log(JSON.stringify(primaryCandidates, null, 2));
    console.log("mergedAliases");
    console.log(JSON.stringify(mergedAliases, null, 2));
    console.log("linkedNightViewTarget");
    console.log(JSON.stringify(linkedNightViewTarget, null, 2));
    console.log("parentInferred");
    console.log(JSON.stringify(parentInferred, null, 2));
    console.log("subStops");
    console.log(JSON.stringify(subStops, null, 2));
    console.log("final day.items");
    console.log(JSON.stringify(dayItems, null, 2));
    assert(planner.itinerary.days.every((day) => day.items.every((item) => item.granularity !== "internal_poi_level")), "snapshot should confirm no internal_poi_level enters city_trip main itinerary");
}
function main() {
    testCityTripDoesNotLeakInternalPoiIntoMainItinerary();
    testInternalPoisMergeIntoParentSubStops();
    testCitywalkAndFoodAreaCanMergeIntoFoodWalk();
    testNightViewCanLinkToExistingArea();
    testMerchantAliasFromScenicTaskIsRejected();
    testAttractionInternalRouteAllowsInternalPoiPlanning();
    printGovernanceSnapshot();
    console.log("poi_granularity_rules_ok");
}
main();

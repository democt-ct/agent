import type {
  CandidatePool,
  ChatInput,
  ConversationMessage,
  Env,
  ItineraryDraft,
  PlannerOutput,
  RequirementInterpretationResult,
  StructuredPayload,
  TripRequirement
} from "../../types";
import { ItineraryRepository } from "../../repositories/itineraryRepository";
import { MessageRepository } from "../../repositories/messageRepository";
import { RequirementRepository } from "../../repositories/requirementRepository";
import { SessionRepository } from "../../repositories/sessionRepository";
import { interpretRequirement } from "../llm/requirementInterpreter";
import { resolveSearchBasePayload } from "../location/searchBaseResolver";
import { buildTravelPlanningPipeline } from "../planning/travelPlanningPipeline";
import {
  fallbackSelectWithoutCluster,
  buildMapData
} from "../planning/dynamicItineraryPlanner";
import { buildCandidateDebugSummary } from "../planning/anchorClusterPlanner";
import {
  buildFollowUpQuestions,
  buildPreferenceFollowUpQuestion,
  findMissingFields
} from "../questionPlanner";
import {
  hasReplanDirectiveSignal,
  summarizeAppliedDirectiveChanges
} from "../replan/replanDirectives";

export type OrchestratorAction =
  | "collect_requirement"
  | "collect_preference"
  | "generate_itinerary"
  | "replan_itinerary"
  | "itinerary_qa"
  | "planning_blocked";

export interface TripPlanResult {
  requirement: TripRequirement;
  itinerary: ItineraryDraft;
  candidatePool: CandidatePool;
  plannerOutput: PlannerOutput;
}

export interface ChatOrchestratorResult {
  action: OrchestratorAction;
  userMessage: ConversationMessage;
  assistantMessage: ConversationMessage;
  requirement: TripRequirement | null;
  itinerary: ItineraryDraft | null;
  candidatePool?: CandidatePool;
  plannerOutput?: PlannerOutput;
  missingFields: string[];
  followUpQuestions: string[];
  recentMessages: ConversationMessage[];
}

export class PlanningBlockedError extends Error {
  readonly candidatePool: CandidatePool;
  readonly plannerOutput: PlannerOutput;
  readonly warnings: string[];

  constructor(params: {
    message: string;
    candidatePool: CandidatePool;
    plannerOutput: PlannerOutput;
    warnings: string[];
  }) {
    super(params.message);
    this.name = "PlanningBlockedError";
    this.candidatePool = params.candidatePool;
    this.plannerOutput = params.plannerOutput;
    this.warnings = params.warnings;
  }
}

function parseJson<T>(value: string | null, fallback: T): T {
  if (!value) return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

function mergePayload(
  existing: StructuredPayload,
  interpreted: RequirementInterpretationResult
): StructuredPayload {
  const next = interpreted.payload;
  return {
    ...existing,
    ...next,
    interests: next.interests ?? existing.interests,
    constraints: next.constraints ?? existing.constraints
  };
}

function hasTripChange(payload: StructuredPayload): boolean {
  return Boolean(
    payload.destination ||
      payload.trip_days ||
      payload.budget_min ||
      payload.budget_max ||
      payload.start_date ||
      payload.end_date
  );
}

function hasRequirementUpdate(payload: StructuredPayload): boolean {
  return hasTripChange(payload) || hasReplanDirectiveSignal(payload);
}

function isItineraryQaMessage(message: string): boolean {
  return /为什么|为何|怎么安排|啥意思|解释|为啥/u.test(message) &&
    !/改|换|不要|轻松|咖啡|夜景|商场|第\d+天|上午|中午|下午|晚上/u.test(message);
}

function buildTitle(payload: StructuredPayload): string {
  const destination = String(payload.destination ?? "目的地");
  const days = payload.trip_days ? `${payload.trip_days}天` : "";
  return `${destination}${days}旅行方案`;
}

function buildSummary(payload: StructuredPayload, plannerOutput: PlannerOutput): string {
  const destination = String(payload.destination ?? "目的地");
  const days = plannerOutput.itinerary.days.length;
  const interests = Array.isArray(payload.interests) ? payload.interests.join("、") : "";
  return [
    `已基于候选池为${destination}生成${days}天行程。`,
    interests ? `重点偏好：${interests}。` : "",
    plannerOutput.warnings.length ? `注意：${plannerOutput.warnings[0]}` : ""
  ].filter(Boolean).join("");
}

function buildAssistantSummary(params: {
  action: OrchestratorAction;
  payload: StructuredPayload;
  plannerOutput?: PlannerOutput;
  followUpQuestions?: string[];
}): string {
  if (params.followUpQuestions?.length) {
    return params.followUpQuestions[0];
  }

  const destination = String(params.payload.destination ?? "目的地");
  const days = params.payload.trip_days ? `${params.payload.trip_days}天` : "";
  const interests = Array.isArray(params.payload.interests)
    ? params.payload.interests.join("、")
    : "";
  const markerCount = params.plannerOutput?.mapData.markers.length ?? 0;
  const itemCount =
    params.plannerOutput?.itinerary.days.reduce((sum, day) => sum + day.items.length, 0) ?? 0;

  if (params.action === "replan_itinerary") {
    return `已按你的新要求重新规划${destination}${days}行程，当前选入${itemCount}个候选点，地图可展示${markerCount}个点位。${interests ? `重点围绕${interests}。` : ""}`;
  }

  return `已生成${destination}${days}行程，当前选入${itemCount}个候选点，地图可展示${markerCount}个点位。${interests ? `重点围绕${interests}。` : ""}`;
}

function buildPlanningBlockedMessage(warnings: string[]): string {
  return [
    "规划链路没有满足硬输出要求，已停止生成成功态行程。",
    warnings.length ? `阻断原因：${warnings.join("；")}` : ""
  ].filter(Boolean).join("");
}

function assertPlannerHardOutput(params: {
  candidatePool: CandidatePool;
  plannerOutput: PlannerOutput;
}): void {
  const warnings: string[] = [];
  const poiResults = params.candidatePool.toolResults.filter((result) => result.tool === "poi_search");
  const poiCandidateCount = params.candidatePool.candidates.filter(
    (candidate) => candidate.source === "mcp_poi" && candidate.location
  ).length;
  const itemCount = params.plannerOutput.itinerary.days.reduce(
    (sum, day) => sum + day.items.length,
    0
  );
  const markerCount = params.plannerOutput.mapData.markers.length;
  const routeSegmentsCount = params.plannerOutput.mapData.polylines.length;

  if (!poiResults.length) {
    warnings.push("searchPOI was not called");
  }
  if (poiResults.length && poiCandidateCount === 0) {
    warnings.push("searchPOI returned no usable located CandidatePlace records");
  }
  if (params.candidatePool.candidates.length === 0) {
    warnings.push("candidatePlaces is empty");
  }
  if (itemCount === 0) {
    warnings.push("planner selected zero itinerary items");
  }
  if (markerCount === 0) {
    warnings.push("planner produced zero map markers");
  }
  if (markerCount >= 2 && routeSegmentsCount === 0) {
    warnings.push("routePlanner produced zero routeSegments");
  }
  if (params.plannerOutput.coverageCheck?.missing_items.length) {
    warnings.push(`city signature coverage missing: ${params.plannerOutput.coverageCheck.missing_items.join(", ")}`);
  }
  if (params.plannerOutput.routeValidation && !params.plannerOutput.routeValidation.is_valid) {
    warnings.push(`route validation failed: ${params.plannerOutput.routeValidation.main_problems.join("; ")}`);
  }

  if (warnings.length) {
    console.warn("[planner] hard output requirements failed", {
      warnings,
      poiResults: poiResults.length,
      poiCandidateCount,
      candidatePlaces: params.candidatePool.candidates.length,
      itemCount,
      markerCount,
      routeSegmentsCount
    });
    throw new PlanningBlockedError({
      message: "planner hard output requirements failed",
      candidatePool: params.candidatePool,
      plannerOutput: params.plannerOutput,
      warnings
    });
  }
}

export async function planTrip(params: {
  env: Env;
  sessionId: string;
  requirement: TripRequirement;
}): Promise<TripPlanResult> {
  const itineraryRepository = new ItineraryRepository(params.env.DB);
  const sessionRepository = new SessionRepository(params.env.DB);
  const payload = parseJson<StructuredPayload>(
    params.requirement.structured_payload_json,
    {}
  );
  const pipelineResult = await buildTravelPlanningPipeline({
    env: params.env,
    requirement: payload
  });
  const totalItemsBeforeFallback = pipelineResult.plannerOutput.itinerary.days.reduce(
    (sum, day) => sum + day.items.length,
    0
  );
  let plannerOutput = pipelineResult.plannerOutput;
  if (totalItemsBeforeFallback === 0) {
    const fallback = fallbackSelectWithoutCluster({
      candidates: pipelineResult.candidatePool.candidates,
      tripDays: plannerOutput.itinerary.days.length || Number(payload.trip_days ?? 1) || 1
    });
    if (fallback.days.length) {
      plannerOutput = {
        ...plannerOutput,
        itinerary: { days: fallback.days },
        mapData: buildMapData(fallback.days),
        warnings: Array.from(new Set([...plannerOutput.warnings, ...fallback.warnings]))
      };
      console.warn("[planner] fallback_select_without_cluster_used", {
        days: fallback.days.length,
        items: fallback.days.reduce((sum, day) => sum + day.items.length, 0)
      });
    } else {
      const diagnostics = buildCandidateDebugSummary(pipelineResult.candidatePool.candidates);
      console.warn("[planner] fallback_select_without_cluster_still_empty", diagnostics);
      plannerOutput = {
        ...plannerOutput,
        warnings: Array.from(new Set([...plannerOutput.warnings, ...fallback.warnings]))
      };
    }
  }
  console.info("[planner] output", {
    dayCount: plannerOutput.itinerary.days.length,
    itemCount: plannerOutput.itinerary.days.reduce((sum, day) => sum + day.items.length, 0),
    markerCount: plannerOutput.mapData.markers.length,
    warnings: plannerOutput.warnings
  });
  assertPlannerHardOutput({
    candidatePool: pipelineResult.candidatePool,
    plannerOutput
  });
  const itinerary = await itineraryRepository.create({
    sessionId: params.sessionId,
    requirementId: params.requirement.id,
    title: buildTitle(payload),
    summary: buildSummary(payload, plannerOutput),
    itinerary: {
      ...plannerOutput.itinerary,
      mapData: plannerOutput.mapData,
      sourceRefs: plannerOutput.sourceRefs,
      queryPlan: pipelineResult.queryPlan,
      selectionHints: pipelineResult.selectionHints
    },
    budgetEstimate: null,
    warnings: plannerOutput.warnings,
    generatorType: "planner"
  });
  await sessionRepository.bumpItineraryVersion(params.sessionId, itinerary.version);

  return {
    requirement: params.requirement,
    itinerary,
    candidatePool: pipelineResult.candidatePool,
    plannerOutput
  };
}

export async function replanTrip(params: {
  env: Env;
  sessionId: string;
  latestRequirement: TripRequirement;
  latestItinerary: ItineraryDraft | null;
  instruction: string;
  strategy?: ChatInput["strategy"];
}): Promise<{
  interpreted: RequirementInterpretationResult;
  requirement: TripRequirement;
  plan: TripPlanResult;
}> {
  const requirementRepository = new RequirementRepository(params.env.DB);
  const sessionRepository = new SessionRepository(params.env.DB);
  const existingPayload = parseJson<StructuredPayload>(
    params.latestRequirement.structured_payload_json,
    {}
  );
  const interpreted = await interpretRequirement(
    params.env,
    params.instruction,
    params.strategy,
    existingPayload
  );
  const payload = mergePayload(existingPayload, interpreted);
  const requirement = await requirementRepository.create(params.sessionId, {
    raw_input: params.instruction,
    structured_payload: payload,
    strategy: interpreted.strategy
  });
  await sessionRepository.bumpRequirementVersion(params.sessionId, requirement.version);

  const plan = await planTrip({
    env: params.env,
    sessionId: params.sessionId,
    requirement
  });

  return { interpreted, requirement, plan };
}

export async function handleChatMessage(params: {
  env: Env;
  sessionId: string;
  input: ChatInput;
}): Promise<ChatOrchestratorResult> {
  const sessionRepository = new SessionRepository(params.env.DB);
  const requirementRepository = new RequirementRepository(params.env.DB);
  const itineraryRepository = new ItineraryRepository(params.env.DB);
  const messageRepository = new MessageRepository(params.env.DB);

  const message = params.input.message.trim();
  if (!message) {
    throw new Error("message is required");
  }
  const session = await sessionRepository.getById(params.sessionId);
  if (!session) {
    throw new Error("session not found");
  }

  const [latestRequirement, latestItinerary] = await Promise.all([
    requirementRepository.getLatestBySessionId(params.sessionId),
    itineraryRepository.getLatestBySessionId(params.sessionId)
  ]);

  const userMessage = await messageRepository.create(params.sessionId, {
    role: "user",
    content: message,
    metadata: {
      has_requirement: Boolean(latestRequirement),
      has_itinerary: Boolean(latestItinerary)
    }
  });

  const existingPayload = latestRequirement
    ? parseJson<StructuredPayload>(latestRequirement.structured_payload_json, {})
    : {};
  const interpreted = await interpretRequirement(
    params.env,
    message,
    params.input.strategy,
    latestRequirement ? existingPayload : undefined
  );
  const mergedPayload = await resolveSearchBasePayload({
    env: params.env,
    payload: mergePayload(existingPayload, interpreted),
    existingPayload,
    userLocation: params.input.user_location
  });
  const missingFields = findMissingFields(mergedPayload);

  if (missingFields.length) {
    const followUpQuestions = interpreted.follow_up_questions.length
      ? interpreted.follow_up_questions
      : buildFollowUpQuestions(mergedPayload);
    const requirement = await requirementRepository.create(params.sessionId, {
      raw_input: message,
      structured_payload: mergedPayload,
      strategy: interpreted.strategy
    });
    await sessionRepository.bumpRequirementVersion(params.sessionId, requirement.version);
    const assistantMessage = await messageRepository.create(params.sessionId, {
      role: "assistant",
      content: buildAssistantSummary({
        action: "collect_requirement",
        payload: mergedPayload,
        followUpQuestions
      }),
      metadata: {
        action: "collect_requirement",
        requirement_id: requirement.id,
        missing_fields: missingFields
      }
    });
    return {
      action: "collect_requirement",
      userMessage,
      assistantMessage,
      requirement,
      itinerary: latestItinerary,
      missingFields,
      followUpQuestions,
      recentMessages: await messageRepository.listBySessionId(params.sessionId, 50)
    };
  }

  const preferenceQuestion = buildPreferenceFollowUpQuestion(mergedPayload);
  if (!latestItinerary && preferenceQuestion) {
    const requirement = await requirementRepository.create(params.sessionId, {
      raw_input: message,
      structured_payload: mergedPayload,
      strategy: interpreted.strategy
    });
    await sessionRepository.bumpRequirementVersion(params.sessionId, requirement.version);
    const assistantMessage = await messageRepository.create(params.sessionId, {
      role: "assistant",
      content: preferenceQuestion,
      metadata: {
        action: "collect_preference",
        requirement_id: requirement.id
      }
    });
    return {
      action: "collect_preference",
      userMessage,
      assistantMessage,
      requirement,
      itinerary: latestItinerary,
      missingFields: [],
      followUpQuestions: [preferenceQuestion],
      recentMessages: await messageRepository.listBySessionId(params.sessionId, 50)
    };
  }

  const shouldReplan = Boolean(latestRequirement && latestItinerary && hasRequirementUpdate(mergedPayload));
  if (latestRequirement && latestItinerary && !shouldReplan && isItineraryQaMessage(message)) {
    const payload = parseJson<StructuredPayload>(latestRequirement.structured_payload_json, {});
    const assistantMessage = await messageRepository.create(params.sessionId, {
      role: "assistant",
      content: buildAssistantSummary({
        action: "itinerary_qa",
        payload
      }),
      metadata: {
        action: "itinerary_qa",
        requirement_id: latestRequirement.id,
        itinerary_id: latestItinerary.id
      }
    });
    return {
      action: "itinerary_qa",
      userMessage,
      assistantMessage,
      requirement: latestRequirement,
      itinerary: latestItinerary,
      missingFields: [],
      followUpQuestions: [],
      recentMessages: await messageRepository.listBySessionId(params.sessionId, 50)
    };
  }
  if (shouldReplan && latestRequirement) {
    let replan: Awaited<ReturnType<typeof replanTrip>>;
    try {
      replan = await replanTrip({
        env: params.env,
        sessionId: params.sessionId,
        latestRequirement,
        latestItinerary,
        instruction: message,
        strategy: params.input.strategy
      });
    } catch (error) {
      if (!(error instanceof PlanningBlockedError)) throw error;
      const assistantMessage = await messageRepository.create(params.sessionId, {
        role: "assistant",
        content: buildPlanningBlockedMessage(error.warnings),
        metadata: {
          action: "planning_blocked",
          warnings: error.warnings,
          candidate_count: error.candidatePool.candidates.length,
          map_marker_count: error.plannerOutput.mapData.markers.length,
          route_segments_count: error.plannerOutput.mapData.polylines.length
        }
      });
      return {
        action: "planning_blocked",
        userMessage,
        assistantMessage,
        requirement: latestRequirement,
        itinerary: null,
        candidatePool: error.candidatePool,
        plannerOutput: error.plannerOutput,
        missingFields: [],
        followUpQuestions: [],
        recentMessages: await messageRepository.listBySessionId(params.sessionId, 50)
      };
    }
    const payload = parseJson<StructuredPayload>(
      replan.plan.requirement.structured_payload_json,
      {}
    );
    const assistantMessage = await messageRepository.create(params.sessionId, {
      role: "assistant",
      content: buildAssistantSummary({
        action: "replan_itinerary",
        payload,
        plannerOutput: replan.plan.plannerOutput
      }),
      metadata: {
        action: "replan_itinerary",
        requirement_id: replan.plan.requirement.id,
        itinerary_id: replan.plan.itinerary.id,
        candidate_count: replan.plan.candidatePool.candidates.length,
        map_marker_count: replan.plan.plannerOutput.mapData.markers.length,
        route_segments_count: replan.plan.plannerOutput.mapData.polylines.length
      }
    });
    return {
      action: "replan_itinerary",
      userMessage,
      assistantMessage,
      requirement: replan.plan.requirement,
      itinerary: replan.plan.itinerary,
      candidatePool: replan.plan.candidatePool,
      plannerOutput: replan.plan.plannerOutput,
      missingFields: [],
      followUpQuestions: [],
      recentMessages: await messageRepository.listBySessionId(params.sessionId, 50)
    };
  }

  const requirement =
    latestRequirement && !hasRequirementUpdate(mergedPayload)
      ? latestRequirement
      : await requirementRepository.create(params.sessionId, {
          raw_input: message,
          structured_payload: mergedPayload,
          strategy: interpreted.strategy
        });
  if (requirement !== latestRequirement) {
    await sessionRepository.bumpRequirementVersion(params.sessionId, requirement.version);
  }

  let plan: TripPlanResult;
  try {
    plan = await planTrip({
      env: params.env,
      sessionId: params.sessionId,
      requirement
    });
  } catch (error) {
    if (!(error instanceof PlanningBlockedError)) throw error;
    const assistantMessage = await messageRepository.create(params.sessionId, {
      role: "assistant",
      content: buildPlanningBlockedMessage(error.warnings),
      metadata: {
        action: "planning_blocked",
        requirement_id: requirement.id,
        warnings: error.warnings,
        candidate_count: error.candidatePool.candidates.length,
        map_marker_count: error.plannerOutput.mapData.markers.length,
        route_segments_count: error.plannerOutput.mapData.polylines.length
      }
    });
    return {
      action: "planning_blocked",
      userMessage,
      assistantMessage,
      requirement,
      itinerary: null,
      candidatePool: error.candidatePool,
      plannerOutput: error.plannerOutput,
      missingFields: [],
      followUpQuestions: [],
      recentMessages: await messageRepository.listBySessionId(params.sessionId, 50)
    };
  }

  const action: OrchestratorAction = "generate_itinerary";
  const payload = parseJson<StructuredPayload>(plan.requirement.structured_payload_json, {});
  const assistantMessage = await messageRepository.create(params.sessionId, {
    role: "assistant",
    content: buildAssistantSummary({
      action,
      payload,
      plannerOutput: plan.plannerOutput
    }),
    metadata: {
      action,
      requirement_id: plan.requirement.id,
      itinerary_id: plan.itinerary.id,
      candidate_count: plan.candidatePool.candidates.length,
      map_marker_count: plan.plannerOutput.mapData.markers.length,
      route_segments_count: plan.plannerOutput.mapData.polylines.length
    }
  });

  return {
    action,
    userMessage,
    assistantMessage,
    requirement: plan.requirement,
    itinerary: plan.itinerary,
    candidatePool: plan.candidatePool,
    plannerOutput: plan.plannerOutput,
    missingFields: [],
    followUpQuestions: [],
    recentMessages: await messageRepository.listBySessionId(params.sessionId, 50)
  };
}

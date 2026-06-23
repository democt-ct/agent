import type {
  CandidatePool,
  Env,
  PlannerOutput,
  StructuredPayload
} from "../../types";
import { buildCandidatePool } from "../candidates/candidatePoolBuilder";
import { McpClient } from "../mcp/mcpClient";
import { buildCandidateQueryPlan, reviewCandidatePoolSelection } from "../llm/candidatePlanner";
import { buildCitySignatureSeed } from "../llm/citySignatureSeeder";
import { enrichPlannerOutputWithRoutes } from "./plannerRouteEnricher";
import { planDynamicItinerary } from "./dynamicItineraryPlanner";

export interface TravelPlanningPipelineResult {
  queryPlan: CandidatePool["queryPlan"];
  selectionHints: CandidatePool["selectionHints"];
  candidatePool: CandidatePool;
  plannerOutput: PlannerOutput;
}

export async function buildTravelPlanningPipeline(params: {
  env: Env;
  requirement: StructuredPayload;
  instruction?: string;
  includeSelectionReview?: boolean;
  routeMode?: "walking" | "driving" | "straight";
}): Promise<TravelPlanningPipelineResult> {
  const citySignatureSeed = await buildCitySignatureSeed({
    env: params.env,
    requirement: params.requirement
  });
  const queryPlan = await buildCandidateQueryPlan({
    env: params.env,
    requirement: params.requirement,
    instruction: params.instruction,
    seed: citySignatureSeed
  });
  const rawCandidatePool = await buildCandidatePool({
    requirement: params.requirement,
    env: params.env,
    queryPlan,
    citySignatureSeed
  });
  const selectionHints = params.includeSelectionReview === false
    ? undefined
    : await reviewCandidatePoolSelection({
        env: params.env,
        requirement: params.requirement,
        queryPlan,
        candidatePool: rawCandidatePool
      });
  const candidatePool: CandidatePool = {
    ...rawCandidatePool,
    queryPlan,
    selectionHints,
    citySignatureSeed
  };
  const basePlannerOutput = planDynamicItinerary({
    requirement: params.requirement,
    candidatePool
  });
  const plannerOutput = await enrichPlannerOutputWithRoutes({
    plannerOutput: basePlannerOutput,
    mcpClient: new McpClient(params.env),
    mode: params.routeMode
  });

  return {
    queryPlan,
    selectionHints,
    candidatePool,
    plannerOutput
  };
}

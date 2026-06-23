import type {
  Env,
  ItineraryDraft,
  ItineraryGenerationResult,
  StructuredPayload,
  TripRequirement
} from "../../types";
import { buildTravelPlanningPipeline } from "../planning/travelPlanningPipeline";

function buildRequirementPayload(requirement: TripRequirement): StructuredPayload {
  return JSON.parse(requirement.structured_payload_json) as StructuredPayload;
}

function buildTitle(payload: StructuredPayload, dayCount: number): string {
  const destination = String(payload.destination ?? "destination").trim() || "destination";
  return `${destination} ${dayCount} day travel plan`;
}

function buildSummary(params: {
  payload: StructuredPayload;
  queryPlanSummary?: string;
  selectionNotes?: string[];
  plannerWarnings: string[];
  dayCount: number;
  itemCount: number;
}): string {
  const interests = Array.isArray(params.payload.interests) ? params.payload.interests.join(", ") : "";
  const parts = [
    params.queryPlanSummary ?? "The itinerary is built from live POI search and route planning.",
    interests ? `Focus: ${interests}.` : "",
    params.selectionNotes?.length ? `Selection hints: ${params.selectionNotes[0]}` : "",
    `Planned ${params.dayCount} days with ${params.itemCount} stops.`,
    params.plannerWarnings.length ? `Warning: ${params.plannerWarnings[0]}` : ""
  ];
  return parts.filter(Boolean).join(" ");
}

function buildExistingItineraryPayload(itinerary: ItineraryDraft | null): unknown {
  if (!itinerary) {
    return null;
  }
  return JSON.parse(itinerary.itinerary_json);
}

export async function generateAgentItinerary(params: {
  env: Env;
  requirement: TripRequirement;
  existingItinerary?: ItineraryDraft | null;
  instruction?: string;
  generatorType: "llm" | "agent";
}): Promise<ItineraryGenerationResult> {
  const payload = buildRequirementPayload(params.requirement);
  const pipeline = await buildTravelPlanningPipeline({
    env: params.env,
    requirement: payload,
    instruction: params.instruction,
    includeSelectionReview: true
  });
  const existingItinerary = buildExistingItineraryPayload(params.existingItinerary ?? null);
  const dayCount = pipeline.plannerOutput.itinerary.days.length;
  const itemCount = pipeline.plannerOutput.itinerary.days.reduce((sum, day) => sum + day.items.length, 0);

  return {
    title: buildTitle(payload, dayCount),
    summary: buildSummary({
      payload,
      queryPlanSummary: pipeline.queryPlan?.summary,
      selectionNotes: pipeline.selectionHints?.notes,
      plannerWarnings: pipeline.plannerOutput.warnings,
      dayCount,
      itemCount
    }),
    itinerary: {
      ...pipeline.plannerOutput.itinerary,
      mapData: pipeline.plannerOutput.mapData,
      sourceRefs: pipeline.plannerOutput.sourceRefs,
      queryPlan: pipeline.queryPlan,
      selectionHints: pipeline.selectionHints,
      preferenceProfile: pipeline.plannerOutput.preferenceProfile,
      citySignatureSeed: pipeline.plannerOutput.citySignatureSeed,
      citySignaturePool: pipeline.plannerOutput.citySignaturePool,
      coverageCheck: pipeline.plannerOutput.coverageCheck,
      routeValidation: pipeline.plannerOutput.routeValidation,
      notSelectedSignatureItems: pipeline.plannerOutput.notSelectedSignatureItems,
      existingItinerary
    },
    budgetEstimate: null,
    warnings: pipeline.plannerOutput.warnings,
    generatorType: params.generatorType
  };
}

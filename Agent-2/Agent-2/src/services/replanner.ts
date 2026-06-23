import type { Env, ItineraryDraft, ItineraryGenerationResult, TripRequirement } from "../types";
import { generateAgentItinerary } from "./llm/itineraryAgent";

export async function replanItinerary(params: {
  env: Env;
  requirement: TripRequirement;
  existingItinerary: ItineraryDraft | null;
  instruction: string;
  generatorType: "llm" | "agent";
}): Promise<ItineraryGenerationResult> {
  return generateAgentItinerary({
    env: params.env,
    requirement: params.requirement,
    existingItinerary: params.existingItinerary,
    instruction: params.instruction,
    generatorType: params.generatorType
  });
}

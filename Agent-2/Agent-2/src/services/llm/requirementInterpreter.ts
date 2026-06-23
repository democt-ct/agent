import type {
  Env,
  RequirementInterpretationResult,
  StructuredPayload
} from "../../types";
import { parseRequirement } from "../requirementParser";
import { buildFollowUpQuestions, findMissingFields } from "../questionPlanner";
import {
  applyReplanDirectivesToPayload,
  extractReplanDirectives,
  mergeReplanDirectives
} from "../replan/replanDirectives";
import { getDefaultRequirementStrategy } from "./modelConfig";
import { OpenAIResponsesClient } from "./openaiResponsesClient";
import { REQUIREMENT_EXTRACTION_SYSTEM_PROMPT } from "./prompts";

interface LlmRequirementPayload {
  origin_city?: string | null;
  destination?: string | null;
  location_scope?: "city_only" | "surrounding" | "nearby" | null;
  start_date?: string | null;
  end_date?: string | null;
  trip_days?: number | null;
  budget_min?: number | null;
  budget_max?: number | null;
  travelers_summary?: string | null;
  interests?: string[] | null;
  constraints?: string[] | null;
}

function mergePayload(
  base: StructuredPayload,
  extra?: StructuredPayload
): StructuredPayload {
  return {
    ...base,
    ...(extra ?? {}),
    interests: extra?.interests ?? base.interests,
    constraints: extra?.constraints ?? base.constraints,
    replan_directives: mergeReplanDirectives(base.replan_directives, extra?.replan_directives)
  };
}

function normalizeLlmPayload(payload: LlmRequirementPayload): StructuredPayload {
  const normalized: StructuredPayload = {};

  if (payload.origin_city) normalized.origin_city = payload.origin_city;
  if (payload.destination) {
    normalized.destination = payload.destination;
    normalized.city_source = "user_explicit";
  }
  if (payload.location_scope) normalized.location_scope = payload.location_scope;
  if (payload.start_date) normalized.start_date = payload.start_date;
  if (payload.end_date) normalized.end_date = payload.end_date;
  if (payload.trip_days) normalized.trip_days = payload.trip_days;
  if (payload.budget_min) normalized.budget_min = payload.budget_min;
  if (payload.budget_max) normalized.budget_max = payload.budget_max;
  if (payload.travelers_summary) {
    normalized.travelers_summary = payload.travelers_summary;
  }
  if (payload.interests?.length) normalized.interests = payload.interests;
  if (payload.constraints?.length) normalized.constraints = payload.constraints;

  return normalized;
}

function buildRulePayload(
  rawInput: string,
  providedPayload?: StructuredPayload
): StructuredPayload {
  const extractedDirectives = extractReplanDirectives(rawInput);
  const rulePayload = parseRequirement(rawInput);
  if (extractedDirectives) {
    rulePayload.replan_directives = extractedDirectives;
  }
  return applyReplanDirectivesToPayload({
    ...mergePayload(providedPayload ?? {}, rulePayload),
    replan_directives: mergeReplanDirectives(providedPayload?.replan_directives, rulePayload.replan_directives)
  });
}

export async function interpretRequirement(
  env: Env,
  rawInput: string,
  strategy: "rule" | "llm" | undefined,
  providedPayload?: StructuredPayload
): Promise<RequirementInterpretationResult> {
  const extractedDirectives = extractReplanDirectives(rawInput);
  const normalizedRulePayload = buildRulePayload(rawInput, providedPayload);
  const resolvedStrategy = strategy ?? getDefaultRequirementStrategy(env);

  if (resolvedStrategy !== "llm") {
    return {
      payload: normalizedRulePayload,
      missing_fields: findMissingFields(normalizedRulePayload),
      follow_up_questions: buildFollowUpQuestions(normalizedRulePayload),
      strategy: "rule"
    };
  }

  const client = new OpenAIResponsesClient(env);
  if (!client.isEnabled()) {
    return {
      payload: normalizedRulePayload,
      missing_fields: findMissingFields(normalizedRulePayload),
      follow_up_questions: buildFollowUpQuestions(normalizedRulePayload),
      strategy: "rule"
    };
  }

  const llmPayload = await client.createStructuredJson<LlmRequirementPayload>({
    system: REQUIREMENT_EXTRACTION_SYSTEM_PROMPT,
    user: JSON.stringify(
      {
        raw_input: rawInput,
        normalization_rules: [
          "Normalize Chinese duration expressions into integer trip_days.",
          "Examples: 两天/2天 => 2; 三天/3天 => 3; 十天/10天 => 10.",
          "Do not invent or autocorrect destination names.",
          "Extract destination only from the user's explicit wording; do not infer from session, geolocation, or heuristics.",
          "If the user says a city plus 周边/附近/近郊, keep the base city as destination and set location_scope to surrounding or nearby.",
          "Do not ask follow-up questions inside this JSON task; return null only when truly absent."
        ]
      },
      null,
      2
    ),
    schemaName: "travel_requirement",
    schema: {
      type: "object",
      additionalProperties: false,
      properties: {
        origin_city: { type: ["string", "null"] },
        destination: { type: ["string", "null"] },
        location_scope: {
          type: ["string", "null"],
          enum: ["city_only", "surrounding", "nearby", null]
        },
        start_date: { type: ["string", "null"] },
        end_date: { type: ["string", "null"] },
        trip_days: { type: ["integer", "null"] },
        budget_min: { type: ["integer", "null"] },
        budget_max: { type: ["integer", "null"] },
        travelers_summary: { type: ["string", "null"] },
        interests: {
          type: ["array", "null"],
          items: { type: "string" }
        },
        constraints: {
          type: ["array", "null"],
          items: { type: "string" }
        }
      },
      required: [
        "origin_city",
        "destination",
        "location_scope",
        "start_date",
        "end_date",
        "trip_days",
        "budget_min",
        "budget_max",
        "travelers_summary",
        "interests",
        "constraints"
      ]
    }
  });

  const mergedPayload = mergePayload(
    mergePayload(providedPayload ?? {}, parseRequirement(rawInput)),
    normalizeLlmPayload(llmPayload)
  );
  const finalPayload = applyReplanDirectivesToPayload({
    ...mergedPayload,
    replan_directives: mergeReplanDirectives(providedPayload?.replan_directives, extractedDirectives)
  });

  return {
    payload: finalPayload,
    missing_fields: findMissingFields(finalPayload),
    follow_up_questions: buildFollowUpQuestions(finalPayload),
    strategy: "llm"
  };
}

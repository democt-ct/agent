import type {
  CitySource,
  CreateItineraryInput,
  ChatInput,
  CreateMessageInput,
  CreateRequirementInput,
  ReplanInput,
  CreateSessionInput,
  Env,
  StructuredPayload
} from "./types";
import { SessionRepository } from "./repositories/sessionRepository";
import { RequirementRepository } from "./repositories/requirementRepository";
import { ItineraryRepository } from "./repositories/itineraryRepository";
import { MessageRepository } from "./repositories/messageRepository";
import { generateTemplateItinerary } from "./services/templateItineraryGenerator";
import { interpretRequirement } from "./services/llm/requirementInterpreter";
import { generateAgentItinerary } from "./services/llm/itineraryAgent";
import { getDefaultGeneratorType } from "./services/llm/modelConfig";
import { replanItinerary } from "./services/replanner";
import { handleChatMessage } from "./services/orchestration/tripOrchestrator";
import { enhanceItineraryWithRoutePlan } from "./services/map/routePlanEnricher";
import { enforceControlledItinerary } from "./services/planning/controlledItineraryPlanner";
import {
  resolvePreferenceOwner,
  UserPreferenceRepository
} from "./repositories/userPreferenceRepository";
import {
  applyPreferencesToRequirement,
  extractPreferencesFromText,
  hasPreferenceSignal
} from "./services/preferences/preferenceExtractor";
import { McpClient } from "./services/mcp/mcpClient";
import { normalizeLocationScope, resolveSearchBasePayload } from "./services/location/searchBaseResolver";
import { error, json, readJson } from "./utils/http";
import { getPublicAmapConfig } from "./config/llm";

function parseCitySource(value: unknown): CitySource | undefined {
  const text = String(value ?? "").trim();
  if (
    text === "user_explicit" ||
    text === "fallback_question"
  ) {
    return text;
  }
  return undefined;
}

function getPathname(request: Request): string {
  return new URL(request.url).pathname.replace(/\/+$/, "") || "/";
}

function matchSessionPath(
  pathname: string,
  suffix: string
): { sessionId: string } | null {
  const match = pathname.match(new RegExp(`^/sessions/([^/]+)${suffix}$`));
  if (!match) {
    return null;
  }
  return { sessionId: match[1] };
}

function parseLimit(request: Request): number {
  const raw = new URL(request.url).searchParams.get("limit");
  const parsed = raw ? Number(raw) : 50;
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return 50;
  }
  return Math.min(parsed, 100);
}

function parseRequirementResponse<T extends {
  structured_payload_json: string;
  interests_json: string | null;
  constraints_json: string | null;
}>(requirement: T): Record<string, unknown> {
  return {
    ...requirement,
    structured_payload: JSON.parse(requirement.structured_payload_json),
    interests: requirement.interests_json ? JSON.parse(requirement.interests_json) : [],
    constraints: requirement.constraints_json ? JSON.parse(requirement.constraints_json) : []
  };
}

function parseItineraryResponse<T extends {
  itinerary_json: string;
  budget_estimate_json: string | null;
  warnings_json: string | null;
}>(itinerary: T): Record<string, unknown> {
  return {
    ...itinerary,
    itinerary: JSON.parse(itinerary.itinerary_json),
    budget_estimate: itinerary.budget_estimate_json
      ? JSON.parse(itinerary.budget_estimate_json)
      : null,
    warnings: itinerary.warnings_json ? JSON.parse(itinerary.warnings_json) : []
  };
}

function parseMessageResponse<T extends {
  metadata_json: string | null;
}>(message: T): Record<string, unknown> {
  return {
    ...message,
    metadata: message.metadata_json ? JSON.parse(message.metadata_json) : null
  };
}

async function requireSession(
  sessionRepository: SessionRepository,
  sessionId: string
) {
  const session = await sessionRepository.getById(sessionId);
  if (!session) {
    throw new Error("session not found");
  }
  return session;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const pathname = getPathname(request);
    const sessionRepository = new SessionRepository(env.DB);
    const requirementRepository = new RequirementRepository(env.DB);
    const itineraryRepository = new ItineraryRepository(env.DB);
    const messageRepository = new MessageRepository(env.DB);
    const userPreferenceRepository = new UserPreferenceRepository(env.DB);

    try {
      if (request.method === "GET" && pathname === "/") {
        return json({
          service: "travel-agent-worker",
          status: "ok",
          date: "2026-04-20"
        });
      }

      if (request.method === "GET" && pathname === "/map/config") {
        return json(getPublicAmapConfig());
      }

      if (request.method === "POST" && pathname === "/map/search") {
        const body = await readJson<{
          keyword?: string;
          city?: string;
          location_scope?: string;
          city_source?: string;
          user_location?: { lng?: number; lat?: number };
        }>(request);
        const keyword = String(body?.keyword ?? "").trim();
        const resolvedPayload = await resolveSearchBasePayload({
          env,
          payload: {
            destination: String(body?.city ?? "").trim() || undefined,
            city_source: parseCitySource(body?.city_source),
            location_scope: normalizeLocationScope(body?.location_scope),
            user_location: body?.user_location
              ? {
                  lng: Number(body.user_location.lng),
                  lat: Number(body.user_location.lat)
                }
              : undefined
          }
        });
        const city = String(resolvedPayload.destination ?? "").trim() || undefined;
        const locationScope = normalizeLocationScope(resolvedPayload.location_scope);
        if (!keyword) {
          return error("keyword is required");
        }

        const client = new McpClient(env);
        const keywordVariants = Array.from(new Set([
          keyword,
          city && locationScope === "nearby" ? `${city}附近 ${keyword}` : "",
          city && locationScope === "surrounding" ? `${city}周边 ${keyword}` : "",
          city && locationScope === "surrounding" ? `${city}近郊 ${keyword}` : ""
        ].filter(Boolean)));
        const result = await Promise.any(
          keywordVariants.map((item) =>
            client.searchPOI(locationScope === "city_only" ? city : undefined, item, undefined)
          )
        ).catch(() => client.searchPOI(city, keyword, undefined));
        const items = Array.isArray(result.data) ? result.data : [];

        return json({
          keyword,
          city: city ?? null,
          location_scope: locationScope,
          city_source: resolvedPayload.city_source ?? null,
          items: items
            .filter((item) => item?.location)
            .slice(0, 20)
            .map((item) => ({
              id: item.id,
              name: item.name,
              city: item.city,
              district: item.district,
              address: item.address,
              category: item.category,
              location: item.location
            })),
          warnings: result.warnings
        });
      }

      if (request.method === "POST" && pathname === "/sessions") {
        const body = await readJson<CreateSessionInput>(request);
        const session = await sessionRepository.create(body ?? {});
        return json(session, 201);
      }

      const sessionDetail = matchSessionPath(pathname, "");
      if (request.method === "GET" && sessionDetail) {
        const session = await sessionRepository.getById(sessionDetail.sessionId);
        if (!session) {
          return error("session not found", 404);
        }
        const [latestRequirementId, latestItineraryId] = await Promise.all([
          requirementRepository.getLatestIdBySessionId(sessionDetail.sessionId),
          itineraryRepository.getLatestIdBySessionId(sessionDetail.sessionId)
        ]);

        return json({
          ...session,
          latest_requirement_id: latestRequirementId,
          latest_itinerary_id: latestItineraryId
        });
      }

      const requirementCreate = matchSessionPath(pathname, "/requirements");
      if (request.method === "POST" && requirementCreate) {
        await requireSession(sessionRepository, requirementCreate.sessionId);

        const body = await readJson<CreateRequirementInput>(request);
        if (!body?.raw_input) {
          return error("raw_input is required");
        }
        const session = await requireSession(
          sessionRepository,
          requirementCreate.sessionId
        );
        const preferenceOwner = resolvePreferenceOwner({
          sessionId: requirementCreate.sessionId,
          userId: session.user_id,
          visitorId: session.visitor_id
        });
        const extractedPreferences = extractPreferencesFromText(body.raw_input);
        if (hasPreferenceSignal(extractedPreferences)) {
          await userPreferenceRepository.upsert(preferenceOwner, extractedPreferences);
        }

        const interpreted = await interpretRequirement(
          env,
          body.raw_input,
          body.strategy,
          body.structured_payload
        );
        const requirement = await requirementRepository.create(
          requirementCreate.sessionId,
          {
            raw_input: body.raw_input,
            structured_payload: applyPreferencesToRequirement({
              requirement: interpreted.payload,
              preferences: await userPreferenceRepository.get(preferenceOwner),
              explicitInput: interpreted.payload
            })
          }
        );

        await sessionRepository.bumpRequirementVersion(
          requirementCreate.sessionId,
          requirement.version
        );

        return json(
          {
            ...parseRequirementResponse(requirement),
            missing_fields: interpreted.missing_fields,
            follow_up_questions: interpreted.follow_up_questions,
            interpretation_strategy: interpreted.strategy
          },
          201
        );
      }

      const requirementInterpret = matchSessionPath(pathname, "/requirements/interpret");
      if (request.method === "POST" && requirementInterpret) {
        await requireSession(sessionRepository, requirementInterpret.sessionId);

        const body = await readJson<CreateRequirementInput>(request);
        if (!body?.raw_input) {
          return error("raw_input is required");
        }

        const interpreted = await interpretRequirement(
          env,
          body.raw_input,
          body.strategy,
          body.structured_payload
        );

        return json(interpreted);
      }

      const requirementLatest = matchSessionPath(pathname, "/requirements/latest");
      if (request.method === "GET" && requirementLatest) {
        const requirement = await requirementRepository.getLatestBySessionId(
          requirementLatest.sessionId
        );
        if (!requirement) {
          return error("requirement not found", 404);
        }
        return json(parseRequirementResponse(requirement));
      }

      const itineraryCreate = matchSessionPath(pathname, "/itineraries");
      if (request.method === "POST" && itineraryCreate) {
        await requireSession(sessionRepository, itineraryCreate.sessionId);

        const body = await readJson<CreateItineraryInput>(request);
        const requirement = body?.requirement_id
          ? await requirementRepository.getById(body.requirement_id)
          : await requirementRepository.getLatestBySessionId(itineraryCreate.sessionId);

        if (!requirement) {
          return error("requirement not found", 404);
        }
        const session = await requireSession(
          sessionRepository,
          itineraryCreate.sessionId
        );
        const preferences = await userPreferenceRepository.get(
          resolvePreferenceOwner({
            sessionId: itineraryCreate.sessionId,
            userId: session.user_id,
            visitorId: session.visitor_id
          })
        );
        const requirementPayload = JSON.parse(
          requirement.structured_payload_json
        ) as StructuredPayload;
        const effectiveRequirement = {
          ...requirement,
          structured_payload_json: JSON.stringify(
            applyPreferencesToRequirement({
              requirement: requirementPayload,
              preferences,
              explicitInput: requirementPayload
            })
          )
        };

        const generatorType =
          body?.generator_type ?? getDefaultGeneratorType(env);
        const generated =
          generatorType === "template"
            ? await enhanceItineraryWithRoutePlan({
                result: enforceControlledItinerary({
                  result: {
                    ...generateTemplateItinerary(effectiveRequirement),
                    generatorType: "template" as const
                  },
                  requirement: JSON.parse(
                    effectiveRequirement.structured_payload_json
                  ) as StructuredPayload
                }),
                requirement: JSON.parse(effectiveRequirement.structured_payload_json) as StructuredPayload
              })
            : await generateAgentItinerary({
                env,
                requirement: effectiveRequirement,
                generatorType
              });

        const itinerary = await itineraryRepository.create({
          sessionId: itineraryCreate.sessionId,
          requirementId: requirement.id,
          title: generated.title,
          summary: generated.summary,
          itinerary: generated.itinerary,
          budgetEstimate: generated.budgetEstimate,
          warnings: generated.warnings,
          generatorType: generated.generatorType
        });

        await sessionRepository.bumpItineraryVersion(
          itineraryCreate.sessionId,
          itinerary.version
        );

        return json(
          parseItineraryResponse(itinerary),
          201
        );
      }

      const itineraryLatest = matchSessionPath(pathname, "/itineraries/latest");
      if (request.method === "GET" && itineraryLatest) {
        const itinerary = await itineraryRepository.getLatestBySessionId(
          itineraryLatest.sessionId
        );
        if (!itinerary) {
          return error("itinerary not found", 404);
        }
        return json(parseItineraryResponse(itinerary));
      }

      const latestRoutePlan = matchSessionPath(
        pathname,
        "/itineraries/latest/route-plan"
      );
      if (request.method === "GET" && latestRoutePlan) {
        const itinerary = await itineraryRepository.getLatestBySessionId(
          latestRoutePlan.sessionId
        );
        if (!itinerary) {
          return error("itinerary not found", 404);
        }

        const parsed = JSON.parse(itinerary.itinerary_json) as Record<string, unknown>;
        const routePlan = parsed.route_plan;
        if (!routePlan) {
          return error("route plan not found", 404);
        }

        return json({
          session_id: latestRoutePlan.sessionId,
          itinerary_id: itinerary.id,
          route_plan: routePlan
        });
      }

      const replanCreate = matchSessionPath(pathname, "/replan");
      if (request.method === "POST" && replanCreate) {
        await requireSession(sessionRepository, replanCreate.sessionId);

        const body = await readJson<ReplanInput>(request);
        if (!body?.instruction) {
          return error("instruction is required");
        }

        const requirement = body.requirement_id
          ? await requirementRepository.getById(body.requirement_id)
          : await requirementRepository.getLatestBySessionId(replanCreate.sessionId);
        if (!requirement) {
          return error("requirement not found", 404);
        }
        const session = await requireSession(sessionRepository, replanCreate.sessionId);
        const replanPreferences = await userPreferenceRepository.get(
          resolvePreferenceOwner({
            sessionId: replanCreate.sessionId,
            userId: session.user_id,
            visitorId: session.visitor_id
          })
        );
        const explicitReplanPayload = JSON.parse(
          requirement.structured_payload_json
        ) as StructuredPayload;
        const effectiveRequirement = {
          ...requirement,
          structured_payload_json: JSON.stringify(
            applyPreferencesToRequirement({
              requirement: explicitReplanPayload,
              preferences: replanPreferences,
              explicitInput: explicitReplanPayload
            })
          )
        };

        const existingItinerary = body.itinerary_id
          ? await itineraryRepository.getById(body.itinerary_id)
          : await itineraryRepository.getLatestBySessionId(replanCreate.sessionId);

        const replanned = await replanItinerary({
          env,
          requirement: effectiveRequirement,
          existingItinerary,
          instruction: body.instruction,
          generatorType: body.generator_type ?? "agent"
        });

        const itinerary = await itineraryRepository.create({
          sessionId: replanCreate.sessionId,
          requirementId: requirement.id,
          title: replanned.title,
          summary: replanned.summary,
          itinerary: replanned.itinerary,
          budgetEstimate: replanned.budgetEstimate,
          warnings: replanned.warnings,
          generatorType: replanned.generatorType
        });

        await sessionRepository.bumpItineraryVersion(
          replanCreate.sessionId,
          itinerary.version
        );

        return json(parseItineraryResponse(itinerary), 201);
      }

      const chatCreate = matchSessionPath(pathname, "/chat");
      if (request.method === "POST" && chatCreate) {
        await requireSession(sessionRepository, chatCreate.sessionId);

        const body = await readJson<ChatInput>(request);
        if (!body?.message) {
          return error("message is required");
        }

        const result = await handleChatMessage({
          env,
          sessionId: chatCreate.sessionId,
          input: body
        });
        const parsedItinerary = result.itinerary
          ? parseItineraryResponse(result.itinerary)
          : null;
        const itineraryPayload = parsedItinerary?.itinerary as Record<string, unknown> | undefined;
        const mapData =
          result.plannerOutput?.mapData ??
          (itineraryPayload?.mapData as unknown) ??
          null;
        const routeSegments =
          result.plannerOutput?.mapData.polylines ??
          ((mapData as { polylines?: unknown[] } | null)?.polylines ?? []);
        const resolvedPlaces = result.plannerOutput?.itinerary.days.flatMap((day) =>
          day.items.map((item) => ({
            day: day.day,
            order: item.order,
            id: item.candidateId,
            name: item.name,
            category: item.category,
            address: item.address,
            location: item.location,
            source: item.source
          }))
        ) ?? [];

        return json({
          action: result.action,
          user_message: parseMessageResponse(result.userMessage),
          assistant_message: parseMessageResponse(result.assistantMessage),
          requirement: result.requirement
            ? parseRequirementResponse(result.requirement)
            : null,
          effective_requirement: result.requirement
            ? parseRequirementResponse(result.requirement)
            : null,
          effective_replan_directives: result.requirement
            ? (parseRequirementResponse(result.requirement).structured_payload as StructuredPayload).replan_directives ?? null
            : null,
          applied_changes_summary: result.requirement
            ? ((parseRequirementResponse(result.requirement).structured_payload as StructuredPayload).replan_directives
                ? ((parseRequirementResponse(result.requirement).structured_payload as StructuredPayload).replan_directives?.source_message
                  ? [String((parseRequirementResponse(result.requirement).structured_payload as StructuredPayload).replan_directives?.source_message)]
                  : [])
                : [])
            : [],
          itinerary: parsedItinerary,
          resolvedPlaces,
          queryTasks: result.candidatePool?.queryTasks ?? [],
          mapData,
          routeSegments,
          assistantMessage: result.assistantMessage.content,
          missing_fields: result.missingFields,
          follow_up_questions: result.followUpQuestions,
          candidate_pool: result.candidatePool ?? null,
          planner_output: result.plannerOutput ?? null,
          messages: result.recentMessages.map(parseMessageResponse)
        });
      }

      const messageCreate = matchSessionPath(pathname, "/messages");
      if (request.method === "POST" && messageCreate) {
        await requireSession(sessionRepository, messageCreate.sessionId);

        const body = await readJson<CreateMessageInput>(request);
        if (!body?.role || !body?.content) {
          return error("role and content are required");
        }

        const message = await messageRepository.create(messageCreate.sessionId, body);
        return json(parseMessageResponse(message), 201);
      }

      const messageList = matchSessionPath(pathname, "/messages");
      if (request.method === "GET" && messageList) {
        await requireSession(sessionRepository, messageList.sessionId);

        const messages = await messageRepository.listBySessionId(
          messageList.sessionId,
          parseLimit(request)
        );

        return json({
          session_id: messageList.sessionId,
          items: messages.map(parseMessageResponse)
        });
      }

      return error("not found", 404);
    } catch (cause) {
      const message =
        cause instanceof Error ? cause.message : "unexpected internal error";
      if (message === "session not found") {
        return error(message, 404);
      }
      return error(message, 500);
    }
  }
};

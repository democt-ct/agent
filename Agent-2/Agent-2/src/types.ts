export interface Env {
  DB: D1Database;
  AMAP_WEB_SERVICE_KEY?: string;
  AMAP_WEB_SERVICEKEY?: string;
  webServiceKey?: string;
}

export interface GeoPoint {
  lng: number;
  lat: number;
}

export type PlaceZoneTag = "urban_core" | "urban_edge" | "nearby_nature";
export type PlaceCategory =
  | "landmark"
  | "food"
  | "cafe"
  | "mall"
  | "park"
  | "citywalk"
  | "nightview"
  | "nature"
  | "museum";

export type PlannerProfileId =
  | "light_comfort"
  | "classic_must_visit"
  | "food_first"
  | "deep_local"
  | "high_intensity"
  | "family_friendly";

export interface PreferenceParams {
  fatigue_tolerance: "very_low" | "low" | "medium" | "high";
  food_priority: "low" | "medium" | "high";
  famous_spot_priority: "low" | "medium" | "high";
  hidden_gem_priority: "low" | "medium" | "high";
  allow_food_transfer: boolean;
  max_major_transfers_per_day: number;
  schedule_density: "low" | "low_to_medium" | "medium" | "high";
  walking_preference?: "low" | "medium" | "high";
}

export interface ResolvedPreferenceProfile {
  primary_profile: PlannerProfileId;
  secondary_profile: PlannerProfileId;
  preference_params: PreferenceParams;
  reason: string;
}

export interface DayScheduleSlot {
  slot: "morning" | "lunch" | "afternoon" | "evening";
  timeLabel: string;
  role: "main_activity" | "meal" | "relax" | "night";
  categories: PlaceCategory[];
}

export interface PlaceCandidatePoolItem {
  id: string;
  name: string;
  city: string;
  zone: PlaceZoneTag;
  poolTier?: "base" | "extended";
  category: PlaceCategory;
  location: GeoPoint;
  suggestedDurationMinutes: number;
  tags: string[];
}

export type CandidateSource = "content_search" | "mcp_search" | "mcp_poi" | "static_pool" | "llm_curator";
export type PlannerCategory = "scenic" | "food" | "walk" | "food_walk" | "supplemental";
export type PoiGranularity =
  | "city_level"
  | "attraction_level"
  | "district_level"
  | "food_level"
  | "internal_poi_level"
  | "service_level";
export type PlanningMode = "city_trip" | "attraction_internal_route";

export interface GroundingTaskDiagnostic {
  taskName: string;
  primarySelected: string[];
  parentInferred: string[];
  internalSubStopsCount: number;
  merchantAliasRejectedCount: number;
  keptAsMainCount: number;
  linkedNightViewTarget?: string;
  mergedAliases: string[];
}

export interface CandidateGovernanceSummary {
  planningMode: PlanningMode;
  containsInternalPoiInDayItems?: boolean;
  containsServiceLevelInDayItems?: boolean;
  dailyMainItemCounts?: Array<{ day: number; count: number }>;
  subStopsCount?: number;
  hasLinkedNightView?: boolean;
  hasFoodWalkMerge?: boolean;
}

export interface CandidatePlace {
  id: string;
  name: string;
  city: string;
  category: PlaceCategory;
  plannerCategory?: PlannerCategory;
  location?: GeoPoint;
  address?: string;
  source: CandidateSource;
  sourceRef?: string;
  tags: string[];
  description?: string;
  suggestedDurationMinutes: number;
  confidence: number;
  candidateTier?: string;
  candidate_tier?: string;
  groundingConfidence?: number;
  grounding_confidence?: number;
  classicnessScore?: number;
  classicness_score?: number;
  eligibleForMainItinerary?: boolean;
  eligible_for_main_itinerary?: boolean;
  qualityFlags?: Record<string, unknown>;
  quality_flags?: Record<string, unknown>;
  citySignatureScore?: number;
  userPreferenceScore?: number;
  qualityScore?: number;
  objectiveQualityScore?: number;
  routeFitScore?: number;
  distanceScore?: number;
  finalScore?: number;
  amapRating?: number;
  amapReviewCount?: number;
  coreRecommendation?: "core" | "backup" | "meal_stop" | "transport" | "remove";
  granularity?: PoiGranularity;
  planningMode?: PlanningMode;
  subStops?: string[];
  roles?: string[];
  linkedPoiId?: string;
  nightView?: boolean;
  role?: string;
  warning?: string;
  sourceOrigin?: string;
  parentName?: string;
  mergedAliases?: string[];
  queryCategories?: PlaceCategory[];
}

export type McpToolName =
  | "web_search"
  | "poi_search"
  | "route_plan"
  | "weather"
  | "place_details";

export interface McpToolResult<T = unknown> {
  tool: McpToolName;
  query: Record<string, unknown>;
  data: T;
  source: string;
  fetchedAt: string;
  confidence: number;
  warnings: string[];
}

export interface CandidateQueryTask {
  tool: "searchPOI" | "searchWeb";
  city: string;
  keyword: string;
  category?: PlaceCategory;
  sourceInterest?: string;
  priority?: number;
  plannedMinResults?: number;
  plannedMaxResults?: number;
  rationale?: string;
  status?: "pending" | "ok" | "failed";
  resultCount?: number;
  warnings?: string[];
}

export interface CandidateQueryPlanItem {
  category: PlaceCategory;
  keywords: string[];
  priority: number;
  minResults: number;
  maxResults: number;
  rationale?: string;
}

export interface CandidateQueryPlan {
  destination: string;
  summary: string;
  categories: CandidateQueryPlanItem[];
  generalKeywords: string[];
  avoidCategories: PlaceCategory[];
}

export interface CandidateSelectionHint {
  preferredCandidateIds: string[];
  avoidCandidateIds: string[];
  preferredCategories: PlaceCategory[];
  notes: string[];
}

export interface ContentSignal {
  id: string;
  source: "web_search";
  city: string;
  query: string;
  title: string;
  snippet?: string;
  url?: string;
  extractedPlaceNames: string[];
  sceneTags: string[];
  styleTags: string[];
  categoryHints: PlaceCategory[];
  confidence: number;
}

export interface CandidatePool {
  destination: string;
  candidates: CandidatePlace[];
  discoveryCandidates?: Array<{
    name: string;
    category: PlaceCategory;
    source: "web_signal" | "generic_poi" | "signature_seed";
    confidence: number;
    query?: string;
  }>;
  toolResults: McpToolResult[];
  queryTasks: CandidateQueryTask[];
  queryPlan?: CandidateQueryPlan;
  selectionHints?: CandidateSelectionHint;
  contentSignals?: ContentSignal[];
  preferenceProfile?: ResolvedPreferenceProfile;
  citySignatureSeed?: CitySignatureSeed;
  citySignaturePool?: CitySignaturePool;
  coverageCheck?: CoverageCheckResult;
  planningMode?: PlanningMode;
  groundingDiagnostics?: GroundingTaskDiagnostic[];
  governanceSummary?: CandidateGovernanceSummary;
  warnings: string[];
}

export type PlannerTimeSlot = "morning" | "lunch" | "afternoon" | "evening";

export interface ReplanGlobalDirectives {
  preferred_pace?: PreferredPace;
  distance_tolerance?: DistanceTolerance;
  preferred_categories?: PlaceCategory[];
  avoid_categories?: PlaceCategory[];
  reduce_transfers?: boolean;
  prefer_nearby?: boolean;
  note?: string;
}

export interface DayOverride {
  day: number;
  slot?: PlannerTimeSlot;
  preferred_categories?: PlaceCategory[];
  avoid_categories?: PlaceCategory[];
  preferred_pace?: PreferredPace;
  note?: string;
}

export interface ReplaceTarget {
  day?: number;
  slot?: PlannerTimeSlot;
  from_categories?: PlaceCategory[];
  to_categories?: PlaceCategory[];
  note?: string;
}

export interface ReplanDirectives {
  global?: ReplanGlobalDirectives;
  day_overrides?: DayOverride[];
  replace_targets?: ReplaceTarget[];
  source_message?: string;
}

export type DaySlotStrategy =
  | "anchor_cluster"
  | "single_anchor"
  | "food_cluster"
  | "meal_stop"
  | "leisure_cluster"
  | "night_cluster"
  | "shopping_cluster"
  | "fallback";

export type DaySegmentType =
  | "sightseeing"
  | "food"
  | "leisure"
  | "night"
  | "shopping"
  | "rest"
  | "transfer";

export interface DaySlotPlan {
  slot: PlannerTimeSlot;
  strategy: DaySlotStrategy;
  segmentType?: DaySegmentType;
  clusterId?: string;
  clusterType?: string;
  candidateIds: string[];
  rationale: string;
  transferReason?: string;
  transferDistanceMeters?: number;
}

export interface PlannedItem {
  candidateId: string;
  name: string;
  category: PlaceCategory;
  day: number;
  order: number;
  timeSlot: PlannerTimeSlot;
  reason: string;
  location?: GeoPoint;
  address?: string;
  durationMinutes: number;
  source: CandidateSource;
  score: number;
  granularity?: PoiGranularity;
  subStops?: string[];
  roles?: string[];
  linkedPoiId?: string;
  nightView?: boolean;
  role?: string;
}

export interface PlannedDay {
  day: number;
  theme: string;
  items: PlannedItem[];
  segments?: DaySlotPlan[];
  totalFatigueScore?: number;
  totalTransferDistanceMeters?: number;
  notes?: string[];
}

export interface PlannerInput {
  requirement: StructuredPayload;
  candidatePool: CandidatePool;
  existingItinerary?: ItineraryDraft | null;
  instruction?: string;
}

export interface PlannerMapData {
  markers: Array<{
    id: string;
    day: number;
    order: number;
    name: string;
    category: PlaceCategory;
    location: GeoPoint;
  }>;
  polylines: RouteSegment[];
  layers: Array<{
    day: number;
    markerIds: string[];
    polylineIds: string[];
  }>;
  center?: GeoPoint;
}

export interface PlannerOutput {
  itinerary: {
    days: PlannedDay[];
  };
  mapData: PlannerMapData;
  warnings: string[];
  sourceRefs: string[];
  preferenceProfile?: ResolvedPreferenceProfile;
  citySignatureSeed?: CitySignatureSeed;
  citySignaturePool?: CitySignaturePool;
  coverageCheck?: CoverageCheckResult;
  routeValidation?: RouteValidationResult;
  notSelectedSignatureItems?: SignaturePoolItemSummary[];
  governanceSummary?: CandidateGovernanceSummary;
}

export interface SignaturePoolItemSummary {
  name: string;
  type: string;
  city_signature_score: number;
  suggested_role:
    | "anchor"
    | "single_anchor"
    | "backup_day_trip"
    | "meal_stop"
    | "food_cluster"
    | "night_cluster"
    | "leisure_cluster"
    | "shopping_cluster"
    | "backup";
  reason: string;
  candidateId?: string;
}

export interface CitySignaturePool {
  must_visit_attractions: SignaturePoolItemSummary[];
  famous_foods: SignaturePoolItemSummary[];
  food_signatures: SignaturePoolItemSummary[];
  food_areas: SignaturePoolItemSummary[];
  shopping_areas: SignaturePoolItemSummary[];
  night_options: SignaturePoolItemSummary[];
  local_experiences: SignaturePoolItemSummary[];
  backup_day_trips: SignaturePoolItemSummary[];
  avoid_as_core: SignaturePoolItemSummary[];
}

export interface CitySignatureSeedItem {
  name: string;
  category: PlaceCategory;
  reason: string;
  confidence: number;
  source: "llm_prior" | "heuristic_prior";
}

export interface CitySignatureSeed {
  destination: string;
  must_visit_attractions: CitySignatureSeedItem[];
  famous_foods: CitySignatureSeedItem[];
  food_areas: CitySignatureSeedItem[];
  shopping_areas: CitySignatureSeedItem[];
  night_options: CitySignatureSeedItem[];
  local_experiences: CitySignatureSeedItem[];
  backup_day_trips: CitySignatureSeedItem[];
}

export interface CoverageCheckResult {
  ok: boolean;
  has_enough_must_visit: boolean;
  has_famous_food_or_food_area: boolean;
  has_night_option: boolean;
  has_local_experience: boolean;
  missing_items: string[];
  coverage_summary: Record<string, number | boolean>;
  repair_actions: string[];
}

export interface CorePoiDecision {
  can_be_core: boolean;
  reason: string;
  suggested_role: "core" | "backup" | "meal_stop" | "transport" | "remove";
}

export interface OutlierHandlingResult {
  action: "remove" | "keep" | "convert_to_meal_stop" | "reassign_cluster" | "backup";
  target_cluster_id: string | null;
  reason: string;
}

export interface RouteValidationIssue {
  name: string;
  problem: string;
  action: "remove" | "replace" | "convert_to_backup" | "convert_to_meal_stop" | "reassign_to_cluster";
}

export interface RouteValidationResult {
  is_valid: boolean;
  main_problems: string[];
  low_quality_items: RouteValidationIssue[];
  missing_city_signature_items: string[];
  weak_anchor_days?: number[];
  skipped_slots?: Array<{
    day: number;
    slot: string;
    reason: string;
  }>;
  route_fatigue_assessment: string;
  food_strategy_assessment: string;
  repair_suggestions: string[];
  repaired_day_structure: Array<{
    day: number;
    theme: string;
    segment_summary: string[];
  }>;
  granularity_audit?: CandidateGovernanceSummary;
}

export interface ItineraryPlaceCandidate {
  day: number;
  order: number;
  name: string;
  city?: string;
  typeHint?: string;
  time?: string;
  note?: string;
}

export interface ConfirmedItineraryPlace extends ItineraryPlaceCandidate {
  status: "confirmed";
  id: string;
  address: string;
  location: GeoPoint;
  amapPoiId?: string;
  amapType?: string;
  confidence: number;
  scoreBreakdown: SpotScoreBreakdown;
}

export interface SpotScoreBreakdown {
  name: number;
  city: number;
  type: number;
  distance: number;
  total: number;
}

export interface ResolvedSpotCandidate {
  amapPoiId?: string;
  name: string;
  city: string;
  district?: string;
  address: string;
  location: GeoPoint;
  amapType?: string;
  confidence: number;
  scoreBreakdown: SpotScoreBreakdown;
}

export interface RejectedItineraryPlace extends ItineraryPlaceCandidate {
  status: "ambiguous" | "unresolved";
  reason: string;
  candidates?: ResolvedSpotCandidate[];
}

export interface RouteSegment {
  fromPlaceId: string;
  toPlaceId: string;
  distanceMeters: number | null;
  durationSeconds: number | null;
  polyline: GeoPoint[];
  provider: "amap";
  mode: "walking" | "driving" | "straight";
}

export interface ItineraryRoutePlan {
  status: "ready" | "partial" | "skipped";
  provider: "amap";
  candidates: ItineraryPlaceCandidate[];
  confirmed_points: ConfirmedItineraryPlace[];
  rejected_candidates: RejectedItineraryPlace[];
  sorted_place_ids: string[];
  segments: RouteSegment[];
  polyline: GeoPoint[];
  warnings: string[];
}

export interface Session {
  id: string;
  user_id: string | null;
  visitor_id: string | null;
  title: string;
  status: string;
  source: string;
  current_requirement_version: number;
  current_itinerary_version: number;
  created_at: string;
  updated_at: string;
}

export type PreferenceOwnerType = "user" | "visitor" | "session";
export type PreferredPace = "relaxed" | "moderate" | "compact";
export type DistanceTolerance = "urban_only" | "nearby_ok" | "flexible";
export type LocationScope = "city_only" | "surrounding" | "nearby";
export type CitySource =
  | "user_explicit"
  | "fallback_question";

export interface UserPreferencePayload {
  preferredPace?: PreferredPace;
  interests?: string[];
  distanceTolerance?: DistanceTolerance;
}

export interface UserPreferenceRecord {
  id: string;
  owner_type: PreferenceOwnerType;
  owner_id: string;
  preferred_pace: PreferredPace | null;
  interests_json: string | null;
  distance_tolerance: DistanceTolerance | null;
  source: string;
  confidence: number;
  updated_at: string;
  created_at: string;
}

export interface UserPreferenceContext extends UserPreferencePayload {
  source?: string;
  confidence?: number;
}

export interface TripRequirement {
  id: string;
  session_id: string;
  version: number;
  raw_input: string;
  origin_city: string | null;
  destination: string | null;
  start_date: string | null;
  end_date: string | null;
  trip_days: number | null;
  budget_min: number | null;
  budget_max: number | null;
  travelers_summary: string | null;
  interests_json: string | null;
  constraints_json: string | null;
  structured_payload_json: string;
  created_at: string;
}

export interface ItineraryDraft {
  id: string;
  session_id: string;
  requirement_id: string;
  version: number;
  status: string;
  title: string;
  summary: string | null;
  itinerary_json: string;
  budget_estimate_json: string | null;
  warnings_json: string | null;
  generator_type: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessage {
  id: string;
  session_id: string;
  role: string;
  message_type: string;
  content: string;
  metadata_json: string | null;
  created_at: string;
}

export interface CreateSessionInput {
  user_id?: string;
  visitor_id?: string;
  title?: string;
  source?: string;
}

export interface StructuredPayload {
  origin_city?: string;
  // Search base city, not a geographic center point.
  destination?: string;
  destination_hint?: string;
  start_date?: string;
  end_date?: string;
  trip_days?: number;
  budget_min?: number;
  budget_max?: number;
  travelers_summary?: string;
  interests?: string[];
  constraints?: string[];
  user_preferences?: UserPreferencePayload & {
    resolved_profile?: ResolvedPreferenceProfile;
  };
  location_scope?: LocationScope;
  city_source?: CitySource;
  user_location?: GeoPoint;
  replan_directives?: ReplanDirectives;
  enable_city_static_pool?: boolean;
  _destination_needs_confirmation?: boolean;
  [key: string]: unknown;
}

export interface CreateRequirementInput {
  raw_input: string;
  structured_payload?: StructuredPayload;
  strategy?: "rule" | "llm";
}

export interface CreateItineraryInput {
  requirement_id?: string;
  generator_type?: "template" | "llm" | "agent";
}

export interface CreateMessageInput {
  role: string;
  message_type?: string;
  content: string;
  metadata?: Record<string, unknown>;
}

export interface ChatInput {
  message: string;
  strategy?: "rule" | "llm";
  generator_type?: "template" | "llm" | "agent";
  user_location?: GeoPoint;
}

export type ConversationAction =
  | "collect_requirement"
  | "generate_itinerary"
  | "replan_itinerary";

export interface ReplanInput {
  instruction: string;
  requirement_id?: string;
  itinerary_id?: string;
  generator_type?: "llm" | "agent";
}

export interface RequirementInterpretationResult {
  payload: StructuredPayload;
  missing_fields: string[];
  follow_up_questions: string[];
  strategy: "rule" | "llm";
}

export interface ItineraryGenerationResult {
  title: string;
  summary: string;
  itinerary: Record<string, unknown>;
  budgetEstimate: Record<string, unknown> | null;
  warnings: string[];
  generatorType: "template" | "llm" | "agent";
}

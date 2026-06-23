from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    lng: float
    lat: float


class SessionCreate(BaseModel):
    title: str = "??????"


class RequirementCreate(BaseModel):
    raw_input: str
    strategy: str = "llm"
    structured_payload: Optional[Dict[str, Any]] = None


class ItineraryCreate(BaseModel):
    requirement_id: Optional[str] = None
    generator_type: str = "agent"


class ReplanCreate(BaseModel):
    instruction: str
    requirement_id: Optional[str] = None
    itinerary_id: Optional[str] = None
    generator_type: str = "agent"


class MessageCreate(BaseModel):
    role: str
    message_type: str = "text"
    content: str
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    session_title: Optional[str] = None
    conversation_context: Optional[str] = None


class MapSearchRequest(BaseModel):
    keyword: str
    city: Optional[str] = None
    category: Optional[str] = None
    location_scope: Optional[str] = None
    city_source: Optional[str] = None
    search_mode: Optional[str] = None
    region_name: Optional[str] = None
    radius_meters: int = 3000
    limit: int = 25
    user_location: Optional[Dict[str, Any]] = None
    anchor_location: Optional[Dict[str, Any]] = None


class RequirementInterpretRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    context: Optional[Dict[str, Any]] = None


class PoiResolveRequest(BaseModel):
    city: Optional[str] = None
    keyword: str
    category_hint: Optional[str] = None
    anchor_location: Optional[GeoPoint] = None
    radius_meters: int = 3000
    limit: int = 8


class PlannerPlaceCandidatesRequest(BaseModel):
    session_id: Optional[str] = None
    day_index: int
    slot: str
    query: str
    intent_type: str = "generic_poi"
    city: Optional[str] = None
    category_hint: Optional[str] = None
    anchor_location: Optional[GeoPoint] = None
    limit: int = 5


class PoiPlaceCandidate(BaseModel):
    poi_id: Optional[str] = None
    name: str
    location: GeoPoint
    address: Optional[str] = None
    category: Optional[str] = None
    resolve_note: Optional[str] = None
    anchor_keyword: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    source: Optional[str] = None
    place_kind: Optional[str] = None
    route_role: Optional[str] = None
    validation_status: Optional[str] = None
    parent_poi_id: Optional[str] = None
    parent_poi_name: Optional[str] = None
    is_primary_poi: Optional[bool] = None
    child_poi_type: Optional[str] = None
    time_slot: Optional[str] = None
    why_here: Optional[str] = None


class PlannerMemoryProfile(BaseModel):
    schema_version: str = "memory_profile_v1"
    short_term: Dict[str, Any] = Field(default_factory=dict)
    long_term: Dict[str, Any] = Field(default_factory=dict)


class PlannerRequirementV2(BaseModel):
    schema_version: str = "planner_v2"
    city: str
    day_count: Optional[int] = None
    theme: str = "general"
    trip_style: str = "moderate"
    time_budget: str = "flexible"
    radius_meters: int = 5000
    location_scope: str = "city_only"
    hotel_location: Optional[str] = None
    must_have: List[str] = Field(default_factory=list)
    avoid: List[str] = Field(default_factory=list)
    anchor_location: Optional[GeoPoint] = None
    memory_profile: Optional[PlannerMemoryProfile] = None


class PlannerCandidateRecallItem(BaseModel):
    candidate_name: str
    kind: str
    reason: Optional[str] = None
    preferred_slots: List[str] = Field(default_factory=list)
    backup_queries: List[str] = Field(default_factory=list)


class PlannerCandidateRecallResult(BaseModel):
    schema_version: str = "planner_v2"
    status: str = "ok"
    assumptions: Optional[str] = None
    candidates: List[PlannerCandidateRecallItem] = Field(default_factory=list)
    backup_candidates: List[str] = Field(default_factory=list)


class PlannerValidatorCheck(BaseModel):
    code: str
    severity: str
    status: str
    message: str
    day_index: Optional[int] = None
    slot: Optional[str] = None
    poi_id: Optional[str] = None


class PlannerRepairAction(BaseModel):
    action: str
    message: str
    day_index: Optional[int] = None
    poi_id: Optional[str] = None


class PlannerValidatorResult(BaseModel):
    schema_version: str = "planner_v2"
    status: str = "ok"
    checks: List[PlannerValidatorCheck] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    repairs: List[PlannerRepairAction] = Field(default_factory=list)


class PlannerPlaceSelectRequest(BaseModel):
    session_id: str
    day_index: int
    slot: str
    query: str
    place: PoiPlaceCandidate
    direct_add: bool = False


class PlannerItineraryReorderRequest(BaseModel):
    session_id: str
    day_index: int
    ordered_poi_ids: list[str]


class PlannerItineraryPlaceRemoveRequest(BaseModel):
    session_id: str
    day_index: int
    slot: Optional[str] = None
    poi_id: Optional[str] = None
    place_name: Optional[str] = None
    query: Optional[str] = None


class PoiValidateRequest(BaseModel):
    city: Optional[str] = None
    anchor_location: GeoPoint
    places: list[PoiPlaceCandidate]
    max_distance_meters: int = 5000


class RoutePlanRequest(BaseModel):
    start: GeoPoint
    points: list[PoiPlaceCandidate]
    mode: str = "walk"


class UserPlaceNoteCreateRequest(BaseModel):
    city: Optional[str] = None
    query: str
    place_name: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    comment: Optional[str] = None
    poi: Optional[Dict[str, Any]] = None

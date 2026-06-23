import importlib
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from models.schemas import (
    ChatRequest,
    ItineraryCreate,
    MapSearchRequest,
    MessageCreate,
    PlannerItineraryPlaceRemoveRequest,
    PlannerItineraryReorderRequest,
    PlannerPlaceCandidatesRequest,
    PlannerPlaceSelectRequest,
    PoiResolveRequest,
    PoiValidateRequest,
    ReplanCreate,
    RequirementInterpretRequest,
    RequirementCreate,
    RoutePlanRequest,
    SessionCreate,
    UserPlaceNoteCreateRequest,
)

router = APIRouter()


def _legacy():
    return importlib.import_module("core")


@router.get(
    "/health",
    summary="Health Check / 健康检查",
    description="Return a simple health status for the FastAPI backend. 返回后端健康状态。"
)
def health() -> Dict[str, str]:
    return _legacy().health()


@router.get(
    "/map/config",
    summary="Map Config / 地图配置",
    description="Return map-related configuration used by the UI. 返回前端地图使用的配置。"
)
def map_config() -> Dict[str, Any]:
    return _legacy().map_config()


@router.post(
    "/map/search",
    summary="Map Search / 地图搜索",
    description="Search AMap POI around a city or nearby anchor. 返回高德 POI 搜索结果。",
)
async def map_search(body: MapSearchRequest) -> Dict[str, Any]:
    return await _legacy().map_search(body)


@router.post(
    "/api/planner/requirement/interpret",
    summary="Interpret Requirement / 解析规划需求",
    description="Interpret a raw travel-location planning request into structured intent."
)
async def api_requirement_interpret(body: RequirementInterpretRequest) -> Dict[str, Any]:
    return await _legacy().api_requirement_interpret(body)


@router.post(
    "/api/planner/place-candidates",
    summary="Planner Place Candidates / 泛需求地点候选",
    description="Search AMap POI candidates for generic place intents such as cafes or malls."
)
async def api_planner_place_candidates(body: PlannerPlaceCandidatesRequest) -> Dict[str, Any]:
    return await _legacy().api_planner_place_candidates(body)


@router.post(
    "/api/planner/itinerary/place-select",
    summary="Planner Place Select / 选择地点写回行程",
    description="Persist a user-selected POI into the current itinerary slot."
)
async def api_planner_itinerary_place_select(body: PlannerPlaceSelectRequest) -> Dict[str, Any]:
    return await _legacy().api_planner_itinerary_place_select(body)


@router.post(
    "/api/planner/itinerary/reorder",
    summary="Planner Itinerary Reorder / 琛岀▼椤哄簭璋冩暣",
    description="Persist the visible POI order for a given itinerary day."
)
async def api_planner_itinerary_reorder(body: PlannerItineraryReorderRequest) -> Dict[str, Any]:
    return await _legacy().api_planner_itinerary_reorder(body)


@router.post(
    "/api/planner/itinerary/place-remove",
    summary="Planner Place Remove / 删除行程地点",
    description="Remove a selected POI from the current itinerary."
)
async def api_planner_itinerary_place_remove(body: PlannerItineraryPlaceRemoveRequest) -> Dict[str, Any]:
    return await _legacy().api_planner_itinerary_place_remove(body)


@router.get(
    "/api/map/config",
    summary="Map Config API / 地图配置",
    description="Return map-related browser and service config."
)
def api_map_config() -> Dict[str, Any]:
    return _legacy().map_config()


@router.post(
    "/api/map/poi/search",
    summary="POI Search API / POI 搜索",
    description="Search AMap POI by nearby or region mode."
)
async def api_poi_search(body: MapSearchRequest) -> Dict[str, Any]:
    return await _legacy().map_search(body)


@router.post(
    "/api/map/poi/resolve",
    summary="POI Resolve API / POI 解析",
    description="Resolve a candidate place name to a normalized AMap POI."
)
async def api_poi_resolve(body: PoiResolveRequest) -> Dict[str, Any]:
    return await _legacy().api_poi_resolve(body)


@router.post(
    "/api/map/poi/validate",
    summary="POI Validate API / POI 校验",
    description="Validate whether places remain within an acceptable anchor radius."
)
async def api_poi_validate(body: PoiValidateRequest) -> Dict[str, Any]:
    return await _legacy().api_poi_validate(body)


@router.post(
    "/api/map/route/plan",
    summary="Route Plan API / 路线规划",
    description="Plan route segments between a start point and ordered POIs."
)
async def api_route_plan(body: RoutePlanRequest) -> Dict[str, Any]:
    return await _legacy().api_route_plan(body)


@router.post(
    "/tools/web-context",
    summary="Preview Web Context / 预览网页上下文",
    description="Collect and preview web context for debugging travel requests. 收集并预览网页上下文，便于调试旅行请求。"
)
async def preview_web_context(body: ChatRequest) -> Dict[str, Any]:
    return await _legacy().preview_web_context(body)


@router.get(
    "/debug",
    summary="Debug UI / 调试界面",
    description="Serve the debug pipeline inspector page. 返回调试管线检查界面。"
)
def debug_ui() -> FileResponse:
    return _legacy().debug_ui()


@router.get(
    "/api/debug/pipeline/{session_id}",
    summary="Debug Pipeline Data / 调试管线数据",
    description="Return pipeline debug data for a session: requirement, LLM recall, POI grounding, reflexion log. 返回会话的完整管线调试数据。"
)
def debug_pipeline(session_id: str) -> Dict[str, Any]:
    return _legacy().debug_pipeline_data(session_id)


@router.get(
    "/",
    summary="App UI / 应用界面",
    description="Serve the main chat and planning UI. 返回主聊天与规划界面。"
)
def app_ui() -> FileResponse:
    return _legacy().app_ui()


@router.post(
    "/chat",
    summary="Chat / 聊天",
    description="Send a chat message and receive the assistant response. 发送聊天消息并获取助手回复。"
)
async def chat(body: ChatRequest) -> Dict[str, Any]:
    return await _legacy().chat(body)


@router.post(
    "/sessions",
    summary="Create Session / 创建会话",
    description="Create a new travel-planning session. 创建一个新的旅行规划会话。"
)
def create_session(body: SessionCreate) -> Dict[str, Any]:
    return _legacy().create_session(body)


@router.get(
    "/sessions/{session_id}",
    summary="Get Session / 获取会话",
    description="Fetch a session by its ID. 根据会话 ID 获取会话。"
)
def get_session(session_id: str) -> Dict[str, Any]:
    return _legacy().get_session(session_id)


@router.get(
    "/sessions",
    summary="List Sessions / 列出会话",
    description="List recent sessions for the UI. 列出最近会话供前端展示。"
)
def list_sessions(request: Request) -> Dict[str, Any]:
    return _legacy().list_sessions(request)


@router.delete(
    "/sessions/{session_id}",
    summary="Delete Session / 删除会话",
    description="Delete a session and its messages. 删除会话及其消息。"
)
def delete_session(session_id: str) -> Dict[str, Any]:
    return _legacy().delete_session(session_id)


@router.post(
    "/sessions/{session_id}/requirements",
    summary="Create Requirement / 创建需求",
    description="Store a new requirement for the session. 为会话保存新的旅行需求。"
)
async def create_requirement(session_id: str, body: RequirementCreate) -> Dict[str, Any]:
    return await _legacy().create_requirement(session_id, body)


@router.post(
    "/sessions/{session_id}/requirements/interpret",
    summary="Preview Requirement Interpretation / 预览需求解析",
    description="Preview how the backend interprets a raw requirement. 预览后端如何解析原始需求。"
)
async def preview_requirement_interpretation(session_id: str, body: RequirementCreate) -> Dict[str, Any]:
    return await _legacy().preview_requirement_interpretation(session_id, body)


@router.get(
    "/sessions/{session_id}/requirements/latest",
    summary="Latest Requirement / 最新需求",
    description="Return the latest requirement for the session. 返回会话的最新需求。"
)
def get_latest_requirement(session_id: str) -> Dict[str, Any]:
    return _legacy().get_latest_requirement(session_id)


@router.post(
    "/sessions/{session_id}/itineraries",
    summary="Create Itinerary / 创建行程",
    description="Generate a new itinerary for the session. 为会话生成新的行程。"
)
async def create_itinerary(session_id: str, body: ItineraryCreate) -> Dict[str, Any]:
    return await _legacy().create_itinerary(session_id, body)


@router.get(
    "/sessions/{session_id}/itineraries/latest",
    summary="Latest Itinerary / 最新行程",
    description="Return the latest itinerary for the session. 返回会话的最新行程。"
)
def get_latest_itinerary(session_id: str) -> Dict[str, Any]:
    return _legacy().get_latest_itinerary(session_id)


@router.post(
    "/sessions/{session_id}/replan",
    summary="Replan Itinerary / 重新规划行程",
    description="Regenerate the itinerary after a user instruction. 根据用户指令重新生成行程。"
)
async def replan(session_id: str, body: ReplanCreate) -> Dict[str, Any]:
    return await _legacy().replan(session_id, body)


@router.post(
    "/sessions/{session_id}/messages",
    summary="Create Message / 创建消息",
    description="Store a new message in the session. 在会话中保存一条新消息。"
)
def create_message(session_id: str, body: MessageCreate) -> Dict[str, Any]:
    return _legacy().create_message(session_id, body)


@router.get(
    "/sessions/{session_id}/messages",
    summary="List Messages / 消息列表",
    description="List messages in a session. 列出会话中的消息。"
)
def list_messages(session_id: str, request: Request) -> Dict[str, Any]:
    return _legacy().list_messages(session_id, request)


@router.get(
    "/sessions/{session_id}/notes",
    summary="List User Notes / 用户记录列表",
    description="List user-saved place notes for the current session."
)
def list_user_notes(session_id: str, request: Request) -> Dict[str, Any]:
    return _legacy().list_user_notes(session_id, request)


@router.post(
    "/sessions/{session_id}/notes",
    summary="Create User Note / 保存用户记录",
    description="Save a user-authored place note, rating, and optional searched POI."
)
def create_user_note(session_id: str, body: UserPlaceNoteCreateRequest) -> Dict[str, Any]:
    return _legacy().create_user_note(session_id, body)


@router.delete(
    "/sessions/{session_id}/notes/{note_id}",
    summary="Delete User Note / 删除用户记录",
    description="Delete a saved user-authored place note from the session."
)
def delete_user_note(session_id: str, note_id: str) -> Dict[str, Any]:
    return _legacy().delete_user_note(session_id, note_id)

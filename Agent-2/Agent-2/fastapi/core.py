import json
import os
import re
import sqlite3
import shutil
import subprocess
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, urlencode

import httpx
import asyncio
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
PROJECT_DIR = BASE_DIR.parent


def _load_env_file(path: Path, *, override: bool = True) -> None:
    if not path.exists():
        return
    # Let local .env edits override inherited process variables.
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if not override and key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def _refresh_runtime_env() -> None:
    for env_path in (
        PROJECT_DIR / ".env",
        PROJECT_DIR / ".dev.vars",
        BASE_DIR / ".env",
    ):
        _load_env_file(env_path, override=True)


for env_path in (
    PROJECT_DIR / ".env",
    PROJECT_DIR / ".dev.vars",
    BASE_DIR / ".env",
):
    _load_env_file(env_path)


def _normalize_config_value(value: Optional[str]) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    placeholders = {
        "ms-4ecca729-328f-4e74-9d9b-39fa76e5b56b",
        "https://api-inference.modelscope.cn/v1/",
        "deepseek-ai/DeepSeek-V3.2",
    }
    return "" if text in placeholders else text


def _resolve_config(primary_key: str, alias_key: str, default: str) -> str:
    primary_value = _normalize_config_value(os.getenv(primary_key))
    if primary_value:
        return primary_value
    alias_value = _normalize_config_value(os.getenv(alias_key))
    if alias_value:
        return alias_value
    return default


def _parse_center(value: Optional[str], fallback: List[float]) -> List[float]:
    text = str(value or "").strip()
    if not text:
        return fallback
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 2:
        return fallback
    try:
        lng = float(parts[0])
        lat = float(parts[1])
    except ValueError:
        return fallback
    return [lng, lat]


# Default to the local Ollama-backed model so the dev server works out of the box.
TEXT_MODEL = _resolve_config(
    "TEXT_MODEL",
    "OPENAI_MODEL",
    "deepseek-ai/DeepSeek-V3.2")
TEXT_API_KEY = _resolve_config("TEXT_API_KEY", "OPENAI_API_KEY", "ms-4ecca729-328f-4e74-9d9b-39fa76e5b56b")
TEXT_API_BASE = _resolve_config("TEXT_API_BASE", "OPENAI_BASE_URL", "https://api-inference.modelscope.cn/v1/")

AMAP_BROWSER_KEY = _resolve_config("AMAP_BROWSER_KEY", "AMAP_BROWSERKEY", "")
AMAP_SECURITY_JS_CODE = _resolve_config("AMAP_SECURITY_JS_CODE", "AMAP_SECURITY_JSCODE", "")
AMAP_WEB_SERVICE_KEY = _resolve_config("AMAP_WEB_SERVICE_KEY", "AMAP_WEB_SERVICEKEY", "")
AMAP_DEFAULT_CITY = _resolve_config("AMAP_DEFAULT_CITY", "AMAP_CITY", "绵阳")
AMAP_DEFAULT_CENTER = _parse_center(
    _resolve_config("AMAP_DEFAULT_CENTER", "AMAP_CENTER", "104.679127,31.467673"),
    [104.679127, 31.467673],
)
AMAP_DEFAULT_RADIUS_METERS = int(os.getenv("AMAP_DEFAULT_RADIUS_METERS", "3000"))
AMAP_SEARCH_TIMEOUT_SECONDS = float(os.getenv("AMAP_SEARCH_TIMEOUT_SECONDS", "20"))
AMAP_BROWSER_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Origin": "https://www.amap.com",
    "Pragma": "no-cache",
    "Referer": "https://www.amap.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

APP_DB_PATH = os.getenv("APP_DB_PATH", os.getenv("DEBUG_DB_PATH", "./fastapi/debug.db"))
PLANNER_SCHEMA_VERSION = "planner_v2"
GLOBAL_PREFERENCE_PROFILE_KEY = "global_preference_profile_v1"


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


@contextmanager
def get_db():
    ensure_parent_dir(APP_DB_PATH)
    conn = sqlite3.connect(APP_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'active',
              current_requirement_version INTEGER NOT NULL DEFAULT 0,
              current_itinerary_version INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversation_messages (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              role TEXT NOT NULL,
              message_type TEXT NOT NULL DEFAULT 'text',
              content TEXT NOT NULL,
              metadata_json TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS requirements (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              version INTEGER NOT NULL,
              raw_input TEXT NOT NULL,
              strategy TEXT NOT NULL DEFAULT 'llm',
              structured_payload_json TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS itineraries (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              version INTEGER NOT NULL,
              requirement_id TEXT,
              generator_type TEXT NOT NULL DEFAULT 'agent',
              content_json TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_place_notes (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              city TEXT,
              query TEXT NOT NULL,
              place_name TEXT NOT NULL,
              rating INTEGER,
              comment TEXT,
              poi_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS app_state (
              key TEXT PRIMARY KEY,
              value_json TEXT NOT NULL
            );
            """
        )
        conn.commit()


def _get_app_state_json(conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
    row = conn.execute("SELECT value_json FROM app_state WHERE key = ?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value_json"])
    except (TypeError, json.JSONDecodeError):
        return default


def _set_app_state_json(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        """
        INSERT INTO app_state (key, value_json)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json
        """,
        (key, json.dumps(value, ensure_ascii=False)),
    )


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _sanitize_city_name(value: Any) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    if re.fullmatch(r"第?[0-9一二两三四五六七八九十]+(?:天|日)?", text):
        return ""
    text = re.sub(r"[，。,.!?！？、/\\\s]+$", "", text)
    text = re.sub(r"(?:city\s*walk|citywalk)$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"(?:[0-9一二两三四五六七八九十]+(?:天|日)(?:行程|游|玩|旅游)?)$", "", text).strip()
    text = re.sub(r"(?:旅游|旅行|游玩|行程|攻略|打卡|玩|逛|耍|住|待|过|游|转)$", "", text).strip()
    if re.fullmatch(r"第?[0-9一二两三四五六七八九十]+(?:天|日)?", text):
        return ""
    return text if len(text) >= 2 else _normalize_text(value)


def _build_session_title(message: str) -> str:
    text = _normalize_text(message)
    if not text:
        return "新会话"
    return text[:24]


def _extract_destination_hint(message: str) -> str:
    text = _normalize_text(message)
    if not text:
        return ""
    patterns = [
        r"(?:我想|想|准备|打算|计划)?(?:在|去|到|前往|奔向|计划去)\s*(?P<dest>[\u4e00-\u9fffA-Za-z0-9·]{2,12}?)(?:玩|旅游|旅行|逛|耍|住|待|过|打卡|游|转)",
        r"(?:在|去|到|前往|奔向|计划去)\s*(?P<dest>[\u4e00-\u9fffA-Za-z0-9·]{2,12}?)(?:玩|旅游|旅行|逛|耍|住|待|过|打卡|游|转)",
        r"(?P<dest>[\u4e00-\u9fffA-Za-z0-9·]{2,12}?)(?:[0-9一二两三四五六七八九十]+)?(?:天|日)(?:行程|游|玩|旅游)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            destination = _sanitize_city_name(match.group("dest"))
            if destination and _parse_day_count_token(destination) is None:
                return destination
    return ""


def _normalize_compact_text(value: Any) -> str:
    return re.sub(r"[\s,，。.!！?？:：;；、\-_/（）()\[\]【】]+", "", _normalize_text(value)).lower()


def _dedupe_keep_order(items: List[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for item in items:
        text = _normalize_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _infer_theme_from_message(message: str) -> str:
    text = _normalize_text(message)
    if any(token in text for token in ("citywalk", "city walk", "散步", "压马路")):
        return "citywalk"
    if any(token in text for token in ("亲子", "带娃", "小朋友", "孩子")):
        return "family"
    if any(token in text for token in ("美食", "好吃", "小吃", "吃")):
        return "food"
    if any(token in text for token in ("夜景", "夜游", "夜市")):
        return "night_view"
    if any(token in text for token in ("博物馆", "历史", "文化", "古镇", "古城")):
        return "culture"
    if any(token in text for token in ("自然", "公园", "徒步", "森林", "露营")):
        return "nature"
    return "general"


def _infer_trip_style_from_message(message: str) -> str:
    text = _normalize_text(message)
    if any(token in text for token in ("轻松", "休闲", "慢慢逛", "别太赶")):
        return "relaxed"
    if any(token in text for token in ("特种兵", "紧凑", "暴走", "多去几个")):
        return "compact"
    return "moderate"


def _extract_preference_tags(message: str) -> List[str]:
    text = _normalize_text(message)
    mapping = [
        ("咖啡", ("咖啡", "cafe")),
        ("夜景", ("夜景", "夜游", "夜市")),
        ("美食", ("美食", "好吃", "小吃", "火锅", "烧烤")),
        ("公园", ("公园", "草坪", "散步")),
        ("博物馆", ("博物馆", "展览", "艺术馆")),
        ("商场", ("商场", "购物", "逛街")),
        ("古镇", ("古镇", "古城", "老街")),
        ("拍照", ("拍照", "出片", "摄影")),
    ]
    tags: List[str] = []
    for label, keywords in mapping:
        if any(keyword in text for keyword in keywords):
            tags.append(label)
    return _dedupe_keep_order(tags)


def _extract_avoid_tags(message: str) -> List[str]:
    text = _normalize_text(message)
    mapping = [
        ("拥挤", ("不要太挤", "不想排队", "人少", "避开人群", "拥挤")),
        ("太远", ("别太远", "就近", "附近")),
        ("爬山", ("不爬山", "别爬山")),
        ("商业化", ("太商业化", "商业化")),
        ("太赶", ("别太赶", "不要太赶")),
    ]
    tags: List[str] = []
    for label, keywords in mapping:
        if any(keyword in text for keyword in keywords):
            tags.append(label)
    return _dedupe_keep_order(tags)


def _parse_day_count_token(token: str) -> Optional[int]:
    text = _normalize_text(token)
    if not text:
        return None
    if text.isdigit():
        value = int(text)
        return value if value > 0 else None
    mapping = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    if text in mapping:
        return mapping[text]
    if "十" in text:
        left, _, right = text.partition("十")
        tens = mapping.get(left, 1 if not left else 0)
        ones = mapping.get(right, 0 if right else 0)
        value = tens * 10 + ones
        return value if value > 0 else None
    return None


def _extract_day_count(message: str) -> Optional[int]:
    text = _normalize_text(message)
    if not text or "半天" in text:
        return None
    match = re.search(r"([0-9一二两三四五六七八九十]+)\s*(天|日)", text)
    if not match:
        return None
    return _parse_day_count_token(match.group(1))


def _infer_time_budget(message: str) -> str:
    text = _normalize_text(message)
    if "半天" in text:
        return "half_day"
    match = re.search(r"([0-9一二两三四五六七八九十]+)\s*(天|日)", text)
    if match:
        token = match.group(1)
        if token in {"1", "一"}:
            return "one_day"
        return "multi_day"
    return "flexible"


def _infer_radius_from_message(message: str) -> int:
    text = _normalize_text(message)
    if any(token in text for token in ("就近", "附近", "不要太远")):
        return 3000
    if any(token in text for token in ("周边", "近郊", "周末周边")):
        return 8000
    return 5000


def _infer_location_scope_from_message(message: str) -> str:
    text = _normalize_text(message)
    if any(token in text for token in ("附近", "就近")):
        return "nearby"
    if any(token in text for token in ("周边", "近郊")):
        return "surrounding"
    return "city_only"


def interpret_requirement_payload(message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    context = context or {}
    explicit_city = _extract_destination_hint(message)
    city = (
        explicit_city
        or _sanitize_city_name(context.get("current_city"))
        or AMAP_DEFAULT_CITY
    )
    anchor_location = parse_amap_location(context.get("anchor_location"))
    return {
        "city": _sanitize_city_name(city) or AMAP_DEFAULT_CITY,
        "theme": _infer_theme_from_message(message),
        "trip_style": _infer_trip_style_from_message(message),
        "must_have": _extract_preference_tags(message),
        "avoid": _extract_avoid_tags(message),
        "time_budget": _infer_time_budget(message),
        "day_count": _extract_day_count(message),
        "radius_meters": _infer_radius_from_message(message),
        "location_scope": _infer_location_scope_from_message(message),
        "anchor_location": anchor_location,
    }


def _merge_requirement_payload(
    previous: Optional[Dict[str, Any]],
    current: Dict[str, Any],
    message: str,
) -> Dict[str, Any]:
    if not previous:
        return current

    merged = dict(previous)
    merged.update({k: v for k, v in current.items() if v is not None})

    explicit_city = _extract_destination_hint(message)
    previous_city = _normalize_text(previous.get("city"))
    if explicit_city:
        merged["city"] = explicit_city
        if previous_city and explicit_city != previous_city:
            merged["anchor_location"] = None
    else:
        merged["city"] = previous_city or current.get("city") or AMAP_DEFAULT_CITY

    explicit_day_count = _extract_day_count(message)
    merged["day_count"] = explicit_day_count if explicit_day_count is not None else (previous.get("day_count") or current.get("day_count"))

    explicit_theme = _infer_theme_from_message(message)
    if explicit_theme != "general":
        merged["theme"] = explicit_theme
    else:
        merged["theme"] = _normalize_text(previous.get("theme")) or current.get("theme") or "general"

    explicit_trip_style = _infer_trip_style_from_message(message)
    if explicit_trip_style != "moderate":
        merged["trip_style"] = explicit_trip_style
    else:
        merged["trip_style"] = _normalize_text(previous.get("trip_style")) or current.get("trip_style") or "moderate"

    explicit_time_budget = _infer_time_budget(message)
    if explicit_time_budget != "flexible":
        merged["time_budget"] = explicit_time_budget
    else:
        merged["time_budget"] = _normalize_text(previous.get("time_budget")) or current.get("time_budget") or "flexible"

    current_must_have = current.get("must_have") or []
    current_avoid = current.get("avoid") or []
    merged["must_have"] = _dedupe_keep_order(list(previous.get("must_have") or []) + list(current_must_have))
    merged["avoid"] = _dedupe_keep_order(list(previous.get("avoid") or []) + list(current_avoid))

    explicit_scope = _infer_location_scope_from_message(message)
    if explicit_scope != "city_only":
        merged["location_scope"] = explicit_scope
    else:
        merged["location_scope"] = _normalize_text(previous.get("location_scope")) or current.get("location_scope") or "city_only"

    explicit_radius = _infer_radius_from_message(message)
    if any(token in _normalize_text(message) for token in ("就近", "附近", "不要太远", "周边", "近郊")):
        merged["radius_meters"] = explicit_radius
    else:
        merged["radius_meters"] = previous.get("radius_meters") or current.get("radius_meters") or 5000

    if explicit_city and previous_city and explicit_city != previous_city:
        merged["anchor_location"] = None
    else:
        merged["anchor_location"] = current.get("anchor_location") or previous.get("anchor_location")
    return merged


def _serialize_requirement_summary(payload: Optional[Dict[str, Any]]) -> str:
    if not payload:
        return ""
    compact = {
        "city": payload.get("city"),
        "day_count": payload.get("day_count"),
        "theme": payload.get("theme"),
        "trip_style": payload.get("trip_style"),
        "must_have": payload.get("must_have") or [],
        "avoid": payload.get("avoid") or [],
        "time_budget": payload.get("time_budget"),
        "location_scope": payload.get("location_scope"),
    }
    return json.dumps(compact, ensure_ascii=False)


def _extract_hotel_location_hint(message: str) -> str:
    text = _normalize_text(message)
    if not text:
        return ""
    patterns = [
        r"(?:住在|住到|酒店在|民宿在|住宿在)\s*(?P<hotel>[^，。,.!?！？\n]{2,24})",
        r"(?:从|以)\s*(?P<hotel>[^，。,.!?！？\n]{2,24})(?:酒店|民宿|客栈|住宿)(?:出发|开始)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _normalize_text(match.group("hotel")).strip("附近周边一带")
    return ""


def _default_global_preference_profile() -> Dict[str, Any]:
    return {
        "schema_version": "memory_profile_v1",
        "scope": "global_single_user",
        "updated_at": None,
        "preferences": {
            "low_fatigue": None,
            "likes_food": None,
            "accepts_taxi": None,
            "likes_niche": None,
            "family_friendly": None,
            "likes_night_view": None,
            "likes_cafe": None,
            "budget_level": None,
            "pace": None,
        },
        "evidence": [],
    }


def _infer_preference_updates_from_message(message: str) -> Dict[str, Any]:
    text = _normalize_text(message)
    updates: Dict[str, Any] = {}
    if re.search(r"(不想太累|别太累|不要太赶|轻松|慢慢逛|休闲)", text):
        updates["low_fatigue"] = True
        updates["pace"] = "relaxed"
    if re.search(r"(特种兵|紧凑|多去几个|暴走)", text):
        updates["low_fatigue"] = False
        updates["pace"] = "compact"
    if re.search(r"(美食|好吃|小吃|火锅|烧烤|夜宵|吃)", text):
        updates["likes_food"] = True
    if re.search(r"(打车|网约车|出租车)", text):
        updates["accepts_taxi"] = True
    if re.search(r"(公共交通|地铁|公交)", text):
        updates.setdefault("accepts_taxi", False)
    if re.search(r"(小众|人少|避开人群|不网红)", text):
        updates["likes_niche"] = True
    if re.search(r"(亲子|带娃|小朋友|孩子|老人)", text):
        updates["family_friendly"] = True
    if re.search(r"(夜景|夜游|夜市)", text):
        updates["likes_night_view"] = True
    if re.search(r"(咖啡|cafe)", text, re.IGNORECASE):
        updates["likes_cafe"] = True
    if re.search(r"(预算高|贵一点|品质|高端)", text):
        updates["budget_level"] = "premium"
    elif re.search(r"(预算低|省钱|便宜|性价比)", text):
        updates["budget_level"] = "value"
    elif re.search(r"(预算适中|中等预算)", text):
        updates["budget_level"] = "moderate"
    return updates


def _load_global_preference_profile(conn: sqlite3.Connection) -> Dict[str, Any]:
    profile = _get_app_state_json(conn, GLOBAL_PREFERENCE_PROFILE_KEY, None)
    if not isinstance(profile, dict):
        return _default_global_preference_profile()
    default = _default_global_preference_profile()
    merged = {**default, **profile}
    preferences = default["preferences"].copy()
    if isinstance(profile.get("preferences"), dict):
        preferences.update(profile["preferences"])
    merged["preferences"] = preferences
    merged["evidence"] = list(profile.get("evidence") or [])[-20:]
    return merged


def _update_global_preference_profile(conn: sqlite3.Connection, message: str) -> Dict[str, Any]:
    profile = _load_global_preference_profile(conn)
    updates = _infer_preference_updates_from_message(message)
    if updates:
        preferences = dict(profile.get("preferences") or {})
        preferences.update(updates)
        profile["preferences"] = preferences
        profile["updated_at"] = _now_iso()
        evidence = list(profile.get("evidence") or [])
        evidence.append(
            {
                "message": _normalize_text(message)[:120],
                "updates": updates,
                "created_at": profile["updated_at"],
            }
        )
        profile["evidence"] = evidence[-20:]
        _set_app_state_json(conn, GLOBAL_PREFERENCE_PROFILE_KEY, profile)
    return profile


def _collect_confirmed_place_names(itinerary: Optional[Dict[str, Any]]) -> List[str]:
    names: List[str] = []
    for day in (itinerary or {}).get("days") or []:
        for item in day.get("items") or []:
            for selected in item.get("selected_places") or []:
                name = _normalize_text(selected.get("name"))
                if name and name not in names:
                    names.append(name)
            for candidate in item.get("place_candidates") or []:
                for selected in candidate.get("selected_places") or []:
                    name = _normalize_text(selected.get("name"))
                    if name and name not in names:
                        names.append(name)
    return names


def _collect_grounded_pois_from_itinerary(itinerary: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    pois: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for day in (itinerary or {}).get("days") or []:
        for item in day.get("items") or []:
            for selected in item.get("selected_places") or []:
                poi_id = _normalize_text(selected.get("poi_id"))
                key = poi_id or f"{_normalize_text(selected.get('name'))}_{selected.get('location')}"
                if not key or key in seen:
                    continue
                seen.add(key)
                pois.append(selected)
    return pois


def _extract_rejected_places_from_message(message: str) -> List[str]:
    text = _normalize_text(message)
    rejected: List[str] = []
    for pattern in (r"(?:不要|避开|别去|去掉|删除)([^，。,.!?！？\n]{2,20})", r"([^，。,.!?！？\n]{2,20})(?:不想去|不喜欢)"):
        for match in re.finditer(pattern, text):
            value = _normalize_place_lookup_text(match.group(1))
            if value and value not in rejected:
                rejected.append(value)
    return rejected[:8]


def _build_memory_profile(
    global_profile: Dict[str, Any],
    requirement_payload: Dict[str, Any],
    latest_itinerary_payload: Optional[Dict[str, Any]],
    message: str,
) -> Dict[str, Any]:
    hotel_hint = _extract_hotel_location_hint(message) or _normalize_text((requirement_payload or {}).get("hotel_location"))
    confirmed_places = _collect_confirmed_place_names(latest_itinerary_payload)
    return {
        "schema_version": "memory_profile_v1",
        "short_term": {
            "destination": _normalize_text(requirement_payload.get("city")),
            "day_count": requirement_payload.get("day_count"),
            "hotel_location": hotel_hint,
            "preferences": requirement_payload.get("must_have") or [],
            "avoid": requirement_payload.get("avoid") or [],
            "confirmed_places": confirmed_places,
            "rejected_places": _extract_rejected_places_from_message(message),
        },
        "long_term": global_profile,
    }


def _apply_memory_to_requirement(requirement_payload: Dict[str, Any], memory_profile: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(requirement_payload or {})
    preferences = (((memory_profile or {}).get("long_term") or {}).get("preferences") or {})
    must_have = list(payload.get("must_have") or [])
    if preferences.get("likes_food") and "美食" not in must_have:
        must_have.append("美食")
    if preferences.get("likes_cafe") and "咖啡" not in must_have:
        must_have.append("咖啡")
    if preferences.get("likes_night_view") and "夜景" not in must_have:
        must_have.append("夜景")
    payload["must_have"] = _dedupe_keep_order(must_have)
    if preferences.get("low_fatigue") is True:
        payload["trip_style"] = "relaxed"
        payload["radius_meters"] = min(int(payload.get("radius_meters") or 5000), 4500)
    if preferences.get("accepts_taxi") is True and payload.get("trip_style") != "relaxed":
        payload["radius_meters"] = max(int(payload.get("radius_meters") or 5000), 7000)
    payload["hotel_location"] = ((memory_profile or {}).get("short_term") or {}).get("hotel_location") or payload.get("hotel_location")
    payload["memory_profile"] = memory_profile
    return payload


def _build_requirement_v2(requirement_payload: Dict[str, Any], memory_profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": PLANNER_SCHEMA_VERSION,
        "city": _normalize_text(requirement_payload.get("city")) or AMAP_DEFAULT_CITY,
        "day_count": requirement_payload.get("day_count"),
        "theme": _normalize_text(requirement_payload.get("theme")) or "general",
        "trip_style": _normalize_text(requirement_payload.get("trip_style")) or "moderate",
        "time_budget": _normalize_text(requirement_payload.get("time_budget")) or "flexible",
        "radius_meters": int(requirement_payload.get("radius_meters") or 5000),
        "location_scope": _normalize_text(requirement_payload.get("location_scope")) or "city_only",
        "hotel_location": _normalize_text(requirement_payload.get("hotel_location")),
        "must_have": list(requirement_payload.get("must_have") or []),
        "avoid": list(requirement_payload.get("avoid") or []),
        "anchor_location": parse_amap_location(requirement_payload.get("anchor_location")),
        "memory_profile": memory_profile,
    }


def _empty_validator_result() -> Dict[str, Any]:
    return {
        "schema_version": PLANNER_SCHEMA_VERSION,
        "status": "ok",
        "checks": [],
        "warnings": [],
        "repairs": [],
    }


def _add_validator_check(
    validator_result: Dict[str, Any],
    *,
    code: str,
    severity: str,
    status: str,
    message: str,
    day_index: Optional[int] = None,
    slot: str = "",
    poi_id: str = "",
) -> None:
    check = {
        "code": code,
        "severity": severity,
        "status": status,
        "message": message,
    }
    if day_index:
        check["day_index"] = day_index
    if _normalize_text(slot):
        check["slot"] = _normalize_text(slot)
    if _normalize_text(poi_id):
        check["poi_id"] = _normalize_text(poi_id)
    validator_result.setdefault("checks", []).append(check)
    if status != "passed":
        validator_result.setdefault("warnings", []).append(message)
        if severity in {"error", "warning"}:
            validator_result["status"] = "warning" if validator_result.get("status") != "error" else "error"
    if severity == "error" and status != "passed":
        validator_result["status"] = "error"


def _add_repair_action(
    validator_result: Dict[str, Any],
    *,
    action: str,
    message: str,
    day_index: Optional[int] = None,
    poi_id: str = "",
) -> None:
    repair = {
        "action": action,
        "message": message,
    }
    if day_index:
        repair["day_index"] = day_index
    if _normalize_text(poi_id):
        repair["poi_id"] = _normalize_text(poi_id)
    validator_result.setdefault("repairs", []).append(repair)


def _extract_generic_requirement_cues(message: str, requirement_payload: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    text = _normalize_text(message)
    tags = set(_extract_preference_tags(text))
    if requirement_payload:
        tags.update(_normalize_text(tag) for tag in (requirement_payload.get("must_have") or []))

    cue_map = [
        ("咖啡", ("咖啡", "cafe"), "咖啡店", "下午"),
        ("商场", ("商场", "购物", "逛街"), "商场", "下午"),
        ("夜景", ("夜景", "夜游", "夜市"), "夜景点", "晚上"),
        ("公园", ("公园", "散步", "草坪"), "公园", "下午"),
        ("酒吧", ("酒吧", "清吧"), "酒吧", "晚上"),
    ]
    cues: List[Dict[str, str]] = []
    for tag, keywords, query, slot in cue_map:
        if tag in tags or any(keyword in text for keyword in keywords):
            cues.append({
                "query": query,
                "slot": slot,
                "category_hint": _derive_place_category_hint(query) or _derive_place_category_hint(text),
                "intent_type": "generic_poi",
            })
    return cues


def _inject_generic_requirement_candidates(
    itinerary: Dict[str, Any],
    message: str,
    requirement_payload: Optional[Dict[str, Any]] = None,
    context_text: str = "",
) -> Dict[str, Any]:
    cues = _extract_generic_requirement_cues(message, requirement_payload)
    if not cues:
        return itinerary

    itinerary = json.loads(json.dumps(itinerary))
    selected_day = _extract_day_reference(context_text) or _extract_day_reference(message)
    if not selected_day:
        days = itinerary.get("days") or []
        selected_day = int(days[0].get("day_index") or 1) if days else 1

    for cue in cues:
        day = _ensure_itinerary_day(itinerary, selected_day)
        item = _ensure_itinerary_slot(day, cue.get("slot") or "下午")
        _append_candidate_to_item(item, cue.get("query") or "")
        for candidate in item.get("place_candidates") or []:
            if _normalize_text(candidate.get("query")) == _normalize_text(cue.get("query")):
                candidate["intent_type"] = "generic_poi"
                candidate["selection_mode"] = "user_pick"
                candidate["category_hint"] = cue.get("category_hint") or candidate.get("category_hint") or ""
                break
    return itinerary


def _build_short_term_memory(messages: List[Dict[str, Any]], max_rounds: int = 5) -> str:
    rows = [item for item in (messages or []) if _normalize_text(item.get("content"))]
    if not rows:
        return ""
    recent_rows = rows[-(max_rounds * 2):]
    rendered = []
    for item in recent_rows:
        role = "用户" if item.get("role") == "user" else "助手"
        rendered.append(f"{role}：{_normalize_text(item.get('content'))}")
    return "\n".join(rendered)


def _get_latest_requirement_payload(conn: sqlite3.Connection, session_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT *
        FROM requirements
        WHERE session_id = ?
        ORDER BY version DESC, created_at DESC, rowid DESC
        LIMIT 1
        """,
        (session_id,),
    ).fetchone()
    if not row:
        return None
    parsed = _parse_requirement_row(row)
    return parsed.get("structured_payload") if isinstance(parsed, dict) else None


def _save_requirement_snapshot(
    conn: sqlite3.Connection,
    session_id: str,
    raw_input: str,
    payload: Dict[str, Any],
    strategy: str = "chat_memory",
) -> Dict[str, Any]:
    session = _get_session_or_404(conn, session_id)
    version = int(session["current_requirement_version"] or 0) + 1
    requirement_id = _new_id("req")
    created_at = _now_iso()
    conn.execute(
        """
        INSERT INTO requirements (id, session_id, version, raw_input, strategy, structured_payload_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            requirement_id,
            session_id,
            version,
            raw_input,
            strategy,
            json.dumps(payload, ensure_ascii=False),
            created_at,
        ),
    )
    conn.execute(
        "UPDATE sessions SET current_requirement_version = ?, updated_at = ? WHERE id = ?",
        (version, created_at, session_id),
    )
    row = conn.execute("SELECT * FROM requirements WHERE id = ?", (requirement_id,)).fetchone()
    return _parse_requirement_row(row)



def _build_travel_system_prompt() -> str:
    return """你是一个中文智能旅游规划助手。
你的任务是输出真实、具体、顺路、具有当地特色的地点规划建议。
请优先推荐目的地内有代表性的景点、街区、美食片区和夜景点。
如果用户没有完整说明出行节奏、预算或住宿位置，请做出合理默认假设，并简要说明。
如果你不确定某个专名是否属于目的地城市，请不要输出它；可以改用更稳妥的当地片区、博物馆、公园、老街或美食片区。
回复要简洁、专业，适合直接展示给用户。"""


def _build_travel_user_prompt(
    message: str,
    destination_hint: str = "",
    requirement_context: Optional[Dict[str, Any]] = None,
) -> str:
    requirement_context = requirement_context or {}
    effective_destination = _normalize_text(destination_hint) or _normalize_text(requirement_context.get("city"))
    destination_section = ""
    if effective_destination:
        destination_section = (
            f"目的地提示：{effective_destination}\n"
            "请将所有地点严格限定在该目的地及其明确周边范围内。"
        )

    day_count = requirement_context.get("day_count")
    if day_count is None:
        day_count = _extract_day_count(message)
    day_count_section = ""
    if day_count:
        day_count_section = (
            f"天数硬约束：用户明确要求 {day_count} 天。\n"
            f"你必须且只能输出 {day_count} 个按天标题：第1天 到 第{day_count}天。\n"
            "不要缺少某一天，不要把多天内容混写在同一段，不要额外增加第N天。\n"
            "每一天都要单独安排，优先按上午 / 中午 / 下午 / 晚上展开。"
        )

    return f"""请根据下面的用户需求输出旅游地点规划建议。

输出规则：
1. 默认直接推荐，不要先反问用户。
2. 如果信息不完整，也要先给出一版可执行的规划，并在开头说明你的默认假设。
3. 如果用户指定了天数，必须严格按照该天数规划。
4. 每一天按上午 / 中午 / 下午 / 晚上组织，但不要为了凑满时间段而硬塞地点；每个时段可以给出 1 到 2 个互相顺路的地点。
5. 每天推荐 5 到 7 个核心地点，优先保证质量和路线顺路。
6. 地点必须具体、真实、容易理解。优先推荐当地地标片区、美食片区、夜景点或体验型地点。
7. 如果地点名称过于泛泛，请替换为更具体的当地地点。
8. 如果你不确定某个专名是否属于目的地，请不要输出它。
9. 每个地点后用一句简短的话说明为什么值得去，以及是否顺路。
10. 餐饮建议要符合时间段：早餐不要推荐火锅、串串、烧烤、酒吧、夜宵类地点。
11. 住宿不要作为游玩景点处理。
12. 如果某个著名地点距离较远或不适合当前天数，请放到备选中，并说明原因。
13. 不要只讲原则，要落到具体地点规划。
14. 不要使用 Markdown 加粗格式。
15. 使用“第1天：”这种普通文本标题即可。
16. 如果你不确定某个专名是否属于目的地城市，请不要输出它。
17. 不要把其他城市的知名地点混入当前目的地规划。
18. 对明确地标或明确景点，可以输出具体地点名。
19. 对“喝咖啡”“逛商场”“看夜景”这类泛需求，不要编造具体店名，可以直接输出“咖啡店候选”“商场候选”“夜景候选”这类语义地点。

{destination_section}

{day_count_section}

推荐输出格式：
默认假设：如果用户没有说明节奏、预算或住宿位置，请说明默认按轻松舒适、公共交通/打车结合、住在市中心来规划。

第1天：主题
上午：具体地点A 
 推荐理由。
中午：具体美食片区或餐饮方向 
 推荐理由。
下午：具体地点B / 具体地点C 
推荐理由，并说明是否与上午或中午的地点顺路。
晚上：具体夜景点或休闲片区 
推荐理由；如果不建议安排太满，可以写晚上回酒店休息。
当天逻辑：用一句话说明这些地点为什么适合放在一起。

备选：列出 2 到 4 个可替换地点，并说明适合什么情况。

用户需求：{message}""" 

def _sanitize_reply_text(text: str) -> str:
    cleaned = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("**", "")
    cleaned = cleaned.replace("__", "")
    cleaned = cleaned.replace("###", "").replace("##", "").replace("#", "")
    cleaned = re.sub(r"\s*(默认假设[：:])", r"\n\1", cleaned)
    cleaned = re.sub(r"\s*(第[0-9一二两三四五六七八九十]+\s*天[：:])", r"\n\1", cleaned)
    cleaned = re.sub(r"\s*((?:上午|中午|下午|晚上|傍晚|早上|午后|夜里|夜间|清晨|凌晨)[：:])", r"\n\1", cleaned)
    cleaned = re.sub(r"\s*(当天逻辑[：:])", r"\n\1", cleaned)
    cleaned = re.sub(r"\s*(备选[：:])", r"\n\1", cleaned)
    cleaned = "\n".join(line.rstrip() for line in cleaned.split("\n"))
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    return cleaned.strip()


DAY_HEADER_RE = re.compile(r"^第\s*([0-9一二两三四五六七八九十]+)\s*天\s*[：:]\s*(.*)$")
SLOT_RE = re.compile(r"^(上午|中午|下午|晚上|傍晚|早上|午后|夜里|夜间|清晨|凌晨)\s*[：:]\s*(.+)$")


def _normalize_itinerary_place(text: str) -> str:
    value = _normalize_text(text)
    if not value:
        return ""
    value = re.sub(r"^(从|去|到|前往|先去|先到|再去|随后去|可以去|建议去|晚上去|在)", "", value)
    value = re.sub(r"^(返回市中心(?:休息或自由活动)?|返回市中心)$", "", value)
    value = re.sub(r"(开始|顺路|漫步|散步|打卡|吃饭|收尾|小坐|闲逛|结束行程).*$", "", value)
    value = re.sub(r"(周边餐饮|周边美食|附近餐饮|附近美食).*$", "", value)
    value = re.sub(r"(附近用餐|附近晚餐|晚餐及休息|休息或自由活动|自由活动|休息|用餐|晚餐)$", "", value)
    value = re.sub(r"(周边|附近|一带|片区|商圈|区域)$", "", value)
    value = re.sub(r"^[0-9]+\s*[.、]\s*", "", value)
    return value.strip(" ，。；：:")


def _is_likely_itinerary_place(text: str) -> bool:
    value = _normalize_itinerary_place(text)
    if not value or len(value) < 2 or len(value) > 30:
        return False
    if re.search(r"^(返回|市中心|高新区|科创园区|附近|周边)", value):
        return False
    if re.search(r"(了解|感受|体验|品尝|欣赏|探访|结束|规划|安排|建议|逻辑|替换|预约|交通|时间|喜欢|适合|可选)", value):
        return False
    if re.fullmatch(r"(默认假设|当天逻辑|备选|路线|行程|景点|公园|夜景|商圈|周边餐饮|周边美食|本地中餐|特色汤锅|江边茶座|清吧小坐)", value):
        return False
    return True


def _derive_place_category_hint(text: str) -> str:
    source = _normalize_text(text)
    if re.search(r"(科技馆|博物馆|美术馆|纪念馆|展览馆|文化馆)", source):
        return "科教文化服务"
    if re.search(r"(商场|购物中心|商城|百货|shopping|mall)", source, re.IGNORECASE):
        return "购物服务"
    if re.search(r"(餐厅|饭店|火锅|咖啡|小吃|酒吧|茶馆|餐饮)", source):
        return "餐饮服务"
    if re.search(r"(公园|广场|景区|风景区|风景名胜区|山|寺|古镇|古城|楼|塔|步行街|小吃街|创意园|半岛|游客中心|休闲区|老街)", source):
        return "风景名胜"
    return ""


def _query_explicitly_wants_education(keyword: str, category_hint: Optional[str] = None) -> bool:
    source = f"{_normalize_text(keyword)} {_normalize_text(category_hint)}"
    return bool(re.search(r"(大学|学院|学校|中学|小学|幼儿园|校区|校园|教育|培训|驾校)", source))


def _is_education_like_poi(item: Dict[str, Any]) -> bool:
    source = " ".join(
        [
            _normalize_text(item.get("name")),
            _normalize_text(item.get("category")),
            _normalize_text(item.get("type")),
            _normalize_text(item.get("typecode")),
            _normalize_text(item.get("address")),
        ]
    )
    return bool(re.search(r"(大学|学院|学校|中学|小学|幼儿园|校区|校园|教育|培训|驾校)", source))


GENERIC_PLACE_RULES: List[Dict[str, Any]] = [
    {
        "pattern": re.compile(r"^(?:想喝|喝|找个|找一家|来个|加个)?咖啡(?:店|馆|厅)?(?:候选)?$", re.IGNORECASE),
        "query": "咖啡店",
        "category_hint": "餐饮服务",
    },
    {
        "pattern": re.compile(r"^(?:(?:想逛|逛|找个|来个|加个)?(?:商场|购物中心|商圈))(?:候选)?$", re.IGNORECASE),
        "query": "商场",
        "category_hint": "购物服务",
    },
    {
        "pattern": re.compile(r"^(?:想看|看|找个|来个|加个)?夜景(?:点|片区)?(?:候选)?$", re.IGNORECASE),
        "query": "夜景点",
        "category_hint": "风景名胜",
    },
    {
        "pattern": re.compile(r"^(?:找个|来个|加个)?(?:酒吧|清吧)(?:候选)?$", re.IGNORECASE),
        "query": "酒吧",
        "category_hint": "餐饮服务",
    },
    {
        "pattern": re.compile(r"^(?:找个|来个|加个)?(?:公园)(?:候选)?$", re.IGNORECASE),
        "query": "公园",
        "category_hint": "风景名胜",
    },
]


def _strip_parenthetical_segments(text: str) -> str:
    return re.sub(r"[（(][^()（）]+[)）]", "", _normalize_text(text))


def _simplify_generic_place_query(query: str) -> str:
    text = _normalize_text(query)
    if not text:
        return ""
    text = re.split(r"\s*(?:——|--|-{2,})\s*", text, maxsplit=1)[0]
    text = _strip_parenthetical_segments(text)
    text = re.sub(r"^(?:有|包含|包含有|可加|可选|可以加|建议加|还可加|再加|再来|顺便加|安排|推荐)", "", text)
    text = re.sub(r"^(?:把|在|去|到|前往|安排到|安排在)", "", text)
    text = re.sub(r"^(?:想喝|喝|想逛|逛|想看|看|找个|找一家|来个|加个|加一个|补个|补一个|增加一个|增加|再加个|再来个)", "", text)
    text = re.sub(r"(?:候选|可选)$", "", text)
    return text.strip(" ，。；：:、")


def _match_generic_place_rule(query: str) -> Optional[Dict[str, Any]]:
    text = _simplify_generic_place_query(query)
    if not text:
        return None
    for rule in GENERIC_PLACE_RULES:
        if rule["pattern"].fullmatch(text):
            return rule
    if text in {"咖啡店", "咖啡馆", "咖啡厅", "商场", "购物中心", "夜景", "夜景点", "酒吧", "公园"}:
        for rule in GENERIC_PLACE_RULES:
            if _normalize_text(rule["query"]) in text or text in _normalize_text(rule["query"]):
                return rule
    return None


def _build_place_candidate_payload(raw: str, query: str) -> Dict[str, Any]:
    generic_rule = _match_generic_place_rule(raw) or _match_generic_place_rule(query)
    if generic_rule:
        normalized_query = _normalize_text(generic_rule["query"])
        return {
            "query": normalized_query,
            "raw_query": _normalize_text(raw) or normalized_query,
            "aliases": [],
            "category_hint": _normalize_text(generic_rule["category_hint"]),
            "intent_type": "generic_poi",
            "selection_mode": "user_pick",
            "selected_places": [],
        }
    explicit_query = _normalize_itinerary_place(_strip_parenthetical_segments(query))
    if explicit_query.endswith("夜景") and len(explicit_query) > 3:
        explicit_query = explicit_query[:-2].strip()
    return {
        "query": explicit_query or query,
        "raw_query": _normalize_text(raw) or explicit_query or query,
        "aliases": _extract_place_aliases(raw),
        "category_hint": _derive_place_category_hint(raw),
        "intent_type": "explicit_poi",
        "selection_mode": "auto_resolve",
        "selected_places": [],
    }


def _extract_place_aliases(text: str) -> List[str]:
    aliases: List[str] = []
    for match in re.finditer(r"[（(]([^()（）]+)[)）]", text):
        inner = _normalize_itinerary_place(match.group(1))
        if inner and _is_likely_itinerary_place(inner):
            aliases.append(inner)
    simplified = _normalize_itinerary_place(re.sub(r"[（(][^()（）]+[)）]", "", text))
    if simplified.endswith("休闲区"):
        aliases.append(simplified[:-3])
    if simplified.endswith("游客中心"):
        aliases.append(simplified[:-4])
    deduped: List[str] = []
    for alias in aliases:
        if alias and alias not in deduped:
            deduped.append(alias)
    return deduped


def _extract_place_candidates_from_slot(slot_text: str) -> List[Dict[str, Any]]:
    main_part = re.split(r"\s*(?:——|--|-{2,})\s*", slot_text, maxsplit=1)[0]
    chunks = [
        part.strip()
        for part in re.split(r"\s*(?:/|／|、|，|和|以及|与|或)\s*", main_part)
        if _normalize_text(part)
    ]
    candidates: List[Dict[str, Any]] = []
    generic_sources = re.findall(
        r"(咖啡店(?:候选|可选)|咖啡馆(?:候选|可选)|咖啡厅(?:候选|可选)|商场(?:候选|可选)|购物中心(?:候选|可选)|夜景(?:点|片区)?(?:候选|可选)|酒吧(?:候选|可选)|清吧(?:候选|可选)|公园(?:候选|可选))",
        slot_text,
    )
    for raw in chunks:
        if re.search(r"(周边餐饮|周边美食|附近餐饮|附近美食)", raw):
            continue
        generic_candidate = _build_place_candidate_payload(raw, _normalize_itinerary_place(raw))
        if _normalize_text(generic_candidate.get("intent_type")) == "generic_poi":
            candidates.append(generic_candidate)
            continue
        query = _normalize_itinerary_place(_strip_parenthetical_segments(raw))
        if not _is_likely_itinerary_place(query):
            continue
        candidates.append(_build_place_candidate_payload(raw, query))
    for raw in generic_sources:
        payload = _build_place_candidate_payload(raw, raw)
        if _normalize_text(payload.get("intent_type")) == "generic_poi":
            candidates.append(payload)
    return candidates


def _build_structured_itinerary(
    message: str,
    assistant_text: str,
    requirement_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    requirement = requirement_override or interpret_requirement_payload(
        message,
        {"current_city": _extract_destination_hint(message) or AMAP_DEFAULT_CITY},
    )
    display_text = _sanitize_reply_text(assistant_text)
    lines = [line.strip() for line in display_text.split("\n") if line.strip()]
    days: List[Dict[str, Any]] = []
    current_day: Optional[Dict[str, Any]] = None

    for line in lines:
        day_match = DAY_HEADER_RE.match(line)
        if day_match:
            day_index = _parse_day_count_token(day_match.group(1))
            if not day_index:
                continue
            current_day = {
                "day_index": day_index,
                "title": _normalize_text(day_match.group(2)),
                "items": [],
            }
            days.append(current_day)
            continue

        slot_match = SLOT_RE.match(line)
        if slot_match:
            if current_day is None:
                current_day = {
                    "day_index": 1,
                    "title": "",
                    "items": [],
                }
                days.append(current_day)
            slot_name = slot_match.group(1)
            slot_text = _normalize_text(slot_match.group(2))
            current_day["items"].append(
                {
                    "slot": slot_name,
                    "text": slot_text,
                    "place_candidates": _extract_place_candidates_from_slot(slot_text),
                    "selected_places": [],
                }
            )

    requested_day_count = requirement.get("day_count")
    if isinstance(requested_day_count, int) and requested_day_count > 0:
        days = [day for day in days if int(day.get("day_index") or 0) <= requested_day_count]

    return {
        "city": requirement.get("city") or AMAP_DEFAULT_CITY,
        "day_count_requested": requested_day_count,
        "days": days,
        "display_text": display_text,
    }


PRIMARY_PLANNER_SLOTS: List[str] = ["上午", "中午", "下午", "晚上"]
EXTENDED_PLANNER_SLOTS: List[str] = ["上午", "中午", "下午", "下午", "晚上"]
TARGET_CORE_PLACES_PER_DAY = 6
TARGET_VALIDATED_CANDIDATES_PER_DAY = 8
PLACE_KIND_TO_CATEGORY_HINT: Dict[str, str] = {
    "attraction": "风景名胜",
    "museum": "科教文化服务",
    "park": "风景名胜",
    "old_street": "风景名胜",
    "food_area": "餐饮服务",
    "food_poi": "餐饮服务",
    "cafe": "餐饮服务",
    "shopping": "购物服务",
    "night_view": "风景名胜",
    "bar": "餐饮服务",
    "lodging": "住宿服务",
    "transport": "交通设施服务",
}
PLACE_KIND_TO_ROUTE_ROLE: Dict[str, str] = {
    "attraction": "anchor",
    "museum": "anchor",
    "park": "anchor",
    "old_street": "anchor",
    "food_area": "meal_stop",
    "food_poi": "meal_stop",
    "cafe": "rest_stop",
    "shopping": "rest_stop",
    "night_view": "night_stop",
    "bar": "night_stop",
    "lodging": "lodging",
    "transport": "search_only",
}


def _target_itinerary_place_count(day_count: int) -> int:
    normalized_days = max(1, int(day_count or 0))
    return max(normalized_days * TARGET_CORE_PLACES_PER_DAY, 8)


def _target_validated_candidate_pool_count(day_count: int) -> int:
    normalized_days = max(1, int(day_count or 0))
    return max(normalized_days * TARGET_VALIDATED_CANDIDATES_PER_DAY, 12)


CITY_HIGHLIGHT_QUERIES: Dict[str, List[Dict[str, Any]]] = {
    "成都": [
        {"query": "宽窄巷子", "kind": "old_street", "reason": "成都高识别度的城市漫步地标", "preferred_slots": ["上午", "下午"]},
        {"query": "武侯祠", "kind": "museum", "reason": "成都代表性的历史文化地标", "preferred_slots": ["上午", "下午"]},
        {"query": "杜甫草堂", "kind": "museum", "reason": "成都稳定且代表性的文化景点", "preferred_slots": ["上午"]},
        {"query": "人民公园", "kind": "park", "reason": "成都很稳妥的本地休闲锚点", "preferred_slots": ["上午", "下午"]},
        {"query": "春熙路", "kind": "shopping", "reason": "成都核心商圈与城市活力代表", "preferred_slots": ["下午", "晚上"]},
        {"query": "太古里", "kind": "shopping", "reason": "成都更有辨识度的商圈与夜间氛围点", "preferred_slots": ["下午", "晚上"]},
        {"query": "锦里", "kind": "old_street", "reason": "适合衔接傍晚与夜间氛围的成都老街点", "preferred_slots": ["下午", "晚上"]},
        {"query": "九眼桥夜景", "kind": "night_view", "reason": "成都夜间氛围和江边散步的常见代表点", "preferred_slots": ["晚上"]},
    ],
}


def _slot_rank(slot: str) -> int:
    normalized = _normalize_text(slot)
    try:
        return SLOT_ORDER.index(normalized)
    except ValueError:
        return len(SLOT_ORDER)


def _preferred_slots_for_place_kind(place_kind: str) -> List[str]:
    kind = _normalize_text(place_kind)
    if kind in {"attraction", "museum", "park", "old_street"}:
        return ["上午", "下午"]
    if kind in {"food_area", "food_poi"}:
        return ["中午", "晚上"]
    if kind == "cafe":
        return ["下午", "中午"]
    if kind == "shopping":
        return ["下午", "晚上"]
    if kind in {"night_view", "bar"}:
        return ["晚上"]
    return ["上午", "下午", "中午", "晚上"]


def _infer_planner_place_kind(name: str, category: str = "", query: str = "") -> str:
    source = " ".join([_normalize_text(name), _normalize_text(category), _normalize_text(query)])
    if re.search(r"(酒店|宾馆|旅馆|住宿|民宿|客栈|hotel)", source, re.IGNORECASE):
        return "lodging"
    if re.search(r"(地铁|公交|车站|机场|火车站|高铁|汽车站)", source):
        return "transport"
    if re.search(r"(博物馆|纪念馆|美术馆|展览馆|科技馆|文化馆)", source):
        return "museum"
    if re.search(r"(咖啡|cafe)", source, re.IGNORECASE):
        return "cafe"
    if re.search(r"(酒吧|清吧|bar)", source, re.IGNORECASE):
        return "bar"
    if re.search(r"(夜景|夜游|夜市|江边夜景|观景台|灯光秀)", source):
        return "night_view"
    if re.search(r"(商场|购物中心|商城|太古里|万象城|奥特莱斯)", source):
        return "shopping"
    if re.search(r"(美食街|小吃街|古街|步行街|街区|巷子|老街|商圈)", source):
        if re.search(r"(美食|小吃|餐饮|火锅|烧烤|串串)", source):
            return "food_area"
        return "old_street"
    if re.search(r"(火锅|餐厅|饭店|小吃|烧烤|面馆|餐饮|川菜|酒楼|食府)", source):
        return "food_poi"
    if re.search(r"(公园|草坪|绿道|湿地)", source):
        return "park"
    return "attraction"


def _infer_planner_route_role(place_kind: str) -> str:
    return PLACE_KIND_TO_ROUTE_ROLE.get(_normalize_text(place_kind), "anchor")


def _slot_suitability_score(slot: str, place_kind: str) -> float:
    normalized_slot = _normalize_text(slot)
    preferred = _preferred_slots_for_place_kind(place_kind)
    if normalized_slot in preferred:
        return 1.0 if preferred.index(normalized_slot) == 0 else 0.86
    if normalized_slot in PRIMARY_PLANNER_SLOTS:
        if place_kind in {"night_view", "bar"} and normalized_slot == "下午":
            return 0.25
        if place_kind in {"food_area", "food_poi"} and normalized_slot == "上午":
            return 0.22
        if place_kind in {"museum", "attraction", "park", "old_street"} and normalized_slot == "晚上":
            return 0.4
        return 0.55
    return 0.45


def _strip_json_fence(text: str) -> str:
    value = _normalize_text(text)
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?", "", value).strip()
        value = re.sub(r"```$", "", value).strip()
    return value


def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    raw = _strip_json_fence(text)
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]+\}", raw)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def _make_workflow_trace_entry(
    stage: str,
    started_at: float,
    *,
    status: str = "ok",
    warnings: Optional[List[str]] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "stage": stage,
        "status": status,
        "duration_ms": round((perf_counter() - started_at) * 1000, 1),
    }
    if warnings:
        payload["warnings"] = warnings
    if details:
        payload["details"] = details
    return payload


def _fallback_city_candidate_queries(requirement_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    city = _normalize_text(requirement_payload.get("city")) or AMAP_DEFAULT_CITY
    tags = set(requirement_payload.get("must_have") or [])
    theme = _normalize_text(requirement_payload.get("theme"))
    long_term_preferences = (((requirement_payload.get("memory_profile") or {}).get("long_term") or {}).get("preferences") or {})
    rows: List[Dict[str, Any]] = [
        {"query": f"{city}人民公园", "kind": "park", "reason": "优先补一处本地知名度较高的公园锚点", "preferred_slots": ["上午", "下午"], "backup_queries": ["人民公园", f"{city}公园"]},
        {"query": f"{city}公园", "kind": "park", "reason": "优先补一处城市里更稳妥的公共休闲锚点", "preferred_slots": ["上午", "下午"], "backup_queries": [f"{city}湿地公园", f"{city}滨江公园"]},
        {"query": f"{city}湿地公园", "kind": "park", "reason": "补足更适合散步和放松的自然向地点", "preferred_slots": ["上午", "下午"]},
        {"query": f"{city}博物馆", "kind": "museum", "reason": "优先补一处当地文化代表点", "preferred_slots": ["上午", "下午"]},
        {"query": f"{city}老街", "kind": "old_street", "reason": "优先召回当地常见的城市漫步片区", "preferred_slots": ["下午", "晚上"]},
        {"query": f"{city}古城", "kind": "old_street", "reason": "补足更有辨识度的历史街区或古城片区", "preferred_slots": ["下午", "晚上"]},
        {"query": f"{city}夜景", "kind": "night_view", "reason": "优先补足夜间行程", "preferred_slots": ["晚上"]},
        {"query": f"{city}江边夜景", "kind": "night_view", "reason": "补足更有城市辨识度的夜间景观带", "preferred_slots": ["晚上"]},
        {"query": f"{city}美食街", "kind": "food_area", "reason": "补足中午或晚上的餐饮锚点", "preferred_slots": ["中午", "晚上"]},
        {"query": f"{city}地标", "kind": "attraction", "reason": "补足城市最有辨识度的代表性地点", "preferred_slots": ["上午", "下午"]},
        {"query": f"{city}地标建筑", "kind": "attraction", "reason": "补足更容易被游客识别的著名建筑或主地标", "preferred_slots": ["上午", "下午"]},
        {"query": f"{city}城市广场", "kind": "attraction", "reason": "补足更稳定的中心地标与城市公共空间", "preferred_slots": ["上午", "下午"]},
        {"query": f"{city}步行街", "kind": "old_street", "reason": "补足更稳定的城市漫步片区", "preferred_slots": ["下午", "晚上"]},
        {"query": f"{city}商圈", "kind": "shopping", "reason": "补足下午到晚上的城市活力区域", "preferred_slots": ["下午", "晚上"]},
    ]
    rows.extend(CITY_HIGHLIGHT_QUERIES.get(city, []))
    if "咖啡" in tags:
        rows.append({"query": "咖啡店", "kind": "cafe", "reason": "用户明确偏好咖啡", "preferred_slots": ["下午"]})
    if "商场" in tags:
        rows.append({"query": "商场", "kind": "shopping", "reason": "用户明确偏好商圈", "preferred_slots": ["下午", "晚上"]})
    if "夜景" in tags or theme == "night_view":
        rows.append({"query": "夜景点", "kind": "night_view", "reason": "用户明确偏好夜景", "preferred_slots": ["晚上"]})
    if long_term_preferences.get("likes_niche"):
        rows.append({"query": f"{city}小众景点", "kind": "attraction", "reason": "长期偏好显示用户喜欢小众体验", "preferred_slots": ["下午"]})
    if long_term_preferences.get("family_friendly"):
        rows.append({"query": f"{city}亲子公园", "kind": "park", "reason": "长期偏好显示需要亲子友好", "preferred_slots": ["上午", "下午"], "backup_queries": [f"{city}儿童公园"]})
    if "公园" in tags or theme == "nature":
        rows.append({"query": f"{city}植物园", "kind": "park", "reason": "用户明确偏好公园或自然散步场景", "preferred_slots": ["上午", "下午"]})
        rows.append({"query": f"{city}滨江公园", "kind": "park", "reason": "补足更适合慢逛和拍照的开放式公园带", "preferred_slots": ["下午", "晚上"]})
    normalized_rows: List[Dict[str, Any]] = []
    seen_queries: set[str] = set()
    for row in rows:
        normalized = _normalize_candidate_recall_entry(row)
        query = _normalize_text((normalized or {}).get("query"))
        if not normalized or not query or query in seen_queries:
            continue
        seen_queries.add(query)
        normalized_rows.append(normalized)
    return normalized_rows


def _normalize_candidate_recall_entry(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(candidate, dict):
        return None
    query = _normalize_text(candidate.get("query") or candidate.get("name"))
    if not query:
        return None
    place_kind = _normalize_text(candidate.get("kind")) or _infer_planner_place_kind(query, candidate.get("category_hint") or "", query)
    preferred_slots = [
        _normalize_text(slot)
        for slot in (candidate.get("preferred_slots") or [])
        if _normalize_text(slot) in PRIMARY_PLANNER_SLOTS
    ]
    backup_queries = [
        _normalize_text(item)
        for item in (candidate.get("backup_queries") or candidate.get("backups") or [])
        if _normalize_text(item)
    ]
    return {
        "query": query,
        "kind": place_kind,
        "reason": _normalize_text(candidate.get("reason")),
        "preferred_slots": preferred_slots or _preferred_slots_for_place_kind(place_kind),
        "category_hint": _normalize_text(candidate.get("category_hint")) or PLACE_KIND_TO_CATEGORY_HINT.get(place_kind) or _derive_place_category_hint(query),
        "backup_queries": _dedupe_keep_order(backup_queries),
    }


def _build_candidate_recall_prompt(
    message: str,
    conversation_context: str,
    requirement_payload: Dict[str, Any],
) -> List[Dict[str, str]]:
    day_count = int(requirement_payload.get("day_count") or 0) or 2
    candidate_target_min = max(day_count * 6, 10)
    candidate_target_max = max(candidate_target_min + 4, day_count * 8)
    requirement_summary = json.dumps(
        {
            "city": requirement_payload.get("city"),
            "day_count": day_count,
            "theme": requirement_payload.get("theme"),
            "trip_style": requirement_payload.get("trip_style"),
            "must_have": requirement_payload.get("must_have") or [],
            "avoid": requirement_payload.get("avoid") or [],
            "time_budget": requirement_payload.get("time_budget"),
            "memory_profile": requirement_payload.get("memory_profile") or {},
        },
        ensure_ascii=False,
    )
    user_prompt = f"""你现在是一个旅游规划 Tool-using Agent 的“城市代表性候选召回器”。
你的任务不是直接给最终行程，而是先给出一批适合进入后续 POI 验证的地点候选。

输出 JSON，不要输出解释文字，不要使用 markdown 代码块之外的文本。
JSON 结构：
{{
  "assumptions": "一句话说明默认假设",
  "representative_candidates": [
    {{
      "query": "候选地点名或可搜索的候选词",
      "kind": "attraction|museum|park|old_street|food_area|food_poi|cafe|shopping|night_view|bar",
      "reason": "为什么它适合这次行程",
      "preferred_slots": ["上午","下午"],
      "backup_queries": ["同类替代候选1","同类替代候选2"]
    }}
  ],
  "global_backups": ["备选1", "备选2", "备选3"]
}}

规则：
1. 必须严格限定在目的地城市范围内，不要混入其他城市。
2. 优先推荐城市代表性的地标、片区、公园、古街、商圈、美食片区、夜景点。
3. 对不够确定的餐饮/咖啡/夜景类，可以给“可搜索词”，后续由工具验证。
4. `representative_candidates` 总数尽量控制在 {candidate_target_min} 到 {candidate_target_max} 个之间，保证热门代表性地点尽量齐全。
5. 不要输出坐标，不要输出虚构地点，不要输出住宿。
6. 如果用户指定 {day_count} 天，请保证候选池足够支撑 {day_count} 天规划。

需求摘要：{requirement_summary}
会话上下文：{conversation_context or "无"}
用户最新消息：{message}"""
    return [
        {
            "role": "system",
            "content": "你是中文旅游规划系统里的候选召回器，只输出合法 JSON。",
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]


def _extract_place_names_from_html(html: str, city: str) -> List[str]:
    """Extract likely place names from DuckDuckGo HTML search results."""
    names: List[str] = []
    seen = set()
    city_normalized = _normalize_text(city)
    skip_words = {"旅游攻略", "必去景点", "推荐", "美食", "小众", "本地人", "打卡", "景点", "攻略", "旅游"}
    for match in re.finditer(r'<a[^>]+class="result__a"[^>]+href="[^"]*"[^>]*>(.*?)</a>', html):
        title = re.sub(r'<[^>]+>', ' ', match.group(1)).strip()
        title = re.sub(r'&amp;|&quot;|&#39;', ' ', title)
        title = re.sub(r'\s+', ' ', title).strip()
        if not title or len(title) < 2:
            continue
        for segment in re.findall(r'[\u4e00-\u9fff]{2,6}', title):
            if segment in seen or segment == city_normalized or segment in skip_words:
                continue
            seen.add(segment)
            names.append(segment)
    for match in re.finditer(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', html):
        snippet = re.sub(r'<[^>]+>', ' ', match.group(1)).strip()
        snippet = re.sub(r'&amp;|&quot;|&#39;', ' ', snippet)
        for segment in re.findall(r'[\u4e00-\u9fff]{2,6}', snippet):
            if segment in seen or segment == city_normalized or segment in skip_words:
                continue
            seen.add(segment)
            names.append(segment)
    return names[:15]


async def _search_web_for_places(city: str, interests: List[str]) -> List[Dict[str, Any]]:
    """Search the web for travel recommendations about a city."""
    rows: List[Dict[str, Any]] = []
    queries = [
        f"{city} 旅游攻略 必去景点",
        f"{city} 小众景点 本地人推荐",
        f"{city} 美食 本地人推荐",
    ]
    if interests:
        interest_str = " ".join(interests[:3])
        queries.append(f"{city} {interest_str} 推荐")

    for query in queries[:4]:
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "TravelAgent/1.0"})
                if resp.status_code != 200:
                    continue
                names = _extract_place_names_from_html(resp.text, city)
                for name in names:
                    rows.append({
                        "query": f"{city} {name}",
                        "kind": "attraction",
                        "reason": f"web discovered: {query}",
                        "preferred_slots": ["上午", "下午"],
                        "backup_queries": [name],
                    })
        except Exception:
            continue

    return rows[:12]


async def _generate_candidate_recall(
    message: str,
    conversation_context: str,
    requirement_payload: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        content = await _request_text_completion(
            _build_candidate_recall_prompt(message, conversation_context, requirement_payload),
            temperature=0.15,
        )
        parsed = _parse_json_object(content) or {}
    except Exception:
        parsed = {}
    rows = parsed.get("representative_candidates") if isinstance(parsed, dict) else None
    normalized_rows: List[Dict[str, Any]] = []
    for row in rows or []:
        normalized = _normalize_candidate_recall_entry(row)
        if normalized:
            normalized_rows.append(normalized)
    fallback_rows = _fallback_city_candidate_queries(requirement_payload)
    if not normalized_rows:
        normalized_rows = list(fallback_rows)
    minimum_candidate_count = min(12, max(8, (int(requirement_payload.get("day_count") or 0) or 2) * 4))
    seen_queries = {_normalize_text(item.get("query")) for item in normalized_rows if _normalize_text(item.get("query"))}
    # Enrich with web-discovered places
    city = _normalize_text(requirement_payload.get("city") or "") or AMAP_DEFAULT_CITY
    interests = requirement_payload.get("must_have") or []
    web_rows = await _search_web_for_places(city, list(interests))
    if web_rows:
        for web_row in web_rows:
            web_query = _normalize_text(web_row.get("query"))
            if web_query and web_query not in seen_queries:
                normalized_rows.append(web_row)
                seen_queries.add(web_query)
    for row in fallback_rows:
        query = _normalize_text(row.get("query"))
        if not query or query in seen_queries:
            continue
        normalized_rows.append(row)
        seen_queries.add(query)
        if len(normalized_rows) >= minimum_candidate_count:
            break
    return {
        "assumptions": _normalize_text(parsed.get("assumptions")) or "默认按轻松舒适、住在市中心附近、公共交通和打车结合来召回候选。",
        "representative_candidates": normalized_rows,
        "global_backups": _dedupe_keep_order([_normalize_text(item) for item in (parsed.get("global_backups") or []) if _normalize_text(item)]),
    }


async def _resolve_workflow_candidate(
    candidate: Dict[str, Any],
    *,
    city: str,
    radius_meters: int,
    anchor_location: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    query = _normalize_text(candidate.get("query"))
    category_hint = _normalize_text(candidate.get("category_hint")) or _derive_place_category_hint(query)
    place_kind = _normalize_text(candidate.get("kind")) or _infer_planner_place_kind(query, category_hint, query)
    warnings: List[str] = []
    alternatives: List[Dict[str, Any]] = []
    if _match_generic_place_rule(query) or place_kind in {"food_area", "food_poi", "cafe", "shopping", "night_view", "bar"}:
        search_res = await api_planner_place_candidates(
            {
                "day_index": 1,
                "slot": (candidate.get("preferred_slots") or ["下午"])[0],
                "query": query,
                "intent_type": "generic_poi",
                "city": city,
                "category_hint": category_hint or PLACE_KIND_TO_CATEGORY_HINT.get(place_kind),
                "anchor_location": anchor_location,
                "radius_meters": radius_meters,
                "limit": 5,
            }
        )
        warnings.extend(search_res.get("warnings", []))
        candidates = list(search_res.get("candidates") or [])
        if candidates:
            alternatives = candidates[1:4]
            best = candidates[0]
            best["is_valid"] = True
            return {
                "status": "resolved",
                "candidate": candidate,
                "poi": best,
                "alternatives": alternatives,
                "warnings": warnings,
            }
        if _is_map_quota_warning(" ".join(str(item) for item in search_res.get("warnings", []))):
            return {
                "status": "invalid",
                "candidate": candidate,
                "poi": None,
                "alternatives": [],
                "warnings": warnings,
            }
    resolve_res = await api_poi_resolve(
        {
            "city": city,
            "keyword": query,
            "category_hint": category_hint or PLACE_KIND_TO_CATEGORY_HINT.get(place_kind),
            "anchor_location": anchor_location,
            "radius_meters": radius_meters,
            "limit": 6,
        }
    )
    warnings.extend(resolve_res.get("warnings", []))
    if resolve_res.get("status") == "resolved" and isinstance(resolve_res.get("poi"), dict):
        poi = dict(resolve_res.get("poi") or {})
        poi["is_valid"] = True
        return {
            "status": "resolved",
            "candidate": candidate,
            "poi": poi,
            "alternatives": list(resolve_res.get("alternatives") or [])[:4],
            "warnings": warnings,
        }
    alternatives = list(resolve_res.get("alternatives") or [])[:4]
    return {
        "status": _normalize_text(resolve_res.get("status")) or "invalid",
        "candidate": candidate,
        "poi": None,
        "alternatives": alternatives,
        "warnings": warnings + ([_normalize_text(resolve_res.get("reason"))] if _normalize_text(resolve_res.get("reason")) else []),
    }


def _decorate_validated_place(
    poi: Dict[str, Any],
    *,
    query: str,
    place_kind: Optional[str] = None,
    source: str = "validated_poi",
    reason: str = "",
) -> Dict[str, Any]:
    actual_place_kind = _normalize_text(place_kind) or _infer_planner_place_kind(poi.get("name") or "", poi.get("category") or "", query)
    decorated = {
        "schema_version": PLANNER_SCHEMA_VERSION,
        "poi_id": _normalize_text(poi.get("poi_id")),
        "name": _normalize_text(poi.get("name")),
        "address": _normalize_text(poi.get("address")),
        "category": _normalize_text(poi.get("category")),
        "city": _normalize_text(poi.get("city")),
        "district": _normalize_text(poi.get("district")),
        "adcode": _normalize_text(poi.get("adcode")),
        "location": parse_amap_location(poi.get("location")),
        "distance_meters": poi.get("distance_meters"),
        "confidence": poi.get("confidence"),
        "resolve_note": _normalize_text(poi.get("resolve_note")) or reason,
        "anchor_keyword": _normalize_text(poi.get("anchor_keyword")),
        "source": source,
        "candidate_name": _normalize_text(query),
        "grounding_status": "grounded",
        "grounding_source": "amap_poi",
        "place_kind": actual_place_kind,
        "route_role": _infer_planner_route_role(actual_place_kind),
        "validation_status": "validated",
        "source_query": query,
    }
    return _apply_poi_hierarchy_fields(decorated, query)


async def _resolve_candidate_pool(
    candidate_defs: List[Dict[str, Any]],
    requirement_payload: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    city = _normalize_text(requirement_payload.get("city")) or AMAP_DEFAULT_CITY
    radius_meters = int(requirement_payload.get("radius_meters") or AMAP_DEFAULT_RADIUS_METERS)
    anchor_location = parse_amap_location(requirement_payload.get("anchor_location"))
    validated: List[Dict[str, Any]] = []
    backups: List[Dict[str, Any]] = []
    warnings: List[str] = []
    seen: set[str] = set()
    for candidate_def in candidate_defs:
        result = await _resolve_workflow_candidate(
            candidate_def,
            city=city,
            radius_meters=radius_meters,
            anchor_location=anchor_location,
        )
        warnings.extend(result.get("warnings", []))
        if result.get("status") == "resolved" and isinstance(result.get("poi"), dict):
            poi = _decorate_validated_place(
                result["poi"],
                query=candidate_def.get("query") or "",
                place_kind=candidate_def.get("kind"),
                source="validated_poi",
                reason=candidate_def.get("reason") or "",
            )
            key = _normalize_text(poi.get("poi_id")) or f"{poi.get('name')}_{poi.get('location')}"
            if key and key not in seen:
                seen.add(key)
                validated.append(
                    {
                        "poi": poi,
                        "query": candidate_def.get("query"),
                        "kind": candidate_def.get("kind"),
                        "reason": candidate_def.get("reason"),
                        "preferred_slots": candidate_def.get("preferred_slots") or _preferred_slots_for_place_kind(candidate_def.get("kind") or ""),
                        "backup_queries": candidate_def.get("backup_queries") or [],
                    }
                )
            for alt in result.get("alternatives") or []:
                if not parse_amap_location(alt.get("location")):
                    continue
                backups.append(
                    {
                        "query": candidate_def.get("query"),
                        "reason": f"同类替代：{candidate_def.get('query')}",
                        "poi": _decorate_validated_place(
                            alt,
                            query=candidate_def.get("query") or "",
                            place_kind=candidate_def.get("kind"),
                            source="backup_candidate",
                        ),
                    }
                )
        else:
            backups.append(
                {
                    "query": candidate_def.get("query"),
                    "reason": "高德未能稳定解析为正式行程点",
                    "alternatives": result.get("alternatives") or [],
                    "status": result.get("status"),
                }
            )
        if _is_map_quota_warning(" ".join(str(item) for item in result.get("warnings", []))):
            break
    return validated, backups, _dedupe_keep_order([item for item in warnings if _normalize_text(item)])


def _validated_candidate_identity_key(item: Dict[str, Any]) -> str:
    poi = item.get("poi") or {}
    poi_id = _normalize_text(poi.get("poi_id"))
    if poi_id:
        return poi_id
    return f"{_normalize_text(poi.get('name'))}_{parse_amap_location(poi.get('location'))}"


def _backup_candidate_promote_score(entry: Dict[str, Any]) -> float:
    poi = entry.get("poi") or {}
    place_kind = _normalize_text(poi.get("place_kind"))
    kind_bonus = {
        "museum": 2.8,
        "attraction": 2.7,
        "old_street": 2.8,
        "park": 2.6,
        "shopping": 2.5,
        "night_view": 2.6,
        "food_area": 2.5,
        "food_poi": 2.2,
        "cafe": 2.0,
        "bar": 1.8,
    }.get(place_kind, 1.5)
    confidence = float(poi.get("confidence") or 0)
    primary_bonus = 0.25 if poi.get("is_primary_poi") is not False else 0.0
    return round(kind_bonus + confidence + primary_bonus, 4)


def _supplement_validated_candidates(
    validated_candidates: List[Dict[str, Any]],
    candidate_backups: List[Dict[str, Any]],
    requirement_payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    day_count = int(requirement_payload.get("day_count") or 0) or 2
    target_count = _target_validated_candidate_pool_count(day_count)
    if len(validated_candidates) >= target_count:
        return validated_candidates
    supplemented = list(validated_candidates)
    seen_keys = {
        _validated_candidate_identity_key(item)
        for item in supplemented
        if _validated_candidate_identity_key(item)
    }
    ranked_backups = sorted(
        [
            entry for entry in (candidate_backups or [])
            if isinstance(entry, dict) and isinstance(entry.get("poi"), dict) and parse_amap_location((entry.get("poi") or {}).get("location"))
        ],
        key=_backup_candidate_promote_score,
        reverse=True,
    )
    for backup in ranked_backups:
        poi = json.loads(json.dumps(backup.get("poi") or {}, ensure_ascii=False))
        key = _normalize_text(poi.get("poi_id")) or f"{_normalize_text(poi.get('name'))}_{parse_amap_location(poi.get('location'))}"
        if not key or key in seen_keys:
            continue
        query = _normalize_text(backup.get("query")) or _normalize_text(poi.get("name"))
        place_kind = _normalize_text(poi.get("place_kind")) or _infer_planner_place_kind(
            poi.get("name") or "",
            poi.get("category") or "",
            query,
        )
        poi["place_kind"] = place_kind
        poi["route_role"] = _infer_planner_route_role(place_kind)
        poi["validation_status"] = _normalize_text(poi.get("validation_status")) or "validated"
        poi["grounding_status"] = _normalize_text(poi.get("grounding_status")) or "grounded"
        poi["source"] = _normalize_text(poi.get("source")) or "supplemental_validated_poi"
        supplemented.append(
            {
                "poi": poi,
                "query": query,
                "kind": place_kind,
                "reason": _normalize_text(backup.get("reason")) or "补足正式行程数量与代表性。",
                "preferred_slots": _preferred_slots_for_place_kind(place_kind),
                "backup_queries": [],
            }
        )
        seen_keys.add(key)
        if len(supplemented) >= target_count:
            break
    return supplemented


def _is_child_like_poi(place_kind: str, name: str = "", category: str = "") -> bool:
    source = " ".join([_normalize_text(place_kind), _normalize_text(name), _normalize_text(category)])
    if place_kind in {"cafe", "food_poi", "bar"}:
        return True
    return bool(re.search(r"(店|馆|餐厅|咖啡|酒吧|小吃|火锅|茶馆|铺|院落|展厅)", source))


def _infer_child_poi_type(place_kind: str) -> str:
    kind = _normalize_text(place_kind)
    if kind == "cafe":
        return "cafe"
    if kind in {"food_poi", "food_area"}:
        return "food"
    if kind == "bar":
        return "bar"
    if kind in {"museum", "attraction"}:
        return "experience"
    return ""


def _guess_parent_poi_name(name: str, query: str, address: str = "") -> str:
    query_text = _normalize_place_lookup_text(query)
    name_text = _normalize_place_lookup_text(name)
    address_text = _normalize_text(address)
    if query_text and query_text != name_text and (query_text in name_text or query_text in address_text):
        return query_text
    match = re.search(r"(宽窄巷子|锦里|太古里|春熙路|人民公园|武侯祠|杜甫草堂|IFS|环球中心|解放碑|洪崖洞)", f"{name_text} {address_text}", flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def _apply_poi_hierarchy_fields(poi: Dict[str, Any], query: str) -> Dict[str, Any]:
    place_kind = _normalize_text(poi.get("place_kind"))
    parent_name = _guess_parent_poi_name(poi.get("name") or "", query, poi.get("address") or "")
    is_child = bool(parent_name) or _is_child_like_poi(place_kind, poi.get("name") or "", poi.get("category") or "")
    if is_child and parent_name and not _place_name_matches(parent_name, poi.get("name") or ""):
        poi["parent_poi_id"] = _normalize_text(poi.get("parent_poi_id"))
        poi["parent_poi_name"] = parent_name
        poi["is_primary_poi"] = False
        poi["child_poi_type"] = _infer_child_poi_type(place_kind)
    else:
        poi["parent_poi_id"] = _normalize_text(poi.get("parent_poi_id")) or _normalize_text(poi.get("poi_id"))
        poi["parent_poi_name"] = _normalize_text(poi.get("parent_poi_name")) or _normalize_text(poi.get("name"))
        poi["is_primary_poi"] = True
        poi["child_poi_type"] = ""
    return poi


def _summarize_validated_pool_for_prompt(validated_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in validated_candidates:
        poi = item.get("poi") or {}
        rows.append(
            {
                "poi_id": poi.get("poi_id"),
                "name": poi.get("name"),
                "category": poi.get("category"),
                "address": poi.get("address"),
                "place_kind": poi.get("place_kind"),
                "route_role": poi.get("route_role"),
                "preferred_slots": item.get("preferred_slots") or [],
                "reason": item.get("reason"),
            }
        )
    return rows


def _fallback_plan_from_validated_pool(
    validated_candidates: List[Dict[str, Any]],
    requirement_payload: Dict[str, Any],
) -> Dict[str, Any]:
    if not validated_candidates:
        return {
            "assumptions": "当前未能拿到足够的可落图 POI，已先保留行程说明并等待下一次补全。",
            "days": [],
            "global_backups": [],
        }

    day_count = int(requirement_payload.get("day_count") or 0) or min(2, max(1, len(validated_candidates) // 3 or 1))
    pool = list(validated_candidates)
    used: set[str] = set()
    slot_sequence = EXTENDED_PLANNER_SLOTS if len(validated_candidates) >= max(day_count * 5, 8) else PRIMARY_PLANNER_SLOTS

    def _pick_for_slot(slot: str, category_used_today: Dict[str, int], trip_category_count: Dict[str, int]) -> Optional[Dict[str, Any]]:
        best = None
        best_score = -1.0
        for item in pool:
            poi = item.get("poi") or {}
            poi_id = _normalize_text(poi.get("poi_id"))
            if not poi_id or poi_id in used:
                continue
            place_kind = poi.get("place_kind") or ""
            score = _slot_suitability_score(slot, place_kind)
            if slot in (item.get("preferred_slots") or []):
                score += 0.2
            # Category diversity: penalize same kind repeating in a day or across days
            today_count = category_used_today.get(place_kind, 0)
            trip_count = trip_category_count.get(place_kind, 0)
            score -= today_count * 0.15
            score -= trip_count * 0.08
            if score > best_score:
                best = item
                best_score = score
        if best:
            best_poi = best.get("poi") or {}
            best_kind = best_poi.get("place_kind") or ""
            used.add(_normalize_text(best_poi.get("poi_id")))
            category_used_today[best_kind] = category_used_today.get(best_kind, 0) + 1
            trip_category_count[best_kind] = trip_category_count.get(best_kind, 0) + 1
        return best

    trip_category_count: Dict[str, int] = {}
    days: List[Dict[str, Any]] = []
    for day_index in range(1, day_count + 1):
        category_used_today: Dict[str, int] = {}
        items: List[Dict[str, Any]] = []
        for slot in slot_sequence:
            picked = _pick_for_slot(slot, category_used_today, trip_category_count)
            if not picked:
                continue
            poi = picked.get("poi") or {}
            items.append(
                {
                    "slot": slot,
                    "poi_id": poi.get("poi_id"),
                    "name": poi.get("name"),
                    "reason": picked.get("reason") or "按顺路性与偏好自动安排。",
                }
            )
        days.append(
            {
                "day_index": day_index,
                "title": f"第{day_index}天顺路安排",
                "items": items,
            }
        )
    return {
        "assumptions": "候选池不足以完全依赖模型排程时，已按已验证 POI 的时段适配和顺路性自动生成。",
        "days": days,
        "global_backups": [],
    }


async def _generate_day_segment_plan(
    message: str,
    conversation_context: str,
    requirement_payload: Dict[str, Any],
    validated_candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    day_count = int(requirement_payload.get("day_count") or 0) or 2
    summarized_pool = _summarize_validated_pool_for_prompt(validated_candidates)
    messages = [
        {
            "role": "system",
            "content": "你是中文旅游规划系统里的 day-segment planner。你只能使用给定的 validated POI，且只输出合法 JSON。",
        },
        {
            "role": "user",
            "content": f"""你现在负责把已验证的 POI 编排成按天、按时段的旅游行程。

输出 JSON：
{{
  "assumptions": "一句话默认假设",
  "days": [
    {{
      "day_index": 1,
      "title": "当天主题",
      "items": [
        {{
          "slot": "上午|中午|下午|晚上",
          "poi_id": "必须来自输入池",
          "name": "便于阅读的地点名",
          "reason": "为什么放在这个时段且与上下文顺路"
        }}
      ]
    }}
  ],
  "global_backups": ["可选备选点名"]
}}

规则：
1. 只能使用下方已验证 POI 池里的 `poi_id`，不要编造新地点。
2. 控制为 {day_count} 天；如果用户天数较少，优先保留代表性强、顺路的点。
3. 每天尽量安排 4 到 5 个点；如果 POI 池足够，可以在同一个时段放 2 个顺路点。
4. 时段仍然使用 上午 / 中午 / 下午 / 晚上；夜景优先放晚上，餐饮优先放中午或晚上，咖啡优先放下午。
5. 同一个 `poi_id` 绝对不要在不同天重复出现，每天只出现一次。
6. 每天必须有不同类别的组合（景点+美食+街区+夜景等），不要连续多天都只有同一种类别。
7. 输出尽量顺路，不要明显来回跑，并优先保留城市关键地标。

需求摘要：{json.dumps(requirement_payload, ensure_ascii=False)}
会话上下文：{conversation_context or "无"}
用户消息：{message}
已验证 POI 池：{json.dumps(summarized_pool, ensure_ascii=False)}""",
        },
    ]
    try:
        content = await _request_text_completion(messages, temperature=0.15)
        parsed = _parse_json_object(content)
        if isinstance(parsed, dict) and isinstance(parsed.get("days"), list):
            return parsed
    except Exception:
        pass
    return _fallback_plan_from_validated_pool(validated_candidates, requirement_payload)


def _lookup_validated_candidate(
    validated_candidates: List[Dict[str, Any]],
    *,
    poi_id: str = "",
    name: str = "",
) -> Optional[Dict[str, Any]]:
    normalized_id = _normalize_text(poi_id)
    normalized_name = _normalize_text(name)
    for item in validated_candidates:
        poi = item.get("poi") or {}
        if normalized_id and _normalize_text(poi.get("poi_id")) == normalized_id:
            return item
    for item in validated_candidates:
        poi = item.get("poi") or {}
        if normalized_name and _place_name_matches(poi.get("name") or "", normalized_name):
            return item
    return None


def _materialize_validated_itinerary(
    plan_payload: Dict[str, Any],
    validated_candidates: List[Dict[str, Any]],
    requirement_payload: Dict[str, Any],
    *,
    candidate_backups: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []
    used_poi_ids: set[str] = set()
    requested_days = int(requirement_payload.get("day_count") or 0) or None
    days: List[Dict[str, Any]] = []
    for day_payload in plan_payload.get("days") or []:
        if not isinstance(day_payload, dict):
            continue
        day_index = int(day_payload.get("day_index") or 0)
        if not day_index:
            continue
        if requested_days and day_index > requested_days:
            continue
        day_items: List[Dict[str, Any]] = []
        for item_payload in day_payload.get("items") or []:
            if not isinstance(item_payload, dict):
                continue
            slot = _normalize_text(item_payload.get("slot"))
            if slot not in PRIMARY_PLANNER_SLOTS:
                continue
            validated = _lookup_validated_candidate(
                validated_candidates,
                poi_id=item_payload.get("poi_id") or "",
                name=item_payload.get("name") or "",
            )
            if not validated:
                warnings.append(f"planner referenced unknown poi: {item_payload.get('poi_id') or item_payload.get('name')}")
                continue
            poi_id = _normalize_text((validated.get("poi") or {}).get("poi_id"))
            if poi_id and poi_id in used_poi_ids:
                warnings.append(f"duplicate poi across days skipped: {poi_id} ({validated.get('poi', {}).get('name', '')})")
                continue
            if poi_id:
                used_poi_ids.add(poi_id)
            poi = json.loads(json.dumps(validated.get("poi") or {}, ensure_ascii=False))
            reason = _normalize_text(item_payload.get("reason")) or _normalize_text(validated.get("reason"))
            candidate_query = _normalize_text(validated.get("query")) or _normalize_text(poi.get("name"))
            poi["time_slot"] = slot
            poi["why_here"] = reason
            poi["source"] = "grounded_poi"
            day_items.append(
                {
                    "slot": slot,
                    "text": f"{poi.get('name')} —— {reason}" if reason else _normalize_text(poi.get("name")),
                    "place_candidates": [
                        {
                            "query": candidate_query,
                            "raw_query": candidate_query,
                            "aliases": [],
                            "category_hint": _normalize_text(poi.get("category")) or _derive_place_category_hint(candidate_query),
                            "intent_type": "explicit_poi",
                            "selection_mode": "tool_resolved",
                            "selected_places": [poi],
                        }
                    ],
                    "selected_places": [poi],
                }
            )
        day_items.sort(key=lambda item: _slot_rank(item.get("slot") or ""))
        manual_order = [
            _normalize_text((item.get("selected_places") or [{}])[0].get("poi_id"))
            for item in day_items
            if _normalize_text((item.get("selected_places") or [{}])[0].get("poi_id"))
        ]
        days.append(
            {
                "day_index": day_index,
                "title": _normalize_text(day_payload.get("title")) or f"第{day_index}天",
                "items": day_items,
                "manual_order_poi_ids": manual_order,
            }
        )
    itinerary = {
        "schema_version": PLANNER_SCHEMA_VERSION,
        "city": _normalize_text(requirement_payload.get("city")) or AMAP_DEFAULT_CITY,
        "day_count_requested": requested_days,
        "days": days,
        "workflow_trace": [],
        "planner_warnings": [],
        "candidate_backups": candidate_backups or [],
        "validator_result": _empty_validator_result(),
    }
    return itinerary, _dedupe_keep_order([item for item in warnings if _normalize_text(item)])


def _enrich_itinerary_with_remaining_validated_candidates(
    itinerary: Dict[str, Any],
    validated_candidates: List[Dict[str, Any]],
    requirement_payload: Dict[str, Any],
) -> None:
    requested_days = int(requirement_payload.get("day_count") or 0) or max(1, len(itinerary.get("days") or []))
    if requested_days <= 0 or not validated_candidates:
        return
    days = list(itinerary.get("days") or [])
    existing_day_indexes = {int(day.get("day_index") or 0) for day in days}
    for day_index in range(1, requested_days + 1):
        if day_index in existing_day_indexes:
            continue
        days.append({"day_index": day_index, "title": f"第{day_index}天", "items": [], "manual_order_poi_ids": []})
    days.sort(key=lambda item: int(item.get("day_index") or 0) or 999)
    itinerary["days"] = days

    used_poi_ids = {
        _normalize_text((item.get("selected_places") or [{}])[0].get("poi_id"))
        for day in days
        for item in (day.get("items") or [])
        if _normalize_text((item.get("selected_places") or [{}])[0].get("poi_id"))
    }
    target_total = min(len(validated_candidates), _target_itinerary_place_count(requested_days))
    current_total = sum(len(day.get("items") or []) for day in days)
    if current_total >= target_total:
        return

    def _fill_score(item: Dict[str, Any]) -> float:
        poi = item.get("poi") or {}
        place_kind = _normalize_text(poi.get("place_kind"))
        return {
            "museum": 2.8,
            "attraction": 2.7,
            "old_street": 2.8,
            "park": 2.6,
            "shopping": 2.5,
            "night_view": 2.6,
            "food_area": 2.5,
            "food_poi": 2.2,
            "cafe": 2.0,
            "bar": 1.8,
        }.get(place_kind, 1.5) + float(poi.get("confidence") or 0)

    remaining = sorted(
        [
            item for item in validated_candidates
            if _normalize_text((item.get("poi") or {}).get("poi_id"))
            and _normalize_text((item.get("poi") or {}).get("poi_id")) not in used_poi_ids
        ],
        key=_fill_score,
        reverse=True,
    )
    for item in remaining:
        if current_total >= target_total:
            break
        poi = json.loads(json.dumps(item.get("poi") or {}, ensure_ascii=False))
        poi_id = _normalize_text(poi.get("poi_id"))
        if not poi_id or poi_id in used_poi_ids:
            continue
        preferred_slots = item.get("preferred_slots") or _preferred_slots_for_place_kind(item.get("kind") or poi.get("place_kind") or "")
        preferred_slot = _normalize_text(preferred_slots[0] if preferred_slots else "下午") or "下午"
        target_day = min(
            days,
            key=lambda day: (
                len(day.get("items") or []),
                sum(1 for row in (day.get("items") or []) if _normalize_text(row.get("slot")) == preferred_slot),
                int(day.get("day_index") or 0),
            ),
        )
        reason = _normalize_text(item.get("reason")) or "补足正式行程的代表性与完整度。"
        poi["time_slot"] = preferred_slot
        poi["why_here"] = reason
        poi["source"] = _normalize_text(poi.get("source")) or "supplemental_validated_poi"
        target_day.setdefault("items", []).append(
            {
                "slot": preferred_slot,
                "text": f"{poi.get('name')} —— {reason}" if reason else _normalize_text(poi.get("name")),
                "place_candidates": [
                    {
                        "query": _normalize_text(item.get("query")) or _normalize_text(poi.get("name")),
                        "raw_query": _normalize_text(item.get("query")) or _normalize_text(poi.get("name")),
                        "aliases": [],
                        "category_hint": _normalize_text(poi.get("category")) or _derive_place_category_hint(_normalize_text(item.get("query")) or _normalize_text(poi.get("name"))),
                        "intent_type": "explicit_poi",
                        "selection_mode": "tool_resolved",
                        "selected_places": [poi],
                    }
                ],
                "selected_places": [poi],
            }
        )
        target_day["items"] = sorted(target_day.get("items") or [], key=lambda row: _slot_rank(row.get("slot") or ""))
        used_poi_ids.add(poi_id)
        current_total += 1
    for day in days:
        _refresh_day_manual_order(day)


def _nearest_neighbor_order(rows: List[Dict[str, Any]]) -> List[str]:
    pool = [row for row in rows if parse_amap_location(row.get("location")) and _normalize_text(row.get("poi_id"))]
    if len(pool) < 2:
        return [_normalize_text(row.get("poi_id")) for row in pool if _normalize_text(row.get("poi_id"))]
    start_index = max(
        range(len(pool)),
        key=lambda index: _slot_suitability_score(_normalize_text(pool[index].get("_slot_hint")), _normalize_text(pool[index].get("place_kind"))),
    )
    ordered = [pool.pop(start_index)]
    while pool:
        last_location = parse_amap_location(ordered[-1].get("location"))
        next_index = min(
            range(len(pool)),
            key=lambda index: _distance_between_points(last_location, parse_amap_location(pool[index].get("location"))) or 10**12,
        )
        ordered.append(pool.pop(next_index))
    return [_normalize_text(row.get("poi_id")) for row in ordered if _normalize_text(row.get("poi_id"))]


def _refresh_day_manual_order(day: Dict[str, Any]) -> None:
    day_places = []
    for item in day.get("items") or []:
        selected = (item.get("selected_places") or [None])[0] or {}
        location = parse_amap_location(selected.get("location"))
        if not location:
            continue
        day_places.append({**selected, "_slot_hint": item.get("slot")})
    if len(day_places) >= 2:
        ordered_ids = _nearest_neighbor_order(day_places)
        if ordered_ids:
            day["manual_order_poi_ids"] = ordered_ids
            return
    day["manual_order_poi_ids"] = [
        _normalize_text((item.get("selected_places") or [{}])[0].get("poi_id"))
        for item in (day.get("items") or [])
        if _normalize_text((item.get("selected_places") or [{}])[0].get("poi_id"))
    ]


def _enforce_distinct_addresses_between_first_two_days(
    itinerary: Dict[str, Any],
    validator_result: Dict[str, Any],
    downgrade_item: Any,
) -> None:
    days = itinerary.get("days") or []
    first_day = next((day for day in days if int(day.get("day_index") or 0) == 1), None)
    second_day = next((day for day in days if int(day.get("day_index") or 0) == 2), None)
    if not first_day or not second_day:
        return

    first_day_addresses = set()
    for item in first_day.get("items") or []:
        selected = (item.get("selected_places") or [None])[0] or {}
        address_key = _normalize_compact_text(selected.get("address"))
        if address_key:
            first_day_addresses.add(address_key)
    if not first_day_addresses:
        return

    kept_items: List[Dict[str, Any]] = []
    changed = False
    for item in second_day.get("items") or []:
        selected = (item.get("selected_places") or [None])[0] or {}
        address_key = _normalize_compact_text(selected.get("address"))
        name = _normalize_text(selected.get("name") or item.get("text"))
        poi_id = _normalize_text(selected.get("poi_id"))
        if address_key and address_key in first_day_addresses:
            message = f"第2天 {name} 与第1天地址重复，已从正式行程排除。"
            _add_validator_check(
                validator_result,
                code="duplicate_address_day_1_2",
                severity="warning",
                status="repaired",
                message=message,
                day_index=2,
                slot=item.get("slot") or "",
                poi_id=poi_id,
            )
            _add_repair_action(
                validator_result,
                action="drop_duplicate_address_across_day_1_2",
                message=message,
                day_index=2,
                poi_id=poi_id,
            )
            downgrade_item(2, item, selected, message)
            changed = True
            continue
        kept_items.append(item)
    if changed:
        second_day["items"] = sorted(kept_items, key=lambda item: _slot_rank(item.get("slot") or ""))
        _refresh_day_manual_order(second_day)


def _validate_and_repair_itinerary(
    itinerary: Dict[str, Any],
    requirement_payload: Dict[str, Any],
) -> List[str]:
    city = _normalize_text(requirement_payload.get("city")) or _normalize_text(itinerary.get("city")) or AMAP_DEFAULT_CITY
    trip_style = _normalize_text(requirement_payload.get("trip_style")) or "moderate"
    memory_preferences = ((((requirement_payload.get("memory_profile") or {}).get("long_term") or {}).get("preferences")) or {})
    max_jump = 13000 if memory_preferences.get("accepts_taxi") else (11000 if trip_style == "compact" else (9000 if trip_style == "moderate" else 7000))
    if memory_preferences.get("low_fatigue") is True:
        max_jump = min(max_jump, 7000)
    validator_result = _empty_validator_result()
    downgraded_backups = list(itinerary.get("candidate_backups") or [])

    def _downgrade_item(day_index: int, item: Dict[str, Any], selected: Dict[str, Any], reason: str) -> None:
        selected = dict(selected or {})
        selected["source"] = "backup_candidate"
        selected["validation_status"] = "downgraded"
        downgraded_backups.append(
            {
                "query": selected.get("source_query") or selected.get("name") or item.get("text"),
                "reason": reason,
                "poi": selected,
                "day_index": day_index,
                "slot": item.get("slot"),
            }
        )
        _add_repair_action(
            validator_result,
            action="downgrade_to_backup",
            message=reason,
            day_index=day_index,
            poi_id=selected.get("poi_id") or "",
        )

    for day in itinerary.get("days") or []:
        slot_taken = {_normalize_text(item.get("slot")) for item in (day.get("items") or [])}
        kept_items: List[Dict[str, Any]] = []
        day_index = int(day.get("day_index") or 0)
        for item in day.get("items") or []:
            selected = (item.get("selected_places") or [None])[0] or {}
            place_kind = _normalize_text(selected.get("place_kind")) or _infer_planner_place_kind(selected.get("name") or "", selected.get("category") or "", selected.get("source_query") or "")
            selected["place_kind"] = place_kind
            selected["route_role"] = _infer_planner_route_role(place_kind)
            selected["validation_status"] = _normalize_text(selected.get("validation_status")) or "validated"
            selected["_slot_hint"] = _normalize_text(item.get("slot"))
            selected.setdefault("time_slot", _normalize_text(item.get("slot")))
            selected.setdefault("why_here", _normalize_text(item.get("text")))
            poi_id = _normalize_text(selected.get("poi_id"))
            name = _normalize_text(selected.get("name") or item.get("text"))

            if not poi_id or not parse_amap_location(selected.get("location")):
                message = f"第{day_index}天 {name or item.get('slot')} 缺少可落图 POI，已降级为备选。"
                _add_validator_check(validator_result, code="missing_grounding", severity="error", status="failed", message=message, day_index=day_index, slot=item.get("slot") or "")
                _downgrade_item(day_index, item, selected, message)
                continue

            grounding_status = _normalize_text(selected.get("grounding_status"))
            if place_kind in {"generic_term", "search_request"} or (grounding_status and grounding_status not in {"grounded", "validated"}):
                message = f"第{day_index}天 {name} 仍是泛化地点，已降级为备选。"
                _add_validator_check(validator_result, code="generic_place", severity="error", status="failed", message=message, day_index=day_index, slot=item.get("slot") or "", poi_id=poi_id)
                _downgrade_item(day_index, item, selected, message)
                continue

            if place_kind == "lodging" and not re.search(r"(酒店|住宿|民宿|客栈)", _normalize_text(requirement_payload.get("hotel_location"))):
                message = f"第{day_index}天 {name} 是住宿类 POI，已从游玩路线降级为备选。"
                _add_validator_check(validator_result, code="lodging_in_route", severity="error", status="failed", message=message, day_index=day_index, slot=item.get("slot") or "", poi_id=poi_id)
                _downgrade_item(day_index, item, selected, message)
                continue

            source_query = (
                _normalize_text(selected.get("source_query"))
                or _normalize_text((item.get("place_candidates") or [{}])[0].get("query"))
                or name
            )
            if _is_auxiliary_poi_name(name) and not _query_explicitly_wants_auxiliary_poi(source_query):
                message = f"第{day_index}天 {name} 更像附属设施而不是主行程点，已降级为备选。"
                _add_validator_check(validator_result, code="auxiliary_poi", severity="error", status="failed", message=message, day_index=day_index, slot=item.get("slot") or "", poi_id=poi_id)
                _downgrade_item(day_index, item, selected, message)
                continue

            if not _matches_city_constraint(selected, city):
                message = f"第{day_index}天包含跨城市点：{name}，已降级为备选。"
                _add_validator_check(validator_result, code="city_mismatch", severity="error", status="failed", message=message, day_index=day_index, slot=item.get("slot") or "", poi_id=poi_id)
                _downgrade_item(day_index, item, selected, message)
                continue

            if selected.get("is_primary_poi") is False and not _normalize_text(selected.get("parent_poi_name")):
                message = f"第{day_index}天 {name} 是低置信子 POI，缺少主体 POI 归属，已降级为备选。"
                _add_validator_check(validator_result, code="orphan_child_poi", severity="warning", status="failed", message=message, day_index=day_index, slot=item.get("slot") or "", poi_id=poi_id)
                _downgrade_item(day_index, item, selected, message)
                continue

            current_slot = _normalize_text(item.get("slot"))
            if _slot_suitability_score(current_slot, place_kind) < 0.4:
                for preferred in _preferred_slots_for_place_kind(place_kind):
                    if preferred not in slot_taken:
                        slot_taken.discard(current_slot)
                        slot_taken.add(preferred)
                        item["slot"] = preferred
                        selected["time_slot"] = preferred
                        message = f"已将 {name} 自动调整到更合适的时段：{preferred}"
                        _add_validator_check(validator_result, code="time_slot_mismatch", severity="warning", status="repaired", message=message, day_index=day_index, slot=current_slot, poi_id=poi_id)
                        _add_repair_action(validator_result, action="move_time_slot", message=message, day_index=day_index, poi_id=poi_id)
                        break
            _add_validator_check(validator_result, code="grounded_poi", severity="info", status="passed", message=f"{name} 已通过 POI grounding。", day_index=day_index, slot=item.get("slot") or "", poi_id=poi_id)
            kept_items.append(item)
        day["items"] = sorted(kept_items, key=lambda item: _slot_rank(item.get("slot") or ""))
        _refresh_day_manual_order(day)
    _enforce_distinct_addresses_between_first_two_days(itinerary, validator_result, _downgrade_item)
    for day in itinerary.get("days") or []:
        day_places = []
        day_index = int(day.get("day_index") or 0)
        for item in day.get("items") or []:
            selected = (item.get("selected_places") or [None])[0] or {}
            location = parse_amap_location(selected.get("location"))
            if not location:
                continue
            day_places.append({**selected, "_slot_hint": item.get("slot")})
        for left, right in zip(day_places, day_places[1:]):
                distance = _distance_between_points(parse_amap_location(left.get("location")), parse_amap_location(right.get("location")))
                if distance is not None and distance > max_jump:
                    message = f"第{day_index}天 {left.get('name')} 到 {right.get('name')} 直线距离约 {int(distance)} 米，可能不够顺路。"
                    _add_validator_check(
                        validator_result,
                        code="distance_too_far",
                        severity="warning",
                        status="failed",
                        message=message,
                        day_index=day_index,
                        poi_id=right.get("poi_id") or "",
                    )
    validator_result["warnings"] = _dedupe_keep_order([item for item in validator_result.get("warnings") or [] if _normalize_text(item)])
    if validator_result.get("repairs"):
        validator_result["status"] = "repaired"
    elif validator_result.get("warnings"):
        validator_result["status"] = "warning"
    else:
        validator_result["status"] = "ok"
    itinerary["candidate_backups"] = downgraded_backups
    itinerary["validator_result"] = validator_result
    itinerary["planner_warnings"] = _sanitize_planner_warnings_for_user(validator_result["warnings"])
    return itinerary["planner_warnings"]


def _render_itinerary_summary_text(
    itinerary: Dict[str, Any],
    assumptions: str = "",
    warnings: Optional[List[str]] = None,
) -> str:
    def _clean_day_title(day_index: int, title: str) -> str:
        value = _normalize_text(title)
        if not value:
            return ""
        value = re.sub(rf"^第\s*{day_index}\s*天\s*[：:\-—\s]*", "", value).strip()
        if value in {"", f"第{day_index}天"}:
            return ""
        return value

    def _build_item_summary(item: Dict[str, Any]) -> str:
        selected_places = item.get("selected_places") or []
        place_name = _normalize_text((selected_places[0] or {}).get("name")) if selected_places else ""
        text = _normalize_text(item.get("text"))
        if text:
            text = re.sub(
                r"^(上午|中午|下午|傍晚|晚上|夜里|夜间|早上|午后|清晨|凌晨)[：:]\s*",
                "",
                text,
            ).strip()
        if place_name and text:
            if text == place_name or text.startswith(f"{place_name} ——"):
                return text
            return f"{place_name} —— {text}"
        return place_name or text

    lines: List[str] = []
    if _normalize_text(assumptions):
        lines.append(f"默认假设：{_normalize_text(assumptions)}")
    days = list(itinerary.get("days") or [])
    if not days:
        concise = [item for item in (warnings or []) if _normalize_text(item)][:2]
        if concise:
            lines.append("提示：" + "；".join(concise))
        return "\n".join(lines).strip()
    for day in days:
        day_index = int(day.get("day_index") or 0)
        title_suffix = _clean_day_title(day_index, day.get("title"))
        title = f"第{day.get('day_index')}天：{title_suffix}" if title_suffix else f"第{day.get('day_index')}天："
        lines.append(title)
        for item in day.get("items") or []:
            item_summary = _build_item_summary(item)
            if item_summary:
                lines.append(f"- {item_summary}")
        selected_names = [
            _normalize_text((item.get("selected_places") or [{}])[0].get("name"))
            for item in day.get("items") or []
            if _normalize_text((item.get("selected_places") or [{}])[0].get("name"))
        ]
        if selected_names:
            lines.append(f"当天逻辑：围绕 {' - '.join(selected_names)} 顺路展开。")
    if warnings:
        concise = [item for item in warnings if _normalize_text(item)][:3]
        if concise:
            lines.append("提示：" + "；".join(concise))
    return "\n".join(lines).strip()


_AUXILIARY_POI_NAME_RE = re.compile(r"(家属区|家属院|宿舍区|宿舍楼|办公区|办公楼|办公室|管理处|服务中心|售票处|停车场|出入口)")


def _is_auxiliary_poi_name(value: Any) -> bool:
    return bool(_AUXILIARY_POI_NAME_RE.search(_normalize_text(value)))


def _query_explicitly_wants_auxiliary_poi(keyword: str) -> bool:
    return bool(_AUXILIARY_POI_NAME_RE.search(_normalize_text(keyword)))


def _join_chinese_list(items: List[str]) -> str:
    values = [item for item in (_normalize_text(value) for value in items) if item]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]}和{values[1]}"
    return f"{'、'.join(values[:-1])}和{values[-1]}"


def _summarize_chat_day(day: Dict[str, Any]) -> str:
    day_index = int(day.get("day_index") or 0) or 1
    place_names = _dedupe_keep_order(
        [
            _normalize_text((item.get("selected_places") or [{}])[0].get("name"))
            for item in (day.get("items") or [])
            if _normalize_text((item.get("selected_places") or [{}])[0].get("name"))
        ]
    )
    if not place_names:
        return f"第{day_index}天我先给你留了一个可继续补点的空位，后面可以按你的偏好再细化。"

    lead_names = place_names[:6]
    if len(place_names) == 1:
        place_segment = f"重点放在{lead_names[0]}"
    else:
        place_segment = f"围绕{_join_chinese_list(lead_names)}来安排"

    detail_text = " ".join(_normalize_text(item.get("text")) for item in (day.get("items") or []))
    mood_fragments: List[str] = []
    if re.search(r"(博物馆|文化|古镇|古城|历史)", detail_text):
        mood_fragments.append("文化慢逛")
    if re.search(r"(小吃|餐饮|夜市|咖啡|下午茶)", detail_text):
        mood_fragments.append("吃喝和休息")
    if re.search(r"(夜景|夜间|晚上|越夜越美)", detail_text):
        mood_fragments.append("夜间体验")
    if re.search(r"(公园|步行街|citywalk|漫步|散步)", detail_text, flags=re.IGNORECASE):
        mood_fragments.append("城市慢逛")

    if mood_fragments:
        return f"第{day_index}天会{place_segment}，整体更偏{_join_chinese_list(_dedupe_keep_order(mood_fragments[:2]))}。"
    return f"第{day_index}天会{place_segment}，整体按顺路慢逛的节奏来走。"


def _select_chat_warnings(warnings: Optional[List[str]]) -> List[str]:
    high_signal: List[str] = []
    secondary: List[str] = []
    for warning in warnings or []:
        text = _normalize_text(warning).rstrip("。")
        if not text:
            continue
        if _is_operational_planner_warning(text):
            continue
        if any(token in text for token in ("额度", "未命中", "跨城市", "不够顺路", "已自动调整", "已调整")):
            high_signal.append(text)
        elif "很接近" in text or "多个" in text:
            secondary.append(text)
    selected = high_signal[:2]
    if not selected and secondary:
        selected.append(secondary[0])
    return _dedupe_keep_order(selected)


def _build_conversational_itinerary_reply(
    itinerary: Dict[str, Any],
    *,
    requirement_payload: Optional[Dict[str, Any]] = None,
    assumptions: str = "",
    warnings: Optional[List[str]] = None,
) -> str:
    days = list(itinerary.get("days") or [])
    city = _normalize_text(itinerary.get("city")) or _normalize_text((requirement_payload or {}).get("city"))
    day_count = len(days) or int((requirement_payload or {}).get("day_count") or 0)
    normalized_assumptions = _normalize_text(assumptions).rstrip("。")
    chat_assumptions = normalized_assumptions
    if chat_assumptions.startswith("默认按"):
        chat_assumptions = chat_assumptions[3:]
    chat_assumptions = re.sub(r"(来召回候选|做候选召回|进行候选召回|自动生成(?:首版)?行程)$", "", chat_assumptions).strip("，,、 ")

    intro = ""
    if normalized_assumptions.startswith("已在现有行程基础上应用你的修改"):
        intro = "我已经按你的修改重新校验并更新了这版行程。"
    elif normalized_assumptions.startswith("默认按") and chat_assumptions:
        intro = (
            f"我先按{chat_assumptions}的方式，帮你排了"
            f"{day_count or max(len(days), 1)}天"
            f"{city if city else ''}行程。"
        )
    elif normalized_assumptions:
        intro = normalized_assumptions + "。"
    elif day_count and city:
        intro = f"我先给你排了一版{day_count}天的{city}行程。"
    elif day_count:
        intro = f"我先给你排了一版{day_count}天的行程。"
    else:
        intro = "我先给你整理了一版行程。"

    lines = [intro]
    for day in days:
        lines.append(_summarize_chat_day(day))

    selected_warnings = _select_chat_warnings(warnings)
    if selected_warnings:
        lines.append(f"需要留意的是，{'；'.join(selected_warnings)}。")

    return "\n".join(line for line in lines if _normalize_text(line)).strip()


async def _generate_validated_itinerary_summary(
    message: str,
    conversation_context: str,
    requirement_payload: Dict[str, Any],
    itinerary: Dict[str, Any],
    planner_warnings: List[str],
    assumptions: str,
) -> str:
    prompt = [
        {
            "role": "system",
            "content": "你是中文旅游规划助手。请基于已经验证过的 itinerary 生成一段适合直接展示给用户的简洁说明，不要编造新地点。",
        },
        {
            "role": "user",
            "content": f"""请把下面这份已经过工具验证的 itinerary 总结成可直接展示给用户的文本。
要求：
1. 只使用输入里已有的地点名。
2. 开头先简短说明默认假设。
3. 按“第1天 / 第2天”分组输出，不要写“上午 / 中午 / 下午 / 晚上”这类时段标签。
4. 每个地点单独一行，格式尽量接近“- 地点 —— 简短理由”。
5. 保留“当天逻辑”和必要提示，文风简洁，适合前端直接显示。
6. 不要加 markdown 粗体。

用户消息：{message}
会话上下文：{conversation_context or "无"}
需求摘要：{json.dumps(requirement_payload, ensure_ascii=False)}
默认假设：{assumptions}
validator warnings：{json.dumps(planner_warnings[:5], ensure_ascii=False)}
validated itinerary：{json.dumps(itinerary, ensure_ascii=False)}""",
        },
    ]
    try:
        return await _request_text_completion(prompt, temperature=0.15)
    except Exception:
        return _render_itinerary_summary_text(itinerary, assumptions, planner_warnings)


async def _validate_existing_itinerary_draft(
    draft_itinerary: Dict[str, Any],
    requirement_payload: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
    itinerary = {
        "schema_version": PLANNER_SCHEMA_VERSION,
        "city": _normalize_text(requirement_payload.get("city")) or _normalize_text(draft_itinerary.get("city")) or AMAP_DEFAULT_CITY,
        "day_count_requested": draft_itinerary.get("day_count_requested") or requirement_payload.get("day_count"),
        "days": [],
        "workflow_trace": [],
        "planner_warnings": [],
        "candidate_backups": [],
        "validator_result": _empty_validator_result(),
    }
    backups: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for day in draft_itinerary.get("days") or []:
        day_payload = {
            "day_index": int(day.get("day_index") or 0),
            "title": _normalize_text(day.get("title")),
            "items": [],
            "manual_order_poi_ids": [],
        }
        if not day_payload["day_index"]:
            continue
        for item in day.get("items") or []:
            slot = _normalize_text(item.get("slot"))
            if not slot:
                continue
            selected_pool = list(item.get("selected_places") or [])
            selected_place: Optional[Dict[str, Any]] = None
            if selected_pool:
                first_selected = selected_pool[0]
                if parse_amap_location(first_selected.get("location")):
                    selected_place = _decorate_validated_place(
                        first_selected,
                        query=_normalize_text(first_selected.get("source_query")) or _normalize_text(first_selected.get("name")),
                        place_kind=_normalize_text(first_selected.get("place_kind")),
                        source=_normalize_text(first_selected.get("source")) or "validated_poi",
                        reason=_normalize_text(first_selected.get("resolve_note")),
                    )
            if not selected_place:
                candidate_rows = item.get("place_candidates") or []
                resolved = None
                for candidate in candidate_rows:
                    query = _normalize_text(candidate.get("query")) or _normalize_text(candidate.get("raw_query"))
                    if not query:
                        continue
                    result = await _resolve_workflow_candidate(
                        {
                            "query": query,
                            "kind": _normalize_text(candidate.get("intent_type")) == "generic_poi" and "food_area" or _infer_planner_place_kind(query, candidate.get("category_hint") or "", query),
                            "category_hint": _normalize_text(candidate.get("category_hint")),
                            "preferred_slots": [slot],
                        },
                        city=itinerary["city"],
                        radius_meters=int(requirement_payload.get("radius_meters") or AMAP_DEFAULT_RADIUS_METERS),
                        anchor_location=parse_amap_location(requirement_payload.get("anchor_location")),
                    )
                    warnings.extend(result.get("warnings", []))
                    if result.get("status") == "resolved" and isinstance(result.get("poi"), dict):
                        resolved = _decorate_validated_place(
                            result["poi"],
                            query=query,
                            place_kind=None,
                            source="validated_poi",
                        )
                        for alt in result.get("alternatives") or []:
                            if parse_amap_location(alt.get("location")):
                                backups.append(
                                    {
                                        "query": query,
                                        "reason": f"替代 {query}",
                                        "poi": _decorate_validated_place(alt, query=query, source="backup_candidate"),
                                    }
                                )
                        break
                selected_place = resolved
            if not selected_place:
                warnings.append(f"第{day_payload['day_index']}天 {slot} 未找到可落图坐标，已从正式行程排除。")
                continue
            reason = _normalize_text(selected_place.get("resolve_note")) or _normalize_text(item.get("text"))
            selected_place["time_slot"] = slot
            selected_place["why_here"] = reason
            day_payload["items"].append(
                {
                    "slot": slot,
                    "text": f"{selected_place.get('name')} —— {reason}" if reason else _normalize_text(selected_place.get("name")),
                    "place_candidates": [
                        {
                            "query": _normalize_text(selected_place.get("source_query")) or _normalize_text(selected_place.get("name")),
                            "raw_query": _normalize_text(selected_place.get("source_query")) or _normalize_text(selected_place.get("name")),
                            "aliases": [],
                            "category_hint": _normalize_text(selected_place.get("category")),
                            "intent_type": "explicit_poi",
                            "selection_mode": "tool_validated",
                            "selected_places": [selected_place],
                        }
                    ],
                    "selected_places": [selected_place],
                }
            )
        day_payload["items"] = sorted(day_payload["items"], key=lambda row: _slot_rank(row.get("slot") or ""))
        day_payload["manual_order_poi_ids"] = [
            _normalize_text((row.get("selected_places") or [{}])[0].get("poi_id"))
            for row in day_payload["items"]
            if _normalize_text((row.get("selected_places") or [{}])[0].get("poi_id"))
        ]
        itinerary["days"].append(day_payload)
    itinerary["candidate_backups"] = backups
    return itinerary, backups, _dedupe_keep_order([item for item in warnings if _normalize_text(item)])


async def _run_tool_using_chat_workflow(
    *,
    message: str,
    conversation_context: str,
    requirement_payload: Dict[str, Any],
    latest_itinerary_payload: Optional[Dict[str, Any]],
    edit_instruction: Optional[Dict[str, Any]],
    memory_profile: Dict[str, Any],
) -> Dict[str, Any]:
    workflow_trace: List[Dict[str, Any]] = []
    planner_warnings: List[str] = []
    requirement_v2 = _build_requirement_v2(requirement_payload, memory_profile)
    candidate_recall_result: Dict[str, Any] = {
        "schema_version": PLANNER_SCHEMA_VERSION,
        "status": "skipped",
        "assumptions": "",
        "candidates": [],
        "backup_candidates": [],
    }
    grounded_pois: List[Dict[str, Any]] = []

    start = perf_counter()
    workflow_trace.append(
        _make_workflow_trace_entry(
            "requirement_interpret",
            start,
            details={
                "city": _normalize_text(requirement_payload.get("city")) or AMAP_DEFAULT_CITY,
                "day_count": requirement_payload.get("day_count"),
                "must_have_count": len(requirement_payload.get("must_have") or []),
            },
        )
    )

    assumptions = ""
    candidate_backups: List[Dict[str, Any]] = []
    if edit_instruction and latest_itinerary_payload:
        edit_start = perf_counter()
        draft_itinerary = _apply_itinerary_edit_instruction(
            latest_itinerary_payload,
            message,
            latest_itinerary_payload.get("display_text") or "",
            requirement_payload=requirement_payload,
            context_text=conversation_context,
        ) or latest_itinerary_payload
        itinerary_payload, candidate_backups, edit_warnings = await _validate_existing_itinerary_draft(draft_itinerary, requirement_payload)
        grounded_pois = _collect_grounded_pois_from_itinerary(itinerary_payload)
        planner_warnings.extend(edit_warnings)
        assumptions = "已在现有行程基础上应用你的修改，并重新做了 POI 校验与顺路性检查。"
        workflow_trace.append(
            _make_workflow_trace_entry(
                "poi_grounding",
                edit_start,
                warnings=edit_warnings,
                details={"mode": "edit_revalidate", "day_count": len(itinerary_payload.get("days") or [])},
            )
        )
    else:
        recall_start = perf_counter()
        recall_payload = await _generate_candidate_recall(message, conversation_context, requirement_payload)
        assumptions = _normalize_text(recall_payload.get("assumptions"))
        candidate_recall_result = {
            "schema_version": PLANNER_SCHEMA_VERSION,
            "status": "ok",
            "assumptions": assumptions,
            "candidates": [
                {
                    "candidate_name": item.get("query"),
                    "kind": item.get("kind"),
                    "reason": item.get("reason"),
                    "preferred_slots": item.get("preferred_slots") or [],
                    "backup_queries": item.get("backup_queries") or [],
                }
                for item in (recall_payload.get("representative_candidates") or [])
            ],
            "backup_candidates": recall_payload.get("global_backups") or [],
        }
        workflow_trace.append(
            _make_workflow_trace_entry(
                "city_recall",
                recall_start,
                details={"candidate_count": len(recall_payload.get("representative_candidates") or [])},
            )
        )

        validation_start = perf_counter()
        validated_candidates, candidate_backups, validation_warnings = await _resolve_candidate_pool(
            recall_payload.get("representative_candidates") or [],
            requirement_payload,
        )
        validated_candidates = _supplement_validated_candidates(
            validated_candidates,
            candidate_backups,
            requirement_payload,
        )
        grounded_pois = [item.get("poi") for item in validated_candidates if isinstance(item.get("poi"), dict)]
        planner_warnings.extend(validation_warnings)
        workflow_trace.append(
            _make_workflow_trace_entry(
                "poi_grounding",
                validation_start,
                warnings=validation_warnings,
                status="ok" if validated_candidates else "failed",
                details={"validated_count": len(validated_candidates), "backup_count": len(candidate_backups)},
            )
        )

        planning_start = perf_counter()
        plan_payload = await _generate_day_segment_plan(
            message,
            conversation_context,
            requirement_payload,
            validated_candidates,
        )
        itinerary_payload, materialize_warnings = _materialize_validated_itinerary(
            plan_payload,
            validated_candidates,
            requirement_payload,
            candidate_backups=candidate_backups,
        )
        _enrich_itinerary_with_remaining_validated_candidates(
            itinerary_payload,
            validated_candidates,
            requirement_payload,
        )
        planner_warnings.extend(materialize_warnings)
        workflow_trace.append(
            _make_workflow_trace_entry(
                "planner",
                planning_start,
                warnings=materialize_warnings,
                details={"day_count": len(itinerary_payload.get("days") or [])},
            )
        )

    validator_start = perf_counter()
    planner_warnings.extend(_validate_and_repair_itinerary(itinerary_payload, requirement_payload))
    itinerary_payload["candidate_backups"] = candidate_backups
    itinerary_payload["grounded_pois"] = grounded_pois
    itinerary_payload["planner_warnings"] = _sanitize_planner_warnings_for_user(
        _dedupe_keep_order([item for item in planner_warnings if _normalize_text(item)])
    )
    itinerary_payload["schema_version"] = PLANNER_SCHEMA_VERSION
    itinerary_payload["requirement_v2"] = requirement_v2
    itinerary_payload["candidate_recall_result"] = candidate_recall_result
    itinerary_payload["memory_profile"] = memory_profile
    workflow_trace.append(
        _make_workflow_trace_entry(
            "validator_repair",
            validator_start,
            warnings=itinerary_payload["planner_warnings"][:6],
            details={
                "day_count": len(itinerary_payload.get("days") or []),
                "repair_count": len((itinerary_payload.get("validator_result") or {}).get("repairs") or []),
            },
        )
    )

    summary_start = perf_counter()
    summary_text = await _generate_validated_itinerary_summary(
        message,
        conversation_context,
        requirement_payload,
        itinerary_payload,
        itinerary_payload["planner_warnings"],
        assumptions,
    )
    workflow_trace.append(
        _make_workflow_trace_entry(
            "summary_generate",
            summary_start,
            details={"warning_count": len(itinerary_payload["planner_warnings"])},
        )
    )
    itinerary_payload["workflow_trace"] = workflow_trace
    itinerary_payload["display_text"] = _sanitize_reply_text(summary_text)
    assistant_text = _sanitize_reply_text(
        _build_conversational_itinerary_reply(
            itinerary_payload,
            requirement_payload=requirement_payload,
            assumptions=assumptions,
            warnings=itinerary_payload["planner_warnings"],
        )
    )
    return {
        "schema_version": PLANNER_SCHEMA_VERSION,
        "assistant_text": assistant_text,
        "display_text": itinerary_payload["display_text"],
        "validated_itinerary": itinerary_payload,
        "requirement_v2": requirement_v2,
        "candidate_recall_result": candidate_recall_result,
        "grounded_pois": grounded_pois,
        "validator_result": itinerary_payload.get("validator_result") or _empty_validator_result(),
        "memory_profile": memory_profile,
        "workflow_trace": workflow_trace,
        "planner_warnings": itinerary_payload["planner_warnings"],
        "candidate_backups": candidate_backups,
    }


def _parse_message_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "role": row["role"],
        "message_type": row["message_type"],
        "content": row["content"],
        "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else None,
        "created_at": row["created_at"],
    }


def _parse_user_note_row(row: sqlite3.Row) -> Dict[str, Any]:
    poi = json.loads(row["poi_json"]) if row["poi_json"] else None
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "city": row["city"],
        "query": row["query"],
        "place_name": row["place_name"],
        "rating": row["rating"],
        "comment": row["comment"],
        "poi": poi,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _parse_session_row(row: sqlite3.Row) -> Dict[str, Any]:
    result = {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "current_requirement_version": row["current_requirement_version"],
        "current_itinerary_version": row["current_itinerary_version"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    keys = set(row.keys())
    if "latest_message" in keys:
        result["latest_message"] = row["latest_message"]
    if "latest_message_role" in keys:
        result["latest_message_role"] = row["latest_message_role"]
    if "message_count" in keys:
        result["message_count"] = row["message_count"]
    if "latest_requirement_id" in keys:
        result["latest_requirement_id"] = row["latest_requirement_id"]
    if "latest_itinerary_id" in keys:
        result["latest_itinerary_id"] = row["latest_itinerary_id"]
    return result


def _parse_requirement_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "version": row["version"],
        "raw_input": row["raw_input"],
        "strategy": row["strategy"],
        "structured_payload": json.loads(row["structured_payload_json"]) if row["structured_payload_json"] else None,
        "created_at": row["created_at"],
    }


def _parse_itinerary_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "version": row["version"],
        "requirement_id": row["requirement_id"],
        "generator_type": row["generator_type"],
        "content": json.loads(row["content_json"]) if row["content_json"] else None,
        "created_at": row["created_at"],
    }


def _get_session_or_404(conn: sqlite3.Connection, session_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="session not found")
    return row


def _get_latest_itinerary_row(conn: sqlite3.Connection, session_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM itineraries
        WHERE session_id = ?
        ORDER BY version DESC, created_at DESC, rowid DESC
        LIMIT 1
        """,
        (session_id,),
    ).fetchone()


def _save_itinerary_snapshot(
    conn: sqlite3.Connection,
    session_id: str,
    content: Dict[str, Any],
    requirement_id: Optional[str] = None,
    generator_type: str = "chat_memory",
) -> Dict[str, Any]:
    session = _get_session_or_404(conn, session_id)
    version = int(session["current_itinerary_version"] or 0) + 1
    itinerary_id = _new_id("iti")
    created_at = _now_iso()
    conn.execute(
        """
        INSERT INTO itineraries (id, session_id, version, requirement_id, generator_type, content_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            itinerary_id,
            session_id,
            version,
            requirement_id,
            generator_type,
            json.dumps(content, ensure_ascii=False),
            created_at,
        ),
    )
    conn.execute(
        "UPDATE sessions SET current_itinerary_version = ?, updated_at = ? WHERE id = ?",
        (version, created_at, session_id),
    )
    row = conn.execute("SELECT * FROM itineraries WHERE id = ?", (itinerary_id,)).fetchone()
    return _parse_itinerary_row(row)


SLOT_ORDER: List[str] = ["上午", "中午", "下午", "晚上", "傍晚", "早上", "午后", "夜里", "夜间", "清晨", "凌晨"]


def _extract_day_reference(text: str) -> Optional[int]:
    match = re.search(r"第\s*([0-9一二两三四五六七八九十]+)\s*天", _normalize_text(text))
    if not match:
        return None
    return _parse_day_count_token(match.group(1))


def _extract_slot_reference(text: str) -> Optional[str]:
    source = _normalize_text(text)
    for slot in SLOT_ORDER:
        if slot in source:
            return slot
    return None


def _normalize_place_lookup_text(text: str) -> str:
    value = _simplify_generic_place_query(text)
    if value:
        return value
    value = _normalize_itinerary_place(_strip_parenthetical_segments(text))
    value = re.sub(r"(?:候选|可选)$", "", value)
    return value.strip(" ，。；：:")


def _place_name_matches(left: str, right: str) -> bool:
    left_text = _normalize_place_lookup_text(left)
    right_text = _normalize_place_lookup_text(right)
    if not left_text or not right_text:
        return False
    return left_text == right_text or left_text in right_text or right_text in left_text


def _iter_itinerary_items(itinerary: Dict[str, Any]) -> Iterable[Tuple[Dict[str, Any], Dict[str, Any]]]:
    for day in itinerary.get("days") or []:
        for item in day.get("items") or []:
            yield day, item


def _pick_default_day_index(itinerary: Dict[str, Any], requested_day_index: Optional[int] = None) -> int:
    if requested_day_index and requested_day_index > 0:
        return requested_day_index
    days = itinerary.get("days") or []
    if days:
        first_day_index = int(days[0].get("day_index") or 1)
        return first_day_index if first_day_index > 0 else 1
    requested_day_count = int(itinerary.get("day_count_requested") or 0)
    return requested_day_count if requested_day_count > 0 else 1


def _ensure_itinerary_day(itinerary: Dict[str, Any], day_index: int) -> Dict[str, Any]:
    for day in itinerary.get("days") or []:
        if int(day.get("day_index") or 0) == int(day_index):
            return day
    day = {"day_index": day_index, "title": f"第{day_index}天", "items": []}
    itinerary.setdefault("days", []).append(day)
    itinerary["days"] = sorted(
        itinerary.get("days") or [],
        key=lambda item: int(item.get("day_index") or 0) or 999,
    )
    return day


def _ensure_itinerary_slot(day: Dict[str, Any], slot: str) -> Dict[str, Any]:
    for item in day.get("items") or []:
        if _normalize_text(item.get("slot")) == _normalize_text(slot):
            return item
    item = {"slot": slot, "text": "", "place_candidates": [], "selected_places": []}
    day.setdefault("items", []).append(item)
    rank = {name: index for index, name in enumerate(SLOT_ORDER)}
    day["items"] = sorted(
        day.get("items") or [],
        key=lambda row: rank.get(_normalize_text(row.get("slot")), len(rank)),
    )
    return item


def _append_candidate_to_item(item: Dict[str, Any], raw_place: str) -> None:
    query = _normalize_itinerary_place(_strip_parenthetical_segments(raw_place))
    payload = _build_place_candidate_payload(raw_place, query)
    candidates = item.setdefault("place_candidates", [])
    for existing in candidates:
        if _place_name_matches(existing.get("query") or "", payload.get("query") or ""):
            return
    candidates.append(payload)
    if not _normalize_text(item.get("text")):
        label = payload.get("raw_query") or payload.get("query") or raw_place
        if payload.get("intent_type") == "generic_poi":
            item["text"] = f"{label} —— 待从高德候选中选择"
        else:
            item["text"] = f"{label} —— 待定位"


def _remove_place_from_item(item: Dict[str, Any], target_place: str, target_poi_id: str = "") -> bool:
    removed = False
    normalized_poi_id = _normalize_text(target_poi_id)
    if not target_place and not normalized_poi_id:
        return False

    kept_selected: List[Dict[str, Any]] = []
    for selected in item.get("selected_places") or []:
        selected_poi_id = _normalize_text(selected.get("poi_id"))
        if (
            normalized_poi_id and selected_poi_id == normalized_poi_id
        ) or _place_name_matches(selected.get("name") or "", target_place):
            removed = True
            continue
        kept_selected.append(selected)
    item["selected_places"] = kept_selected

    kept_candidates: List[Dict[str, Any]] = []
    for candidate in item.get("place_candidates") or []:
        candidate_hits = (
            (bool(target_place) and _place_name_matches(candidate.get("query") or "", target_place))
            or (bool(target_place) and _place_name_matches(candidate.get("raw_query") or "", target_place))
            or (bool(target_place) and any(_place_name_matches(alias, target_place) for alias in (candidate.get("aliases") or [])))
        )
        candidate_selected_raw = candidate.get("selected_places")
        candidate_selected = list(candidate_selected_raw or [])
        filtered_selected = [
            selected for selected in candidate_selected
            if not (
                (normalized_poi_id and _normalize_text(selected.get("poi_id")) == normalized_poi_id)
                or _place_name_matches(selected.get("name") or "", target_place)
            )
        ]
        if candidate_hits:
            removed = True
            continue
        if candidate_selected_raw is not None and len(filtered_selected) != len(candidate_selected):
            removed = True
            if filtered_selected:
                candidate["selected_places"] = filtered_selected
            else:
                continue
        kept_candidates.append(candidate)
    item["place_candidates"] = kept_candidates
    return removed


def _remove_query_from_itinerary(itinerary: Dict[str, Any], target_place: str) -> bool:
    removed = False
    if not target_place:
        return False
    for _, item in _iter_itinerary_items(itinerary):
        if _remove_place_from_item(item, target_place):
            removed = True
    return removed


def _find_edit_target_slot(
    itinerary: Dict[str, Any],
    day_index: Optional[int] = None,
    slot: Optional[str] = None,
    target_place: str = "",
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    scoped_items: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for day, item in _iter_itinerary_items(itinerary):
        if day_index and int(day.get("day_index") or 0) != int(day_index):
            continue
        if slot and _normalize_text(item.get("slot")) != _normalize_text(slot):
            continue
        scoped_items.append((day, item))
    if target_place:
        for day, item in scoped_items:
            snapshot = {
                **item,
                "place_candidates": [json.loads(json.dumps(candidate)) for candidate in (item.get("place_candidates") or [])],
                "selected_places": [json.loads(json.dumps(place)) for place in (item.get("selected_places") or [])],
            }
            if _remove_place_from_item(snapshot, target_place):
                return day, item
    if scoped_items:
        return scoped_items[0]
    return None


def _parse_itinerary_edit_instruction(message: str, context_text: str = "") -> Optional[Dict[str, Any]]:
    text = _normalize_text(message)
    context = _normalize_text(context_text)
    combined = "\n".join(part for part in [text, context] if part)
    if not combined:
        return None

    day_index = _extract_day_reference(text) or _extract_day_reference(context)
    slot = _extract_slot_reference(text) or _extract_slot_reference(context)

    replace_match = re.search(r"把(.+?)换成(.+)$", text)
    if replace_match:
        return {
            "action": "replace",
            "day_index": day_index,
            "slot": slot,
            "target_place": _normalize_text(replace_match.group(1)),
            "replacement_place": _normalize_text(replace_match.group(2)),
        }

    if any(token in text for token in ("删掉", "删除", "去掉")):
        delete_source = re.split(r"(?:删掉|删除|去掉)", text, maxsplit=1)[0]
        delete_source = re.sub(r"^(?:请|帮我|麻烦|把|请把|帮我把)\s*", "", delete_source)
        target_place = _normalize_place_lookup_text(delete_source)
        if target_place:
            return {
                "action": "delete",
                "day_index": day_index,
                "slot": slot,
                "target_place": target_place,
            }
        delete_match = re.search(r"把(.+?)(?:删掉|删除|去掉)", text)
        if delete_match:
            return {
                "action": "delete",
                "day_index": day_index,
                "slot": slot,
                "target_place": _normalize_place_lookup_text(delete_match.group(1)),
            }
        delete_match = re.search(r"(?:删掉|删除|去掉)(.+)$", text)
        if delete_match:
            return {
                "action": "delete",
                "day_index": day_index,
                "slot": slot,
                "target_place": _normalize_place_lookup_text(delete_match.group(1)),
            }

    add_match = re.search(r"(?:加个|加一个|增加一个|增加|补个|补一个|再来个)(.+)$", text)
    if add_match:
        return {
            "action": "add",
            "day_index": day_index,
            "slot": slot,
            "place": _normalize_text(add_match.group(1)),
        }

    return None


def _apply_itinerary_edit_instruction(
    previous_itinerary: Optional[Dict[str, Any]],
    message: str,
    assistant_text: str,
    requirement_payload: Optional[Dict[str, Any]] = None,
    context_text: str = "",
) -> Optional[Dict[str, Any]]:
    if not previous_itinerary:
        return None
    instruction = _parse_itinerary_edit_instruction(message, context_text=context_text)
    if not instruction:
        return None

    itinerary = json.loads(json.dumps(previous_itinerary))
    requirement_payload = requirement_payload or {}
    itinerary["city"] = _normalize_text(requirement_payload.get("city")) or itinerary.get("city") or AMAP_DEFAULT_CITY
    itinerary["day_count_requested"] = requirement_payload.get("day_count") or itinerary.get("day_count_requested")
    itinerary["display_text"] = _sanitize_reply_text(assistant_text)

    action = instruction.get("action")
    day_index = _pick_default_day_index(itinerary, instruction.get("day_index"))
    slot = _normalize_text(instruction.get("slot")) or "下午"

    if action == "add":
        _remove_query_from_itinerary(itinerary, _normalize_text(instruction.get("place")))
        day = _ensure_itinerary_day(itinerary, day_index)
        item = _ensure_itinerary_slot(day, slot)
        _append_candidate_to_item(item, _normalize_text(instruction.get("place")))
        return itinerary

    target_place = _normalize_text(instruction.get("target_place"))
    target = _find_edit_target_slot(
        itinerary,
        day_index=instruction.get("day_index"),
        slot=instruction.get("slot"),
        target_place=target_place,
    )

    if action == "delete":
        _remove_query_from_itinerary(itinerary, target_place)
        if target:
            _, item = target
            _remove_place_from_item(item, target_place)
        return itinerary

    if action == "replace":
        replacement_place = _normalize_text(instruction.get("replacement_place"))
        if target:
            _, item = target
        else:
            day = _ensure_itinerary_day(itinerary, day_index)
            item = _ensure_itinerary_slot(day, slot)
        if target_place:
            _remove_query_from_itinerary(itinerary, target_place)
        _append_candidate_to_item(item, replacement_place)
        return itinerary

    return None


def _build_itinerary_edit_acknowledgement(
    instruction: Dict[str, Any],
    previous_itinerary: Optional[Dict[str, Any]],
    edited_itinerary: Optional[Dict[str, Any]],
) -> str:
    action = _normalize_text(instruction.get("action"))
    day_index = instruction.get("day_index")
    slot = _normalize_text(instruction.get("slot"))
    target_place = _normalize_text(instruction.get("target_place"))
    replacement_place = _normalize_text(instruction.get("replacement_place"))
    place = _normalize_text(instruction.get("place"))

    day_prefix = f"第{day_index}天" if day_index else ""
    slot_prefix = f"{slot}" if slot else ""
    scope_prefix = "、".join(part for part in [day_prefix, slot_prefix] if part)
    scope_text = f"{scope_prefix}的" if scope_prefix else ""

    def _structure_only(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        data = json.loads(json.dumps(payload or {}, ensure_ascii=False))
        data.pop("display_text", None)
        return data

    changed = json.dumps(_structure_only(previous_itinerary), ensure_ascii=False, sort_keys=True) != json.dumps(
        _structure_only(edited_itinerary), ensure_ascii=False, sort_keys=True
    )

    if action == "add":
        if changed:
            target = place or "新地点"
            return f"已按你的要求在{scope_text}{target}加入行程。"
        target = place or "该地点"
        return f"我在当前行程里没有找到可修改的位置，{target}暂时还没有加入。"

    if action == "delete":
        if changed:
            target = target_place or "该地点"
            return f"已按你的要求从当前行程里删除{scope_text}{target}。"
        target = target_place or "该地点"
        return f"当前行程里没有找到{target}，我先保持原计划不变。"

    if action == "replace":
        if changed:
            target = target_place or "原地点"
            replacement = replacement_place or "新地点"
            return f"已按你的要求把{scope_text}{target}替换成{replacement}。"
        target = target_place or "原地点"
        return f"当前行程里没有找到{target}，暂时没法替换。"

    return "已按你的要求更新行程。"


def _insert_message(
    conn: sqlite3.Connection,
    session_id: str,
    role: str,
    content: str,
    message_type: str = "text",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    message_id = _new_id("msg")
    created_at = _now_iso()
    conn.execute(
        """
        INSERT INTO conversation_messages (id, session_id, role, message_type, content, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message_id,
            session_id,
            role,
            message_type,
            content,
            json.dumps(metadata, ensure_ascii=False) if metadata else None,
            created_at,
        ),
    )
    row = conn.execute(
        "SELECT * FROM conversation_messages WHERE id = ?",
        (message_id,),
    ).fetchone()
    return _parse_message_row(row)


def _list_messages(conn: sqlite3.Connection, session_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM conversation_messages
        WHERE session_id = ?
        ORDER BY created_at ASC, rowid ASC
        LIMIT ?
        """,
        (session_id, limit),
    ).fetchall()
    return [_parse_message_row(row) for row in rows]


def _insert_user_note(
    conn: sqlite3.Connection,
    session_id: str,
    *,
    city: str,
    query: str,
    place_name: str,
    rating: Optional[int],
    comment: str,
    poi: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    note_id = _new_id("note")
    created_at = _now_iso()
    normalized_rating = int(rating) if isinstance(rating, int) and 1 <= int(rating) <= 5 else None
    conn.execute(
        """
        INSERT INTO user_place_notes (id, session_id, city, query, place_name, rating, comment, poi_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            note_id,
            session_id,
            city or None,
            query,
            place_name,
            normalized_rating,
            comment or None,
            json.dumps(poi, ensure_ascii=False) if isinstance(poi, dict) else None,
            created_at,
            created_at,
        ),
    )
    row = conn.execute("SELECT * FROM user_place_notes WHERE id = ?", (note_id,)).fetchone()
    return _parse_user_note_row(row)


def _list_user_notes(conn: sqlite3.Connection, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM user_place_notes
        WHERE session_id = ?
        ORDER BY updated_at DESC, created_at DESC, rowid DESC
        LIMIT ?
        """,
        (session_id, limit),
    ).fetchall()
    return [_parse_user_note_row(row) for row in rows]


async def _request_text_completion(
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.2,
) -> str:
    _refresh_runtime_env()
    text_model = _resolve_config("TEXT_MODEL", "OPENAI_MODEL", "deepseek-ai/DeepSeek-V3.2")
    text_api_key = _resolve_config("TEXT_API_KEY", "OPENAI_API_KEY", "ms-4ecca729-328f-4e74-9d9b-39fa76e5b56b")
    text_api_base = _resolve_config("TEXT_API_BASE", "OPENAI_BASE_URL", "https://api-inference.modelscope.cn/v1/")

    if not _normalize_text(text_api_base):
        raise HTTPException(status_code=503, detail="TEXT_API_BASE is not configured")

    url = text_api_base.rstrip("/") + "/chat/completions"
    destination_hint = _extract_destination_hint(message)

    async def _request_reply(messages: List[Dict[str, str]]) -> Dict[str, Any]:
        payload = {
            "model": text_model,
            "messages": messages,
            "temperature": temperature,
        }
        headers = {"Content-Type": "application/json"}
        if _normalize_text(text_api_key):
            headers["Authorization"] = f"Bearer {text_api_key}"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    try:
        data = await _request_reply(messages)
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or str(exc)
        raise HTTPException(status_code=502, detail=f"llm http error: {detail}") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"llm request failed: {exc}") from exc

    choices = data.get("choices") if isinstance(data, dict) else None
    assistant_text = ""
    if isinstance(choices, list) and choices:
        content = choices[0].get("message", {}).get("content")
        if isinstance(content, str) and content.strip():
            assistant_text = _sanitize_reply_text(content)

    if assistant_text:
        return assistant_text

    if isinstance(data, dict):
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        raise HTTPException(
            status_code=502,
            detail=(
                f"llm returned no usable content for model {text_model}. "
                f"choices={type(choices).__name__}, "
                f"prompt_tokens={usage.get('prompt_tokens')}, "
                f"completion_tokens={usage.get('completion_tokens')}"
            ),
        )

    raise HTTPException(status_code=502, detail=f"llm returned unexpected payload for model {text_model}")


async def _generate_text_reply(
    message: str,
    conversation_context: str = "",
    requirement_context: Optional[Dict[str, Any]] = None,
) -> str:
    if not _normalize_text(message):
        raise HTTPException(status_code=400, detail="message is required")

    destination_hint = _extract_destination_hint(message)
    messages: List[Dict[str, str]] = [
        {
            "role": "system",
            "content": _build_travel_system_prompt(),
        }
    ]
    if _normalize_text(conversation_context):
        messages.append(
            {
                "role": "system",
                "content": f"这是用户提供的会话上下文，仅供参考：{conversation_context.strip()}",
            }
        )
    messages.append(
        {
            "role": "user",
            "content": _build_travel_user_prompt(message, destination_hint, requirement_context=requirement_context),
        }
    )
    return await _request_text_completion(messages, temperature=0.2)


def _get_amap_web_service_key() -> str:
    return _normalize_text(AMAP_WEB_SERVICE_KEY) or _normalize_text(AMAP_BROWSER_KEY)



def _build_amap_request_url(url: str, params: Dict[str, str]) -> str:
    return f"{url}?{urlencode(params, quote_via=quote, safe=',:')}"


def _is_map_quota_warning(value: Any) -> bool:
    text = _normalize_text(value).upper()
    if not text:
        return False
    return any(
        token in text
        for token in (
            "USER_DAILY_QUERY_OVER_LIMIT",
            "DAILY_QUERY_OVER_LIMIT",
            "OVER_LIMIT",
            "QUOTA",
        )
    )


def _is_operational_planner_warning(value: Any) -> bool:
    text = _normalize_text(value)
    if not text:
        return False
    return _is_map_quota_warning(text) or "CUQPS_HAS_EXCEEDED_THE_LIMIT" in text


def _sanitize_planner_warnings_for_user(warnings: List[str]) -> List[str]:
    cleaned: List[str] = []
    has_quota_warning = any(_is_operational_planner_warning(item) for item in warnings)
    no_match_added = False
    multi_match_added = False

    for warning in warnings:
        text = _normalize_text(warning)
        if not text:
            continue
        if _is_operational_planner_warning(text):
            continue
        if text == "multiple close poi matches":
            if not multi_match_added:
                cleaned.append("有些地点搜到了多个很接近的 POI，系统已先保留更稳妥的候选。")
                multi_match_added = True
            continue
        if text in {
            "no poi match",
            "no poi match within requested city",
            "no poi match after filtering school-like results",
        }:
            if has_quota_warning:
                continue
            if not no_match_added:
                cleaned.append("部分地点暂未命中可落图 POI，系统已先保留可用结果。")
                no_match_added = True
            continue
        if text.startswith("no poi matched city constraint:"):
            if has_quota_warning:
                continue
            if not no_match_added:
                cleaned.append("部分地点未命中当前城市范围内的可落图 POI。")
                no_match_added = True
            continue
        cleaned.append(text)

    return _dedupe_keep_order([item for item in cleaned if _normalize_text(item)])


def _amap_response_to_items(
    data: Any,
    *,
    category: Optional[str],
    city: str,
    user_location: Optional[Dict[str, float]],
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    if not isinstance(data, dict):
        return [], "invalid AMap response"

    pois = data.get("pois")
    if not isinstance(pois, list):
        return [], _normalize_text(data.get("info")) or "invalid AMap response"

    items: List[Dict[str, Any]] = []
    for poi in pois:
        if not isinstance(poi, dict):
            continue
        normalized = normalize_amap_poi_candidate(poi, category)
        if not normalized:
            continue
        if city and not _matches_city_constraint(normalized, city):
            continue
        if user_location and normalized.get("location"):
            normalized["distance_meters"] = _distance_between_points(user_location, normalized["location"])
        items.append(normalized)

    items.sort(
        key=lambda item: (
            item.get("distance_meters") if isinstance(item.get("distance_meters"), (int, float)) else 10**12,
            item.get("name") or "",
        )
    )
    return items, None


async def _fetch_amap_json_with_httpx(
    client: Any,
    url: str,
    params: Dict[str, str],
) -> Dict[str, Any]:
    if client is not None and hasattr(client, "get"):
        try:
            response = await client.get(url, params=params, headers=AMAP_BROWSER_HEADERS)
        except TypeError:
            response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async with httpx.AsyncClient(
        timeout=AMAP_SEARCH_TIMEOUT_SECONDS,
        headers=AMAP_BROWSER_HEADERS,
        follow_redirects=True,
        trust_env=False,
    ) as http_client:
        response = await http_client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def _fetch_amap_json_with_curl(url: str, params: Dict[str, str]) -> Dict[str, Any]:
    curl_path = shutil.which("curl.exe") or shutil.which("curl")
    if not curl_path:
        raise FileNotFoundError("curl.exe is not available")

    request_url = _build_amap_request_url(url, params)
    base_command = [
        curl_path,
        "--silent",
        "--show-error",
        "--location",
    ]
    for header_name, header_value in AMAP_BROWSER_HEADERS.items():
        base_command.extend(["-H", f"{header_name}: {header_value}"])
    base_command.append(request_url)

    def _run_command(include_compressed: bool) -> subprocess.CompletedProcess[str]:
        command = list(base_command)
        if include_compressed:
            command.insert(4, "--compressed")
        return subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=AMAP_SEARCH_TIMEOUT_SECONDS,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def _run() -> Dict[str, Any]:
        completed = _run_command(include_compressed=True)
        stderr = _normalize_text(completed.stderr)
        if completed.returncode != 0 and "doesn't support this" in stderr and "--compressed" in stderr:
            completed = _run_command(include_compressed=False)
        if completed.returncode != 0:
            stderr = _normalize_text(completed.stderr) or f"curl exited with {completed.returncode}"
            raise RuntimeError(stderr)
        raw_text = _normalize_text(completed.stdout)
        if not raw_text:
            return {}
        return json.loads(raw_text)

    return await asyncio.to_thread(_run)


def _distance_between_points(a: Dict[str, float], b: Dict[str, float]) -> Optional[float]:
    try:
        lng1 = float(a.get("lng"))
        lat1 = float(a.get("lat"))
        lng2 = float(b.get("lng"))
        lat2 = float(b.get("lat"))
    except (TypeError, ValueError, AttributeError):
        return None

    from math import asin, cos, radians, sin, sqrt

    radius = 6371000
    d_lat = radians(lat2 - lat1)
    d_lng = radians(lng2 - lng1)
    lat1_r = radians(lat1)
    lat2_r = radians(lat2)
    h = sin(d_lat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(d_lng / 2) ** 2
    return round(2 * radius * asin(sqrt(h)))


def parse_amap_location(value: Any) -> Optional[Dict[str, float]]:
    if value is None:
        return None
    if isinstance(value, dict):
        try:
            return {"lng": float(value.get("lng")), "lat": float(value.get("lat"))}
        except (TypeError, ValueError):
            nested = value.get("location") or value.get("point")
            return parse_amap_location(nested)
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return {"lng": float(value[0]), "lat": float(value[1])}
        except (TypeError, ValueError):
            return None
    text = _normalize_text(value)
    if not text or "," not in text:
        return None
    parts = [part.strip() for part in text.split(",")]
    if len(parts) < 2:
        return None
    try:
        return {"lng": float(parts[0]), "lat": float(parts[1])}
    except ValueError:
        return None


def parse_amap_polyline(value: Any) -> List[Dict[str, float]]:
    if not value:
        return []
    if isinstance(value, list):
        points: List[Dict[str, float]] = []
        for item in value:
            location = parse_amap_location(item)
            if location:
                points.append(location)
        return points
    text = _normalize_text(value)
    if not text:
        return []
    points: List[Dict[str, float]] = []
    for pair in text.split(";"):
        location = parse_amap_location(pair)
        if location:
            points.append(location)
    return points


def _infer_place_kind(name: str, type_text: str, keyword: str, category_hint: Optional[str]) -> str:
    source = f"{name} {type_text} {keyword} {category_hint or ''}".lower()
    if any(token in source for token in ("hotel", "宾馆", "旅馆", "住宿", "民宿")):
        return "lodging"
    if any(token in source for token in ("咖啡", "cafe")):
        return "cafe"
    if any(token in source for token in ("夜景", "夜游", "夜市")):
        return "night_view"
    if any(token in source for token in ("商场", "shopping", "mall")):
        return "shopping"
    if any(token in source for token in ("地铁", "公交", "车站", "机场", "火车站", "高铁", "汽车站")):
        return "transport"
    if any(token in source for token in ("景", "公园", "景区", "古镇", "古城", "博物馆", "地标", "广场")):
        return "attraction"
    if any(token in source for token in ("美食", "餐", "饭", "小吃", "烧烤", "火锅", "夜宵")):
        return "food_poi"
    if "search" in source or "查询" in source:
        return "search_request"
    return category_hint or "generic_term"


def _infer_route_role(place_kind: str, search_mode: Optional[str] = None) -> str:
    if place_kind == "lodging":
        return "lodging"
    if place_kind in {"cafe", "food_poi", "food_area"}:
        return "meal_stop"
    if place_kind == "night_view":
        return "night_stop"
    if place_kind == "transport":
        return "search_only"
    if place_kind in {"search_request", "generic_term"}:
        return "search_only"
    if search_mode == "fallback":
        return "backup"
    return "anchor"


def normalize_amap_poi_candidate(poi: Dict[str, Any], category: Optional[str]):
    location = parse_amap_location(poi.get("location"))
    if not location:
        return None
    name = _normalize_text(poi.get("name"))
    poi_type = _normalize_text(poi.get("type"))
    poi_typecode = _normalize_text(poi.get("typecode"))
    place_kind = _infer_place_kind(name, f"{poi_type} {poi_typecode}", name, category)
    distance_value = poi.get("distance")
    try:
        distance_meters = float(distance_value) if distance_value not in (None, "") else None
    except (TypeError, ValueError):
        distance_meters = None
    return {
        "poi_id": _normalize_text(poi.get("id") or poi.get("poi_id") or poi.get("uid")),
        "name": name,
        "category": category or poi_type or place_kind,
        "place_kind": place_kind,
        "route_role": _infer_route_role(place_kind),
        "address": _normalize_text(poi.get("address")),
        "location": location,
        "city": _normalize_text(poi.get("cityname")),
        "district": _normalize_text(poi.get("adname")),
        "type": poi_type,
        "typecode": poi_typecode,
        "source": "amap_poi",
        "distance_meters": distance_meters,
    }


def _normalize_admin_name(value: Any) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    text = re.sub(r"(特别行政区|自治区|自治州|地区|盟|省|市|区|县|旗)$", "", text)
    return text.strip()


def _matches_city_constraint(item: Dict[str, Any], city: str) -> bool:
    requested_city = _normalize_admin_name(city)
    if not requested_city:
        return True
    raw_fields = [
        _normalize_text(item.get("city")),
        _normalize_text(item.get("district")),
        _normalize_text(item.get("address")),
        _normalize_text(item.get("name")),
    ]
    normalized_fields = [_normalize_admin_name(value) for value in raw_fields]
    for value in normalized_fields:
        if value and (requested_city in value or value in requested_city):
            return True
    for value in raw_fields:
        if value and requested_city in value:
            return True
    return False


async def search_amap_poi(client: Any, task: Dict[str, Any]) -> Dict[str, Any]:
    key = _get_amap_web_service_key()
    city = _sanitize_city_name(task.get("city"))
    keyword = _normalize_text(task.get("keyword"))
    category = _normalize_text(task.get("category")) or None
    search_mode = _normalize_text(task.get("search_mode")) or ""
    location_scope = _normalize_text(task.get("location_scope")) or ""
    region_name = _normalize_text(task.get("region_name")) or ""
    user_location = parse_amap_location(task.get("user_location")) or parse_amap_location(task.get("anchor_location"))
    radius_meters = int(task.get("radius_meters") or AMAP_DEFAULT_RADIUS_METERS)
    limit = max(1, min(25, int(task.get("limit") or 25)))
    warnings: List[str] = []

    if not key:
        return {"tool": "poi_search", "query": task, "data": [], "warnings": ["AMap web service key is not configured"]}

    effective_mode = search_mode or ("nearby" if user_location and location_scope != "city_only" else "region")
    effective_keyword = keyword or city or AMAP_DEFAULT_CITY

    params: Dict[str, str] = {
        "key": key,
        "keywords": effective_keyword,
        "offset": str(limit),
        "page": "1",
        "extensions": "all",
    }
    url = "https://restapi.amap.com/v3/place/text"
    if effective_mode == "nearby" and user_location:
        url = "https://restapi.amap.com/v3/place/around"
        params["location"] = f"{user_location['lng']},{user_location['lat']}"
        params["radius"] = str(radius_meters)
    else:
        effective_city = city or region_name or AMAP_DEFAULT_CITY
        if effective_city:
            params["city"] = effective_city
            params["citylimit"] = "true"
        if region_name:
            params["keywords"] = f"{region_name} {params['keywords']}".strip()

    data: Any = None
    httpx_error: Optional[str] = None
    curl_error: Optional[str] = None

    try:
        data = await _fetch_amap_json_with_httpx(client, url, params)
    except Exception as exc:
        httpx_error = _normalize_text(exc)

    items, response_warning = _amap_response_to_items(
        data,
        category=category,
        city=city,
        user_location=user_location,
    )

    if not items and _is_map_quota_warning(response_warning):
        warnings.append(response_warning or "USER_DAILY_QUERY_OVER_LIMIT")
        if httpx_error:
            warnings.append(f"httpx request failed: {httpx_error}")
        return {"tool": "poi_search", "query": task, "data": [], "warnings": warnings}

    if not items:
        try:
            data = await _fetch_amap_json_with_curl(url, params)
        except Exception as exc:
            curl_error = _normalize_text(exc)
        else:
            items, response_warning = _amap_response_to_items(
                data,
                category=category,
                city=city,
                user_location=user_location,
            )

    if not items:
        if response_warning:
            warnings.append(response_warning)
        if httpx_error:
            warnings.append(f"httpx request failed: {httpx_error}")
        if curl_error:
            warnings.append(f"curl fallback failed: {curl_error}")
        return {"tool": "poi_search", "query": task, "data": [], "warnings": warnings}

    return {
        "tool": "poi_search",
        "query": task,
        "data": items,
        "warnings": warnings,
        "source": "amap",
        "search_mode": effective_mode,
    }


async def plan_amap_route(client: Any, points: List[Dict[str, float]]) -> Dict[str, Any]:
    if len(points) < 2:
        return {"mode": "straight", "segments": [], "polyline": [], "totalDistanceMeters": 0, "totalDurationSeconds": None}

    mode = "driving"
    if isinstance(client, str) and client.strip().lower() in {"driving", "walking"}:
        mode = client.strip().lower()

    key = _get_amap_web_service_key()
    if not key:
        segments = []
        total_distance = 0
        for index in range(len(points) - 1):
            origin = points[index]
            destination = points[index + 1]
            distance = _distance_between_points(origin, destination) or 0
            total_distance += distance
            segments.append(
                {
                    "fromPlaceId": f"point_{index}",
                    "toPlaceId": f"point_{index + 1}",
                    "distanceMeters": distance,
                    "durationSeconds": None,
                    "polyline": [origin, destination],
                    "provider": "amap",
                    "mode": "straight",
                }
            )
        return {
            "mode": "straight",
            "segments": segments,
            "polyline": [point for segment in segments for point in segment["polyline"]],
            "totalDistanceMeters": total_distance,
            "totalDurationSeconds": None,
            "warnings": ["AMap web service key is not configured"],
        }

    endpoint = "direction/driving" if mode == "driving" else "direction/walking"
    segments = []
    total_distance = 0
    total_duration: Optional[float] = 0

    async def _fetch_direction(origin: Dict[str, float], destination: Dict[str, float]) -> Dict[str, Any]:
        params = {
            "key": key,
            "origin": f"{origin['lng']},{origin['lat']}",
            "destination": f"{destination['lng']},{destination['lat']}",
        }
        if client is not None and hasattr(client, "get"):
            response = await client.get(f"https://restapi.amap.com/v3/{endpoint}", params=params)
            response.raise_for_status()
            return response.json()
        async with httpx.AsyncClient(timeout=AMAP_SEARCH_TIMEOUT_SECONDS) as http_client:
            response = await http_client.get(f"https://restapi.amap.com/v3/{endpoint}", params=params)
            response.raise_for_status()
            return response.json()

    for index in range(len(points) - 1):
        origin = points[index]
        destination = points[index + 1]
        try:
            data = await _fetch_direction(origin, destination)
        except httpx.HTTPError:
            data = {}
        route = data.get("route") if isinstance(data, dict) else None
        path = route.get("paths", [None])[0] if isinstance(route, dict) else None
        polyline: List[Dict[str, float]] = []
        if isinstance(path, dict):
            steps = path.get("steps") or []
            for step in steps:
                if isinstance(step, dict):
                    polyline.extend(parse_amap_polyline(step.get("polyline")))
        if not polyline:
            polyline = [origin, destination]
        distance: Optional[float] = None
        duration: Optional[float] = None
        if isinstance(path, dict):
            try:
                distance = float(path.get("distance")) if path.get("distance") is not None else None
            except (TypeError, ValueError):
                distance = None
            try:
                duration = float(path.get("duration")) if path.get("duration") is not None else None
            except (TypeError, ValueError):
                duration = None
        if distance is None:
            distance = _distance_between_points(origin, destination) or 0
        total_distance += int(distance)
        if duration is None:
            total_duration = None
        elif total_duration is not None:
            total_duration += duration
        segments.append(
            {
                "fromPlaceId": f"point_{index}",
                "toPlaceId": f"point_{index + 1}",
                "distanceMeters": int(distance),
                "durationSeconds": int(duration) if duration is not None else None,
                "polyline": polyline,
                "provider": "amap",
                "mode": mode,
            }
        )

    return {
        "mode": mode,
        "segments": segments,
        "polyline": [point for segment in segments for point in segment["polyline"]],
        "totalDistanceMeters": total_distance,
        "totalDurationSeconds": int(total_duration) if total_duration is not None else None,
    }


def _not_implemented(name: str) -> HTTPException:
    return HTTPException(
        status_code=501,
        detail=f"{name} is not implemented in the minimal core skeleton",
    )


def health() -> Dict[str, str]:
    _refresh_runtime_env()
    return {
        "service": "travel-agent-fastapi",
        "status": "ok",
        "mode": "minimal-core",
        "model": _resolve_config("TEXT_MODEL", "OPENAI_MODEL", "deepseek-ai/DeepSeek-V3.2"),
        "api_base": _resolve_config("TEXT_API_BASE", "OPENAI_BASE_URL", "https://api-inference.modelscope.cn/v1/"),
    }


def map_config() -> Dict[str, Any]:
    browser_enabled = bool(_normalize_text(AMAP_BROWSER_KEY))
    service_enabled = bool(_normalize_text(AMAP_WEB_SERVICE_KEY))
    return {
        "enabled": browser_enabled,
        "browserKey": AMAP_BROWSER_KEY if browser_enabled else "",
        "securityJsCode": AMAP_SECURITY_JS_CODE if browser_enabled else "",
        "webServiceEnabled": service_enabled,
        "defaultCity": AMAP_DEFAULT_CITY,
        "defaultCenter": AMAP_DEFAULT_CENTER,
        "searchRadiusMeters": AMAP_DEFAULT_RADIUS_METERS,
        "configHint": "Fill AMAP_BROWSER_KEY and AMAP_SECURITY_JS_CODE in fastapi/.env for map rendering; AMAP_WEB_SERVICE_KEY is used server-side for POI search.",
    }


async def map_search(body: Any) -> Dict[str, Any]:
    payload = body.model_dump() if hasattr(body, "model_dump") else dict(body or {})
    result = await search_amap_poi(None, payload)
    items = result.get("data") if isinstance(result, dict) else []
    return {
        "status": "ok" if items else "empty",
        "items": items,
        "warnings": result.get("warnings") if isinstance(result, dict) else [],
        "search_mode": result.get("search_mode") if isinstance(result, dict) else None,
        "query": result.get("query") if isinstance(result, dict) else payload,
    }


def _poi_match_score(keyword: str, item: Dict[str, Any], category_hint: Optional[str] = None) -> float:
    keyword_compact = _normalize_compact_text(keyword)
    name_compact = _normalize_compact_text(item.get("name"))
    address_compact = _normalize_compact_text(item.get("address"))
    if not keyword_compact or not name_compact:
        return 0.0
    score = 0.0
    if keyword_compact == name_compact:
        score = 1.0
    elif keyword_compact in name_compact:
        score = 0.92
    elif name_compact in keyword_compact:
        score = 0.86
    elif keyword_compact in address_compact:
        score = 0.74

    category_text = _normalize_text(item.get("category"))
    name_text = _normalize_text(item.get("name"))
    place_kind = _normalize_text(item.get("place_kind"))
    wants_lodging = bool(re.search(r"(酒店|宾馆|旅馆|民宿|客栈|住宿)", keyword))
    wants_transport = bool(re.search(r"(地铁站|公交站|车站|机场|高铁|火车站|汽车站)", keyword))
    wants_education = _query_explicitly_wants_education(keyword, category_hint)
    if score > 0:
        if re.search(r"(停车场|出入口|办公室|管理处|服务中心|售票处)", name_text) and not re.search(r"(停车场|出入口|办公室|管理处|服务中心|售票处)", keyword):
            score -= 0.45
        elif "游客中心" in name_text and "游客中心" not in keyword:
            score -= 0.12
        if _is_auxiliary_poi_name(name_text) and not _query_explicitly_wants_auxiliary_poi(keyword):
            score -= 0.58

        if place_kind == "lodging" and not wants_lodging:
            score -= 0.28
        if place_kind == "transport" and not wants_transport:
            score -= 0.22
        if _is_education_like_poi(item) and not wants_education:
            score -= 0.5
        if re.search(r"(风景名胜|旅游景点|公园广场|博物馆|古镇|古城|景区)", category_text) and not wants_lodging and not wants_transport:
            score += 0.04

        if category_hint == "风景名胜" and re.search(r"(交通设施服务|政府机构及社会团体|住宿服务)", category_text):
            score -= 0.35
        if category_hint == "科教文化服务" and "科教文化服务" not in category_text:
            score -= 0.3
        if category_hint == "餐饮服务" and "餐饮服务" not in category_text:
            score -= 0.3
        if category_hint in {"风景名胜", "餐饮服务", "购物服务"} and _is_education_like_poi(item):
            score -= 0.4

    return max(0.0, round(score, 4))


def _generic_candidate_score(query: str, item: Dict[str, Any], category_hint: Optional[str] = None) -> float:
    query_text = _normalize_text(query)
    name_text = _normalize_text(item.get("name"))
    category_text = _normalize_text(item.get("category"))
    address_text = _normalize_text(item.get("address"))
    score = 0.0

    if category_hint and category_hint in category_text:
        score += 1.2
    if query_text and (query_text in name_text or query_text in category_text or query_text in address_text):
        score += 0.7

    distance = item.get("distance_meters")
    if isinstance(distance, (int, float)):
        score += max(0.0, 1.0 - (float(distance) / 6000.0))

    if re.search(r"(停车场|出入口|办公室|管理处|服务中心|售票处)", name_text):
        score -= 1.0
    if _is_auxiliary_poi_name(name_text) and not _query_explicitly_wants_auxiliary_poi(query):
        score -= 1.6
    if _is_education_like_poi(item) and not _query_explicitly_wants_education(query, category_hint):
        score -= 2.2
    if category_hint == "餐饮服务" and "餐饮服务" not in category_text:
        score -= 0.6
    if category_hint == "购物服务" and "购物服务" not in category_text:
        score -= 0.6
    if category_hint == "风景名胜" and re.search(r"(交通设施服务|政府机构及社会团体|住宿服务)", category_text):
        score -= 0.8
    if category_hint in {"风景名胜", "餐饮服务", "购物服务"} and _is_education_like_poi(item):
        score -= 1.2

    return round(score, 4)


async def api_planner_place_candidates(body: Any) -> Dict[str, Any]:
    payload = body.model_dump() if hasattr(body, "model_dump") else dict(body or {})
    query = _normalize_text(payload.get("query"))
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    city = _normalize_text(payload.get("city")) or AMAP_DEFAULT_CITY
    anchor_location = parse_amap_location(payload.get("anchor_location"))
    limit = max(1, min(5, int(payload.get("limit") or 5)))
    intent_type = _normalize_text(payload.get("intent_type")) or "generic_poi"
    category_hint = _normalize_text(payload.get("category_hint")) or _derive_place_category_hint(query) or None
    wants_education = _query_explicitly_wants_education(query, category_hint)

    search_payloads: List[Dict[str, Any]] = []
    if anchor_location:
        search_payloads.append(
            {
                "city": city,
                "keyword": query,
                "category": category_hint,
                "anchor_location": anchor_location,
                "user_location": anchor_location,
                "radius_meters": max(int(payload.get("radius_meters") or AMAP_DEFAULT_RADIUS_METERS), 3000),
                "limit": max(limit * 2, 8),
                "search_mode": "nearby",
            }
        )
    search_payloads.append(
        {
            "city": city,
            "keyword": query,
            "category": category_hint,
            "anchor_location": anchor_location,
            "user_location": anchor_location,
            "radius_meters": int(payload.get("radius_meters") or AMAP_DEFAULT_RADIUS_METERS),
            "limit": max(limit * 2, 8),
            "search_mode": "region",
        }
    )

    warnings: List[str] = []
    pooled: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    for search_payload in search_payloads:
        result = await search_amap_poi(None, search_payload)
        warnings.extend(result.get("warnings", []))
        for item in result.get("data") or []:
            key = _normalize_text(item.get("poi_id")) or f"{_normalize_text(item.get('name'))}_{item.get('location')}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            pooled.append(item)
        if _is_map_quota_warning(" ".join(str(item) for item in result.get("warnings", []))):
            break

    if not pooled:
        return {
            "status": "failed",
            "query": query,
            "intent_type": intent_type,
            "candidates": [],
            "warnings": warnings,
        }

    pooled = [item for item in pooled if _matches_city_constraint(item, city)]
    if not pooled:
        return {
            "status": "failed",
            "query": query,
            "intent_type": intent_type,
            "candidates": [],
            "warnings": warnings + [f"no poi matched city constraint: {city}"],
        }

    if not wants_education:
        pooled = [item for item in pooled if not _is_education_like_poi(item)]
    if not pooled:
        return {
            "status": "failed",
            "query": query,
            "intent_type": intent_type,
            "candidates": [],
            "warnings": warnings + ["all poi candidates were filtered out as school-like results"],
        }

    scored = sorted(
        (
            {
                **item,
                "confidence": _generic_candidate_score(query, item, category_hint),
            }
            for item in pooled
        ),
        key=lambda item: (
            float(item.get("confidence") or 0),
            -(float(item.get("distance_meters")) if isinstance(item.get("distance_meters"), (int, float)) else 10**12),
            item.get("name") or "",
        ),
        reverse=True,
    )
    candidates = [item for item in scored if float(item.get("confidence") or 0) > 0][:limit]
    return {
        "status": "ok" if candidates else "failed",
        "query": query,
        "intent_type": intent_type,
        "day_index": payload.get("day_index"),
        "slot": _normalize_text(payload.get("slot")),
        "candidates": candidates,
        "warnings": warnings,
    }


def _select_itinerary_slot(itinerary: Dict[str, Any], day_index: int, slot: str, query: str) -> Optional[Dict[str, Any]]:
    for day in itinerary.get("days") or []:
        if int(day.get("day_index") or 0) != int(day_index):
            continue
        for item in day.get("items") or []:
            if _normalize_text(item.get("slot")) != _normalize_text(slot):
                continue
            for candidate in item.get("place_candidates") or []:
                if _normalize_text(candidate.get("query")) == _normalize_text(query):
                    return item
            return item
    return None


def _next_direct_add_slot(day: Dict[str, Any], base_slot: str = "加点") -> str:
    existing_slots = {
        _normalize_text(item.get("slot"))
        for item in (day.get("items") or [])
        if _normalize_text(item.get("slot"))
    }
    if base_slot not in existing_slots:
        return base_slot
    index = 2
    while f"{base_slot}{index}" in existing_slots:
        index += 1
    return f"{base_slot}{index}"


def _append_direct_place_to_day(
    itinerary: Dict[str, Any],
    day_index: int,
    query: str,
    place: Dict[str, Any],
) -> Dict[str, Any]:
    day = _ensure_itinerary_day(itinerary, day_index)
    poi_id = _normalize_text(place.get("poi_id"))
    if poi_id:
        for item in day.get("items") or []:
            for selected in item.get("selected_places") or []:
                if _normalize_text(selected.get("poi_id")) == poi_id:
                    return item

    slot_name = _next_direct_add_slot(day)
    normalized_place = {
        "poi_id": poi_id,
        "name": _normalize_text(place.get("name")),
        "address": _normalize_text(place.get("address")),
        "category": _normalize_text(place.get("category")),
        "location": parse_amap_location(place.get("location")),
        "resolve_note": _normalize_text(place.get("resolve_note")),
        "anchor_keyword": _normalize_text(place.get("anchor_keyword")),
    }
    if not normalized_place["name"] or not normalized_place["location"]:
        raise HTTPException(status_code=400, detail="place.name and place.location are required")

    label = _normalize_text(query) or normalized_place["name"]
    note = normalized_place.get("resolve_note") or ""
    item = {
        "slot": slot_name,
        "text": f"{label} —— 直接加入第{day_index}天" + (f"（{note}）" if note else ""),
        "place_candidates": [
            {
                "query": label,
                "raw_query": label,
                "aliases": [normalized_place["name"]] if normalized_place["name"] and normalized_place["name"] != label else [],
                "category_hint": normalized_place["category"] or "",
                "intent_type": "direct_add",
                "selection_mode": "manual_add",
                "selected_places": [normalized_place],
            }
        ],
        "selected_places": [normalized_place],
    }
    day.setdefault("items", []).append(item)
    rank = {name: index for index, name in enumerate(SLOT_ORDER)}
    day["items"] = sorted(
        day.get("items") or [],
        key=lambda row: rank.get(_normalize_text(row.get("slot")), len(rank)),
    )
    return item


def _primary_item_poi_id(item: Dict[str, Any]) -> str:
    for selected in item.get("selected_places") or []:
        poi_id = _normalize_text(selected.get("poi_id"))
        if poi_id:
            return poi_id
    for candidate in item.get("place_candidates") or []:
        for selected in candidate.get("selected_places") or []:
            poi_id = _normalize_text(selected.get("poi_id"))
            if poi_id:
                return poi_id
    return ""


def _collect_day_selected_poi_ids(day: Dict[str, Any]) -> List[str]:
    poi_ids: List[str] = []
    for item in day.get("items") or []:
        for selected in item.get("selected_places") or []:
            poi_id = _normalize_text(selected.get("poi_id"))
            if poi_id and poi_id not in poi_ids:
                poi_ids.append(poi_id)
        for candidate in item.get("place_candidates") or []:
            for selected in candidate.get("selected_places") or []:
                poi_id = _normalize_text(selected.get("poi_id"))
                if poi_id and poi_id not in poi_ids:
                    poi_ids.append(poi_id)
    return poi_ids


def _reorder_itinerary_day_items(
    itinerary: Dict[str, Any],
    day_index: int,
    ordered_poi_ids: List[str],
) -> bool:
    normalized_ids = [_normalize_text(item) for item in ordered_poi_ids if _normalize_text(item)]
    if not normalized_ids:
        return False
    days = itinerary.get("days") or []
    day = next((item for item in days if int(item.get("day_index") or 0) == int(day_index)), None)
    if not day:
        return False
    existing_day_poi_ids = _collect_day_selected_poi_ids(day)
    matched_ids = [poi_id for poi_id in normalized_ids if poi_id in existing_day_poi_ids]
    if len(matched_ids) < 2:
        return False
    day["manual_order_poi_ids"] = matched_ids

    items = list(day.get("items") or [])
    if len(items) < 2:
        return True
    order_map = {poi_id: index for index, poi_id in enumerate(normalized_ids)}
    matched = False
    decorated = []
    for original_index, item in enumerate(items):
        primary_poi_id = _primary_item_poi_id(item)
        if primary_poi_id in order_map:
            matched = True
        decorated.append(
            (
                order_map.get(primary_poi_id, len(order_map) + original_index),
                original_index,
                item,
            )
        )
    if not matched:
        return False
    decorated.sort(key=lambda row: (row[0], row[1]))
    day["items"] = [row[2] for row in decorated]
    return True


async def api_planner_itinerary_place_select(body: Any) -> Dict[str, Any]:
    payload = body.model_dump() if hasattr(body, "model_dump") else dict(body or {})
    session_id = _normalize_text(payload.get("session_id"))
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    day_index = int(payload.get("day_index") or 0)
    slot = _normalize_text(payload.get("slot"))
    query = _normalize_text(payload.get("query"))
    place = payload.get("place") or {}
    if not day_index or not slot or not query:
        raise HTTPException(status_code=400, detail="day_index, slot, and query are required")

    normalized_place = {
        "poi_id": _normalize_text(place.get("poi_id")),
        "name": _normalize_text(place.get("name")),
        "address": _normalize_text(place.get("address")),
        "category": _normalize_text(place.get("category")),
        "location": parse_amap_location(place.get("location")),
        "resolve_note": _normalize_text(place.get("resolve_note")),
        "anchor_keyword": _normalize_text(place.get("anchor_keyword")),
    }
    if not normalized_place["name"] or not normalized_place["location"]:
        raise HTTPException(status_code=400, detail="place.name and place.location are required")

    with get_db() as conn:
        _get_session_or_404(conn, session_id)
        latest_itinerary_row = _get_latest_itinerary_row(conn, session_id)
        if not latest_itinerary_row:
            raise HTTPException(status_code=404, detail="itinerary not found")
        parsed_itinerary = _parse_itinerary_row(latest_itinerary_row)
        itinerary_content = parsed_itinerary.get("content") or {}
        if bool(payload.get("direct_add")):
            target_item = _append_direct_place_to_day(itinerary_content, day_index, query, normalized_place)
        else:
            target_item = _select_itinerary_slot(itinerary_content, day_index, slot, query)
            if not target_item:
                raise HTTPException(status_code=404, detail="itinerary slot not found")

        selected_places = target_item.setdefault("selected_places", [])
        place_candidates = target_item.get("place_candidates") or []
        matched_candidate = False
        for candidate in place_candidates:
            if _normalize_text(candidate.get("query")) == query:
                candidate.setdefault("selected_places", [])
                already = any(_normalize_text(existing.get("poi_id")) == normalized_place["poi_id"] for existing in candidate["selected_places"])
                if not already:
                    candidate["selected_places"].append(normalized_place)
                matched_candidate = True
                break

        if not matched_candidate:
            direct_candidate = {
                "query": query,
                "raw_query": query,
                "aliases": [normalized_place["name"]] if normalized_place["name"] and normalized_place["name"] != query else [],
                "category_hint": normalized_place["category"] or "",
                "intent_type": "direct_add",
                "selection_mode": "manual_add",
                "selected_places": [normalized_place],
            }
            if not any(
                _normalize_text(candidate.get("query")) == query
                and any(_normalize_text(existing.get("poi_id")) == normalized_place["poi_id"] for existing in (candidate.get("selected_places") or []))
                for candidate in place_candidates
            ):
                target_item.setdefault("place_candidates", []).append(direct_candidate)

        already_selected = any(_normalize_text(existing.get("poi_id")) == normalized_place["poi_id"] for existing in selected_places)
        if not already_selected:
            selected_places.append(normalized_place)

        saved = _save_itinerary_snapshot(
            conn,
            session_id,
            itinerary_content,
            requirement_id=parsed_itinerary.get("requirement_id"),
            generator_type="user_place_select",
        )
        conn.commit()

    return {
        "status": "ok",
        "session_id": session_id,
        "itinerary": saved.get("content"),
        "itinerary_snapshot": saved,
        "selected_place": normalized_place,
    }


async def api_planner_itinerary_place_remove(body: Any) -> Dict[str, Any]:
    payload = body.model_dump() if hasattr(body, "model_dump") else dict(body or {})
    session_id = _normalize_text(payload.get("session_id"))
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    day_index = int(payload.get("day_index") or 0)
    if not day_index:
        raise HTTPException(status_code=400, detail="day_index is required")

    slot = _normalize_text(payload.get("slot"))
    poi_id = _normalize_text(payload.get("poi_id"))
    place_name = _normalize_text(payload.get("place_name"))
    query = _normalize_text(payload.get("query"))
    target_place = place_name or query
    if not poi_id and not target_place:
        raise HTTPException(status_code=400, detail="poi_id or place_name/query is required")

    with get_db() as conn:
        _get_session_or_404(conn, session_id)
        latest_itinerary_row = _get_latest_itinerary_row(conn, session_id)
        if not latest_itinerary_row:
            raise HTTPException(status_code=404, detail="itinerary not found")
        parsed_itinerary = _parse_itinerary_row(latest_itinerary_row)
        itinerary_content = parsed_itinerary.get("content") or {}
        days = itinerary_content.get("days") or []
        day = next((item for item in days if int(item.get("day_index") or 0) == day_index), None)
        if not day:
            raise HTTPException(status_code=404, detail="itinerary day not found")

        removed = False
        next_items: List[Dict[str, Any]] = []
        for item in day.get("items") or []:
            if slot and _normalize_text(item.get("slot")) != slot:
                next_items.append(item)
                continue
            item_copy = json.loads(json.dumps(item))
            item_removed = _remove_place_from_item(item_copy, target_place, poi_id)
            if item_removed:
                removed = True
            has_selected = bool(item_copy.get("selected_places"))
            has_candidates = bool(item_copy.get("place_candidates"))
            if not has_selected and not has_candidates:
                item_copy["text"] = ""
            if _normalize_text(item_copy.get("text")) or has_selected or has_candidates:
                next_items.append(item_copy)

        if not removed:
            raise HTTPException(status_code=404, detail="itinerary place not found")

        day["items"] = next_items
        ordered_poi_ids = _collect_day_selected_poi_ids(day)
        if len(ordered_poi_ids) >= 2:
            day["manual_order_poi_ids"] = ordered_poi_ids
        else:
            day.pop("manual_order_poi_ids", None)
        itinerary_content["display_text"] = _sanitize_reply_text(
            _render_itinerary_summary_text(
                itinerary_content,
                _normalize_text(((itinerary_content.get("candidate_recall_result") or {}).get("assumptions"))),
                itinerary_content.get("planner_warnings") or [],
            )
        )

        saved = _save_itinerary_snapshot(
            conn,
            session_id,
            itinerary_content,
            requirement_id=parsed_itinerary.get("requirement_id"),
            generator_type="user_place_remove",
        )
        conn.commit()

    return {
        "status": "ok",
        "session_id": session_id,
        "itinerary": saved.get("content"),
        "itinerary_snapshot": saved,
    }


async def api_planner_itinerary_reorder(body: Any) -> Dict[str, Any]:
    payload = body.model_dump() if hasattr(body, "model_dump") else dict(body or {})
    session_id = _normalize_text(payload.get("session_id"))
    day_index = int(payload.get("day_index") or 0)
    ordered_poi_ids = payload.get("ordered_poi_ids") or []
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not day_index:
        raise HTTPException(status_code=400, detail="day_index is required")
    if not isinstance(ordered_poi_ids, list) or not ordered_poi_ids:
        raise HTTPException(status_code=400, detail="ordered_poi_ids is required")

    with get_db() as conn:
        _get_session_or_404(conn, session_id)
        latest_itinerary_row = _get_latest_itinerary_row(conn, session_id)
        if not latest_itinerary_row:
            raise HTTPException(status_code=404, detail="itinerary not found")
        parsed_itinerary = _parse_itinerary_row(latest_itinerary_row)
        itinerary_content = parsed_itinerary.get("content") or {}
        changed = _reorder_itinerary_day_items(itinerary_content, day_index, ordered_poi_ids)
        if not changed:
            raise HTTPException(status_code=400, detail="unable to reorder itinerary day items")
        saved = _save_itinerary_snapshot(
            conn,
            session_id,
            itinerary_content,
            requirement_id=parsed_itinerary.get("requirement_id"),
            generator_type="user_reorder",
        )
        conn.commit()

    return {
        "status": "ok",
        "session_id": session_id,
        "itinerary": saved.get("content"),
        "itinerary_snapshot": saved,
        "day_index": day_index,
        "ordered_poi_ids": [_normalize_text(item) for item in ordered_poi_ids if _normalize_text(item)],
    }


async def api_requirement_interpret(body: Any) -> Dict[str, Any]:
    payload = body.model_dump() if hasattr(body, "model_dump") else dict(body or {})
    message = _normalize_text(payload.get("message"))
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    intent = interpret_requirement_payload(message, payload.get("context") or {})
    return {
        "status": "ok",
        "session_id": _normalize_text(payload.get("session_id")) or None,
        "intent": intent,
    }


async def api_poi_resolve(body: Any) -> Dict[str, Any]:
    payload = body.model_dump() if hasattr(body, "model_dump") else dict(body or {})
    keyword = _normalize_text(payload.get("keyword"))
    if not keyword:
        raise HTTPException(status_code=400, detail="keyword is required")
    city = _sanitize_city_name(payload.get("city")) or AMAP_DEFAULT_CITY
    category_hint = _normalize_text(payload.get("category_hint")) or None
    anchor_location = payload.get("anchor_location")
    radius_meters = int(payload.get("radius_meters") or AMAP_DEFAULT_RADIUS_METERS)
    limit = max(1, min(10, int(payload.get("limit") or 8)))
    wants_education = _query_explicitly_wants_education(keyword, category_hint)
    search_payloads = []
    if anchor_location:
        search_payloads.append(
            {
                "city": city,
                "keyword": keyword,
                "category": category_hint,
                "anchor_location": anchor_location,
                "user_location": anchor_location,
                "radius_meters": max(radius_meters, 15000),
                "limit": limit,
                "search_mode": "nearby",
            }
        )
    search_payloads.append(
        {
            "city": city,
            "keyword": keyword,
            "category": category_hint,
            "anchor_location": anchor_location,
            "user_location": anchor_location,
            "radius_meters": radius_meters,
            "limit": limit,
            "search_mode": "region",
        }
    )

    warnings: List[str] = []
    items: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    for search_payload in search_payloads:
        result = await search_amap_poi(None, search_payload)
        warnings.extend(result.get("warnings", []))
        for item in result.get("data") or []:
            key = _normalize_text(item.get("poi_id")) or f"{_normalize_text(item.get('name'))}_{item.get('location')}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            items.append(item)
        if _is_map_quota_warning(" ".join(str(item) for item in result.get("warnings", []))):
            break
    if not items:
        return {
            "status": "invalid",
            "reason": "no poi match",
            "alternatives": [],
            "warnings": warnings,
        }

    items = [item for item in items if _matches_city_constraint(item, city)]
    if not items:
        return {
            "status": "invalid",
            "reason": "no poi match within requested city",
            "alternatives": [],
            "warnings": warnings + [f"no poi matched city constraint: {city}"],
        }

    if not wants_education:
        items = [item for item in items if not _is_education_like_poi(item)]
    if not items:
        return {
            "status": "invalid",
            "reason": "no poi match after filtering school-like results",
            "alternatives": [],
            "warnings": warnings + ["all poi matches were filtered out as school-like results"],
        }

    scored = sorted(
        (
            {
                **item,
                "confidence": _poi_match_score(keyword, item, category_hint)
            }
            for item in items
        ),
        key=lambda item: (
            float(item.get("confidence") or 0),
            -float(item.get("distance_meters") or 10**12),
            item.get("name") or "",
        ),
        reverse=True,
    )
    best = scored[0]
    second_confidence = float(scored[1].get("confidence") or 0) if len(scored) > 1 else 0.0
    if float(best.get("confidence") or 0) >= 0.9 or (len(scored) == 1 and float(best.get("confidence") or 0) >= 0.6):
        best["is_valid"] = True
        return {
            "status": "resolved",
            "poi": best,
            "warnings": warnings,
        }
    if float(best.get("confidence") or 0) >= 0.72 and (float(best.get("confidence") or 0) - second_confidence) >= 0.12:
        best["is_valid"] = True
        return {
            "status": "resolved",
            "poi": best,
            "warnings": warnings,
        }
    return {
        "status": "ambiguous",
        "reason": "multiple close poi matches",
        "alternatives": scored[:5],
        "warnings": warnings,
    }


async def api_poi_validate(body: Any) -> Dict[str, Any]:
    payload = body.model_dump() if hasattr(body, "model_dump") else dict(body or {})
    anchor_location = parse_amap_location(payload.get("anchor_location"))
    if not anchor_location:
        raise HTTPException(status_code=400, detail="anchor_location is required")
    max_distance = max(1, int(payload.get("max_distance_meters") or 5000))
    validated_places: List[Dict[str, Any]] = []
    for place in payload.get("places") or []:
        location = parse_amap_location(place.get("location"))
        distance = _distance_between_points(anchor_location, location) if location else None
        is_valid = bool(location and distance is not None and distance <= max_distance)
        validated_places.append(
            {
                "poi_id": _normalize_text(place.get("poi_id")),
                "name": _normalize_text(place.get("name")),
                "address": _normalize_text(place.get("address")),
                "category": _normalize_text(place.get("category")),
                "location": location,
                "is_valid": is_valid,
                "distance_meters": distance,
                "reason": "within_range" if is_valid else ("missing_location" if not location else "too_far"),
            }
        )
    return {
        "status": "ok",
        "validated_places": validated_places,
    }


async def api_route_plan(body: Any) -> Dict[str, Any]:
    payload = body.model_dump() if hasattr(body, "model_dump") else dict(body or {})
    start = parse_amap_location(payload.get("start"))
    if not start:
        raise HTTPException(status_code=400, detail="start is required")
    points = payload.get("points") or []
    ordered_points = [start]
    ordered_ids = ["start"]
    for point in points:
        location = parse_amap_location(point.get("location"))
        if not location:
            continue
        ordered_points.append(location)
        ordered_ids.append(_normalize_text(point.get("poi_id")) or _normalize_text(point.get("name")) or f"point_{len(ordered_ids)}")
    mode_raw = _normalize_text(payload.get("mode")).lower()
    mode = "walking" if mode_raw in {"walk", "walking", "foot"} else "driving"
    route = await plan_amap_route(mode, ordered_points)
    normalized_segments: List[Dict[str, Any]] = []
    for index, segment in enumerate(route.get("segments") or []):
        normalized_segments.append(
            {
                "from_poi_id": ordered_ids[index] if index < len(ordered_ids) else f"point_{index}",
                "to_poi_id": ordered_ids[index + 1] if index + 1 < len(ordered_ids) else f"point_{index + 1}",
                "distance_meters": segment.get("distanceMeters"),
                "duration_minutes": round(float(segment.get("durationSeconds")) / 60, 1) if segment.get("durationSeconds") is not None else None,
                "polyline": segment.get("polyline") or [],
                "mode": segment.get("mode") or mode,
            }
        )
    return {
        "status": "ok",
        "route": {
            "mode": route.get("mode") or mode,
            "segments": normalized_segments,
            "total_distance_meters": route.get("totalDistanceMeters") or 0,
            "total_duration_minutes": round(float(route.get("totalDurationSeconds")) / 60, 1) if route.get("totalDurationSeconds") is not None else None,
        },
        "warnings": route.get("warnings", []),
    }


async def preview_web_context(_body: Any) -> Dict[str, Any]:
    raise _not_implemented("preview_web_context")


def app_ui() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    raise HTTPException(status_code=404, detail="static/index.html not found")


async def chat(_body: Any) -> Dict[str, Any]:
    message = _normalize_text(getattr(_body, "message", None) if _body is not None else None)
    session_id = _normalize_text(getattr(_body, "session_id", None) if _body is not None else None)
    session_title = _normalize_text(getattr(_body, "session_title", None) if _body is not None else None)
    client_conversation_context = _normalize_text(getattr(_body, "conversation_context", None) if _body is not None else None)

    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    prior_messages: List[Dict[str, Any]] = []
    latest_requirement_payload: Optional[Dict[str, Any]] = None
    latest_itinerary_payload: Optional[Dict[str, Any]] = None
    with get_db() as conn:
        if session_id:
            session_row = _get_session_or_404(conn, session_id)
        else:
            session_id = _new_id("sess")
            created_at = _now_iso()
            conn.execute(
                """
                INSERT INTO sessions (
                  id, title, status, current_requirement_version, current_itinerary_version, created_at, updated_at
                ) VALUES (?, ?, 'active', 0, 0, ?, ?)
                """,
                (session_id, session_title or _build_session_title(message), created_at, created_at),
            )
            session_row = _get_session_or_404(conn, session_id)
        prior_messages = _list_messages(conn, session_id, limit=200)
        latest_requirement_payload = _get_latest_requirement_payload(conn, session_id)
        latest_itinerary_row = _get_latest_itinerary_row(conn, session_id)
        if latest_itinerary_row:
            latest_itinerary_payload = _parse_itinerary_row(latest_itinerary_row).get("content") or None
        _insert_message(conn, session_id, "user", message)
        conn.commit()

    explicit_city = _extract_destination_hint(message)
    previous_city = _normalize_text((latest_requirement_payload or {}).get("city"))
    city_switched = bool(explicit_city and previous_city and explicit_city != previous_city)
    current_requirement_payload = interpret_requirement_payload(
        message,
        {
            "current_city": previous_city or AMAP_DEFAULT_CITY,
            "anchor_location": None if city_switched else (latest_requirement_payload or {}).get("anchor_location"),
        },
    )
    requirement_payload = _merge_requirement_payload(latest_requirement_payload, current_requirement_payload, message)
    with get_db() as conn:
        global_preference_profile = _update_global_preference_profile(conn, message)
        conn.commit()
    memory_profile = _build_memory_profile(
        global_preference_profile,
        requirement_payload,
        None if city_switched else latest_itinerary_payload,
        message,
    )
    requirement_payload = _apply_memory_to_requirement(requirement_payload, memory_profile)
    requirement_payload["schema_version"] = PLANNER_SCHEMA_VERSION

    short_term_memory = _build_short_term_memory(prior_messages, max_rounds=5)
    memory_sections = []
    if latest_requirement_payload and not city_switched:
        memory_sections.append(f"当前已确认需求草案：{_serialize_requirement_summary(latest_requirement_payload)}")
    if short_term_memory and not city_switched:
        memory_sections.append(f"最近5轮对话：\n{short_term_memory}")
    if city_switched:
        memory_sections.append(f"用户本轮明确将目的地切换为：{explicit_city}。请忽略此前其他城市的地点推荐和路线。")
    if client_conversation_context and not city_switched:
        memory_sections.append(f"前端补充上下文：\n{client_conversation_context}")
    conversation_context = "\n\n".join(section for section in memory_sections if section)

    edit_instruction = _parse_itinerary_edit_instruction(message, conversation_context)
    workflow_result = await _run_tool_using_chat_workflow(
        message=message,
        conversation_context=conversation_context,
        requirement_payload=requirement_payload,
        latest_itinerary_payload=latest_itinerary_payload,
        edit_instruction=edit_instruction,
        memory_profile=memory_profile,
    )
    itinerary_payload = workflow_result.get("validated_itinerary") or {
        "city": requirement_payload.get("city") or AMAP_DEFAULT_CITY,
        "days": [],
    }
    assistant_text = _normalize_text(workflow_result.get("assistant_text")) or _build_conversational_itinerary_reply(
        itinerary_payload,
        requirement_payload=requirement_payload,
        assumptions=_normalize_text(((workflow_result.get("candidate_recall_result") or {}).get("assumptions"))),
        warnings=workflow_result.get("planner_warnings") or [],
    )
    if edit_instruction and latest_itinerary_payload:
        edit_source = latest_itinerary_payload
        edited_ack = _build_itinerary_edit_acknowledgement(edit_instruction, edit_source, itinerary_payload)
        if edited_ack and assistant_text and assistant_text != edited_ack:
            assistant_text = f"{edited_ack}\n\n{assistant_text}"

    with get_db() as conn:
        saved_requirement = _save_requirement_snapshot(conn, session_id, message, requirement_payload, strategy="chat_memory")
        saved_itinerary = _save_itinerary_snapshot(
            conn,
            session_id,
            itinerary_payload,
            requirement_id=saved_requirement.get("id"),
            generator_type="tool_using_agent",
        )
        _insert_message(
            conn,
            session_id,
            "assistant",
            assistant_text,
            metadata={
                "source": "tool_using_agent",
                "schema_version": workflow_result.get("schema_version") or PLANNER_SCHEMA_VERSION,
                "workflow_trace": workflow_result.get("workflow_trace") or [],
                "planner_warnings": workflow_result.get("planner_warnings") or [],
                "validator_result": workflow_result.get("validator_result") or {},
            },
        )
        session_row = _get_session_or_404(conn, session_id)
        messages = _list_messages(conn, session_id, limit=200)
        conn.commit()

    session = _parse_session_row(session_row)
    return {
        "action": "chat",
        "session_id": session_id,
        "session": session,
        "messages": messages,
        "assistantMessage": assistant_text,
        "schema_version": workflow_result.get("schema_version") or PLANNER_SCHEMA_VERSION,
        "requirement": requirement_payload,
        "requirement_v2": workflow_result.get("requirement_v2") or _build_requirement_v2(requirement_payload, memory_profile),
        "requirement_snapshot": saved_requirement,
        "candidate_recall_result": workflow_result.get("candidate_recall_result") or {},
        "grounded_pois": workflow_result.get("grounded_pois") or [],
        "itinerary": itinerary_payload,
        "validated_itinerary": itinerary_payload,
        "itinerary_snapshot": saved_itinerary,
        "validator_result": workflow_result.get("validator_result") or {},
        "memory_profile": workflow_result.get("memory_profile") or memory_profile,
        "workflow_trace": workflow_result.get("workflow_trace") or [],
        "planner_warnings": workflow_result.get("planner_warnings") or [],
        "candidate_backups": workflow_result.get("candidate_backups") or [],
        "memory": {
            "short_term_rounds": 5,
            "short_term_message_count": min(len(prior_messages), 10),
            "has_requirement_memory": bool(latest_requirement_payload),
        },
    }


def create_session(_body: Any) -> Dict[str, Any]:
    title = _normalize_text(getattr(_body, "title", None) if _body is not None else None) or "新会话"
    session_id = _new_id("sess")
    created_at = _now_iso()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO sessions (
              id, title, status, current_requirement_version, current_itinerary_version, created_at, updated_at
            ) VALUES (?, ?, 'active', 0, 0, ?, ?)
            """,
            (session_id, title, created_at, created_at),
        )
        conn.commit()
        row = _get_session_or_404(conn, session_id)
    return _parse_session_row(row)


def get_session(_session_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        row = _get_session_or_404(conn, _session_id)
    result = _parse_session_row(row)
    result["latest_requirement_id"] = None
    result["latest_itinerary_id"] = None
    return result


def _list_sessions(conn: sqlite3.Connection, limit: int = 20) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            s.*,
            (
                SELECT content
                FROM conversation_messages m
                WHERE m.session_id = s.id
                ORDER BY m.created_at DESC, m.rowid DESC
                LIMIT 1
            ) AS latest_message,
            (
                SELECT role
                FROM conversation_messages m
                WHERE m.session_id = s.id
                ORDER BY m.created_at DESC, m.rowid DESC
                LIMIT 1
            ) AS latest_message_role,
            (
                SELECT COUNT(*)
                FROM conversation_messages m
                WHERE m.session_id = s.id
            ) AS message_count
        FROM sessions s
        ORDER BY s.updated_at DESC, s.created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_parse_session_row(row) for row in rows]


def list_sessions(_request: Request) -> Dict[str, Any]:
    raw_limit = _request.query_params.get("limit")
    try:
        limit = max(1, min(100, int(raw_limit))) if raw_limit else 20
    except ValueError:
        limit = 20
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        items = _list_sessions(conn, limit=limit)
    return {"items": items, "limit": limit, "total": total}


def delete_session(_session_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        _get_session_or_404(conn, _session_id)
        conn.execute("DELETE FROM user_place_notes WHERE session_id = ?", (_session_id,))
        conn.execute("DELETE FROM conversation_messages WHERE session_id = ?", (_session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (_session_id,))
        conn.commit()
    return {"deleted": _session_id}


async def create_requirement(_session_id: str, _body: Any) -> Dict[str, Any]:
    raw_input = _normalize_text(getattr(_body, "raw_input", None) if _body is not None else None)
    if not raw_input:
        raise HTTPException(status_code=400, detail="raw_input is required")
    structured_payload = getattr(_body, "structured_payload", None) if _body is not None else None
    strategy = _normalize_text(getattr(_body, "strategy", None) if _body is not None else None) or "llm"
    with get_db() as conn:
        session = _get_session_or_404(conn, _session_id)
        version = int(session["current_requirement_version"] or 0) + 1
        payload = structured_payload or interpret_requirement_payload(raw_input, {"current_city": AMAP_DEFAULT_CITY})
        requirement_id = _new_id("req")
        created_at = _now_iso()
        conn.execute(
            """
            INSERT INTO requirements (id, session_id, version, raw_input, strategy, structured_payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                requirement_id,
                _session_id,
                version,
                raw_input,
                strategy,
                json.dumps(payload, ensure_ascii=False),
                created_at,
            ),
        )
        conn.execute(
            "UPDATE sessions SET current_requirement_version = ?, updated_at = ? WHERE id = ?",
            (version, created_at, _session_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM requirements WHERE id = ?", (requirement_id,)).fetchone()
    return {"status": "ok", "requirement": _parse_requirement_row(row)}


async def preview_requirement_interpretation(_session_id: str, _body: Any) -> Dict[str, Any]:
    raw_input = _normalize_text(getattr(_body, "raw_input", None) if _body is not None else None)
    if not raw_input:
        raise HTTPException(status_code=400, detail="raw_input is required")
    with get_db() as conn:
        _get_session_or_404(conn, _session_id)
    structured_payload = interpret_requirement_payload(raw_input, {"current_city": AMAP_DEFAULT_CITY})
    return {
        "status": "ok",
        "session_id": _session_id,
        "raw_input": raw_input,
        "structured_payload": structured_payload,
    }


def get_latest_requirement(_session_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        _get_session_or_404(conn, _session_id)
        row = conn.execute(
            """
            SELECT * FROM requirements
            WHERE session_id = ?
            ORDER BY version DESC, created_at DESC
            LIMIT 1
            """,
            (_session_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="requirement not found")
    return {"status": "ok", "requirement": _parse_requirement_row(row)}


async def create_itinerary(_session_id: str, _body: Any) -> Dict[str, Any]:
    requirement_id = _normalize_text(getattr(_body, "requirement_id", None) if _body is not None else None) or None
    generator_type = _normalize_text(getattr(_body, "generator_type", None) if _body is not None else None) or "agent"
    with get_db() as conn:
        _get_session_or_404(conn, _session_id)
        latest_requirement_payload = _get_latest_requirement_payload(conn, _session_id) or {"city": AMAP_DEFAULT_CITY}
        content = {
            "city": latest_requirement_payload.get("city") or AMAP_DEFAULT_CITY,
            "day_count_requested": latest_requirement_payload.get("day_count"),
            "days": [],
            "display_text": "",
        }
        saved = _save_itinerary_snapshot(
            conn,
            _session_id,
            content,
            requirement_id=requirement_id,
            generator_type=generator_type,
        )
        conn.commit()
    return {"status": "ok", "itinerary": saved}


def get_latest_itinerary(_session_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        _get_session_or_404(conn, _session_id)
        row = _get_latest_itinerary_row(conn, _session_id)
    if not row:
        raise HTTPException(status_code=404, detail="itinerary not found")
    return {"status": "ok", "itinerary": _parse_itinerary_row(row)}


async def replan(_session_id: str, _body: Any) -> Dict[str, Any]:
    raise _not_implemented("replan")


def create_message(_session_id: str, _body: Any) -> Dict[str, Any]:
    content = _normalize_text(getattr(_body, "content", None) if _body is not None else None)
    role = _normalize_text(getattr(_body, "role", None) if _body is not None else None) or "user"
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    with get_db() as conn:
        _get_session_or_404(conn, _session_id)
        message = _insert_message(conn, _session_id, role, content, metadata=getattr(_body, "metadata", None))
        conn.commit()
    return message


def list_messages(_session_id: str, _request: Request) -> Dict[str, Any]:
    raw_limit = _request.query_params.get("limit")
    try:
        limit = max(1, min(200, int(raw_limit))) if raw_limit else 200
    except ValueError:
        limit = 200
    with get_db() as conn:
        _get_session_or_404(conn, _session_id)
        items = _list_messages(conn, _session_id, limit=limit)
    return {"session_id": _session_id, "items": items}


def list_user_notes(_session_id: str, _request: Request) -> Dict[str, Any]:
    raw_limit = _request.query_params.get("limit")
    try:
        limit = max(1, min(200, int(raw_limit))) if raw_limit else 100
    except ValueError:
        limit = 100
    with get_db() as conn:
        _get_session_or_404(conn, _session_id)
        items = _list_user_notes(conn, _session_id, limit=limit)
    return {"session_id": _session_id, "items": items, "limit": limit}


def create_user_note(_session_id: str, _body: Any) -> Dict[str, Any]:
    payload = _body.model_dump() if hasattr(_body, "model_dump") else dict(_body or {})
    query = _normalize_text(payload.get("query"))
    place_name = _normalize_text(payload.get("place_name")) or query
    city = _normalize_text(payload.get("city"))
    comment = _normalize_text(payload.get("comment"))
    rating_raw = payload.get("rating")
    rating: Optional[int] = None
    if rating_raw not in (None, ""):
        try:
            rating = int(rating_raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="rating must be an integer between 1 and 5")
        if rating < 1 or rating > 5:
            raise HTTPException(status_code=400, detail="rating must be between 1 and 5")
    poi = payload.get("poi") if isinstance(payload.get("poi"), dict) else None
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    if not place_name:
        raise HTTPException(status_code=400, detail="place_name is required")
    if not comment and rating is None and not poi:
        raise HTTPException(status_code=400, detail="comment, rating, or poi is required")

    with get_db() as conn:
        _get_session_or_404(conn, _session_id)
        saved = _insert_user_note(
            conn,
            _session_id,
            city=city,
            query=query,
            place_name=place_name,
            rating=rating,
            comment=comment,
            poi=poi,
        )
        conn.commit()
    return {"session_id": _session_id, "note": saved}


def delete_user_note(_session_id: str, note_id: str) -> Dict[str, Any]:
    normalized_note_id = _normalize_text(note_id)
    if not normalized_note_id:
        raise HTTPException(status_code=400, detail="note_id is required")
    with get_db() as conn:
        _get_session_or_404(conn, _session_id)
        row = conn.execute(
            "SELECT * FROM user_place_notes WHERE id = ? AND session_id = ?",
            (normalized_note_id, _session_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="note not found")
        conn.execute(
            "DELETE FROM user_place_notes WHERE id = ? AND session_id = ?",
            (normalized_note_id, _session_id),
        )
        conn.commit()
    return {"session_id": _session_id, "deleted": normalized_note_id}

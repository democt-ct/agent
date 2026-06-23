import math
import os
import re
import uuid
from html import unescape
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx


WEB_CONTEXT_MAX_ITEMS = int(os.getenv("WEB_CONTEXT_MAX_ITEMS", "5"))
WEB_CONTEXT_MAX_CHARS = int(os.getenv("WEB_CONTEXT_MAX_CHARS", "1800"))


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def repair_mojibake_text(text: str) -> str:
    if not text:
        return text

    def score(candidate: str) -> int:
        cjk_count = len(re.findall(r"[\u4e00-\u9fff]", candidate))
        meaningful_chars = sum(
            candidate.count(char)
            for char in "\u6211\u60f3\u5728\u53bb\u5230\u73a9\u5929\u65e5\u9884\u7b97\u8f7b\u677e\u5403\u672c\u5730\u7f8e\u98df\u591c\u666f\u57ce\u5e02\u666f\u533a"
        )
        mojibake_markers = sum(
            candidate.count(marker)
            for marker in [
                "\u00e6",
                "\u00e5",
                "\u00e8",
                "\u00e7",
                "\u00c2",
                "\u00c3",
                "\u5fd9",
                "\u8062",
                "\u806d",
                "\u6c13",
                "\u83bd",
                "\u7984",
                "\u788c",
                "\u8305",
                "\u9c81",
                "\u8075",
                "\u8059",
                "\u805c",
                "\u732b",
                "\u76f2",
                "\u8d42",
            ]
        )
        return cjk_count * 2 + meaningful_chars * 20 - mojibake_markers * 8 - candidate.count("\ufffd") * 10

    def try_decode(candidate: str, encode_as: str, decode_as: str) -> Optional[str]:
        try:
            return candidate.encode(encode_as).decode(decode_as)
        except UnicodeError:
            return None

    candidates = [text]
    latin1_repaired = try_decode(text, "latin1", "utf-8")
    if latin1_repaired:
        candidates.append(latin1_repaired)
    cp1252_repaired = try_decode(text, "cp1252", "utf-8")
    if cp1252_repaired:
        candidates.append(cp1252_repaired)

    utf8_seen_as_gbk = try_decode(text, "gbk", "utf-8")
    if utf8_seen_as_gbk:
        candidates.append(utf8_seen_as_gbk)
        second_pass = try_decode(utf8_seen_as_gbk, "latin1", "utf-8")
        if second_pass:
            candidates.append(second_pass)
        second_pass = try_decode(utf8_seen_as_gbk, "cp1252", "utf-8")
        if second_pass:
            candidates.append(second_pass)

    return max(candidates, key=score)


def normalize_request_text(text: Optional[str]) -> str:
    return repair_mojibake_text(text or "").strip()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def parse_limit(raw: Optional[str]) -> int:
    try:
        if raw is None:
            return 50
        value = int(raw)
        if value <= 0:
            return 50
        return min(value, 100)
    except (TypeError, ValueError):
        return 50


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _decode_label(value: str) -> str:
    return value.encode("ascii").decode("unicode_escape")


def _parse_chinese_number(value: str) -> Optional[int]:
    value = value.strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)

    digits = {
        _decode_label(r"\u96f6"): 0,
        _decode_label(r"\u4e00"): 1,
        _decode_label(r"\u4e8c"): 2,
        _decode_label(r"\u4e24"): 2,
        _decode_label(r"\u4e09"): 3,
        _decode_label(r"\u56db"): 4,
        _decode_label(r"\u4e94"): 5,
        _decode_label(r"\u516d"): 6,
        _decode_label(r"\u4e03"): 7,
        _decode_label(r"\u516b"): 8,
        _decode_label(r"\u4e5d"): 9,
    }
    ten = _decode_label(r"\u5341")
    if value == ten:
        return 10
    if ten in value:
        left, _, right = value.partition(ten)
        tens = digits.get(left, 1) if left else 1
        ones = digits.get(right, 0) if right else 0
        return tens * 10 + ones
    return digits.get(value)


def normalize_text_for_matching(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", (value or "").lower())


def extract_urls(text: str, limit: int = WEB_CONTEXT_MAX_ITEMS) -> List[str]:
    urls = re.findall(r"https?://[^\s<>\"]+", text or "")
    cleaned: List[str] = []
    for url in urls:
        normalized = url.rstrip("。，,.;:!?")
        if normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned[: max(1, limit)]


def is_blocked_fetch_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return True
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "0.0.0.0", "::1"}:
        return True
    if host.startswith(("127.", "10.", "169.254.", "192.168.")):
        return True
    if re.match(r"^172\.(1[6-9]|2\d|3[0-1])\.", host):
        return True
    return False


def strip_html_to_text(html: str, max_chars: int = WEB_CONTEXT_MAX_CHARS) -> str:
    text = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", html or "")
    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html or "")
    description_match = re.search(
        r"(?is)<meta[^>]+name=[\"']description[\"'][^>]+content=[\"'](.*?)[\"'][^>]*>",
        html or "",
    )
    title = unescape(re.sub(r"<[^>]+>", " ", title_match.group(1))).strip() if title_match else ""
    description = unescape(description_match.group(1)).strip() if description_match else ""
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    combined = " ".join(part for part in [title, description, text] if part)
    return combined[: max(1, max_chars)]


def normalize_location_point(point: Any) -> Optional[Dict[str, float]]:
    if isinstance(point, dict):
        lat = point.get("lat")
        lng = point.get("lng")
        if lat is None or lng is None:
            return None
        try:
            return {"lat": float(lat), "lng": float(lng)}
        except (TypeError, ValueError):
            return None
    if isinstance(point, (list, tuple)) and len(point) >= 2:
        try:
            return {"lng": float(point[0]), "lat": float(point[1])}
        except (TypeError, ValueError, IndexError):
            return None
    return None


def haversine_meters(a: Any, b: Any) -> int:
    point_a = normalize_location_point(a)
    point_b = normalize_location_point(b)
    if not point_a or not point_b:
        return 0
    radius = 6371000
    lat1 = math.radians(point_a["lat"])
    lat2 = math.radians(point_b["lat"])
    d_lat = math.radians(point_b["lat"] - point_a["lat"])
    d_lng = math.radians(point_b["lng"] - point_a["lng"])
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    return round(2 * radius * math.asin(math.sqrt(h)))


def parse_amap_location(value: Any) -> Optional[Dict[str, float]]:
    if isinstance(value, dict):
        if value.get("lng") is not None and value.get("lat") is not None:
            try:
                return {"lng": float(value["lng"]), "lat": float(value["lat"])}
            except (TypeError, ValueError, KeyError):
                return None
        if value.get("longitude") is not None and value.get("latitude") is not None:
            try:
                return {"lng": float(value["longitude"]), "lat": float(value["latitude"])}
            except (TypeError, ValueError, KeyError):
                return None
        if isinstance(value.get("location"), str):
            return parse_amap_location(value["location"])
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        if len(parts) >= 2:
            try:
                return {"lng": float(parts[0]), "lat": float(parts[1])}
            except (TypeError, ValueError):
                return None
    return None


def parse_amap_polyline(value: Any) -> List[Dict[str, float]]:
    if not value:
        return []
    raw_points: List[str] = []
    if isinstance(value, str):
        raw_points = [part.strip() for part in value.split(";") if part.strip()]
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                raw_points.extend([part.strip() for part in item.split(";") if part.strip()])
            elif isinstance(item, dict):
                location = parse_amap_location(item)
                if location:
                    raw_points.append(f"{location['lng']},{location['lat']}")
    points: List[Dict[str, float]] = []
    for part in raw_points:
        point = parse_amap_location(part)
        if point:
            points.append(point)
    return points


def infer_place_category(text: str, fallback: Optional[str] = None) -> str:
    content = normalize_text_for_matching(text)
    if not content:
        return fallback or "other"
    if any(keyword in content for keyword in ["酒店", "宾馆", "住宿", "民宿"]):
        return "hotel"
    if any(keyword in content for keyword in ["美食", "餐厅", "饭店", "火锅", "小吃", "餐饮", "食府"]):
        return "food"
    if any(keyword in content for keyword in ["咖啡", "咖啡店", "咖啡馆", "下午茶"]):
        return "cafe"
    if any(keyword in content for keyword in ["商场", "购物", "广场", "购物中心"]):
        return "mall"
    if any(keyword in content for keyword in ["夜景", "夜游", "观景台", "灯光", "夜市"]):
        return "nightview"
    if any(keyword in content for keyword in ["公园", "景点", "景区", "博物馆", "古城", "古镇", "寺", "塔", "桥", "街", "步行街"]):
        return "landmark"
    if any(keyword in content for keyword in ["散步", "citywalk", "老街", "街区", "步行"]):
        return "citywalk"
    if any(keyword in content for keyword in ["山", "湖", "海", "自然", "风景", "景区"]):
        return "nature"
    return fallback or "other"


def extract_place_name_candidates(text: str) -> List[str]:
    if not text:
        return []
    cleaned = re.sub(r"\s+", " ", str(text)).strip()
    if not cleaned:
        return []
    patterns = [
        r"([A-Za-z][A-Za-z0-9&·\-\s]{2,40}?(?:coffee|cafe|restaurant|hotel|bar|bistro|museum|park|plaza|mall))",
        r"([\u4e00-\u9fffA-Za-z0-9·]{2,20}?(?:景区|景点|公园|广场|寺|塔|桥|街|巷|馆|楼|城|镇|村|园|湾|湖|山|岛|夜市|商场|中心|博物馆|老街|古镇|步行街|观景台|咖啡馆|咖啡店|咖啡|火锅店|餐厅|小吃街|美食街))",
        r"“([^”]{2,24})”",
        r'"([^"]{2,24})"',
    ]
    results: List[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, cleaned, re.I):
            candidate = " ".join(match.group(1).split()).strip(" ,.;:!?，。；：")
            normalized = normalize_text_for_matching(candidate)
            if not candidate or len(normalized) < 2 or normalized in seen:
                continue
            seen.add(normalized)
            results.append(candidate[:32])
    return results[:12]


def extract_web_place_names(web_context: Optional[Dict[str, Any]]) -> List[str]:
    if not web_context or not isinstance(web_context, dict):
        return []
    collected: List[str] = []
    seen: set[str] = set()
    for item in web_context.get("items", []):
        if not isinstance(item, dict) or item.get("status") != "ok":
            continue
        for source_text in (
            str(item.get("title") or ""),
            str(item.get("snippet") or ""),
            str(item.get("text") or ""),
        ):
            for name in extract_place_name_candidates(source_text):
                normalized = normalize_text_for_matching(name)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                collected.append(name)
                if len(collected) >= 12:
                    return collected
    return collected


def has_web_context_intent(text: str) -> bool:
    lowered = (text or "").lower()
    keywords = [
        "http://",
        "https://",
        "联网",
        "网页",
        "搜索",
        "查一查",
        "小红书",
        "微博",
        "攻略",
        "推荐",
        "打卡",
        "必打卡",
        "散步",
        "地标",
        "景点",
    ]
    return any(keyword in lowered for keyword in keywords)


def should_auto_web_search(text: str, requirement: Optional[Dict[str, Any]] = None) -> bool:
    normalized = normalize_request_text(text)
    if not normalized:
        return False
    if has_web_context_intent(normalized):
        return True
    requirement = requirement or {}
    destination = str(requirement.get("destination") or "").strip()
    interests = " ".join(str(item) for item in (requirement.get("interests") or []) if str(item).strip())
    preferences = requirement.get("user_preferences") if isinstance(requirement.get("user_preferences"), dict) else {}
    search_intent = bool(
        re.search(
            r"推荐|攻略|路线|行程|怎么玩|怎么逛|适合|安排|规划|day\s*\d|第\d+天|一日游|两日游|三日游|周末游|亲子|情侣|带娃|轻松|深度",
            normalized,
            re.I,
        )
    )
    has_trip_signal = bool(destination or interests or preferences or requirement.get("trip_days"))
    return search_intent or has_trip_signal


async def fetch_public_web_page(client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
    if is_blocked_fetch_url(url):
        return {"url": url, "status": "blocked", "reason": "unsupported_or_private_url"}
    try:
        response = await client.get(url, follow_redirects=True)
    except httpx.HTTPError as exc:
        return {"url": url, "status": "error", "reason": str(exc)}

    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400:
        return {"url": url, "status": "error", "reason": f"http_{response.status_code}"}
    if "text/html" not in content_type and "text/plain" not in content_type:
        return {"url": str(response.url), "status": "skipped", "reason": f"content_type:{content_type}"}

    text = strip_html_to_text(response.text)
    title = text[:120]
    return {
        "url": str(response.url),
        "status": "ok",
        "title": title,
        "snippet": text,
    }

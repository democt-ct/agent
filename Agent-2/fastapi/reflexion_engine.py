"""
Reflexion engine: two-round validate-and-repair loop for itinerary quality.
Round 1 – Quality: coordinates, generic names, classicness, category diversity.
Round 2 – Route: jump distance, total daily distance, backtrack ratio, 2-opt reorder.
"""
import re
import math
from typing import Any, Dict, List, Optional, Set
from copy import deepcopy


# ── Constants ──────────────────────────────────────────────────

SIGHTSEEING_SLOTS = ["上午", "午间", "下午", "午后", "晚上"]
SIGHTSEEING_SLOT_LABELS = {
    "上午": "核心景点",
    "午间": "文化探索",
    "下午": "街区漫步",
    "午后": "休闲体验",
    "晚上": "夜景夜游",
}

GENERIC_NAME_PATTERNS = [
    re.compile(r"^[景点美食小吃咖啡商场公园夜景博物馆步行街商圈老街]+$"),
    re.compile(r"^(景点|美食|小吃|咖啡|商场|公园|夜景|博物馆|步行街|商圈|老街|夜市|住宿|酒店|特色|打卡|路线)$"),
    re.compile(r"^(特色景点|本地美食|热门景点|旅游攻略|美食推荐|必去路线|经典路线|必去)$"),
    re.compile(r"^.*攻略.*$|^.*推荐.*$|^.*路线.*$"),
    re.compile(r"步行街$"),
    re.compile(r"美食$"),
    re.compile(r"^(.{1,3}(路|街|道|巷|弄|镇|乡|村|区|县|新城|新区|片区|板块))$"),
    re.compile(r"^(.{1,4}(商圈|片区|板块|开发区|高新区|经济区))$"),
]

CLASSICNESS_MIN_SCORE = 35
MAX_JUMP_METERS = 15000
MAX_DAILY_TOTAL_METERS = 40000
MAX_SUBURB_DISTANCE_METERS = 25000
BACKTRACK_RATIO_THRESHOLD = 0.45
PER_DAY_TARGET = 5

FOOD_INTEREST_PATTERNS = re.compile(
    r"food|cafe|shopping|restaurant|eat|meal"
    r"|美食|咖啡|商场|小吃|火锅|餐饮|下午茶|夜宵|茶饮|吃|饭|餐厅|料理|烤肉"
)

SLOT_KIND_PREFERENCE = {
    "上午": ["attraction", "museum", "park", "old_street"],
    "午间": ["museum", "old_street", "park", "attraction"],
    "下午": ["old_street", "shopping", "park", "cafe", "attraction"],
    "午后": ["cafe", "park", "shopping", "old_street", "museum"],
    "晚上": ["night_view", "bar", "old_street", "shopping", "attraction"],
}


# ── Helpers ────────────────────────────────────────────────────

def _norm(value: Any) -> str:
    return re.sub(r"[^一-龥a-z0-9]", "", str(value or "").strip().lower())


def _is_generic_name(name: str) -> bool:
    return any(p.search(name.strip()) for p in GENERIC_NAME_PATTERNS)


def _distance_meters(a: Optional[Dict[str, float]], b: Optional[Dict[str, float]]) -> Optional[float]:
    if not a or not b:
        return None
    lat1, lng1 = float(a.get("lat", 0)), float(a.get("lng", 0))
    lat2, lng2 = float(b.get("lat", 0)), float(b.get("lng", 0))
    r = 6371000
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    h = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(h)))


def _within_suburb_limit(candidate: Dict[str, Any], reference_center: Dict[str, float], max_meters: float = MAX_SUBURB_DISTANCE_METERS) -> bool:
    poi = candidate.get("poi") or {}
    loc = poi.get("location")
    if not loc or not reference_center:
        return True
    d = _distance_meters(loc, reference_center)
    if d is None:
        return True
    return d <= max_meters


def _get_place_name(item: Dict[str, Any]) -> str:
    selected = (item.get("selected_places") or [{}])[0] or {}
    return str(selected.get("name") or item.get("text") or "").strip()


def _get_place_location(item: Dict[str, Any]) -> Optional[Dict[str, float]]:
    from core import parse_amap_location  # resolved at runtime

    selected = (item.get("selected_places") or [{}])[0] or {}
    return parse_amap_location(selected.get("location"))


def _get_place_kind(item: Dict[str, Any]) -> str:
    selected = (item.get("selected_places") or [{}])[0] or {}
    return _norm(selected.get("place_kind") or "")


def _get_place_poi_id(item: Dict[str, Any]) -> str:
    selected = (item.get("selected_places") or [{}])[0] or {}
    return _norm(selected.get("poi_id") or "")


# ── Food interest detection ────────────────────────────────────

def has_food_interest(requirement_payload: Dict[str, Any]) -> bool:
    interests = requirement_payload.get("interests") or []
    if not interests:
        user_input = _norm(requirement_payload.get("raw_input") or requirement_payload.get("message") or "")
        return bool(FOOD_INTEREST_PATTERNS.search(user_input))
    return any(FOOD_INTEREST_PATTERNS.search(_norm(str(i))) for i in interests)


# ── Round 1: Quality Validation ────────────────────────────────

def validate_quality(itinerary: Dict[str, Any]) -> List[Dict[str, Any]]:
    from poi_tags import infer_poi_tags, FunctionDimension
    issues: List[Dict[str, Any]] = []
    for day in itinerary.get("days") or []:
        day_index = int(day.get("day_index") or 0)
        categories_seen: Set[str] = set()
        functions_seen: Set[str] = set()
        for idx, item in enumerate(day.get("items") or []):
            name = _get_place_name(item)
            loc = _get_place_location(item)
            kind = _get_place_kind(item)
            poi_id = _get_place_poi_id(item)

            if not loc or not poi_id:
                issues.append({
                    "day": day_index, "index": idx, "name": name,
                    "type": "no_location", "detail": f"{name} 无坐标或POI ID", "action": "replace"
                })
                continue

            if _is_generic_name(name):
                issues.append({
                    "day": day_index, "index": idx, "name": name,
                    "type": "generic_name", "detail": f"{name} 是泛类别词", "action": "replace"
                })

            if kind in categories_seen:
                issues.append({
                    "day": day_index, "index": idx, "name": name,
                    "type": "category_overlap", "detail": f"{name} 类别 {kind} 当天重复", "action": "swap"
                })
            categories_seen.add(kind)

            # Five-dimension function overlap check
            selected = (item.get("selected_places") or [{}])[0] or {}
            tag = infer_poi_tags(
                name=name,
                category=selected.get("category") or "",
                query=selected.get("source_query") or selected.get("candidate_name") or "",
                legacy_place_kind=kind,
            )
            func_val = tag.function.value
            if func_val in functions_seen:
                issues.append({
                    "day": day_index, "index": idx, "name": name,
                    "type": "function_overlap", "detail": f"{name} 功能属性 {func_val} 当天重复", "action": "swap"
                })
            functions_seen.add(func_val)

        located_count = sum(1 for item in (day.get("items") or []) if _get_place_location(item))
        if located_count < 4:
            issues.append({
                "day": day_index, "index": -1, "name": "",
                "type": "too_few_items", "detail": f"Day {day_index} 仅有 {located_count} 个可落图地点", "action": "fill"
            })

    return issues


# ── Round 2: Route Validation ─────────────────────────────────

def validate_route(itinerary: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    for day in itinerary.get("days") or []:
        day_index = int(day.get("day_index") or 0)
        located: List[Dict[str, Any]] = []
        for item in day.get("items") or []:
            loc = _get_place_location(item)
            if loc:
                located.append({"item": item, "location": loc, "name": _get_place_name(item)})

        if len(located) < 2:
            continue

        total_dist = 0
        for i in range(len(located) - 1):
            d = _distance_meters(located[i]["location"], located[i + 1]["location"])
            if d is None:
                continue
            total_dist += d
            if d > MAX_JUMP_METERS:
                issues.append({
                    "day": day_index, "type": "long_jump",
                    "detail": f"{located[i]['name']} → {located[i+1]['name']} 距离 {d / 1000:.1f}km",
                    "segment_index": i, "distance_meters": d, "action": "swap_points"
                })

        if total_dist > MAX_DAILY_TOTAL_METERS:
            issues.append({
                "day": day_index, "type": "excessive_total",
                "detail": f"当天总距离 {total_dist / 1000:.1f}km",
                "distance_meters": total_dist, "action": "reorder_2opt"
            })

        if len(located) >= 3:
            crown = _distance_meters(located[0]["location"], located[-1]["location"])
            if crown and crown > 0 and total_dist > 0:
                ratio = crown / total_dist
                if ratio < BACKTRACK_RATIO_THRESHOLD:
                    issues.append({
                        "day": day_index, "type": "backtrack",
                        "detail": f"折返比 {ratio:.2f}，路线之字形严重",
                        "distance_meters": round(crown), "action": "reorder_2opt"
                    })

    return issues


# ── 2-opt Route Optimizer ─────────────────────────────────────

def reorder_2opt(day: Dict[str, Any]) -> Dict[str, Any]:
    items = day.get("items") or []
    located = [(i, _get_place_location(item)) for i, item in enumerate(items) if _get_place_location(item)]
    if len(located) < 3:
        return day

    n = len(located)
    best_order = list(range(n))
    best_dist = _path_distance([loc for _, loc in located], best_order)

    for a in range(n - 1):
        for b in range(a + 2, n):
            cand = best_order[:a] + best_order[a:b + 1][::-1] + best_order[b + 1:]
            d = _path_distance([loc for _, loc in located], cand)
            if d is not None and d < (best_dist or float("inf")):
                best_order = cand
                best_dist = d

    ordered = [located[i][0] for i in best_order]
    ordered_items = [items[i] for i in ordered]
    no_loc = [items[i] for i in range(len(items)) if not _get_place_location(items[i])]
    day["items"] = ordered_items + no_loc
    return day


def _path_distance(locations: List, order: List[int]) -> Optional[float]:
    total = 0.0
    for j in range(len(order) - 1):
        d = _distance_meters(locations[order[j]], locations[order[j + 1]])
        if d is None:
            return None
        total += d
    return total


# ── Main Reflexion Loop ────────────────────────────────────────

def reflexion_loop(
    itinerary: Dict[str, Any],
    validated_candidates: List[Dict[str, Any]],
    max_rounds: int = 2,
    reference_center: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Two-round reflexion loop:
      Round 1 → validate quality → repair → re-validate
      Round 2 → validate route   → repair → 2-opt
    Returns enriched itinerary with reflexion metadata.
    """
    enriched = deepcopy(itinerary)
    reflexion_log: List[str] = []

    for round_num in range(1, max_rounds + 1):
        # Round 1: Quality
        q_issues = validate_quality(enriched)
        if q_issues:
            _apply_quality_repairs(enriched, q_issues, validated_candidates, reflexion_log, reference_center=reference_center)

        # Round 2: Route
        r_issues = validate_route(enriched)
        if r_issues:
            _apply_route_repairs(enriched, r_issues, reflexion_log)

        # Re-check
        q_remaining = validate_quality(enriched)
        r_remaining = validate_route(enriched)

        if not q_remaining and not r_remaining:
            reflexion_log.append(f"[reflexion] stable after round {round_num}")
            break
    else:
        reflexion_log.append("[reflexion] max rounds reached, may have remaining issues")

    # Fill under-filled days
    _fill_underfilled_days(enriched, validated_candidates, reflexion_log, reference_center=reference_center)

    # Final 2-opt on each day
    for day in enriched.get("days") or []:
        reorder_2opt(day)

    enriched["reflexion_log"] = reflexion_log
    enriched["reflexion_stable"] = not bool(validate_quality(enriched) or validate_route(enriched))
    return enriched


def _apply_quality_repairs(
    itinerary: Dict[str, Any],
    issues: List[Dict[str, Any]],
    validated_candidates: List[Dict[str, Any]],
    log: List[str],
    reference_center: Optional[Dict[str, float]] = None,
) -> None:
    used_poi_ids: Set[str] = set()
    for day in itinerary.get("days") or []:
        for item in day.get("items") or []:
            pid = _get_place_poi_id(item)
            if pid:
                used_poi_ids.add(pid)

    for issue in issues:
        day = next((d for d in itinerary.get("days") or [] if int(d.get("day_index") or 0) == issue["day"]), None)
        if not day:
            continue
        idx = issue["index"]
        if idx < 0 or idx >= len(day.get("items") or []):
            continue

        if issue["action"] == "replace":
            old_item = day["items"][idx]
            old_name = _get_place_name(old_item)
            replacement = _find_replacement(old_item, validated_candidates, used_poi_ids, reference_center=reference_center)
            if replacement:
                used_poi_ids.add(_norm((replacement.get("poi") or {}).get("poi_id") or ""))
                day["items"][idx] = replacement
                log.append(f"[repair] replace: {old_name} → {_get_place_name(replacement)} ({issue['type']})")
            else:
                log.append(f"[repair] no replacement for: {old_name} ({issue['type']})")

        elif issue["action"] == "swap" and idx + 1 < len(day["items"]):
            day["items"][idx], day["items"][idx + 1] = day["items"][idx + 1], day["items"][idx]
            log.append(f"[repair] swap: {issue['name']} ({issue['type']})")


def _apply_route_repairs(
    itinerary: Dict[str, Any],
    issues: List[Dict[str, Any]],
    log: List[str],
) -> None:
    for issue in issues:
        day = next((d for d in itinerary.get("days") or [] if int(d.get("day_index") or 0) == issue["day"]), None)
        if not day:
            continue
        if issue["action"] == "reorder_2opt":
            reorder_2opt(day)
            log.append(f"[repair] 2-opt: Day {issue['day']} ({issue['type']}: {issue['detail']})")


def _fill_underfilled_days(
    itinerary: Dict[str, Any],
    validated_candidates: List[Dict[str, Any]],
    log: List[str],
    reference_center: Optional[Dict[str, float]] = None,
) -> None:
    used_poi_ids: Set[str] = set()
    for day in itinerary.get("days") or []:
        for item in day.get("items") or []:
            pid = _get_place_poi_id(item)
            if pid:
                used_poi_ids.add(pid)

    for day in itinerary.get("days") or []:
        day_index = int(day.get("day_index") or 0)
        current = len(day.get("items") or [])
        if current >= PER_DAY_TARGET:
            continue

        available = [
            c for c in validated_candidates
            if _norm((c.get("poi") or {}).get("poi_id") or "") not in used_poi_ids
            and (c.get("poi") or {}).get("location")
            and not _is_generic_name(str((c.get("poi") or {}).get("name") or ""))
            and _norm((c.get("poi") or {}).get("place_kind") or "") != "admin_area"
        ]

        if reference_center:
            available = [
                c for c in available
                if _within_suburb_limit(c, reference_center)
            ]

        slots_pool = SIGHTSEEING_SLOTS
        for i, candidate in enumerate(available):
            if current + i >= PER_DAY_TARGET:
                break
            poi = candidate.get("poi") or {}
            pid = _norm(poi.get("poi_id") or "")
            used_poi_ids.add(pid)
            slot = slots_pool[min(current + i, len(slots_pool) - 1)]
            day.setdefault("items", []).append({
                "slot": slot,
                "poi_id": poi.get("poi_id"),
                "name": poi.get("name"),
                "reason": "reflexion fill – 自动补全游玩地点",
                "selected_places": [poi],
            })
            log.append(f"[repair] fill Day {day_index}: +{poi.get('name')} @ {slot}")


def _find_replacement(
    old_item: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    used_poi_ids: Set[str],
    reference_center: Optional[Dict[str, float]] = None,
) -> Optional[Dict[str, Any]]:
    from poi_tags import infer_poi_tags
    old_name = _get_place_name(old_item)
    old_loc = _get_place_location(old_item)
    old_kind = _get_place_kind(old_item)
    old_selected = (old_item.get("selected_places") or [{}])[0] or {}
    old_tag = infer_poi_tags(
        name=old_name,
        category=old_selected.get("category") or "",
        query=old_selected.get("source_query") or old_selected.get("candidate_name") or "",
        legacy_place_kind=old_kind,
    )

    scored = []
    for c in candidates:
        poi = c.get("poi") or {}
        pid = _norm(poi.get("poi_id") or "")
        if not pid or pid in used_poi_ids:
            continue
        name = str(poi.get("name") or "")
        if _is_generic_name(name) or _norm(name) == _norm(old_name):
            continue
        if _norm(poi.get("place_kind") or "") == "admin_area":
            continue
        loc = (c.get("poi") or {}).get("location")
        if not loc:
            continue
        if reference_center and not _within_suburb_limit(c, reference_center):
            continue
        # Five-dimension similarity scoring
        new_tag = infer_poi_tags(
            name=name,
            category=poi.get("category") or "",
            query=c.get("query") or "",
            legacy_place_kind=poi.get("place_kind") or "",
        )
        if old_tag.function == new_tag.function:
            kind_match = 25
        elif old_tag.legacy_place_kind == (poi.get("place_kind") or ""):
            kind_match = 15
        else:
            kind_match = 5
        kind_match += len(set(old_tag.experience) & set(new_tag.experience)) * 3
        dist_bonus = 0
        if old_loc and loc:
            d = _distance_meters(old_loc, loc)
            if d is not None:
                dist_bonus = max(0, 15 - d / 1000)
        score = kind_match + dist_bonus
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored else None

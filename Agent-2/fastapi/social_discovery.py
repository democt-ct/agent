"""
Social Discovery Module — 社交媒体地点发现层

用网络搜索（DuckDuckGo，免费无 Key）采集小红书、抖音等平台上的真实地点推荐，
替代 LLM 凭训练记忆"编造"候选地点。LLM 角色从"生成"转变为"策展/筛选"。

Usage:
    result = await discover_places_from_social("成都", interests=["美食", "历史文化"])
    # result["places"] → [{"name": "人民公园", "source_snippet": "...", ...}, ...]
"""
import asyncio
import os
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote

import httpx

from utils.helpers import (
    extract_place_name_candidates,
    normalize_text_for_matching,
)

# ── Configurable environment variables ──────────────────────────

SOCIAL_DISCOVERY_TIMEOUT_SEC = float(os.getenv("SOCIAL_DISCOVERY_TIMEOUT_SEC", "10.0"))
SOCIAL_DISCOVERY_MAX_PLACES = int(os.getenv("SOCIAL_DISCOVERY_MAX_PLACES", "25"))
SOCIAL_DISCOVERY_MAX_QUERIES = int(os.getenv("SOCIAL_DISCOVERY_MAX_QUERIES", "8"))
SOCIAL_DISCOVERY_RESULTS_PER_QUERY = int(os.getenv("SOCIAL_DISCOVERY_RESULTS_PER_QUERY", "5"))


def _norm(value: str) -> str:
    return normalize_text_for_matching(value)


# ── Query generation ────────────────────────────────────────────

# General discovery queries — capture different angles of "not just tourist traps"
DISCOVERY_QUERY_TEMPLATES: List[str] = [
    "{city} 小众景点 本地人推荐",
    "{city} 冷门但值得去 宝藏打卡",
    "{city} 避开游客 深度游攻略",
    "{city} 本地人才知道的地方",
    "{city} 周末去哪儿 推荐 2025",
]

# Interest-specific query templates
INTEREST_QUERY_TEMPLATES: List[str] = [
    "{city} {interest} 推荐 攻略",
    "{city} {interest} 小众 本地人",
]

# Trip-style specific
STYLE_QUERY_HINTS: Dict[str, List[str]] = {
    "relaxed": ["{city} 慢节奏 散步路线", "{city} 适合发呆的地方"],
    "compact": ["{city} 一日游 高效路线", "{city} 特种兵 打卡路线"],
    "photography": ["{city} 拍照出片 小众机位", "{city} 摄影打卡"],
    "food": ["{city} 本地人爱吃 非网红 美食", "{city} 苍蝇馆子 老店"],
    "culture": ["{city} 冷门博物馆 历史街区", "{city} 非遗体验 手作"],
    "nature": ["{city} 冷门公园 徒步路线", "{city} 近郊自然 一日游"],
    "family": ["{city} 亲子 不挤 好玩", "{city} 遛娃 宝藏地"],
    "night": ["{city} 夜景 非大众 观景点", "{city} 夜晚氛围 街区"],
}


def generate_social_queries(
    city: str,
    interests: Optional[List[str]] = None,
    trip_style: str = "",
    max_queries: int = SOCIAL_DISCOVERY_MAX_QUERIES,
) -> List[str]:
    """Generate diverse search queries targeting social platform content."""
    queries: List[str] = []

    # 1. General discovery
    for template in DISCOVERY_QUERY_TEMPLATES:
        queries.append(template.format(city=city))

    # 2. Interest-specific
    for interest in (interests or [])[:3]:
        for template in INTEREST_QUERY_TEMPLATES:
            queries.append(template.format(city=city, interest=interest))

    # 3. Trip-style specific hints
    style_key = (trip_style or "").strip().lower()
    if style_key in STYLE_QUERY_HINTS:
        for template in STYLE_QUERY_HINTS[style_key]:
            queries.append(template.format(city=city))

    # 4. Deduplicate by normalized text
    seen: Set[str] = set()
    deduped: List[str] = []
    for q in queries:
        nq = _norm(q)
        if nq and nq not in seen:
            seen.add(nq)
            deduped.append(q)

    return deduped[:max_queries]


# ── Bing search (works in China, no API key required) ──────────

_BING_URL = "https://www.bing.com/search"
_TAG_RE = re.compile(r'<[^>]+>')


def _strip_html_tags(html: str) -> str:
    return _TAG_RE.sub(' ', html).strip()


def _extract_bing_results(html: str, max_results: int) -> List[Dict[str, str]]:
    """Parse Bing search results page."""
    results: List[Dict[str, str]] = []
    # Bing organic results have class="b_algo" — find each block
    # Use split approach: find all b_algo start positions, extract until next b_algo or end
    algo_positions = [m.start() for m in re.finditer(r'class="b_algo"', html)]
    
    for i, pos in enumerate(algo_positions[:max_results]):
        end_pos = algo_positions[i + 1] if i + 1 < len(algo_positions) else len(html)
        block = html[pos:end_pos]

        # Extract title — h2 > a
        title_m = re.search(r'<h2[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', block, re.DOTALL)
        if not title_m:
            continue
        url = title_m.group(1)
        title = _strip_html_tags(title_m.group(2))

        # Extract snippet
        snippet = ""
        for pat in [r'<p[^>]*>(.*?)</p>', r'class="b_caption"[^>]*>(.*?)</div>']:
            m = re.search(pat, block, re.DOTALL)
            if m:
                snippet = _strip_html_tags(m.group(1))
                if len(snippet) > 10:
                    break

        if title:
            results.append({
                "title": title,
                "snippet": snippet,
                "url": url,
            })

    return results


async def search_bing(
    query: str,
    max_results: int = SOCIAL_DISCOVERY_RESULTS_PER_QUERY,
) -> List[Dict[str, str]]:
    """
    Search Bing via HTML scraping. Works in China, no API key required.
    """
    url = f"{_BING_URL}?q={quote(query)}&setlang=zh-cn"

    try:
        async with httpx.AsyncClient(timeout=SOCIAL_DISCOVERY_TIMEOUT_SEC, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )
            resp.raise_for_status()
    except httpx.HTTPError:
        return []

    return _extract_bing_results(resp.text, max_results)


# ── POI name extraction from search results ─────────────────────

def extract_poi_names_from_results(
    results: List[Dict[str, str]],
    max_places: int = SOCIAL_DISCOVERY_MAX_PLACES,
) -> List[Dict[str, Any]]:
    """
    Extract distinct POI names from a batch of search result snippets.
    Uses the existing `extract_place_name_candidates` helper for pattern matching.
    """
    places: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for result in results:
        combined = f"{result.get('title', '')} {result.get('snippet', '')}"
        names = extract_place_name_candidates(combined)

        for name in names:
            n = _norm(name)
            if not n or len(n) < 2 or n in seen:
                continue
            # Skip names that are pure category/query terms, not real places
            if _is_generic_category_term(name):
                continue
            seen.add(n)
            places.append({
                "name": name,
                "source_title": result.get("title", ""),
                "source_snippet": (result.get("snippet", "") or "")[:200],
                "source_url": result.get("url", ""),
            })

        if len(places) >= max_places:
            break

    return places


# Category terms that aren't real place names — filter them out
_GENERIC_CATEGORY_PATTERNS = [
    re.compile(r"^(景点|美食|小吃|咖啡|商场|公园|夜景|博物馆|步行街|商圈|老街|夜市|住宿|酒店|特色|打卡|路线|攻略|推荐)$"),
    re.compile(r"^(特色景点|本地美食|热门景点|旅游攻略|美食推荐|必去路线|经典路线|必去|小众景点|宝藏打卡)$"),
    re.compile(r"^(怎么|如何|哪里|有什么|哪些|推荐几).*$"),
    re.compile(r"^.*(攻略|路线|推荐|排行|榜单|top\d*)$", re.IGNORECASE),
    re.compile(r"^\d+[个大小]|^[一二三四五六七八九十]"),  # Starts with number
    re.compile(r"^.{1,3}(镇|乡|街道|片区|新区|开发区|高新区|经济区)$"),
    re.compile(r"^(小红书|抖音|马蜂窝|携程|飞猪|穷游|大众点评|美团)$"),
    # Listicle / title patterns — not real places
    re.compile(r"^\d+[个大处]|^\d+[个处]|冷门景点|小众打卡|宝藏好去处|必去景点"),
    re.compile(r"^[A-Za-z].*"),  # Pure English/Latin start — likely not a Chinese place
    # Overly short generic suffixes
    re.compile(r"^(老街|旧巷|小巷|胡同|弄堂|步行街|美食街|小吃街|古街|夜市|商圈|老街旧巷|老巷子|旧街)$"),
    # Generic description + 景点/打卡, e.g. "经典景点", "网红打卡地"
    re.compile(r"^(经典|网红|热门|冷门|小众|必去|宝藏|隐藏|本地人).{0,4}(景点|打卡|推荐|好去处|拍照)"),
    # City name + generic suffix (not a real POI)
    re.compile(r"^.{2,6}(景点|逛街|步行街|老街|美食|打卡|攻略|推荐|玩乐)$"),
    # Listicle fragment patterns
    re.compile(r"^.{1,3}的\d+[条个].*"),
    # (intentionally no standalone "X城" filter — would catch real POIs like 白帝城)
    # Number-prefixed list items like "7大冷门景点"
    re.compile(r"^\d+大.*(景点|美食|打卡|推荐)"),
    re.compile(r"^.*\d+[个大小].*(景点|美食|打卡|推荐)"),
    # Negation / descriptive fragments
    re.compile(r"^(这不是|不是|没有|并非).*"),
    re.compile(r"^.{2,4}(小众|冷门|经典|热门|必去|好玩的|值得去).*(景点|地方|打卡|推荐)"),
    re.compile(r"^(探寻|发现|解锁|打卡|收藏|盘点|整理|汇总).*"),
    re.compile(r"^(是|一座|一个|一处).*(城|城市|地方|景点)"),
    # Very short fragments likely from mid-sentence
    re.compile(r"^.{1,2}(茶|馆|寺|庙|塔|阁|楼)$"),  # "内茶馆", "4点来寺" type fragments
    re.compile(r"^[0-9]+[点分秒].*"),  # Time fragments
    # Other fragments from sentences
    re.compile(r"^(除了|除了这些|还有|以及|包括).*"),
    re.compile(r"^(这座|那个|这些|那些).*(城|城市|地方)"),
]


def _is_generic_category_term(name: str) -> bool:
    stripped = name.strip()
    if len(stripped) < 2:
        return True
    if len(stripped) > 20:  # Unlikely to be a real POI name
        return True
    # Check if it's mostly ASCII (English text), not a Chinese place name
    ascii_count = sum(1 for c in stripped if ord(c) < 128)
    if ascii_count > len(stripped) * 0.5:
        return True
    return any(p.search(stripped) for p in _GENERIC_CATEGORY_PATTERNS)


# ── Main entry point ────────────────────────────────────────────

async def discover_places_from_social(
    city: str,
    interests: Optional[List[str]] = None,
    trip_style: str = "",
    max_places: int = SOCIAL_DISCOVERY_MAX_PLACES,
) -> Dict[str, Any]:
    """
    Main orchestrator: search social platforms, extract POI names, return structured results.

    Returns:
        {
            "status": "ok" | "partial" | "failed",
            "places": [{"name": str, "source_title": str, "source_snippet": str, "source_url": str}, ...],
            "queries_used": [...],
            "total_raw_results": int,
            "reason": str (only when failed),
        }
    """
    if not city or not _norm(city):
        return {"status": "failed", "places": [], "reason": "no_city"}

    queries = generate_social_queries(city, interests, trip_style)

    # Sequential search with small delay between queries
    BING_DELAY_SEC = float(os.getenv("SOCIAL_DISCOVERY_DELAY_SEC", "0.8"))
    all_results: List[Dict[str, str]] = []
    successful_queries = 0
    for i, q in enumerate(queries):
        if i > 0:
            await asyncio.sleep(BING_DELAY_SEC)
        try:
            results = await search_bing(q)
            if results:
                successful_queries += 1
                all_results.extend(results)
        except Exception:
            pass

    if not all_results:
        return {
            "status": "failed",
            "places": [],
            "reason": "no_results",
            "queries_used": queries,
            "total_raw_results": 0,
        }

    places = extract_poi_names_from_results(all_results, max_places)

    return {
        "status": "ok" if successful_queries >= max(len(queries) // 2, 1) else "partial",
        "places": places,
        "queries_used": queries,
        "total_raw_results": len(all_results),
    }

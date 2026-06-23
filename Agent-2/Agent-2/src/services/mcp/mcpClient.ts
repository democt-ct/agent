import { AMAP_CONFIG } from "../../config/llm";
import type { Env, GeoPoint, McpToolName, PlaceCategory, RouteSegment } from "../../types";
import type {
  McpPoiItem,
  McpRouteMode,
  McpRoutePlan,
  McpWeatherForecast,
  McpWebSearchItem,
  PlaceDetailsToolResult,
  PoiSearchToolResult,
  RoutePlanToolResult,
  WeatherToolResult,
  WebSearchToolResult
} from "./mcpTypes";
import {
  poiSearchCache,
  routeSegmentCache,
  webSearchCache,
  buildPoiCacheKey,
  buildRouteCacheKey,
  buildWebCacheKey
} from "../../utils/cache";

interface AmapPoi {
  id?: string;
  name?: string;
  type?: string;
  typecode?: string;
  cityname?: string;
  adname?: string;
  address?: string;
  location?: string;
}

interface AmapPoiResponse {
  status?: string;
  info?: string;
  pois?: AmapPoi[];
}

interface AmapWeatherResponse {
  status?: string;
  info?: string;
  lives?: Array<Record<string, string>>;
  forecasts?: Array<{
    city?: string;
    casts?: Array<Record<string, string>>;
  }>;
}

interface AmapRegeoResponse {
  status?: string;
  info?: string;
  regeocode?: {
    addressComponent?: {
      city?: string | string[];
      province?: string;
    };
  };
}

interface AmapDirectionResponse {
  status?: string;
  info?: string;
  route?: {
    paths?: Array<{
      distance?: string;
      duration?: string;
      steps?: Array<{ polyline?: string }>;
    }>;
  };
}

function nowIso(): string {
  return new Date().toISOString();
}

function maskKey(value: string): string {
  if (!value) return "missing";
  return value.length <= 8 ? "***" : `${value.slice(0, 4)}...${value.slice(-4)}`;
}

export function resolveAmapWebServiceKey(env?: Partial<Env>): string {
  return (
    env?.AMAP_WEB_SERVICE_KEY ||
    env?.AMAP_WEB_SERVICEKEY ||
    env?.webServiceKey ||
    AMAP_CONFIG.webServiceKey ||
    AMAP_CONFIG.browserKey
  );
}

function emptyResult<T>(
  tool: McpToolName,
  query: Record<string, unknown>,
  data: T,
  warnings: string[]
) {
  return {
    tool,
    query,
    data,
    source: "mcp",
    fetchedAt: nowIso(),
    confidence: warnings.length ? 0.2 : 0.7,
    warnings
  };
}

function parseLocation(value?: string): GeoPoint | undefined {
  if (!value) return undefined;
  const [lngRaw, latRaw] = value.split(",");
  const lng = Number(lngRaw);
  const lat = Number(latRaw);
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) return undefined;
  return { lng, lat };
}

function pointToAmap(point: GeoPoint): string {
  return `${point.lng},${point.lat}`;
}

function parsePolyline(value?: string): GeoPoint[] {
  if (!value) return [];
  return value
    .split(";")
    .map(parseLocation)
    .filter((point): point is GeoPoint => Boolean(point));
}

function distanceMeters(a: GeoPoint, b: GeoPoint): number {
  const earthRadius = 6371000;
  const toRad = (degree: number) => (degree * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return Math.round(2 * earthRadius * Math.asin(Math.sqrt(h)));
}

function inferCategory(text?: string): PlaceCategory | undefined {
  const value = text ?? "";
  if (/\u9910\u996e|\u7f8e\u98df|\u5c0f\u5403|\u706b\u9505|050/.test(value)) return "food";
  if (/\u5496\u5561|\u8336|\u996e\u54c1/.test(value)) return "cafe";
  if (/\u8d2d\u7269|\u5546\u573a|\u5546\u5708|060/.test(value)) return "mall";
  if (/\u516c\u56ed|\u7eff\u5730|110/.test(value)) return "park";
  if (/\u535a\u7269\u9986|\u5c55\u89c8|140/.test(value)) return "museum";
  if (/\u591c\u666f|\u9152\u5427|\u591c\u5e02|\u89c2\u666f/.test(value)) return "nightview";
  if (/\u98ce\u666f|\u666f\u533a|\u540d\u80dc|\u81ea\u7136|081/.test(value)) return "nature";
  if (/餐饮|美食|小吃|火锅|050/.test(value)) return "food";
  if (/咖啡|茶|饮品/.test(value)) return "cafe";
  if (/购物|商场|商圈|060/.test(value)) return "mall";
  if (/公园|绿地|110/.test(value)) return "park";
  if (/博物馆|展览|140/.test(value)) return "museum";
  if (/风景|景区|名胜|自然|110|081/.test(value)) return "nature";
  if (/夜景|酒吧|夜市/.test(value)) return "nightview";
  return undefined;
}

function toPoiItem(poi: AmapPoi): McpPoiItem | null {
  const id = poi.id?.trim();
  const name = poi.name?.trim();
  const city = poi.cityname?.trim() || AMAP_CONFIG.defaultCity;
  if (!id || !name) return null;
  return {
    id,
    name,
    city,
    district: poi.adname,
    address: poi.address,
    location: parseLocation(poi.location),
    category: inferCategory(`${poi.type ?? ""} ${poi.typecode ?? ""}`),
    rawType: poi.type
  };
}

function stripHtml(value: string): string {
  return value
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

async function readJson<T>(response: Response): Promise<T> {
  return (await response.json()) as T;
}

export class McpClient {
  constructor(private readonly env?: Partial<Env>) {}

  private getAmapKey(): string {
    return resolveAmapWebServiceKey(this.env);
  }

  async searchWeb(query: string, city?: string): Promise<WebSearchToolResult> {
    const fullQuery = [city, query].filter(Boolean).join(" ");
    const cacheKey = buildWebCacheKey(query, city);
    const cached = webSearchCache.get(cacheKey);
    if (cached) {
      return cached as WebSearchToolResult;
    }

    const url = `https://duckduckgo.com/html/?q=${encodeURIComponent(fullQuery)}`;
    const warnings: string[] = [];
    try {
      const response = await fetch(url, {
        headers: { "user-agent": "TravelAgentMcpClient/0.1" }
      });
      if (!response.ok) {
        return emptyResult("web_search", { query, city }, [], [`web search failed: ${response.status}`]);
      }
      const html = await response.text();
      const items: McpWebSearchItem[] = [];
      const pattern = /<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)<\/a>/g;
      const snippetPattern = /<a[^>]+class="result__snippet"[^>]*>(.*?)<\/a>/g;
      const snippets = Array.from(html.matchAll(snippetPattern)).map((match) => stripHtml(match[1]));
      for (const match of html.matchAll(pattern)) {
        const url = stripHtml(match[1]);
        const title = stripHtml(match[2]);
        const snippet = snippets[items.length] ?? undefined;
        if (url && title && !items.some((item) => item.url === url)) {
          items.push({ title, url, snippet });
        }
        if (items.length >= 8) break;
      }
      const result = emptyResult("web_search", { query, city }, items, warnings);
      webSearchCache.set(cacheKey, result);
      return result;
    } catch (error) {
      warnings.push(error instanceof Error ? error.message : "web search error");
      return emptyResult("web_search", { query, city }, [], warnings);
    }
  }

  async searchPOI(
    city: string | undefined,
    keyword: string,
    category?: PlaceCategory
  ): Promise<PoiSearchToolResult> {
    const key = this.getAmapKey();
    const warnings: string[] = [];
    const cacheKey = buildPoiCacheKey(city, keyword, category);
    const cached = poiSearchCache.get(cacheKey);
    if (cached) {
      return cached as PoiSearchToolResult;
    }

    console.info("[amap.searchPOI] request", {
      city,
      keyword,
      category,
      key: maskKey(key)
    });
    if (!key) {
      return emptyResult("poi_search", { city, keyword, category }, [], ["AMap key is not configured"]);
    }
    const params = new URLSearchParams({
      key,
      keywords: keyword,
      offset: "25",
      page: "1",
      extensions: "all"
    });
    if (city) {
      params.set("city", city);
    }
    const url = `https://restapi.amap.com/v3/place/text?${params.toString()}`;
    try {
      const response = await fetch(url);
      const data = await readJson<AmapPoiResponse>(response);
      console.info("[amap.searchPOI] response", {
        city,
        keyword,
        httpStatus: response.status,
        amapStatus: data.status,
        info: data.info,
        poiCount: data.pois?.length ?? 0
      });
      if (data.status !== "1") {
        return emptyResult("poi_search", { city, keyword, category }, [], [data.info ?? "AMap POI search failed"]);
      }
      const pois = (data.pois ?? [])
        .map(toPoiItem)
        .filter((item): item is McpPoiItem => Boolean(item))
        .map((item) => ({ ...item, category: item.category ?? category }));
      const result = emptyResult("poi_search", { city, keyword, category }, pois, warnings);
      poiSearchCache.set(cacheKey, result);
      return result;
    } catch (error) {
      warnings.push(error instanceof Error ? error.message : "POI search error");
      return emptyResult("poi_search", { city, keyword, category }, [], warnings);
    }
  }

  async planRoute(points: GeoPoint[], mode: McpRouteMode): Promise<RoutePlanToolResult> {
    const key = this.getAmapKey();
    const warnings: string[] = [];
    console.info("[amap.routePlanner] request", {
      pointCount: points.length,
      mode,
      key: maskKey(key)
    });
    if (points.length < 2) {
      return emptyResult("route_plan", { points, mode }, {
        mode,
        segments: [],
        polyline: [],
        totalDistanceMeters: 0,
        totalDurationSeconds: 0
      }, warnings);
    }

    if (!key || mode === "straight") {
      const segments = points.slice(0, -1).map((point, index): RouteSegment => {
        const next = points[index + 1];
        return {
          fromPlaceId: `point_${index}`,
          toPlaceId: `point_${index + 1}`,
          distanceMeters: distanceMeters(point, next),
          durationSeconds: null,
          polyline: [point, next],
          provider: "amap",
          mode: "straight"
        };
      });
      return emptyResult("route_plan", { points, mode }, {
        mode: "straight",
        segments,
        polyline: segments.flatMap((segment) => segment.polyline),
        totalDistanceMeters: segments.reduce((sum, segment) => sum + (segment.distanceMeters ?? 0), 0),
        totalDurationSeconds: null
      }, key ? warnings : ["AMap key is not configured, using straight-line route"]);
    }

    const endpoint = mode === "driving" ? "driving" : "walking";
    const segmentPromises = points.slice(0, -1).map(async (origin, index) => {
      const destination = points[index + 1];
      const cacheKey = buildRouteCacheKey(pointToAmap(origin), pointToAmap(destination), mode);
      const cached = routeSegmentCache.get(cacheKey);
      if (cached) {
        return cached as RouteSegment;
      }

      const params = new URLSearchParams({
        key,
        origin: pointToAmap(origin),
        destination: pointToAmap(destination)
      });
      try {
        const response = await fetch(`https://restapi.amap.com/v3/direction/${endpoint}?${params.toString()}`);
        const data = await readJson<AmapDirectionResponse>(response);
        console.info("[amap.routePlanner] response", {
          segmentIndex: index,
          httpStatus: response.status,
          amapStatus: data.status,
          info: data.info,
          pathCount: data.route?.paths?.length ?? 0
        });
        const path = data.route?.paths?.[0];
        const polyline = path?.steps?.flatMap((step) => parsePolyline(step.polyline)) ?? [];
        const segment: RouteSegment = {
          fromPlaceId: `point_${index}`,
          toPlaceId: `point_${index + 1}`,
          distanceMeters: path?.distance ? Number(path.distance) : distanceMeters(origin, destination),
          durationSeconds: path?.duration ? Number(path.duration) : null,
          polyline: polyline.length ? polyline : [origin, destination],
          provider: "amap",
          mode
        };
        routeSegmentCache.set(cacheKey, segment);
        return segment;
      } catch (error) {
        warnings.push(error instanceof Error ? error.message : "route segment error");
        return null;
      }
    });

    const segmentResults = await Promise.all(segmentPromises);
    const segments = segmentResults.filter((segment): segment is RouteSegment => segment !== null);

    return emptyResult("route_plan", { points, mode }, {
      mode,
      segments,
      polyline: segments.flatMap((segment) => segment.polyline),
      totalDistanceMeters: segments.reduce((sum, segment) => sum + (segment.distanceMeters ?? 0), 0),
      totalDurationSeconds: segments.some((segment) => segment.durationSeconds == null)
        ? null
        : segments.reduce((sum, segment) => sum + (segment.durationSeconds ?? 0), 0)
    }, warnings);
  }

  async getWeather(city: string, date?: string): Promise<WeatherToolResult> {
    const key = this.getAmapKey();
    const warnings: string[] = [];
    if (!key) {
      return emptyResult("weather", { city, date }, [], ["AMap key is not configured"]);
    }
    const params = new URLSearchParams({
      key,
      city,
      extensions: date ? "all" : "base"
    });
    try {
      const response = await fetch(`https://restapi.amap.com/v3/weather/weatherInfo?${params.toString()}`);
      const data = await readJson<AmapWeatherResponse>(response);
      if (data.status !== "1") {
        return emptyResult("weather", { city, date }, [], [data.info ?? "AMap weather failed"]);
      }
      const forecasts: McpWeatherForecast[] = date
        ? (data.forecasts?.[0]?.casts ?? []).map((cast) => ({
            city,
            date: cast.date,
            weather: [cast.dayweather, cast.nightweather].filter(Boolean).join("/"),
            temperature: [cast.nighttemp, cast.daytemp].filter(Boolean).join("-"),
            wind: cast.daywind,
            raw: cast
          }))
        : (data.lives ?? []).map((live) => ({
            city,
            date,
            weather: live.weather,
            temperature: live.temperature,
            wind: live.winddirection,
            raw: live
          }));
      return emptyResult("weather", { city, date }, forecasts, warnings);
    } catch (error) {
      warnings.push(error instanceof Error ? error.message : "weather error");
      return emptyResult("weather", { city, date }, [], warnings);
    }
  }

  async getPlaceDetails(placeId: string): Promise<PlaceDetailsToolResult> {
    const key = this.getAmapKey();
    const warnings: string[] = [];
    if (!key) {
      return emptyResult("place_details", { placeId }, null, ["AMap key is not configured"]);
    }
    const params = new URLSearchParams({
      key,
      id: placeId,
      extensions: "all"
    });
    try {
      const response = await fetch(`https://restapi.amap.com/v3/place/detail?${params.toString()}`);
      const data = await readJson<AmapPoiResponse>(response);
      if (data.status !== "1") {
        return emptyResult("place_details", { placeId }, null, [data.info ?? "AMap place detail failed"]);
      }
      return emptyResult("place_details", { placeId }, toPoiItem(data.pois?.[0] ?? {}), warnings);
    } catch (error) {
      warnings.push(error instanceof Error ? error.message : "place detail error");
      return emptyResult("place_details", { placeId }, null, warnings);
    }
  }

  async inferCityFromLocation(point: GeoPoint): Promise<string | null> {
    const key = this.getAmapKey();
    if (!key) return null;
    const params = new URLSearchParams({
      key,
      location: pointToAmap(point),
      extensions: "base"
    });
    try {
      const response = await fetch(`https://restapi.amap.com/v3/geocode/regeo?${params.toString()}`);
      const data = await readJson<AmapRegeoResponse>(response);
      if (data.status !== "1") return null;
      const city = data.regeocode?.addressComponent?.city;
      if (Array.isArray(city)) {
        return String(city[0] ?? "").trim() || data.regeocode?.addressComponent?.province?.trim() || null;
      }
      return String(city ?? "").trim() || data.regeocode?.addressComponent?.province?.trim() || null;
    } catch {
      return null;
    }
  }
}

export const mcpClient = new McpClient();

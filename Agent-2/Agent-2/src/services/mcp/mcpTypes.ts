import type { GeoPoint, McpToolResult, PlaceCategory, RouteSegment } from "../../types";

export type McpRouteMode = "walking" | "driving" | "straight";

export interface McpWebSearchItem {
  title: string;
  url: string;
  snippet?: string;
}

export interface McpPoiItem {
  id: string;
  name: string;
  city: string;
  district?: string;
  address?: string;
  location?: GeoPoint;
  category?: PlaceCategory;
  rawType?: string;
  sourceUrl?: string;
}

export interface McpRoutePlan {
  mode: McpRouteMode;
  segments: RouteSegment[];
  polyline: GeoPoint[];
  totalDistanceMeters: number | null;
  totalDurationSeconds: number | null;
}

export interface McpWeatherForecast {
  city: string;
  date?: string;
  weather?: string;
  temperature?: string;
  wind?: string;
  raw?: unknown;
}

export type WebSearchToolResult = McpToolResult<McpWebSearchItem[]>;
export type PoiSearchToolResult = McpToolResult<McpPoiItem[]>;
export type RoutePlanToolResult = McpToolResult<McpRoutePlan>;
export type WeatherToolResult = McpToolResult<McpWeatherForecast[]>;
export type PlaceDetailsToolResult = McpToolResult<McpPoiItem | null>;

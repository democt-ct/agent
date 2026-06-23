import type { PlannerOutput, RouteSegment } from "../../types";
import { McpClient, mcpClient as defaultMcpClient } from "../mcp/mcpClient";
import type { McpRouteMode } from "../mcp/mcpTypes";

type PlannerMarker = PlannerOutput["mapData"]["markers"][number];

function sortMarkers(markers: PlannerMarker[]): PlannerMarker[] {
  return [...markers].sort((a, b) => a.order - b.order);
}

function groupMarkersByDay(markers: PlannerMarker[]): Map<number, PlannerMarker[]> {
  const grouped = new Map<number, PlannerMarker[]>();
  for (const marker of markers) {
    const dayMarkers = grouped.get(marker.day) ?? [];
    dayMarkers.push(marker);
    grouped.set(marker.day, dayMarkers);
  }
  return grouped;
}

function attachPlaceIds(
  segments: RouteSegment[],
  markers: PlannerMarker[]
): RouteSegment[] {
  return segments.map((segment, index) => ({
    ...segment,
    fromPlaceId: markers[index]?.id ?? segment.fromPlaceId,
    toPlaceId: markers[index + 1]?.id ?? segment.toPlaceId
  }));
}

export async function enrichPlannerOutputWithRoutes(params: {
  plannerOutput: PlannerOutput;
  mcpClient?: McpClient;
  mode?: McpRouteMode;
}): Promise<PlannerOutput> {
  const client = params.mcpClient ?? defaultMcpClient;
  const mode = params.mode ?? "walking";
  const warnings = [...params.plannerOutput.warnings];
  const groupedMarkers = groupMarkersByDay(params.plannerOutput.mapData.markers);
  const polylines: RouteSegment[] = [];
  const polylineIdsByDay = new Map<number, string[]>();

  for (const [day, rawMarkers] of groupedMarkers) {
    const markers = sortMarkers(rawMarkers);
    if (markers.length < 2) {
      polylineIdsByDay.set(day, []);
      continue;
    }

    const routeResult = await client.planRoute(
      markers.map((marker) => marker.location),
      mode
    );
    warnings.push(...routeResult.warnings);

    const routeSegments = attachPlaceIds(routeResult.data.segments, markers);
    console.info("[plannerRouteEnricher] routeSegments count", {
      day,
      markerCount: markers.length,
      routeSegments: routeSegments.length
    });
    const ids: string[] = [];
    for (const segment of routeSegments) {
      const id = `day-${day}-route-${ids.length + 1}`;
      ids.push(id);
      polylines.push(segment);
    }
    polylineIdsByDay.set(day, ids);
  }

  return {
    ...params.plannerOutput,
    warnings: Array.from(new Set(warnings)),
    mapData: {
      ...params.plannerOutput.mapData,
      polylines,
      layers: params.plannerOutput.mapData.layers.map((layer) => ({
        ...layer,
        polylineIds: polylineIdsByDay.get(layer.day) ?? []
      }))
    }
  };
}

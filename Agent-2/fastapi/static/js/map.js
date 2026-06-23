(function () {
  const map = (window.TravelMap = window.TravelMap || {});

  function formatDistance(distanceMeters) {
    if (!Number.isFinite(distanceMeters)) {
      return "-";
    }
    if (distanceMeters >= 1000) {
      return `${(distanceMeters / 1000).toFixed(distanceMeters >= 10000 ? 0 : 1)} km`;
    }
    return `${Math.round(distanceMeters)} m`;
  }

  function haversineMetersBetweenPoints(a, b) {
    if (!a || !b) return null;
    const radius = 6371000;
    const toRad = (value) => value * Math.PI / 180;
    const lat1 = toRad(Number(a.lat));
    const lat2 = toRad(Number(b.lat));
    const dLat = toRad(Number(b.lat) - Number(a.lat));
    const dLng = toRad(Number(b.lng) - Number(a.lng));
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
    return Math.round(2 * radius * Math.asin(Math.sqrt(h)));
  }

  function getItineraryDays(bundle) {
    return bundle?.itinerary?.itinerary?.days || bundle?.itinerary?.days || [];
  }

  function getMapData(bundle) {
    return bundle?.mapData || bundle?.itinerary?.mapData || null;
  }

  function getRouteSegments(bundle) {
    return getMapData(bundle)?.polylines || bundle?.routeSegments || bundle?.itinerary?.routeSegments || [];
  }

  function getMapMarkers(bundle) {
    return getMapData(bundle)?.markers || [];
  }

  function getItemId(item) {
    return String(item?.candidateId || item?.id || item?.name || "").trim();
  }

  function resolveActiveMapDay(bundle) {
    const days = getItineraryDays(bundle);
    if (!days.length) {
      window.state.activeMapDay = null;
      return null;
    }
    if (window.state.activeMapDay && days.some((day) => Number(day.day) === Number(window.state.activeMapDay))) {
      return Number(window.state.activeMapDay);
    }
    window.state.activeMapDay = Number(days[0].day);
    return window.state.activeMapDay;
  }

  function getDayMarkers(bundle, dayNumber) {
    return getMapMarkers(bundle)
      .filter((marker) => Number(marker.day) === Number(dayNumber))
      .sort((left, right) => Number(left.order || 0) - Number(right.order || 0));
  }

  function getDayRouteSegments(bundle, dayNumber) {
    const markerIds = new Set(getDayMarkers(bundle, dayNumber).map((marker) => String(marker.id)));
    return getRouteSegments(bundle).filter((segment) => {
      const fromPlaceId = String(segment.fromPlaceId || "");
      const toPlaceId = String(segment.toPlaceId || "");
      return markerIds.has(fromPlaceId) && markerIds.has(toPlaceId);
    });
  }

  function getRouteDistanceBetween(bundle, dayNumber, fromId, toId) {
    const segment = getDayRouteSegments(bundle, dayNumber).find((entry) => {
      return String(entry.fromPlaceId || "") === String(fromId) && String(entry.toPlaceId || "") === String(toId);
    }) || getRouteSegments(bundle).find((entry) => {
      return String(entry.fromPlaceId || "") === String(fromId) && String(entry.toPlaceId || "") === String(toId);
    });
    return Number.isFinite(segment?.distanceMeters) ? segment.distanceMeters : null;
  }

  function getStartDistanceForItem(item, index) {
    if (!item?.location) return null;
    if (index === 0 && window.state.userLocation) {
      return haversineMetersBetweenPoints(window.state.userLocation, item.location);
    }
    return null;
  }

  function requestBrowserLocation() {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (position) => {
        window.state.userLocation = {
          lng: position.coords.longitude,
          lat: position.coords.latitude
        };
        if (window.state.itineraryBundle && typeof window.renderItineraryV2 === "function") {
          window.renderItineraryV2(window.state.itineraryBundle);
        }
      },
      () => {
        window.state.userLocation = null;
      },
      { enableHighAccuracy: true, timeout: 6000, maximumAge: 300000 }
    );
  }

  function clearMap() {
    if (Array.isArray(window.state.mapMarkers)) {
      window.state.mapMarkers.forEach((marker) => marker?.setMap?.(null));
    }
    if (Array.isArray(window.state.mapPolylines)) {
      window.state.mapPolylines.forEach((polyline) => polyline?.setMap?.(null));
    }
    window.state.mapMarkers = [];
    window.state.mapPolylines = [];
  }

  map.formatDistance = formatDistance;
  map.haversineMetersBetweenPoints = haversineMetersBetweenPoints;
  map.getItineraryDays = getItineraryDays;
  map.getMapData = getMapData;
  map.getRouteSegments = getRouteSegments;
  map.getMapMarkers = getMapMarkers;
  map.getItemId = getItemId;
  map.resolveActiveMapDay = resolveActiveMapDay;
  map.getDayMarkers = getDayMarkers;
  map.getDayRouteSegments = getDayRouteSegments;
  map.getRouteDistanceBetween = getRouteDistanceBetween;
  map.getStartDistanceForItem = getStartDistanceForItem;
  map.requestBrowserLocation = requestBrowserLocation;
  map.clearMap = clearMap;
})();

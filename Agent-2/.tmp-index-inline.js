
    const state = {
      sessionId: null,
      loading: false,
      messages: [],
      sessions: [],
      sessionHistoryTotal: 0,
      recentPanelOpen: false,
      modelName: "-",
      userLocation: null,
      mapConfig: null,
      map: null,
      mapCameraOverride: null,
      mapBuildingLayer: null,
      mapMarkers: [],
      mapPolylines: [],
      mapSearchResults: [],
      mapPreviewItems: [],
      mapPendingCandidates: [],
      mapRouteSegments: [],
      mapItineraryDays: [],
      mapSelectedDay: null,
      mapActiveResultKey: null,
      mapInfoWindow: null,
      latestItinerary: null,
      latestAssistantReply: "",
      mapSdkError: null,
      map3D: false
    };

    const sessionIdEl = document.getElementById("sessionId");
    const modelNameEl = document.getElementById("modelName");
    const statusEl = document.getElementById("status");
    const transcriptEl = document.getElementById("transcript");
    const promptInputEl = document.getElementById("promptInput");
    const sendBtnEl = document.getElementById("sendBtn");
    const newSessionBtnEl = document.getElementById("newSessionBtn");
    const sessionPanelToggleEl = document.getElementById("sessionPanelToggle");
    const sessionPanelCloseEl = document.getElementById("sessionPanelClose");
    const sessionPanelEl = document.getElementById("sessionPanel");
    const sessionPanelBadgeEl = document.getElementById("sessionPanelBadge");
    const sessionListEl = document.getElementById("sessionList");
    const sessionListMetaEl = document.getElementById("sessionListMeta");
    const mapStatusEl = document.getElementById("mapStatus");
    const mapCanvasEl = document.getElementById("mapCanvas");
    const mapResultListEl = document.getElementById("mapResultList");
    const mapDayTabsEl = document.getElementById("mapDayTabs");
    const mapSearchInputEl = document.getElementById("mapSearchInput");
    const mapSearchBtnEl = document.getElementById("mapSearchBtn");
    const mapMode2DBtnEl = document.getElementById("mapMode2DBtn");
    const mapMode3DBtnEl = document.getElementById("mapMode3DBtn");
    const mapZoomInBtnEl = document.getElementById("mapZoomInBtn");
    const mapZoomOutBtnEl = document.getElementById("mapZoomOutBtn");

    function setStatus(text) {
      statusEl.textContent = text;
    }

    function escapeHtml(text) {
      const div = document.createElement("div");
      div.textContent = text ?? "";
      return div.innerHTML;
    }

    function scrollBottom() {
      transcriptEl.scrollTop = transcriptEl.scrollHeight;
    }

    function setModelName(value) {
      state.modelName = value || "-";
      modelNameEl.textContent = state.modelName;
    }

    function formatSessionTime(value) {
      if (!value) return "";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      return date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit"
      });
    }

    function summarizeMessageContent(content) {
      const text = String(content || "").replace(/\s+/g, " ").trim();
      if (!text) return "无内容";
      return text.length > 70 ? `${text.slice(0, 70)}…` : text;
    }

    function setRecentPanelOpen(open) {
      state.recentPanelOpen = Boolean(open);
      if (sessionPanelEl) {
        sessionPanelEl.classList.toggle("open", state.recentPanelOpen);
        sessionPanelEl.setAttribute("aria-hidden", String(!state.recentPanelOpen));
      }
      if (sessionPanelToggleEl) {
        sessionPanelToggleEl.setAttribute("aria-expanded", String(state.recentPanelOpen));
      }
    }

    function requestBrowserLocation() {
      if (!navigator.geolocation) {
        setStatus("浏览器不支持定位，地图将使用默认中心点。");
        renderMap();
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (position) => {
          state.userLocation = {
            lng: position.coords.longitude,
            lat: position.coords.latitude
          };
          renderMap();
        },
        () => {
          renderMap();
        },
        { enableHighAccuracy: true, timeout: 6000, maximumAge: 300000 }
      );
    }

    function parseLocation(value) {
      if (!value) return null;
      if (Array.isArray(value) && value.length >= 2) {
        const lng = Number(value[0]);
        const lat = Number(value[1]);
        if (Number.isFinite(lng) && Number.isFinite(lat)) return { lng, lat };
      }
      if (typeof value === "string" && value.includes(",")) {
        const [lngRaw, latRaw] = value.split(",");
        const lng = Number(lngRaw);
        const lat = Number(latRaw);
        if (Number.isFinite(lng) && Number.isFinite(lat)) return { lng, lat };
      }
      if (typeof value === "object") {
        const lng = Number(value.lng ?? value.longitude ?? value.x);
        const lat = Number(value.lat ?? value.latitude ?? value.y);
        if (Number.isFinite(lng) && Number.isFinite(lat)) return { lng, lat };
        return parseLocation(value.location || value.point);
      }
      return null;
    }

    function syncMapModeButtons() {
      if (mapMode2DBtnEl) {
        mapMode2DBtnEl.classList.toggle("is-active", !state.map3D);
        mapMode2DBtnEl.setAttribute("aria-pressed", String(!state.map3D));
      }
      if (mapMode3DBtnEl) {
        mapMode3DBtnEl.classList.toggle("is-active", state.map3D);
        mapMode3DBtnEl.setAttribute("aria-pressed", String(state.map3D));
      }
    }

    function applyMapMode() {
      syncMapModeButtons();
      if (!state.map) return;
      const viewMode = state.map3D ? "3D" : "2D";
      state.map.setViewMode?.(viewMode);
      state.map.setPitch?.(state.map3D ? 52 : 0);
      state.map.setRotation?.(state.map3D ? -16 : 0);
      if (state.mapBuildingLayer) {
        if (state.map3D) {
          state.mapBuildingLayer.show?.();
        } else {
          state.mapBuildingLayer.hide?.();
        }
      }
      if (state.map3D) {
        const currentZoom = Number(state.map.getZoom?.() ?? 0);
        if (currentZoom && currentZoom < 13.8) {
          state.map.setZoom?.(13.8);
        } else if (currentZoom && currentZoom > 15.2) {
          state.map.setZoom?.(15.2);
        }
      }
    }

    function ensureMapBuildingLayer() {
      if (!state.map || !window.AMap?.Buildings || state.mapBuildingLayer) return;
      state.mapBuildingLayer = new AMap.Buildings({
        zooms: [15, 20],
        heightFactor: 1.7,
        wallColor: "rgba(30, 64, 175, 0.55)",
        roofColor: "rgba(249, 115, 22, 0.28)"
      });
      state.map.addLayer?.(state.mapBuildingLayer);
      if (!state.map3D) {
        state.mapBuildingLayer.hide?.();
      }
    }

    function setMapMode(nextIs3D) {
      state.map3D = Boolean(nextIs3D);
      syncMapModeButtons();
      if (state.map) {
        const center = parseLocation(state.map.getCenter?.());
        const zoom = Number(state.map.getZoom?.());
        state.mapCameraOverride = center
          ? {
              lng: center.lng,
              lat: center.lat,
              zoom: Number.isFinite(zoom) ? zoom : undefined
            }
          : null;
        destroyMap();
      }
      renderMap();
    }

    function getMapUnavailableReason() {
      if (state.mapSdkError) return `AMap SDK load failed: ${state.mapSdkError}`;
      if (!state.mapConfig?.enabled) return "AMap browser key or security code is not configured.";
      if (!window.AMap) return "AMap JS SDK is not available in the browser yet.";
      return "Map is unavailable.";
    }

function getMapResultKey(item, index = 0) {
      const dayIndex = Number.isFinite(Number(item?.day_index)) ? Number(item.day_index) : 0;
      return [dayIndex, String(item?.name || ""), String(item?.address || ""), String(item?.location || ""), index].join("|");
    }

function focusMapResult(item) {
      const location = parseLocation(item?.location);
      if (!location || !state.map) return;
      state.mapActiveResultKey = getMapResultKey(item);
      const targetCenter = [location.lng, location.lat];
      if (typeof state.map.setZoomAndCenter === "function") {
        const zoom = Number.isFinite(Number(state.map.getZoom?.())) ? Number(state.map.getZoom?.()) : 12;
        state.map.setZoomAndCenter(Math.max(zoom, state.map3D ? 14.4 : 15), targetCenter, false, 220);
      } else {
        state.map.setCenter?.(targetCenter);
        state.map.setZoom?.(state.map3D ? 14.4 : 15);
      }
      if (window.AMap?.InfoWindow) {
        const title = escapeHtml(item?.name || "地点");
        const address = escapeHtml(item?.address || item?.category || "");
        const dayText = Number.isFinite(Number(item?.day_index)) ? `第${Number(item.day_index)}天` : "";
        const content = `
          <div style="padding:8px 10px; min-width:160px;">
            <div style="font-weight:700; margin-bottom:4px;">${title}</div>
            <div style="font-size:12px; color:#64748b; line-height:1.6;">${[dayText, address].filter(Boolean).join(" · ")}</div>
          </div>
        `;
        if (!state.mapInfoWindow) {
          state.mapInfoWindow = new AMap.InfoWindow({
            offset: new AMap.Pixel(0, -24),
            autoMove: false
          });
        }
        state.mapInfoWindow.setContent(content);
        state.mapInfoWindow.open(state.map, targetCenter);
      }
      state.map.setCenter?.(targetCenter);
      renderMapResults(getVisibleMapResults());
    }

    function getVisibleMapPendingCandidates() {
      if (!Number.isFinite(Number(state.mapSelectedDay))) {
        return Array.isArray(state.mapPendingCandidates) ? state.mapPendingCandidates : [];
      }
      return (Array.isArray(state.mapPendingCandidates) ? state.mapPendingCandidates : []).filter((item) => Number(item?.day_index) === Number(state.mapSelectedDay));
    }

    function getVisibleMapPreviewItems() {
      if (!Number.isFinite(Number(state.mapSelectedDay))) {
        return Array.isArray(state.mapPreviewItems) ? state.mapPreviewItems : [];
      }
      return (Array.isArray(state.mapPreviewItems) ? state.mapPreviewItems : []).filter((item) => Number(item?.day_index) === Number(state.mapSelectedDay));
    }

    async function selectPendingCandidate(item) {
      if (!state.sessionId || !item?.location) return;
      try {
        const result = await api("/api/planner/itinerary/place-select", {
          method: "POST",
          body: JSON.stringify({
            session_id: state.sessionId,
            day_index: item.day_index,
            slot: item.slot,
            query: item.source_query,
            place: {
              poi_id: item.poi_id,
              name: item.name,
              address: item.address,
              category: item.category,
              location: item.location
            }
          })
        });
        state.latestItinerary = result.itinerary || null;
        await syncMapFromConversation(
          "",
          state.latestAssistantReply || getLatestAssistantText(state.messages || []),
          state.latestItinerary
        );
        setStatus(`已加入 ${item.name || item.source_query}`);
      } catch (error) {
        console.error(error);
        setStatus(`加入地点失败：${error?.message || error}`);
      }
    }

    function renderMapResults(items) {
      const rows = Array.isArray(items) ? items : [];
      const previewRows = getVisibleMapPreviewItems().filter((item) => {
        return !rows.some((resolved) => {
          return Number(resolved?.day_index || 0) === Number(item?.day_index || 0)
            && String(resolved?.name || "").trim() === String(item?.name || "").trim();
        });
      });
      const pendingRows = getVisibleMapPendingCandidates();
      if (!mapResultListEl) return;
      if (!rows.length && !previewRows.length && !pendingRows.length) {
        mapResultListEl.innerHTML = "";
        return;
      }
      const confirmedHtml = rows.map((item, index) => {
        const location = parseLocation(item.location);
        const distance = Number.isFinite(Number(item.distance_meters)) ? `${Math.round(Number(item.distance_meters))} m` : "";
        const dayLabel = Number.isFinite(Number(item.day_index)) ? `第${Number(item.day_index)}天` : "";
        const slotLabel = item.slot ? String(item.slot) : "";
        const metaPrefix = [dayLabel, slotLabel].filter(Boolean).join(" · ");
        return `
          <article class="map-result" role="button" tabindex="0" data-resolved-index="${index}">
            <h3>${escapeHtml(item.name || `地点 ${index + 1}`)}</h3>
            <p>${metaPrefix ? `${escapeHtml(metaPrefix)} · ` : ""}${escapeHtml(item.address || item.category || "")}${distance ? ` · ${escapeHtml(distance)}` : ""}</p>
          </article>
        `;
      }).join("");
      const previewHtml = previewRows.map((item, index) => {
        const dayLabel = Number.isFinite(Number(item.day_index)) ? `第${Number(item.day_index)}天` : "";
        const slotLabel = item.slot ? String(item.slot) : "";
        const metaPrefix = [dayLabel, slotLabel].filter(Boolean).join(" · ");
        const description = item.address || item.sourceLine || item.category || "已识别到地点名称，等待坐标解析";
        return `
          <article class="map-result">
            <div class="map-result-tag" style="background: rgba(217, 119, 6, 0.12); color: #b45309;">待解析坐标</div>
            <h3>${escapeHtml(item.name || `地点 ${index + 1}`)}</h3>
            <p>${metaPrefix ? `${escapeHtml(metaPrefix)} · ` : ""}${escapeHtml(description)}</p>
          </article>
        `;
      }).join("");
      const pendingHtml = pendingRows.map((item, index) => {
        const distance = Number.isFinite(Number(item.distance_meters)) ? `${Math.round(Number(item.distance_meters))} m` : "";
        const dayLabel = Number.isFinite(Number(item.day_index)) ? `第${Number(item.day_index)}天` : "";
        const slotLabel = item.slot ? String(item.slot) : "";
        const metaPrefix = [dayLabel, slotLabel, item.source_query ? `${item.source_query} 候选` : ""].filter(Boolean).join(" · ");
        return `
          <article class="map-result" data-pending-candidate="${index}">
            <div class="map-result-tag">待选择候选</div>
            <h3>${escapeHtml(item.name || `候选地点 ${index + 1}`)}</h3>
            <p>${metaPrefix ? `${escapeHtml(metaPrefix)} · ` : ""}${escapeHtml(item.address || item.category || "")}${distance ? ` · ${escapeHtml(distance)}` : ""}</p>
            <div class="map-result-actions">
              <button type="button" data-pending-select="${index}">加入当天行程</button>
            </div>
          </article>
        `;
      }).join("");
      mapResultListEl.innerHTML = `${confirmedHtml}${previewHtml}${pendingHtml}`;
      mapResultListEl.querySelectorAll("[data-resolved-index]").forEach((element) => {
        const resolvedIndex = Number(element.getAttribute("data-resolved-index"));
        const item = rows[resolvedIndex];
        if (!item || !parseLocation(item.location)) return;
        element.classList.toggle("is-active", state.mapActiveResultKey === getMapResultKey(item, resolvedIndex));
        const activate = () => focusMapResult(item);
        element.addEventListener("click", activate);
        element.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            activate();
          }
        });
      });
      mapResultListEl.querySelectorAll("[data-pending-select]").forEach((button) => {
        button.addEventListener("click", async (event) => {
          event.preventDefault();
          event.stopPropagation();
          const index = Number(button.dataset.pendingSelect);
          const item = pendingRows[index];
          if (!item) return;
          await selectPendingCandidate(item);
        });
      });
    }

    function getRouteColor(dayIndex) {
      const palette = ["#d97706", "#0f766e", "#2563eb", "#be185d", "#7c3aed", "#0891b2"];
      const index = Number.isFinite(Number(dayIndex)) && Number(dayIndex) > 0 ? Number(dayIndex) - 1 : 0;
      return palette[index % palette.length];
    }

    function getVisibleMapResults() {
      if (!Number.isFinite(Number(state.mapSelectedDay))) {
        return Array.isArray(state.mapSearchResults) ? state.mapSearchResults : [];
      }
      return (Array.isArray(state.mapSearchResults) ? state.mapSearchResults : []).filter((item) => Number(item?.day_index) === Number(state.mapSelectedDay));
    }

    function getVisibleMapRouteSegments() {
      if (!Number.isFinite(Number(state.mapSelectedDay))) {
        return Array.isArray(state.mapRouteSegments) ? state.mapRouteSegments : [];
      }
      return (Array.isArray(state.mapRouteSegments) ? state.mapRouteSegments : []).filter((item) => Number(item?.day_index) === Number(state.mapSelectedDay));
    }

    function renderMapDayTabs() {
      if (!mapDayTabsEl) return;
      const days = (Array.isArray(state.mapItineraryDays) ? state.mapItineraryDays : [])
        .filter((day) => Number.isFinite(Number(day?.day_index)))
        .sort((a, b) => Number(a.day_index) - Number(b.day_index));
      if (!days.length) {
        mapDayTabsEl.hidden = true;
        mapDayTabsEl.innerHTML = "";
        return;
      }

      const validDayIndexes = days.map((day) => Number(day.day_index));
      if (!validDayIndexes.includes(Number(state.mapSelectedDay))) {
        state.mapSelectedDay = validDayIndexes[0];
      }

      mapDayTabsEl.hidden = false;
      mapDayTabsEl.innerHTML = days.map((day) => {
        const dayIndex = Number(day.day_index);
        const title = String(day.title || "").trim();
        return `
          <button
            type="button"
            class="map-day-tab ${dayIndex === Number(state.mapSelectedDay) ? "is-active" : ""}"
            data-map-day="${dayIndex}"
          >
            ${escapeHtml(`第${dayIndex}天`)}${title ? `<span> · ${escapeHtml(title)}</span>` : ""}
          </button>
        `;
      }).join("");

      mapDayTabsEl.querySelectorAll("[data-map-day]").forEach((button) => {
        button.addEventListener("click", () => {
          state.mapSelectedDay = Number(button.dataset.mapDay);
          renderMap();
        });
      });
    }

    function normalizeRoutePoint(item) {
      const location = parseLocation(item?.location);
      if (!location) return null;
      return {
        poi_id: item.poi_id || item.id || item.name,
        name: item.name || "地点",
        location
      };
    }

    function extractPlaceCandidatesFromItinerary(itinerary, assistantReply = "") {
      const days = Array.isArray(itinerary?.days) ? itinerary.days : [];
      const candidates = [];
      const seen = new Set();
      const addCandidate = (candidate) => {
        const query = String(candidate?.query || "").trim();
        if (!query) return;
        const aliases = Array.isArray(candidate?.aliases) ? candidate.aliases.filter(Boolean) : [];
        const categoryHint = String(candidate?.categoryHint || "");
        const intentType = String(candidate?.intentType || "explicit_poi");
        const selectionMode = String(candidate?.selectionMode || "auto_resolve");
        const selectedPlaces = Array.isArray(candidate?.selectedPlaces) ? candidate.selectedPlaces.filter(Boolean) : [];
        const dayIndex = Number.isFinite(Number(candidate?.day_index)) ? Number(candidate.day_index) : null;
        const dayTitle = String(candidate?.day_title || "");
        const slot = String(candidate?.slot || "");
        const sourceLine = String(candidate?.sourceLine || candidate?.slot_text || "");
        const dedupeKey = [dayIndex || 0, query, aliases.join("|"), categoryHint, intentType, slot, sourceLine].join("::");
        if (seen.has(dedupeKey)) return;
        seen.add(dedupeKey);
        candidates.push({
          query,
          aliases,
          categoryHint,
          intentType,
          selectionMode,
          selectedPlaces,
          sourceLine,
          day_index: dayIndex,
          day_title: dayTitle,
          slot,
          slot_text: sourceLine
        });
      };
      for (const day of days) {
        const dayIndex = Number(day?.day_index);
        const dayTitle = String(day?.title || "");
        const items = Array.isArray(day?.items) ? day.items : [];
        for (const item of items) {
          const slot = String(item?.slot || "");
          const slotText = String(item?.text || "");
          const places = Array.isArray(item?.place_candidates) ? item.place_candidates : [];
          for (const place of places) {
            addCandidate({
              query: place?.query,
              aliases: place?.aliases,
              categoryHint: place?.category_hint,
              intentType: place?.intent_type,
              selectionMode: place?.selection_mode,
              selectedPlaces: place?.selected_places,
              sourceLine: slotText,
              day_index: Number.isFinite(dayIndex) ? dayIndex : null,
              day_title: dayTitle,
              slot,
              slot_text: slotText
            });
          }
        }
      }
      const replyCandidates = extractPlaceCandidatesFromReply(assistantReply);
      for (const candidate of replyCandidates) {
        addCandidate(candidate);
      }
      return candidates;
    }

    function getLatestAssistantText(messages) {
      const rows = Array.isArray(messages) ? messages : [];
      for (let index = rows.length - 1; index >= 0; index -= 1) {
        if (rows[index]?.role === "assistant" && rows[index]?.content) {
          return String(rows[index].content);
        }
      }
      return "";
    }

    function buildConversationContext() {
      if (!state.messages.length) return "";
      const lines = [];
      if (Number.isFinite(Number(state.mapSelectedDay))) {
        lines.push(`当前地图选中：第${Number(state.mapSelectedDay)}天`);
      }
      lines.push(
        ...state.messages
          .slice(-8)
          .map((message) => `${message.role === "user" ? "用户" : "助手"}：${message.content || ""}`)
      );
      return lines.join("\n");
    }

    function normalizePlaceCandidate(raw) {
      let text = String(raw || "").trim();
      if (!text) return "";
      text = text.replace(/^[第\d一二三四五六七八九十两天日\s]+/, "");
      text = text.replace(/^(上午|中午|下午|傍晚|晚上|夜里|夜间|早上|午后|清晨|凌晨)[：:]\s*/u, "");
      text = text.replace(/^第[0-9一二三四五六七八九十]+天\s*[：:]?\s*/u, "");
      text = text.replace(/^(从|去|到|前往|先去|先到|再去|随后去|可以去|建议去|晚上去|在)\s*/u, "");
      text = text.replace(/(开始|顺路|漫步|散步|打卡|休息|看夜景|吃饭|用餐|收尾|小坐|闲逛|结束行程).*$/u, "");
      text = text.replace(/(周边餐饮|周边美食|附近餐饮|附近美食).*$/u, "");
      text = text.replace(/(周边|附近|一带|片区|商圈|区域)$/u, "");
      text = text.replace(/[，。；！!？?]+$/u, "");
      text = text.replace(/^\d+[.、]\s*/u, "");
      text = text.replace(/[“”"'`]/g, "");
      return text.trim();
    }

    function isLikelyPlaceCandidate(text) {
      const value = normalizePlaceCandidate(text);
      if (!value || value.length < 2 || value.length > 30) return false;
      if (/^(默认假设|当天逻辑|当日逻辑|备选|推荐理由|这里|完全符合|适合作为|如果|全程|步行与短途交通|公共交通|打车结合|轻松舒适|市中心|涪城区)$/u.test(value)) return false;
      if (/(了解|感受|体验|品尝|欣赏|探访|结束|规划|安排|建议|逻辑|替换|预约|交通|时间|喜欢|适合|可选)/u.test(value)) return false;
      if (/^(咖啡馆|清吧|美食片区|夜景|公园|景点|商圈|路线|行程|周边餐饮|周边美食|本地中餐|特色汤锅|江边茶座|清吧小坐)$/u.test(value)) return false;
      if (/[0-9]{2,}\s*(公里|分钟|小时)/u.test(value)) return false;
      return true;
    }

    function derivePlaceCategoryHint(name, sourceLine) {
      const text = `${name || ""} ${sourceLine || ""}`;
      if (/(科技馆|博物馆|美术馆|纪念馆|展览馆|文化馆)/u.test(text)) return "科教文化服务";
      if (/(餐厅|饭店|火锅|咖啡|小吃|酒吧|茶馆|餐饮)/u.test(text)) return "餐饮服务";
      if (/(公园|广场|景区|风景区|风景名胜区|山|寺|古镇|楼|塔|步行街|小吃街|创意园|半岛|游客中心|休闲区|老街|古城)/u.test(text)) return "风景名胜";
      return "";
    }

    function extractAliasesFromCandidate(text) {
      const aliases = [];
      const bracketMatches = Array.from(String(text || "").matchAll(/[（(]([^()（）]+)[)）]/gu));
      for (const match of bracketMatches) {
        const inner = normalizePlaceCandidate(match[1]);
        if (!inner || /[、，,/]/u.test(inner)) continue;
        if (isLikelyPlaceCandidate(inner)) aliases.push(inner);
      }
      const simplified = normalizePlaceCandidate(String(text || "").replace(/[（(][^()（）]+[)）]/gu, ""));
      if (simplified.endsWith("休闲区")) {
        aliases.push(simplified.replace(/休闲区$/u, ""));
      }
      if (simplified.endsWith("游客中心")) {
        aliases.push(simplified.replace(/游客中心$/u, ""));
      }
      return Array.from(new Set(aliases.filter(Boolean)));
    }

    function extractRegexPlaceCandidates(replyText) {
      const matches = String(replyText || "").match(/[\u4e00-\u9fa5A-Za-z0-9]{2,24}(?:博物馆|科技馆|纪念馆|美术馆|文化馆|游客中心|风景名胜区|风景区|景区|小吃街|步行街|创意园|休闲区|古镇|古城|公园|广场|半岛|老街|夜市|寺|楼|塔|山|街|巷)/gu) || [];
      return matches
        .map((item) => ({
          query: normalizePlaceCandidate(item),
          aliases: [],
          categoryHint: derivePlaceCategoryHint(item, item),
          sourceLine: item
        }))
        .filter((item) => isLikelyPlaceCandidate(item.query));
    }

    function extractPlaceCandidatesFromReply(replyText) {
      const text = String(replyText || "");
      if (!text) return [];
      const lines = text
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
      const itineraryLines = lines.filter((line) => /^(上午|中午|下午|傍晚|晚上|夜里|夜间|早上|午后|清晨|凌晨)[：:]/u.test(line));
      const sourceLines = itineraryLines.length ? itineraryLines : lines;
      const candidates = [];
      const seen = new Set();
      const pushCandidate = (query, aliases, sourceLine) => {
        const normalized = normalizePlaceCandidate(query);
        if (!isLikelyPlaceCandidate(normalized)) return;
        const categoryHint = derivePlaceCategoryHint(normalized, sourceLine);
        const uniqueAliases = Array.from(
          new Set(
            (aliases || [])
              .map((item) => normalizePlaceCandidate(item))
              .filter((item) => item && item !== normalized && isLikelyPlaceCandidate(item))
          )
        );
        const dedupeKey = [normalized, ...uniqueAliases].join("|");
        if (seen.has(dedupeKey)) return;
        seen.add(dedupeKey);
        candidates.push({
          query: normalized,
          aliases: uniqueAliases,
          categoryHint,
          intentType: "explicit_poi",
          selectionMode: "auto_resolve",
          selectedPlaces: [],
          sourceLine
        });
      };

      for (const line of sourceLines) {
        const mainPart = line.split(/\s*(?:——|--|-{2,})\s*/u)[0].trim();
        const contentRaw = mainPart.includes("：") ? mainPart.split("：").slice(1).join("：") : mainPart;
        const rawChunks = contentRaw
          .split(/\s*(?:\/|／|、|，|和|以及|与|或)\s*/u)
          .map((chunk) => chunk.trim())
          .filter(Boolean);
        for (const rawChunk of rawChunks) {
          if (/(周边餐饮|周边美食|附近餐饮|附近美食)/u.test(rawChunk)) continue;
          const chunk = normalizePlaceCandidate(rawChunk);
          if (!chunk) continue;
          pushCandidate(chunk, extractAliasesFromCandidate(chunk), line);
        }
      }

      if (!candidates.length) {
        for (const item of extractRegexPlaceCandidates(text)) {
          pushCandidate(item.query, item.aliases, item.sourceLine);
        }
      }

      return candidates.slice(0, 12);
    }

    function extractDestinationHintFromText(text) {
      const source = String(text || "").trim();
      if (!source) return "";
      const patterns = [
        /(?:我想|想|准备|打算|计划)?(?:在|去|到|前往|奔向|计划去)\s*([\u4e00-\u9fffA-Za-z0-9·]{2,12}?)(?:玩|旅游|旅行|逛|耍|住|待|过|打卡|游|转)/u,
        /([\u4e00-\u9fffA-Za-z0-9·]{2,12}?)(?:两|三|四|五|六|七|八|九|十)?(?:天|日)(?:行程|游|玩|旅游)?/u
      ];
      for (const pattern of patterns) {
        const match = source.match(pattern);
        if (!match) continue;
        const city = String(match[1] || "").trim();
        if (city && !/^(一|二|两|三|四|五|六|七|八|九|十|\d+)$/u.test(city)) {
          return city;
        }
      }
      return "";
    }

    function getLatestUserMessageText() {
      const messages = Array.isArray(state.messages) ? state.messages : [];
      for (let i = messages.length - 1; i >= 0; i -= 1) {
        const message = messages[i];
        if (message?.role === "user" && String(message.content || "").trim()) {
          return String(message.content || "").trim();
        }
      }
      return "";
    }

    function getActivePlanningCity(preferredMessage = "") {
      const explicitFromMessage = extractDestinationHintFromText(preferredMessage);
      if (explicitFromMessage) return explicitFromMessage;
      const itineraryCity = String(state.latestItinerary?.city || "").trim();
      if (itineraryCity) return itineraryCity;
      const latestUserCity = extractDestinationHintFromText(getLatestUserMessageText());
      if (latestUserCity) return latestUserCity;
      const configuredCity = String(state.mapConfig?.defaultCity || "").trim();
      return configuredCity || "绵阳";
    }

    function scoreResolvedPoi(poi, candidate, matchedKeyword) {
      const name = String(poi?.name || "");
      const category = String(poi?.category || "");
      let score = Number(poi?.confidence || 0);
      if (name === candidate.query || name === matchedKeyword) score += 1.2;
      if (name.includes(candidate.query) || candidate.query.includes(name)) score += 0.6;
      if (matchedKeyword && (name.includes(matchedKeyword) || matchedKeyword.includes(name))) score += 0.4;
      if (Array.isArray(candidate.aliases) && candidate.aliases.some((alias) => alias && (name.includes(alias) || alias.includes(name)))) score += 0.35;
      if (candidate.categoryHint && category.includes(candidate.categoryHint)) score += 0.7;
      if (candidate.categoryHint === "科教文化服务" && !category.includes("科教文化服务")) score -= 0.8;
      if (candidate.categoryHint === "风景名胜" && category.includes("餐饮服务")) score -= 1;
      if (candidate.categoryHint === "餐饮服务" && !category.includes("餐饮服务")) score -= 0.4;
      if (/周边|附近/u.test(name)) score -= 0.3;
      return score;
    }

    function pickResolvedPoi(resolveRes, candidate, matchedKeyword) {
      const pool = [];
      if (resolveRes?.poi) pool.push(resolveRes.poi);
      if (Array.isArray(resolveRes?.alternatives)) pool.push(...resolveRes.alternatives);
      let bestPoi = null;
      let bestScore = -Infinity;
      for (const poi of pool) {
        if (!poi?.location) continue;
        const score = scoreResolvedPoi(poi, candidate, matchedKeyword);
        if (score > bestScore) {
          bestScore = score;
          bestPoi = {
            ...poi,
            _resolveScore: score
          };
        }
      }
      return bestPoi;
    }

    async function resolvePlaceCandidate(candidate) {
      const keywords = Array.from(new Set([candidate.query, ...(candidate.aliases || [])].filter(Boolean)));
      let bestPoi = null;
      let bestScore = -Infinity;
      for (const keyword of keywords) {
        const resolveRes = await api("/api/map/poi/resolve", {
          method: "POST",
          body: JSON.stringify({
            city: getActivePlanningCity(),
            keyword,
            category_hint: candidate.categoryHint || null,
            anchor_location: null,
            radius_meters: 5000,
            limit: 6
          })
        });
        const poi = pickResolvedPoi(resolveRes, candidate, keyword);
        if (!poi?.location) continue;
        const score = Number(poi._resolveScore || 0);
        if (score > bestScore) {
          bestScore = score;
          bestPoi = {
            ...poi,
            source_query: candidate.query,
            matched_keyword: keyword,
            category_hint: candidate.categoryHint || ""
          };
        }
      }
      return bestPoi;
    }

    function getDayAnchorLocation(groupedByDay, dayIndex) {
      const dayKey = String(dayIndex || 0);
      const dayPlaces = groupedByDay.get(dayKey) || [];
      const lastPlace = dayPlaces[dayPlaces.length - 1];
      const firstPlace = dayPlaces[0];
      return (
        parseLocation(lastPlace?.location) ||
        parseLocation(firstPlace?.location) ||
        null
      );
    }

    function buildPendingCandidateEntries(candidate, response) {
      const rows = Array.isArray(response?.candidates) ? response.candidates : [];
      return rows.map((item, index) => ({
        ...item,
        list_index: index,
        source_query: candidate.query,
        category_hint: candidate.categoryHint || "",
        day_index: candidate.day_index,
        day_title: candidate.day_title,
        slot: candidate.slot,
        slot_text: candidate.slot_text,
        intent_type: "generic_poi",
        pending_key: [
          candidate.day_index || 0,
          candidate.slot || "",
          candidate.query || "",
          item.poi_id || item.name || index
        ].join("|")
      }));
    }

    async function syncMapFromConversation(message, assistantReply, itinerary) {
      try {
        state.latestAssistantReply = String(assistantReply || state.latestAssistantReply || "");
        state.latestItinerary = itinerary || state.latestItinerary || null;
        const itineraryCity = String(state.latestItinerary?.city || "").trim();
        if (state.mapConfig) {
          state.mapConfig.defaultCity = itineraryCity || extractDestinationHintFromText(message) || state.mapConfig.defaultCity || "绵阳";
        }
        const resolvedPlaces = [];
        const previewItems = [];
        const pendingCandidates = [];
        const seen = new Set();
        const previewSeen = new Set();
        const groupedByDay = new Map();
        const itineraryDays = Array.isArray(state.latestItinerary?.days) ? state.latestItinerary.days : [];
        const structuredCandidates = extractPlaceCandidatesFromItinerary(state.latestItinerary, state.latestAssistantReply);
        const placeCandidates = structuredCandidates.length
          ? structuredCandidates
          : extractPlaceCandidatesFromReply(state.latestAssistantReply);
        for (const candidate of placeCandidates) {
          const previewName = String(candidate?.query || "").trim();
          if (!previewName) continue;
          const previewKey = [candidate.day_index || 0, candidate.slot || "", previewName].join("|");
          if (previewSeen.has(previewKey)) continue;
          previewSeen.add(previewKey);
          previewItems.push({
            name: previewName,
            address: candidate.slot_text || candidate.sourceLine || "",
            category: candidate.categoryHint || "",
            day_index: candidate.day_index,
            day_title: candidate.day_title,
            slot: candidate.slot,
            sourceLine: candidate.slot_text || candidate.sourceLine || "",
            source_query: candidate.query,
            intent_type: candidate.intentType || ""
          });
        }
        state.mapItineraryDays = itineraryDays;
        state.mapPreviewItems = previewItems.slice(0, 30);
        if (!Number.isFinite(Number(state.mapSelectedDay))) {
          state.mapSelectedDay = itineraryDays.length ? Number(itineraryDays[0]?.day_index || 1) : null;
        }
        state.mapActiveResultKey = null;
        if (!placeCandidates.length) {
          state.mapSearchResults = [];
          state.mapPreviewItems = [];
          state.mapPendingCandidates = [];
          state.mapRouteSegments = [];
          renderMap();
          if (mapStatusEl) {
            mapStatusEl.textContent = "这次回复里没有识别到明确地点，地图暂时不自动落点。";
          }
          return;
        }

        for (const candidate of placeCandidates) {
          if (Array.isArray(candidate.selectedPlaces) && candidate.selectedPlaces.length) {
            for (const selectedPlace of candidate.selectedPlaces) {
              const location = parseLocation(selectedPlace?.location);
              if (!location) continue;
              const key = `${candidate.day_index || 0}_${selectedPlace.poi_id || ""}_${selectedPlace.name || candidate.query}`;
              if (seen.has(key)) continue;
              seen.add(key);
              const enrichedSelected = {
                ...selectedPlace,
                location,
                day_index: candidate.day_index,
                day_title: candidate.day_title,
                slot: candidate.slot,
                slot_text: candidate.slot_text,
                source_query: candidate.query,
                category_hint: candidate.categoryHint || ""
              };
              resolvedPlaces.push(enrichedSelected);
              const dayKey = String(candidate.day_index || 0);
              if (!groupedByDay.has(dayKey)) groupedByDay.set(dayKey, []);
              groupedByDay.get(dayKey).push(enrichedSelected);
            }
            continue;
          }

          if (candidate.intentType === "generic_poi") {
            continue;
          }

          let poi = null;
          try {
            poi = await resolvePlaceCandidate(candidate);
          } catch (resolveError) {
            console.warn("resolvePlaceCandidate failed", resolveError);
          }
          if (!poi?.location) continue;
          const key = `${candidate.day_index || 0}_${poi.poi_id || ""}_${poi.name || candidate.query}`;
          if (seen.has(key)) continue;
          seen.add(key);
          const enrichedPoi = {
            ...poi,
            day_index: candidate.day_index,
            day_title: candidate.day_title,
            slot: candidate.slot,
            slot_text: candidate.slot_text
          };
          resolvedPlaces.push(enrichedPoi);
          const dayKey = String(candidate.day_index || 0);
          if (!groupedByDay.has(dayKey)) groupedByDay.set(dayKey, []);
          groupedByDay.get(dayKey).push(enrichedPoi);
        }

        for (const candidate of placeCandidates) {
          if (candidate.intentType !== "generic_poi") continue;
          if (Array.isArray(candidate.selectedPlaces) && candidate.selectedPlaces.length) continue;
          try {
            const candidateRes = await api("/api/planner/place-candidates", {
              method: "POST",
              body: JSON.stringify({
                session_id: state.sessionId,
                day_index: candidate.day_index,
                slot: candidate.slot,
                query: candidate.query,
                intent_type: candidate.intentType,
                city: getActivePlanningCity(message),
                category_hint: candidate.categoryHint || null,
                anchor_location: getDayAnchorLocation(groupedByDay, candidate.day_index),
                limit: 5
              })
            });
            pendingCandidates.push(...buildPendingCandidateEntries(candidate, candidateRes));
          } catch (candidateError) {
            console.warn("place-candidates failed", candidateError);
          }
        }

        state.mapSearchResults = resolvedPlaces.slice(0, 30);
        state.mapPendingCandidates = pendingCandidates.slice(0, 30);
        state.mapRouteSegments = [];
        renderMap();
        if (mapSearchInputEl) {
          mapSearchInputEl.value = placeCandidates[0]?.query || "";
        }

        const routeStart = state.userLocation || parseLocation(state.mapConfig?.defaultCenter);
        if (routeStart && state.mapConfig?.enabled) {
          const allSegments = [];
          for (const [, dayPlaces] of groupedByDay.entries()) {
            const routePoints = dayPlaces
              .map(normalizeRoutePoint)
              .filter(Boolean)
              .slice(0, 10);
            if (routePoints.length < 2) continue;
            try {
              const routeRes = await api("/api/map/route/plan", {
                method: "POST",
                body: JSON.stringify({
                  start: routeStart,
                  points: routePoints,
                  mode: "walk"
                })
              });
              const dayIndex = dayPlaces[0]?.day_index || null;
              const segments = Array.isArray(routeRes.route?.segments)
                ? routeRes.route.segments.map((segment) => ({
                    ...segment,
                    day_index: dayIndex
                  }))
                : [];
              allSegments.push(...segments);
            } catch (routeError) {
              console.warn("routePlan failed", routeError);
            }
          }
          state.mapRouteSegments = allSegments;
          renderMap();
        }
      } catch (error) {
        console.warn("syncMapFromConversation failed", error);
        if (mapStatusEl) {
          mapStatusEl.textContent = `对话地图同步失败：${error?.message || error}`;
        }
      }
    }

    function clearMap() {
      if (!state.map) return;
      if (Array.isArray(state.mapMarkers)) {
        for (const marker of state.mapMarkers) {
          if (marker && typeof marker.setMap === "function") marker.setMap(null);
        }
      }
      if (Array.isArray(state.mapPolylines)) {
        for (const polyline of state.mapPolylines) {
          if (polyline && typeof polyline.setMap === "function") polyline.setMap(null);
        }
      }
      state.mapMarkers = [];
      state.mapPolylines = [];
    }

    function destroyMap() {
      clearMap();
      if (state.mapBuildingLayer) {
        state.mapBuildingLayer.destroy?.();
        state.mapBuildingLayer = null;
      }
      if (state.map) {
        state.map.destroy?.();
        state.map = null;
      }
      if (mapCanvasEl) {
        mapCanvasEl.innerHTML = "";
      }
    }

    function renderMapFallback(message) {
      if (mapCanvasEl) {
        mapCanvasEl.innerHTML = `
          <div class="map-placeholder">
            <div>
              <div style="font-weight:700; color:#0f172a; margin-bottom:6px;">Map not loaded</div>
              <div>${escapeHtml(message)}</div>
            </div>
          </div>
        `;
      }
    }

    function renderMap() {
      if (!mapStatusEl || !mapCanvasEl) return;
      renderMapDayTabs();
      const visibleResults = getVisibleMapResults();
      const visiblePreviewItems = getVisibleMapPreviewItems();
      const visibleRouteSegments = getVisibleMapRouteSegments();
      if (!state.mapConfig?.enabled || !window.AMap) {
        const fallbackMessage = visiblePreviewItems.length
          ? "当前无法加载高德地图，但已识别到行程地点，可先在下方查看地点列表。"
          : getMapUnavailableReason();
        mapStatusEl.textContent = `${fallbackMessage} (${state.mapSearchResults.length} results)`;
        destroyMap();
        renderMapFallback(fallbackMessage);
        renderMapResults(visibleResults);
        return;
      }

      if (!visibleResults.length && !visibleRouteSegments.length && visiblePreviewItems.length) {
        mapStatusEl.textContent = `已识别 ${visiblePreviewItems.length} 个行程地点，但当前还没有可定位坐标。`;
        destroyMap();
        renderMapFallback("已识别到当前行程地点，但暂时没有可落图的坐标。你可以先查看下方地点列表，或手动搜索更精确的地点。");
        renderMapResults(visibleResults);
        return;
      }

      mapStatusEl.textContent = visibleResults.length
        ? `已显示 ${visibleResults.length} 个地点`
        : (state.userLocation ? "地图已加载，当前位置已显示。可直接搜索地点。" : "地图已加载，可直接搜索地点。");

      const hasCameraOverride = Boolean(state.mapCameraOverride);
      if (!state.map) {
        const overrideCenter = parseLocation(state.mapCameraOverride);
        const defaultCenter = overrideCenter || parseLocation(state.userLocation) || parseLocation(state.mapConfig?.defaultCenter) || { lng: 104.195397, lat: 35.86166 };
        state.map = new AMap.Map("mapCanvas", {
          viewMode: state.map3D ? "3D" : "2D",
          layers: [AMap.createDefaultLayer()],
          showBuildingBlock: true,
          features: ["bg", "point", "road", "building"],
          zoom: Number.isFinite(Number(state.mapCameraOverride?.zoom)) ? Number(state.mapCameraOverride.zoom) : 12,
          center: [defaultCenter.lng, defaultCenter.lat],
          pitch: state.map3D ? 52 : 0,
          rotation: state.map3D ? -16 : 0
        });
      }

      ensureMapBuildingLayer();

      clearMap();
      const markers = [];
      if (state.userLocation) {
        const currentMarker = new AMap.Marker({
          position: [state.userLocation.lng, state.userLocation.lat],
          title: "当前位置"
        });
        currentMarker.setMap(state.map);
        markers.push(currentMarker);
      }
      for (const item of visibleResults) {
        const location = parseLocation(item.location);
        if (!location) continue;
        const dayLabel = Number.isFinite(Number(item.day_index)) ? `第${Number(item.day_index)}天 · ` : "";
        const marker = new AMap.Marker({
          position: [location.lng, location.lat],
          title: `${dayLabel}${item.name || "地点"}`
        });
        marker.setMap(state.map);
        marker.on?.("click", () => focusMapResult(item));
        markers.push(marker);
      }
      state.mapMarkers = markers;

      const polylines = [];
      for (const segment of visibleRouteSegments) {
        const polylinePoints = Array.isArray(segment.polyline) ? segment.polyline.map((point) => parseLocation(point)).filter(Boolean) : [];
        if (polylinePoints.length < 2) continue;
        const line = new AMap.Polyline({
          path: polylinePoints.map((point) => [point.lng, point.lat]),
          strokeColor: getRouteColor(segment.day_index),
          strokeWeight: state.map3D ? 6 : 5,
          strokeOpacity: 0.92,
          lineJoin: "round",
          lineCap: "round",
          showDir: true
        });
        line.setMap(state.map);
        polylines.push(line);
      }
      state.mapPolylines = polylines;

      if (!hasCameraOverride && markers.length && typeof state.map.setFitView === "function") {
        state.map.setFitView([...markers, ...polylines]);
        const fittedZoom = Number(state.map.getZoom?.() ?? 0);
        if (state.map3D && fittedZoom > 15.2) {
          state.map.setZoom?.(15.2);
        }
      } else if (!hasCameraOverride && typeof state.map.setZoomAndCenter === "function") {
        const fallbackCenter = parseLocation(state.mapConfig?.defaultCenter) || { lng: 104.195397, lat: 35.86166 };
        state.map.setZoomAndCenter(5, [fallbackCenter.lng, fallbackCenter.lat], false, 220);
      }

      state.mapCameraOverride = null;
      applyMapMode();
      renderMapResults(visibleResults);
    }

    async function loadMapSdk() {
      try {
        state.mapSdkError = null;
        state.mapConfig = await api("/map/config");
        if (state.mapConfig) {
          const configuredCity = String(state.mapConfig.defaultCity || "").trim();
          state.mapConfig.defaultCity = configuredCity || "绵阳";
        }
        if (!state.mapConfig.enabled) {
          state.mapSdkError = "AMap browser key is missing.";
          return;
        }
        window._AMapSecurityConfig = { securityJsCode: state.mapConfig.securityJsCode };
        if (window.AMap) return;
        await new Promise((resolve, reject) => {
          const script = document.createElement("script");
          script.src = `https://webapi.amap.com/maps?v=2.0&key=${state.mapConfig.browserKey}`;
          script.onload = resolve;
          script.onerror = reject;
          document.head.appendChild(script);
        });
      } catch (error) {
        state.mapSdkError = error?.message || "unknown load error";
        console.warn("map sdk load failed", error);
      }
      renderMap();
    }

    async function runMapSearch() {
      const keyword = String(mapSearchInputEl?.value || "").trim();
      if (!keyword) {
        mapStatusEl.textContent = "请输入要搜索的地点关键词。";
        return;
      }
      mapStatusEl.textContent = `正在搜索 ${keyword}...`;
      try {
        const res = await api("/map/search", {
          method: "POST",
          body: JSON.stringify({
            keyword,
            city: getActivePlanningCity(),
            search_mode: "region",
            radius_meters: 3000,
            limit: 10,
            user_location: state.userLocation
          })
        });
        state.mapItineraryDays = [];
        state.mapSelectedDay = null;
        state.mapActiveResultKey = null;
        state.mapPreviewItems = [];
        state.mapPendingCandidates = [];
        state.mapSearchResults = Array.isArray(res.items) ? res.items : [];
        state.mapRouteSegments = [];
        renderMap();
        setStatus(res.status === "ok" ? `地图搜索已完成：${keyword}` : `地图搜索结果：${res.status || "empty"}`);
      } catch (error) {
        console.error(error);
        mapStatusEl.textContent = `地图搜索失败：${error?.message || error}`;
      }
    }

    function appendMessage(message) {
      const wrapper = document.createElement("div");
      wrapper.className = `message-row ${message.role === "user" ? "user" : "assistant"}`;
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      bubble.innerHTML = `<div>${escapeHtml(message.content || "")}</div>`;
      wrapper.appendChild(bubble);
      transcriptEl.appendChild(wrapper);
      scrollBottom();
    }

    function renderMessages(messages) {
      state.messages = Array.isArray(messages) ? messages.slice() : [];
      transcriptEl.innerHTML = "";
      if (!state.messages.length) {
        transcriptEl.innerHTML = '<div class="empty">先发一条需求，我会开始做旅游地点规划建议。</div>';
        return;
      }
      for (const message of state.messages) {
        const wrapper = document.createElement("div");
        wrapper.className = `message-row ${message.role === "user" ? "user" : "assistant"}`;
        const bubble = document.createElement("div");
        bubble.className = "bubble";
        bubble.innerHTML = `<div>${escapeHtml(message.content || "")}</div>`;
        wrapper.appendChild(bubble);
        transcriptEl.appendChild(wrapper);
      }
      scrollBottom();
    }

    function renderSessionList() {
      const sessions = Array.isArray(state.sessions) ? state.sessions : [];
      const loadedCount = sessions.length;
      const totalCount = Number(state.sessionHistoryTotal || loadedCount || 0);
      if (sessionPanelBadgeEl) {
        sessionPanelBadgeEl.textContent = String(totalCount || 0);
      }
      sessionListMetaEl.textContent = loadedCount
        ? `显示 ${loadedCount} 个最近会话，共 ${totalCount || loadedCount} 个会话`
        : "暂无会话";
      if (!sessions.length) {
        sessionListEl.innerHTML = '<div class="session-empty">还没有历史会话。先发一条消息，系统会自动创建会话并保留记录。</div>';
        return;
      }

      sessionListEl.innerHTML = sessions.map((session) => {
        const active = state.sessionId && session.id === state.sessionId;
        const preview = session.latest_message || session.title || "未命名会话";
        const roleLabel = session.latest_message_role === "assistant" ? "助手" : "用户";
        const messageCount = Number(session.message_count || 0);
        return `
          <article class="session-card ${active ? "active" : ""}" data-session-open="${escapeHtml(session.id)}">
            <button class="session-delete" type="button" title="删除会话" aria-label="删除会话 ${escapeHtml(session.title || session.id)}" data-session-delete="${escapeHtml(session.id)}">×</button>
            <h3>${escapeHtml(session.title || "未命名会话")}</h3>
            <div class="preview">${escapeHtml(preview)}</div>
            <div class="meta-row">
              <span>${escapeHtml(roleLabel)} · ${escapeHtml(String(messageCount))} 条消息</span>
              <span>${escapeHtml(formatSessionTime(session.updated_at || session.created_at || ""))}</span>
            </div>
          </article>
        `;
      }).join("");

      sessionListEl.querySelectorAll("[data-session-open]").forEach((button) => {
        button.addEventListener("click", async () => {
          await openSession(button.dataset.sessionOpen);
        });
      });
      sessionListEl.querySelectorAll("[data-session-delete]").forEach((button) => {
        button.addEventListener("click", async (event) => {
          event.preventDefault();
          event.stopPropagation();
          await deleteSession(button.dataset.sessionDelete);
        });
      });
    }

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }
      return response.json();
    }

    async function loadAppInfo() {
      try {
        const info = await api("/health");
        const model = info?.model || "-";
        const apiBase = info?.api_base || "";
        const provider = apiBase.includes("11434") ? "Ollama" : "ModelScope";
        setModelName(model === "-" ? "-" : `${provider} · ${model}`);
      } catch (error) {
        console.warn("loadAppInfo failed", error);
        setModelName("-");
      }
    }

    async function loadSessionHistory() {
      try {
        const result = await api("/sessions?limit=12");
        state.sessions = Array.isArray(result.items) ? result.items : [];
        state.sessionHistoryTotal = Number.isFinite(Number(result.total))
          ? Number(result.total)
          : state.sessions.length;
      } catch (error) {
        console.warn("loadSessionHistory failed", error);
        state.sessions = [];
        state.sessionHistoryTotal = 0;
      }
      renderSessionList();
    }

    async function createSession() {
      const session = await api("/sessions", {
        method: "POST",
        body: JSON.stringify({ title: "旅行问答会话" }),
      });
      state.sessionId = session.id;
      sessionIdEl.textContent = session.id;
      localStorage.setItem("travelAgentSessionId", session.id);
      await loadSessionHistory();
      setRecentPanelOpen(false);
      return session.id;
    }

    async function loadSessionItinerary(sessionId) {
      if (!sessionId) return null;
      try {
        const result = await api(`/sessions/${sessionId}/itineraries/latest`);
        return result?.itinerary?.content || null;
      } catch (error) {
        return null;
      }
    }

    async function openSession(sessionId) {
      if (!sessionId) return;
      const result = await api(`/sessions/${sessionId}/messages?limit=200`);
      state.sessionId = sessionId;
      sessionIdEl.textContent = sessionId;
      localStorage.setItem("travelAgentSessionId", sessionId);
      renderMessages(result.items || []);
      state.latestAssistantReply = getLatestAssistantText(result.items || []);
      state.latestItinerary = await loadSessionItinerary(sessionId);
      await syncMapFromConversation("", state.latestAssistantReply, state.latestItinerary);
      await loadSessionHistory();
      setRecentPanelOpen(false);
      setStatus("已打开历史会话。");
    }

    async function deleteSession(sessionId) {
      if (!sessionId) return;
      const ok = window.confirm("确定删除这个会话吗？删除后消息也会一起清除。");
      if (!ok) return;
      await api(`/sessions/${sessionId}`, { method: "DELETE" });
      if (state.sessionId === sessionId) {
        localStorage.removeItem("travelAgentSessionId");
        state.sessionId = null;
        sessionIdEl.textContent = "未创建";
        state.latestAssistantReply = "";
        state.latestItinerary = null;
        renderMessages([]);
      }
      await loadSessionHistory();
      setStatus("会话已删除。");
    }

    async function sendMessage() {
      if (state.loading) return;
      const message = promptInputEl.value.trim();
      if (!message) return;
      const previousPromptValue = promptInputEl.value;
      promptInputEl.value = "";
      appendMessage({ role: "user", content: message });

      state.loading = true;
      sendBtnEl.disabled = true;
      setStatus("正在请求大模型...");

      try {
        const sessionId = state.sessionId || await createSession();
        const result = await api("/chat", {
          method: "POST",
          body: JSON.stringify({
            message,
            session_id: sessionId,
            conversation_context: buildConversationContext(),
          }),
        });
        state.sessionId = result.session_id;
        sessionIdEl.textContent = result.session_id;
        localStorage.setItem("travelAgentSessionId", result.session_id);
        renderMessages(result.messages || []);
        state.latestAssistantReply = result.assistantMessage || getLatestAssistantText(result.messages || []);
        state.latestItinerary = result.itinerary || null;
        await syncMapFromConversation(
          message,
          state.latestAssistantReply,
          state.latestItinerary
        );
        await loadSessionHistory();
        setStatus("已收到回复。");
      } catch (error) {
        console.error(error);
        promptInputEl.value = previousPromptValue;
        setStatus("请求失败，请检查后端或模型接口配置。");
      } finally {
        state.loading = false;
        sendBtnEl.disabled = false;
      }
    }

    async function restoreSession() {
      const saved = localStorage.getItem("travelAgentSessionId");
      await loadAppInfo();
      await loadMapSdk();
      requestBrowserLocation();
      await loadSessionHistory();
      if (!saved) return;
      try {
        const result = await api(`/sessions/${saved}/messages?limit=200`);
        state.sessionId = saved;
        sessionIdEl.textContent = saved;
        renderMessages(result.items || []);
        state.latestAssistantReply = getLatestAssistantText(result.items || []);
        state.latestItinerary = await loadSessionItinerary(saved);
        await syncMapFromConversation("", state.latestAssistantReply, state.latestItinerary);
        setStatus("已恢复上次会话。");
        renderSessionList();
      } catch (error) {
        localStorage.removeItem("travelAgentSessionId");
      }
    }

    sendBtnEl.addEventListener("click", sendMessage);
    mapSearchBtnEl.addEventListener("click", runMapSearch);
    mapSearchInputEl.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runMapSearch();
      }
    });
    mapMode2DBtnEl.addEventListener("click", () => setMapMode(false));
    mapMode3DBtnEl.addEventListener("click", () => setMapMode(true));
    mapZoomInBtnEl.addEventListener("click", () => {
      if (state.map && typeof state.map.zoomIn === "function") state.map.zoomIn();
    });
    mapZoomOutBtnEl.addEventListener("click", () => {
      if (state.map && typeof state.map.zoomOut === "function") state.map.zoomOut();
    });
    newSessionBtnEl.addEventListener("click", async () => {
      localStorage.removeItem("travelAgentSessionId");
      state.sessionId = null;
      state.messages = [];
      state.latestAssistantReply = "";
      state.latestItinerary = null;
      state.mapSearchResults = [];
      state.mapPreviewItems = [];
      state.mapPendingCandidates = [];
      state.mapRouteSegments = [];
      state.mapItineraryDays = [];
      state.mapSelectedDay = null;
      sessionIdEl.textContent = "未创建";
      renderMessages([]);
      renderMap();
      await loadSessionHistory();
      setRecentPanelOpen(false);
      setStatus("已重置为新会话。");
    });
    sessionPanelToggleEl.addEventListener("click", () => {
      setRecentPanelOpen(!state.recentPanelOpen);
    });
    sessionPanelCloseEl.addEventListener("click", () => {
      setRecentPanelOpen(false);
    });
    document.addEventListener("click", (event) => {
      if (!state.recentPanelOpen) return;
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (
        sessionPanelEl.contains(target) ||
        sessionPanelToggleEl.contains(target)
      ) {
        return;
      }
      setRecentPanelOpen(false);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        setRecentPanelOpen(false);
      }
    });
    promptInputEl.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
    });

    syncMapModeButtons();
    restoreSession();
  
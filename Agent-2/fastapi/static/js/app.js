    const state = {
      theme: "light",
      motion: true,
      typing: false,
      session: null,
      activeRequirement: null,
      itineraryBundle: null,
      mapConfig: null,
      map: null,
      mapInfoWindow: null,
      mapMarkers: [],
      mapPolylines: [],
      map3D: false,
      activeMapDay: null,
      activePlaceId: null,
      activePanel: "itinerary",
      userLocation: null,
      chatTranscriptDirty: false,
      mapSearchResults: [],
      mapSdkError: null,
      modelInfo: null,
      sessions: []
    };

    const api = async (path, options = {}) => {
      const res = await fetch(path, {
        headers: { "content-type": "application/json", ...(options.headers || {}) },
        ...options
      });
      if (!res.ok) {
        const detail = await res.text().catch(() => "");
        throw new Error(detail || `Request failed: ${res.status}`);
      }
      return res.json();
    };

    function escapeHtml(text) {
      const div = document.createElement("div");
      div.textContent = text ?? "";
      return div.innerHTML;
    }

    function normalizeDisplayText(text) {
      return String(text ?? "")
        .replace(/\*\*(.*?)\*\*/g, "$1")
        .replace(/\*\*/g, "");
    }

    function displayText(text) {
      return escapeHtml(normalizeDisplayText(text));
    }

    function getMapUnavailableReason() {
      if (state.mapSdkError) return `AMap SDK load failed: ${state.mapSdkError}`;
      if (!state.mapConfig?.enabled) return "AMap browser key or security code is not configured.";
      if (!window.AMap) return "AMap JS SDK is not available in the browser yet.";
      return "Map is unavailable.";
    }

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
      const rawDays = bundle?.itinerary?.itinerary?.days || bundle?.itinerary?.days || [];
      const requestedDays = resolveRequestedTripDays(bundle);
      const totalDays = Math.max(rawDays.length, requestedDays);
      if (!totalDays) return [];
      return Array.from({ length: totalDays }, (_, index) => {
        const existingDay = rawDays[index];
        if (existingDay) {
          return {
            ...existingDay,
            day: Number(existingDay.day) || index + 1,
            items: Array.isArray(existingDay.items) ? existingDay.items : []
          };
        }
        return {
          day: index + 1,
          theme: `Day ${index + 1}`,
          items: []
        };
      });
    }

    function getMapData(bundle) {
      return bundle?.mapData || bundle?.itinerary?.mapData || null;
    }

    function getRouteSegments(bundle) {
      return getMapData(bundle)?.polylines || bundle?.routeSegments || bundle?.itinerary?.routeSegments || [];
    }

    function getMapMarkers(bundle) {
      const markers = getMapData(bundle)?.markers || [];
      const itineraryMarkers = flattenItineraryItems(bundle)
        .filter((item) => item?.location && Number.isFinite(Number(item.location.lng)) && Number.isFinite(Number(item.location.lat)))
        .map((item) => ({
          id: getItemId(item),
          day: Number(item.day) || 1,
          order: item.order,
          name: item.name,
          category: item.category,
          location: item.location
        }));
      if (!itineraryMarkers.length) return markers;
      return markers.length === itineraryMarkers.length ? markers : itineraryMarkers;
    }

    function getItemId(item) {
      return String(item?.candidateId || item?.id || item?.name || "").trim();
    }

    function escapeAttribute(text) {
      return String(text ?? "").replace(/"/g, "&quot;");
    }

    function setActivePlace(placeId, bundle = state.itineraryBundle) {
      state.activePlaceId = String(placeId || "");
      renderItineraryV2(bundle);
      renderMapV2Clean(bundle);
      renderResolvedPlacesV2Clean(bundle);
      const target = document.querySelector(`[data-place-id="${escapeAttribute(state.activePlaceId)}"]`);
      target?.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    function resolveActiveMapDay(bundle) {
      const days = getItineraryDays(bundle);
      if (!days.length) {
        state.activeMapDay = null;
        return null;
      }
      if (state.activeMapDay && days.some((day) => Number(day.day) === Number(state.activeMapDay))) {
        return Number(state.activeMapDay);
      }
      state.activeMapDay = Number(days[0].day);
      return state.activeMapDay;
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
      if (index === 0 && state.userLocation) {
        return haversineMetersBetweenPoints(state.userLocation, item.location);
      }
      return null;
    }

    function requestBrowserLocation() {
      if (!navigator.geolocation) return;
      navigator.geolocation.getCurrentPosition(
        (position) => {
          state.userLocation = {
            lng: position.coords.longitude,
            lat: position.coords.latitude
          };
          renderMapV2Clean(state.itineraryBundle || null);
          if (state.itineraryBundle) {
            renderItineraryV2(state.itineraryBundle);
          }
        },
        () => {
          state.userLocation = null;
        },
        { enableHighAccuracy: true, timeout: 6000, maximumAge: 300000 }
      );
    }

    function nowTime() {
      return new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    }

    function flattenItineraryItems(bundle) {
      const days = getItineraryDays(bundle);
      return days.flatMap((day) =>
        (day.items || []).map((item) => ({
          ...item,
          day: day.day,
          theme: day.theme
        }))
      );
    }

    function buildConversationContext(requirement) {
      if (!requirement) return "";
      const payload = requirement.structured_payload || requirement.payload || {};
      const pieces = [];
      if (payload.destination) pieces.push(`目的地：${payload.destination}`);
      if (payload.trip_days) pieces.push(`天数：${payload.trip_days}天`);
      const interests = Array.isArray(payload.interests) ? payload.interests.filter(Boolean) : [];
      if (interests.length) pieces.push(`偏好：${interests.slice(0, 6).join("、")}`);
      const prefs = payload.user_preferences || {};
      if (prefs.preferredPace) pieces.push(`节奏：${prefs.preferredPace}`);
      if (prefs.distanceTolerance) pieces.push(`距离：${prefs.distanceTolerance}`);
      if (requirement.raw_input) pieces.push(`原始需求：${requirement.raw_input}`);
      return pieces.join("；");
    }

    function getConversationContext() {
      return buildConversationContext(state.activeRequirement || state.itineraryBundle?.requirement || null);
    }

    function buildRelocationPrompt(item) {
      const parts = [
        `请围绕「${item?.name || "这个地点"}」重新定位行程，优先保留我之前的需求和偏好。`
      ];
      if (item?.category) parts.push(`目标类别：${item.category}`);
      if (item?.address) parts.push(`地点地址：${item.address}`);
      return parts.join(" ");
    }

    function setWorkbenchStatus(text) {
      const el = document.getElementById("workbenchStatus");
      if (el) el.textContent = text;
    }

    function showTemporaryNotice(text, tone = "info") {
      let el = document.getElementById("toastNotice");
      if (!el) {
        el = document.createElement("div");
        el.id = "toastNotice";
        document.body.appendChild(el);
      }
      el.className = [
        "fixed bottom-24 right-4 z-[60] max-w-[320px] rounded-2xl border px-4 py-3 text-sm shadow-2xl backdrop-blur-xl",
        tone === "error"
          ? "border-rose-400/30 bg-rose-950/90 text-rose-100"
          : "border-white/10 bg-slate-950/90 text-slate-100",
      ].join(" ");
      el.textContent = text;
      clearTimeout(showTemporaryNotice._timer);
      showTemporaryNotice._timer = window.setTimeout(() => {
        el?.remove();
      }, 3500);
    }

    function syncSessionIds(session, bundle) {
      const sessionEl = document.getElementById("currentSessionId");
      const requirementEl = document.getElementById("currentRequirementId");
      const itineraryEl = document.getElementById("currentItineraryId");
      if (sessionEl) sessionEl.textContent = session?.id || bundle?.session_id || "-";
      if (requirementEl) requirementEl.textContent = `req: ${session?.latest_requirement_id || bundle?.requirement?.id || "-"}`;
      if (itineraryEl) itineraryEl.textContent = `iti: ${session?.latest_itinerary_id || bundle?.itinerary?.id || "-"}`;
    }

    function syncModelName(modelInfo) {
      const el = document.getElementById("currentModelName");
      if (!el) return;
      const modelName = modelInfo?.model || modelInfo?.name || "-";
      const provider = modelInfo?.api_base?.includes("11434") ? "Ollama" : "Model";
      el.textContent = modelName === "-" ? "-" : `${provider} · ${modelName}`;
    }

    function formatSessionTimestamp(value) {
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

    function renderSessionHistory() {
      const list = document.getElementById("sessionHistoryList");
      const meta = document.getElementById("sessionHistoryMeta");
      if (!list || !meta) return;
      const sessions = Array.isArray(state.sessions) ? state.sessions : [];
      meta.textContent = sessions.length ? `最近 ${sessions.length} 个会话` : "暂无历史会话";
      if (!sessions.length) {
        list.innerHTML = `
          <div class="rounded-[1.35rem] border border-dashed border-white/12 bg-slate-950/25 px-4 py-5 text-sm text-slate-500 sm:col-span-2 xl:col-span-3">
            这里会显示你最近聊过的会话，点一下就能恢复，右上角可以删除。
          </div>
        `;
        return;
      }
      list.innerHTML = sessions.map((session) => {
        const isActive = state.session?.id && session.id === state.session.id;
        const preview = session.latest_message || session.title || "未命名会话";
        const roleLabel = session.latest_message_role === "assistant" ? "助手" : "用户";
        return `
          <article class="group relative overflow-hidden rounded-[1.35rem] border ${isActive ? "border-[color:var(--accent)]/60 bg-[color:var(--accent)]/10" : "border-white/10 bg-white/5"} p-4 transition hover:-translate-y-0.5 hover:border-white/20">
            <button
              type="button"
              class="absolute right-3 top-3 rounded-full border border-white/10 bg-slate-950/70 px-2 py-1 text-[11px] text-slate-300 opacity-90 transition hover:border-rose-400/40 hover:text-rose-200"
              data-session-delete="${escapeHtml(session.id)}"
              aria-label="删除会话 ${escapeHtml(session.title || session.id)}"
              title="删除会话"
            >
              删除
            </button>
            <button
              type="button"
              class="block w-full text-left"
              data-session-open="${escapeHtml(session.id)}"
            >
              <div class="pr-12">
                <div class="text-sm font-semibold ${isActive ? "text-white" : "text-slate-100"}">${displayText(session.title || "新会话")}</div>
                <div class="mt-1 text-[11px] uppercase tracking-[0.28em] ${isActive ? "text-[color:var(--accent)]/90" : "text-slate-500"}">${isActive ? "当前会话" : "历史会话"}</div>
              </div>
              <div class="mt-3 max-h-[4.75rem] min-h-[3.75rem] overflow-hidden text-sm leading-6 text-slate-300">${displayText(preview)}</div>
              <div class="mt-4 flex items-center justify-between gap-3 text-[11px] text-slate-500">
                <span>${escapeHtml(roleLabel)} · ${escapeHtml(String(session.message_count || 0))} 条消息</span>
                <span>${escapeHtml(formatSessionTimestamp(session.updated_at || session.created_at || ""))}</span>
              </div>
            </button>
          </article>
        `;
      }).join("");

      list.querySelectorAll("article .mt-4 span:first-child").forEach((element) => {
        const text = element.textContent || "";
        const countIndex = text.search(/\d/);
        if (countIndex > 0) {
          element.innerHTML = `${escapeHtml(text.slice(0, countIndex))}<span class="session-count">${escapeHtml(text.slice(countIndex))}</span>`;
          return;
        }
        element.classList.add("session-count");
      });

      list.querySelectorAll("[data-session-open]").forEach((button) => {
        button.addEventListener("click", () => openSession(button.dataset.sessionOpen));
      });
      list.querySelectorAll("[data-session-delete]").forEach((button) => {
        button.addEventListener("click", async (event) => {
          event.stopPropagation();
          await deleteSession(button.dataset.sessionDelete);
        });
      });
    }

    async function loadSessionHistory() {
      try {
        const result = await api("/sessions?limit=9");
        state.sessions = Array.isArray(result.items) ? result.items : [];
      } catch (error) {
        console.warn("loadSessionHistory failed", error);
        state.sessions = [];
      }
      renderSessionHistory();
    }

    async function openSession(sessionId) {
      if (!sessionId) return;
      await loadSessionData(sessionId);
      await loadSessionHistory();
    }

    async function deleteSession(sessionId) {
      if (!sessionId) return;
      const activeSessionId = state.session?.id || localStorage.getItem("nightAtlasSessionId");
      const confirmed = window.confirm("确定删除这个会话吗？删除后无法恢复。");
      if (!confirmed) return;
      await api(`/sessions/${sessionId}`, { method: "DELETE" });
      if (activeSessionId === sessionId) {
        prepareNewSession();
      }
      await loadSessionHistory();
    }

    function setTheme(theme) {
      state.theme = theme;
      document.documentElement.dataset.theme = theme;
      document.querySelectorAll(".theme-btn").forEach((btn) => {
        const active = btn.dataset.theme === theme;
        btn.classList.toggle("ring-2", active);
        btn.classList.toggle("ring-[color:var(--accent)]", active);
      });
    }

    function setLanguage(lang) {
      document.querySelectorAll(".lang-btn").forEach((btn) => {
        const active = btn.dataset.lang === lang;
        btn.classList.toggle("ring-2", active);
        btn.classList.toggle("ring-[color:var(--accent)]", active);
      });
      document.getElementById("promptInput").placeholder = lang === "en"
        ? "Tell me your trip needs, preferences, or pace."
        : "你有什么需求？比如想多景点、咖啡、美食、夜景，或者想轻松一点。";
      document.getElementById("mapSearchInput").placeholder = lang === "en"
        ? "Search places, e.g. cafe, mall, night view"
        : "搜索地点，比如：咖啡店、景点、夜景";
    }

    function openSettings(open) {
      document.getElementById("settingsPanel").classList.toggle("open", open);
      document.getElementById("overlay").classList.toggle("open", open);
    }

    function setPanel(panel) {
      state.activePanel = panel;
      document.querySelectorAll(".panel-tab").forEach((btn) => {
        const active = btn.dataset.panel === panel;
        btn.setAttribute("aria-selected", active ? "true" : "false");
      });
      const itineraryPanel = document.getElementById("itineraryPanel");
      const debugPanel = document.getElementById("debugPanel");
      const mapBlock = document.getElementById("mapBlock");
      if (itineraryPanel) itineraryPanel.classList.remove("hidden");
      if (debugPanel) debugPanel.classList.toggle("hidden", panel !== "debug");
      if (panel === "itinerary" && mapBlock) {
        mapBlock.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }

        function scrollChatBottom() {
      const el = document.getElementById("chatTranscript");
      requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
    }

    function appendTranscriptMessage(message) {
      const el = document.getElementById("chatTranscript");
      const wrapper = document.createElement("div");
      wrapper.className = `bubble-enter flex ${message.role === "user" ? "justify-end" : "justify-start"}`;
      const bubble = document.createElement("div");
      bubble.className = [
        "w-full max-w-[72%] rounded-[1.85rem] px-5.5 py-5 sm:max-w-[68%] sm:px-6 sm:py-5.5",
        message.role === "user" ? "bubble-user text-slate-950" : "bubble-ai text-slate-100"
      ].join(" ");
      bubble.innerHTML = `
        <div class="mb-1 flex items-center justify-between gap-3">
          <div class="text-[11px] uppercase tracking-[0.28em] ${message.role === "user" ? "text-slate-950/70" : "text-slate-400"}">
            ${message.role === "user" ? "你" : "助手"}
          </div>
          <div class="text-[11px] ${message.role === "user" ? "text-slate-950/60" : "text-slate-500"}">${escapeHtml(message.created_at || message.time || nowTime())}</div>
        </div>
        <p class="whitespace-pre-wrap text-[17px] leading-[2.05] sm:text-[18px] sm:leading-[2.05]">${displayText(message.content || message.text || "")}</p>
      `;
      wrapper.appendChild(bubble);
      el.appendChild(wrapper);
      if (message.role === "user") {
        state.chatTranscriptDirty = true;
      }
      scrollChatBottom();
    }

    function renderTranscript(messages) {
      const el = document.getElementById("chatTranscript");
      el.innerHTML = "";
      if (!messages || !messages.length) {
        el.innerHTML = `
          <div class="bubble-enter flex justify-start">
            <div class="bubble-ai w-full max-w-[68%] rounded-[1.6rem] px-5 py-5 text-left text-slate-100 sm:max-w-[62%]">
              <div class="mb-2 text-[11px] uppercase tracking-[0.28em] text-slate-400">助手</div>
              <div class="text-sm leading-7 text-slate-200">你可以先告诉我想去哪儿、几天、偏好什么，我来帮你开始规划。</div>
            </div>
          </div>`;
        return;
      }
      messages.forEach((message) => {
        const wrapper = document.createElement("div");
        wrapper.className = `bubble-enter flex ${message.role === "user" ? "justify-end" : "justify-start"}`;
        const bubble = document.createElement("div");
        bubble.className = [
          "w-full max-w-[72%] rounded-[1.85rem] px-5.5 py-5 sm:max-w-[68%] sm:px-6 sm:py-5.5",
          message.role === "user" ? "bubble-user text-slate-950" : "bubble-ai text-slate-100"
        ].join(" ");
        bubble.innerHTML = `
          <div class="mb-1 flex items-center justify-between gap-3">
            <div class="text-[11px] uppercase tracking-[0.28em] ${message.role === "user" ? "text-slate-950/70" : "text-slate-400"}">
              ${message.role === "user" ? "你" : "助手"}
            </div>
            <div class="text-[11px] ${message.role === "user" ? "text-slate-950/60" : "text-slate-500"}">${escapeHtml(message.created_at || message.time || nowTime())}</div>
          </div>
          <p class="whitespace-pre-wrap text-[17px] leading-[2.05] sm:text-[18px] sm:leading-[2.05]">${displayText(message.content || message.text || "")}</p>
        `;
        wrapper.appendChild(bubble);
        el.appendChild(wrapper);
      });
      state.chatTranscriptDirty = false;
      scrollChatBottom();
    }

    function showTyping(show) {
      const el = document.getElementById("chatTranscript");
      document.getElementById("typingBubble")?.remove();
      if (show) {
        el.insertAdjacentHTML("beforeend", `
          <div id="typingBubble" class="bubble-enter flex justify-start">
            <div class="bubble-ai flex w-full max-w-[74%] items-center gap-3 rounded-[1.85rem] px-5.5 py-5 sm:max-w-[70%] sm:px-6 sm:py-5.5">
              <div class="flex h-10 w-10 items-center justify-center rounded-full bg-white/7">
                <span class="text-xs font-semibold text-[color:var(--accent)]">AI</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
              </div>
            </div>
          </div>`);
        scrollChatBottom();
      }
    }

    function renderRecommendations(bundle) {
      const container = document.getElementById("recommendations");
      const grid = document.getElementById("cardGrid");
      const items = flattenItineraryItems(bundle).slice(0, 4);
      if (!items.length) {
        container.classList.add("hidden");
        grid.innerHTML = "";
        return;
      }
      container.classList.remove("hidden");
      grid.innerHTML = "";
      items.forEach((item, index) => {
        const el = document.createElement("article");
        el.className = "recommend-card card-enter cursor-pointer overflow-hidden rounded-[1.4rem] border border-white/10 bg-white/5";
        el.style.animationDelay = `${index * 90}ms`;
        el.innerHTML = `
          <div class="p-4">
            <div class="title-font text-lg font-semibold text-slate-100">${displayText(item.name)}</div>
            <div class="mt-1 text-xs text-slate-500">${displayText(item.category || "")} · ${displayText(item.timeSlot || "")}</div>
            <div class="flex flex-wrap gap-2">
              <span class="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300">${displayText(item.category || "")}</span>
              <span class="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300">Day ${item.day}</span>
              <span class="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300">${displayText(item.timeSlot || "")}</span>
            </div>
          </div>
        `;
        el.addEventListener("click", () => sendMessage(buildRelocationPrompt(item)));
        grid.appendChild(el);
      });
    }

    function renderItinerary(bundle) {
      const summary = document.getElementById("itinerarySummary");
      const dayList = document.getElementById("dayList");
      const routeList = document.getElementById("routeList");
      const itinerary = bundle?.itinerary?.itinerary || bundle?.itinerary || null;
      const days = itinerary?.days || [];
      if (!days.length) {
        summary.classList.add("hidden");
        summary.innerHTML = "";
        dayList.innerHTML = "";
        routeList.innerHTML = "";
        return;
      }

      const title = bundle?.itinerary?.title || "旅行草案";
      const subtitle = bundle?.itinerary?.summary || "";
      summary.classList.remove("hidden");
      summary.innerHTML = `
        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="text-xs uppercase tracking-[0.28em] text-slate-500">Latest itinerary</div>
            <h3 class="mt-2 title-font text-2xl text-slate-100">${escapeHtml(title)}</h3>
            <p class="mt-2 max-w-2xl text-sm leading-6 text-slate-400">${escapeHtml(subtitle)}</p>
          </div>
          <div class="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-right">
            <div class="text-xs text-slate-500">Generator</div>
            <div class="mt-1 text-sm font-medium text-slate-200">${escapeHtml(bundle?.action || "planner")}</div>
          </div>
        </div>
      `;

      dayList.innerHTML = days.map((day) => `
        <article class="rounded-[1.4rem] border border-white/10 bg-white/5 p-4">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-xs uppercase tracking-[0.28em] text-slate-500">Day ${day.day}</div>
              <div class="mt-1 text-lg font-semibold text-slate-100">${escapeHtml(day.theme || "行程日")}</div>
            </div>
            <div class="text-xs text-slate-500">${(day.items || []).length} stops</div>
          </div>
          <div class="mt-4 grid gap-3">
            ${(day.items || []).map((item) => `
              <div class="flex items-start justify-between gap-3 rounded-2xl border border-white/8 bg-slate-950/35 p-3">
                <div>
                  <div class="text-sm font-medium text-slate-100">${escapeHtml(item.name)}</div>
                  <div class="mt-1 text-xs text-slate-500">${escapeHtml(item.category || "")} · ${escapeHtml(item.timeSlot || "")} · ${escapeHtml(item.source || "")}</div>
                </div>
                <div class="rounded-full bg-[color:var(--accent-soft)] px-2.5 py-1 text-[11px] text-[color:var(--accent)]">${item.durationMinutes || 0} min</div>
              </div>
            `).join("")}
          </div>
        </article>
      `).join("");

      const routes = bundle?.routeSegments || bundle?.itinerary?.routeSegments || [];
      routeList.innerHTML = routes.length ? `
        <div class="rounded-[1.4rem] border border-white/10 bg-white/5 p-4">
          <div class="text-sm font-medium text-slate-200">路线片段</div>
          <div class="mt-3 space-y-2">
            ${routes.map((seg, index) => `
              <div class="flex items-center justify-between rounded-2xl border border-white/8 bg-slate-950/35 px-3 py-2 text-xs text-slate-400">
                <span>${index + 1}. ${escapeHtml(seg.fromPlaceId)} → ${escapeHtml(seg.toPlaceId)}</span>
                <span>${seg.distanceMeters ?? "-"} m</span>
              </div>
            `).join("")}
          </div>
        </div>` : "";
    }

    function renderDebug(bundle) {
      document.getElementById("debugJson").textContent = JSON.stringify(bundle || {}, null, 2);
      const queryTaskList = document.getElementById("queryTaskList");
      const tasks = bundle?.queryTasks || bundle?.candidate_pool?.queryTasks || [];
      queryTaskList.innerHTML = tasks.length ? tasks.map((task) => `
        <div class="rounded-2xl border border-white/10 bg-slate-950/35 px-3 py-2">
          <div class="flex items-center justify-between gap-3">
            <div class="text-xs font-medium text-slate-200">${escapeHtml(task.tool || "")} · ${escapeHtml(task.keyword || "")}</div>
            <div class="text-[11px] text-slate-500">${escapeHtml(task.status || "pending")}</div>
          </div>
          <div class="mt-1 text-[11px] text-slate-500">${escapeHtml(task.category || "")} · ${escapeHtml(task.sourceInterest || "")}</div>
        </div>
      `).join("") : '<div class="text-xs text-slate-500">暂无查询任务。</div>';
    }

    function clearMap() {
      if (!state.map) return;
      if (state.mapInfoWindow && typeof state.mapInfoWindow.close === "function") {
        try {
          state.mapInfoWindow.close();
        } catch (error) {
          console.warn("map info window close failed", error);
        }
      }
      state.map.clearMap();
      if (typeof state.map.destroy === "function") {
        try {
          state.map.destroy();
        } catch (error) {
          console.warn("map destroy failed", error);
        }
      }
      state.map = null;
      state.mapInfoWindow = null;
      state.mapMarkers = [];
      state.mapPolylines = [];
    }

    function getSearchOverlayResults() {
      return Array.isArray(state.mapSearchResults) ? state.mapSearchResults : [];
    }

    function renderFallbackMap(bundle) {
      const canvas = document.getElementById("mapCanvas");
      const markers = bundle?.mapData?.markers || bundle?.itinerary?.mapData?.markers || [];
      canvas.innerHTML = markers.length ? `
        <div class="grid h-full grid-cols-2 gap-3 overflow-auto p-3 sm:grid-cols-3">
          ${markers.map((marker) => `
            <div class="rounded-2xl border border-white/10 bg-white/5 p-3">
              <div class="text-sm font-medium text-slate-100">${escapeHtml(marker.name)}</div>
              <div class="mt-1 text-xs text-slate-500">${escapeHtml(marker.category || "")} · Day ${marker.day}</div>
            </div>
          `).join("")}
        </div>` : '<div class="flex h-full items-center justify-center text-sm text-slate-500">暂无地图数据。</div>';
    }

    function syncMapModeLabel() {
      const btn = document.getElementById("mapModeBtn");
      btn.textContent = state.map3D ? "3D" : "2D";
    }

    function applyMapMode() {
      if (!state.map) return;
      if (state.map3D) {
        state.map.setPitch(60);
        state.map.setRotation(12);
      } else {
        state.map.setPitch(0);
        state.map.setRotation(0);
      }
      syncMapModeLabel();
    }

    function renderMap(bundle) {
      const status = document.getElementById("mapStatus");
      const markers = bundle?.mapData?.markers || bundle?.itinerary?.mapData?.markers || [];
      if (!state.mapConfig?.enabled || !window.AMap) {
        status.textContent = "未检测到高德地图密钥，已切换到地图预览模式。";
        renderFallbackMap(bundle);
        return;
      }

      status.textContent = `高德地图已加载，共 ${markers.length} 个标记点。`;
      const canvas = document.getElementById("mapCanvas");
      canvas.innerHTML = "";
      clearMap();
      state.map = new AMap.Map("mapCanvas", {
        viewMode: state.map3D ? "3D" : "2D",
        zoom: 11,
        center: markers[0]?.location
          ? [markers[0].location.lng, markers[0].location.lat]
          : (state.mapConfig.defaultCenter || [104.679127, 31.467673]),
        pitch: state.map3D ? 60 : 0
      });

      markers.forEach((marker) => {
        const point = new AMap.Marker({
          position: [marker.location.lng, marker.location.lat],
          title: marker.name,
          label: { content: marker.name, direction: "top" }
        });
        point.setMap(state.map);
        state.mapMarkers.push(point);
      });

      const polylines = bundle?.mapData?.polylines || bundle?.itinerary?.mapData?.polylines || [];
      polylines.forEach((poly) => {
        if (!poly.polyline || !poly.polyline.length) return;
        const line = new AMap.Polyline({
          path: poly.polyline.map((p) => [p.lng, p.lat]),
          strokeColor: "#f59e0b",
          strokeWeight: 4,
          strokeOpacity: 0.86
        });
        line.setMap(state.map);
        state.mapPolylines.push(line);
      });

      if (markers.length) {
        state.map.setFitView();
      }
      syncMapModeLabel();
      applyMapMode();
    }

    function renderResolvedPlaces(bundle) {
      const el = document.getElementById("resolvedPlacesList");
      const items = flattenItineraryItems(bundle).slice(0, 6);
      el.innerHTML = items.length ? items.map((item, index) => `
        <div class="rounded-2xl border border-white/10 bg-slate-950/35 p-3">
          <div class="flex items-start gap-3">
            <img src="https://picsum.photos/seed/${encodeURIComponent(item.name)}-${index}/160/120" alt="${escapeHtml(item.name)}" class="h-16 w-20 rounded-xl object-cover" loading="lazy" />
            <div class="min-w-0 flex-1">
              <div class="text-sm font-medium text-slate-100">${escapeHtml(item.name)}</div>
              <div class="mt-1 text-[11px] text-slate-500">${escapeHtml(item.category || "")} · ${escapeHtml(item.timeSlot || "")}</div>
              <div class="mt-2 flex flex-wrap gap-2">
                <span class="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-slate-300">Day ${item.day}</span>
                <span class="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-slate-300">${escapeHtml(item.source || "")}</span>
              </div>
            </div>
          </div>
        </div>
      `).join("") : '<div class="text-xs text-slate-500">暂无地点。</div>';
    }

    function renderMapDayTabs(bundle) {
      const el = document.getElementById("mapDayTabs");
      const days = getItineraryDays(bundle);
      if (!days.length) {
        el.innerHTML = "";
        state.activeMapDay = null;
        return null;
      }
      const activeDay = resolveActiveMapDay(bundle);
      el.innerHTML = days.map((day) => `
        <button class="day-tab rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs text-slate-300" data-day="${day.day}" aria-selected="${Number(day.day) === Number(activeDay) ? "true" : "false"}">
          第 ${day.day} 天
        </button>
      `).join("");
      el.querySelectorAll("[data-day]").forEach((button) => {
        button.addEventListener("click", () => setActiveMapDayClean(Number(button.dataset.day), bundle));
      });
      return activeDay;
    }

    function renderItineraryV2(bundle) {
      const summary = document.getElementById("itinerarySummary");
      const dayList = document.getElementById("dayList");
      const routeList = document.getElementById("routeList");
      const days = getItineraryDays(bundle);
      if (!days.length) {
        summary.classList.add("hidden");
        summary.innerHTML = "";
        dayList.innerHTML = "";
        routeList.innerHTML = "";
        return;
      }

      const activeDay = resolveActiveMapDay(bundle);
      const title = bundle?.itinerary?.title || "旅行草案";
      const subtitle = bundle?.itinerary?.summary || "";
      summary.classList.remove("hidden");
      summary.innerHTML = `
        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="text-xs uppercase tracking-[0.28em] text-slate-500">Latest itinerary</div>
            <h3 class="mt-2 title-font text-2xl text-slate-100">${displayText(title)}</h3>
            <p class="mt-2 max-w-2xl text-sm leading-6 text-slate-400">${displayText(subtitle)}</p>
          </div>
          <div class="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-right">
            <div class="text-xs text-slate-500">Generator</div>
            <div class="mt-1 text-sm font-medium text-slate-200">${displayText(bundle?.action || "planner")}</div>
          </div>
        </div>
      `;

      dayList.innerHTML = days.map((day) => {
        const items = Array.isArray(day.items) ? day.items : [];
        const isActive = Number(day.day) === Number(activeDay);
        return `
          <article class="rounded-[1.4rem] border ${isActive ? "border-[color:var(--accent)]/45 bg-white/8 shadow-[0_18px_40px_rgba(245,158,11,0.08)]" : "border-white/10 bg-white/5"} p-4">
            <div class="flex items-center justify-between gap-3">
              <div>
                <div class="text-xs uppercase tracking-[0.28em] text-slate-500">Day ${day.day}</div>
                <div class="mt-1 text-lg font-semibold text-slate-100">${displayText(day.theme || "行程日")}</div>
              </div>
              <div class="text-xs text-slate-500">${items.length} stops</div>
            </div>
            <div class="mt-4 grid gap-3">
              ${items.map((item, index) => {
                const previousItem = index > 0 ? items[index - 1] : null;
                const distanceMeters = index === 0
                  ? getStartDistanceForItem(item, index)
                  : previousItem
                    ? getRouteDistanceBetween(bundle, day.day, getItemId(previousItem), getItemId(item))
                    : null;
                const distanceLabel = index === 0
                  ? "起点到这里"
                  : "距离上一个点";
                const isActiveItem = String(getItemId(item) || "") === String(state.activePlaceId || "");
                const itemCardClass = isActiveItem
                  ? "rounded-2xl border border-white/14 bg-white/[0.06] p-3 scroll-mt-24 transition-colors duration-200"
                  : "rounded-2xl border border-white/8 bg-slate-950/35 p-3 scroll-mt-24 transition-colors duration-200";
                const numberClass = isActiveItem
                  ? "flex h-8 w-8 items-center justify-center rounded-full border border-[color:var(--accent)]/25 bg-[color:var(--accent-soft)] text-xs font-semibold text-[color:var(--accent)]"
                  : "flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-white/5 text-xs font-semibold text-slate-200";
                const titleClass = isActiveItem ? "text-sm font-medium text-white" : "text-sm font-medium text-slate-100";
                return `
                  <div data-place-id="${escapeAttribute(getItemId(item))}" class="${itemCardClass}">
                    <div class="flex gap-3">
                      <div class="flex flex-col items-center pt-1">
                        <div class="${numberClass}">${index + 1}</div>
                        ${index < items.length - 1 ? '<div class="mt-2 h-full w-px bg-white/10"></div>' : ''}
                      </div>
                      <div class="min-w-0 flex-1">
                        <div class="flex items-start justify-between gap-3">
                          <div class="min-w-0">
                            <div class="${titleClass}">${displayText(item.name)}</div>
                            <div class="mt-1 text-xs text-slate-500">${displayText(item.category || "")} · ${displayText(item.timeSlot || "")} · ${displayText(item.source || "")}</div>
                          </div>
                          <div class="rounded-full bg-[color:var(--accent-soft)] px-2.5 py-1 text-[11px] text-[color:var(--accent)]">${item.durationMinutes || 0} min</div>
                        </div>
                        <div class="mt-2 text-[11px] text-slate-400">
                          ${distanceMeters === null ? "起点" : `${distanceLabel} ${formatDistance(distanceMeters)}`}
                        </div>
                      </div>
                    </div>
                  </div>
                `;
              }).join("")}
            </div>
          </article>
        `;
      }).join("");

      const routes = getDayRouteSegments(bundle, activeDay);
      routeList.innerHTML = routes.length ? `
        <div class="rounded-[1.4rem] border border-white/10 bg-white/5 p-4">
          <div class="text-sm font-medium text-slate-200">Day ${activeDay} 路线</div>
          <div class="mt-3 space-y-2">
            ${routes.map((seg, index) => `
              <div class="flex items-center justify-between rounded-2xl border border-white/8 bg-slate-950/35 px-3 py-2 text-xs text-slate-400">
                <span>${index + 1}. ${displayText(seg.fromPlaceId)} → ${displayText(seg.toPlaceId)}</span>
                <span>${formatDistance(seg.distanceMeters)}</span>
              </div>
            `).join("")}
          </div>
        </div>` : "";
    }

    function renderFallbackMapV2(bundle) {
      const canvas = document.getElementById("mapCanvas");
      const activeDay = resolveActiveMapDay(bundle);
      const markers = activeDay ? getDayMarkers(bundle, activeDay) : getMapMarkers(bundle);
      const routes = activeDay ? getDayRouteSegments(bundle, activeDay) : getRouteSegments(bundle);
      canvas.innerHTML = markers.length ? `
        <div class="flex h-full flex-col gap-3 overflow-auto p-3">
          <div class="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-400">
            ${activeDay ? `Day ${activeDay} 预览` : "全部路线预览"}
          </div>
          <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
            ${markers.map((marker) => `
              <div class="rounded-2xl border border-white/10 bg-white/5 p-3">
                <div class="flex items-center gap-2">
                  <div class="flex h-7 w-7 items-center justify-center rounded-full bg-[color:var(--accent)] text-[11px] font-semibold text-slate-950">${marker.order || 0}</div>
                  <div class="text-sm font-medium text-slate-100">${displayText(marker.name)}</div>
                </div>
                <div class="mt-2 text-xs text-slate-500">${displayText(marker.category || "")} · Day ${marker.day}</div>
              </div>
            `).join("")}
          </div>
          ${routes.length ? `
            <div class="rounded-2xl border border-white/10 bg-slate-950/35 p-3 text-xs text-slate-400">
              路线段数：${routes.length}，总里程：${formatDistance(routes.reduce((sum, seg) => sum + (Number.isFinite(seg.distanceMeters) ? seg.distanceMeters : 0), 0))}
            </div>
          ` : ""}
        </div>` : '<div class="flex h-full items-center justify-center text-sm text-slate-500">暂无地图数据。</div>';
    }

    function renderMapV2LegacyOld(bundle) {
      const status = document.getElementById("mapStatus");
      const activeDay = resolveActiveMapDay(bundle);
      const markers = activeDay ? getDayMarkers(bundle, activeDay) : getMapMarkers(bundle);
      const routes = activeDay ? getDayRouteSegments(bundle, activeDay) : getRouteSegments(bundle);
      renderMapDayTabs(bundle);

      if (!state.mapConfig?.enabled || !window.AMap) {
        status.textContent = "未检测到高德地图密钥，已切换到地图预览模式。";
        renderFallbackMapV2(bundle);
        const canvas = document.getElementById("mapCanvas");
        if (canvas) {
          const reason = getMapUnavailableReason();
          canvas.insertAdjacentHTML("afterbegin", `
            <div class="mb-3 rounded-2xl border border-amber-400/20 bg-amber-400/10 px-4 py-3 text-xs text-amber-50">
              <div class="font-medium">Map not loaded</div>
              <div class="mt-1 leading-6">${escapeHtml(reason)}</div>
            </div>`);
        }
        return;
      }

      status.textContent = activeDay
        ? `高德地图已加载，当前显示第 ${activeDay} 天，共 ${markers.length} 个点。`
        : `高德地图已加载，共 ${markers.length} 个标记点。`;
      const canvas = document.getElementById("mapCanvas");
      canvas.innerHTML = "";
      clearMap();
      state.map = new AMap.Map("mapCanvas", {
        viewMode: state.map3D ? "3D" : "2D",
        zoom: 11,
        center: markers[0]?.location
          ? [markers[0].location.lng, markers[0].location.lat]
          : (state.mapConfig.defaultCenter || [104.679127, 31.467673]),
        pitch: state.map3D ? 60 : 0
      });

      markers.forEach((marker, index) => {
        const point = new AMap.Marker({
          position: [marker.location.lng, marker.location.lat],
          title: marker.name,
          extData: { overviewType: "route" },
          content: `
            <div style="
              width: 30px;
              height: 30px;
              border-radius: 999px;
              display: flex;
              align-items: center;
              justify-content: center;
              background: rgba(245,158,11,0.96);
              border: 1px solid rgba(255,255,255,0.5);
              color: #0f172a;
              font-size: 12px;
              font-weight: 700;
              box-shadow: 0 12px 24px rgba(245,158,11,0.28);
            ">${marker.order || index + 1}</div>`,
          offset: new AMap.Pixel(-15, -15)
        });
        point.setMap(state.map);
        state.mapMarkers.push(point);
      });

      routes.forEach((poly) => {
        if (!poly.polyline || !poly.polyline.length) return;
        const line = new AMap.Polyline({
          path: poly.polyline.map((p) => [p.lng, p.lat]),
          strokeColor: "#f59e0b",
          strokeWeight: 4,
          strokeOpacity: 0.86
        });
        line.setMap(state.map);
        state.mapPolylines.push(line);
      });

      if (markers.length) {
        state.map.setFitView();
      }
      syncMapModeLabel();
      applyMapMode();
    }

    function renderResolvedPlacesV2LegacyOld(bundle) {
      const el = document.getElementById("resolvedPlacesList");
      const items = flattenItineraryItems(bundle).slice(0, 6);
      el.innerHTML = items.length ? items.map((item) => `
        <div class="rounded-2xl border border-white/10 bg-slate-950/35 p-3">
          <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/5 text-xs font-semibold text-slate-200">${item.day}</div>
            <div class="min-w-0 flex-1">
              <div class="text-sm font-medium text-slate-100">${displayText(item.name)}</div>
              <div class="mt-1 text-[11px] text-slate-500">${displayText(item.category || "")} · ${displayText(item.timeSlot || "")}</div>
              <div class="mt-2 flex flex-wrap gap-2">
                <span class="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-slate-300">Day ${item.day}</span>
                <span class="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-slate-300">${displayText(item.source || "")}</span>
              </div>
            </div>
          </div>
        </div>
      `).join("") : '<div class="text-xs text-slate-500">暂无地点。</div>';
    }

    function renderResolvedPlacesV2Legacy(bundle) {
      const el = document.getElementById("resolvedPlacesList");
      const activeDay = resolveActiveMapDay(bundle);
      const items = activeDay ? getDayMarkers(bundle, activeDay) : [];
      el.innerHTML = items.length ? `
        <div class="mb-2 flex items-center justify-between">
          <div class="text-sm font-medium text-slate-200">Day ${activeDay} · 地图下方地点</div>
          <div class="text-xs text-slate-500">点击地图编号会联动这里</div>
        </div>
        <div class="grid gap-2 sm:grid-cols-2">
          ${items.map((item, index) => {
            const active = String(item.id || "") === String(state.activePlaceId || "");
            return `
              <button data-place-id="${escapeAttribute(item.id)}" class="text-left rounded-2xl border ${active ? "border-[color:var(--accent)]/50 bg-white/8" : "border-white/10 bg-slate-950/35"} p-3 transition hover:border-[color:var(--accent)]/35">
                <div class="flex items-start gap-3">
                  <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[color:var(--accent)] text-[11px] font-semibold text-slate-950">${item.order || 0}</div>
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center justify-between gap-2">
                      <div class="text-sm font-medium text-slate-100">${displayText(item.name)}</div>
                      <div class="text-[10px] text-slate-500">Day ${item.day}</div>
                    </div>
                    <div class="mt-1 text-[11px] text-slate-500">${displayText(item.category || "")} · ${displayText(item.timeSlot || "")}</div>
                    <div class="mt-2 flex flex-wrap gap-2">
                      <span class="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-slate-300">${displayText(item.source || "")}</span>
                      ${item.role ? `<span class="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-slate-300">${displayText(item.role)}</span>` : ""}
                    </div>
                  </div>
                </div>
              </button>
            `;
          }).join("")}
        </div>
      ` : '<div class="text-xs text-slate-500">暂无结果</div>';
      el.querySelectorAll("[data-place-id]").forEach((button) => {
        button.addEventListener("click", () => setActivePlace(button.dataset.placeId, bundle));
      });
    }

    function renderMapV2Legacy(bundle) {
      const status = document.getElementById("mapStatus");
      const activeDay = resolveActiveMapDay(bundle);
      const markers = activeDay ? getDayMarkers(bundle, activeDay) : getMapMarkers(bundle);
      const routes = activeDay ? getDayRouteSegments(bundle, activeDay) : getRouteSegments(bundle);
      const searchResults = getSearchOverlayResults();
      renderMapDayTabs(bundle);

      if (!state.mapConfig?.enabled || !window.AMap) {
        status.textContent = activeDay
          ? `Day ${activeDay} 地图未加载，显示地点列表 ${markers.length} 个`
          : `地图未加载，显示地点列表 ${markers.length} 个`;
        renderFallbackMapV2(bundle);
        return;
      }

      status.textContent = activeDay
        ? `Day ${activeDay} · 地点 ${markers.length} 个`
        : `共 ${markers.length} 个地点`;
      const canvas = document.getElementById("mapCanvas");
      canvas.innerHTML = "";
      clearMap();
      state.map = new AMap.Map("mapCanvas", {
        viewMode: state.map3D ? "3D" : "2D",
        zoom: 11,
        center: markers[0]?.location
          ? [markers[0].location.lng, markers[0].location.lat]
          : (state.mapConfig.defaultCenter || [104.679127, 31.467673]),
        pitch: state.map3D ? 60 : 0
      });

      markers.forEach((marker, index) => {
        const point = new AMap.Marker({
          position: [marker.location.lng, marker.location.lat],
          title: marker.name,
          extData: { overviewType: "route" },
          content: `
            <div style="
              width: 30px;
              height: 30px;
              border-radius: 999px;
              display: flex;
              align-items: center;
              justify-content: center;
              background: rgba(245,158,11,0.96);
              border: 1px solid rgba(255,255,255,0.5);
              color: #0f172a;
              font-size: 12px;
              font-weight: 700;
              box-shadow: 0 12px 24px rgba(245,158,11,0.28);
            ">${marker.order || index + 1}</div>`,
          offset: new AMap.Pixel(-15, -15)
        });
        point.setMap(state.map);
        point.on("click", () => {
          setActivePlace(marker.id, bundle);
        });
        state.mapMarkers.push(point);
      });

      routes.forEach((poly) => {
        if (!poly.polyline || !poly.polyline.length) return;
        const line = new AMap.Polyline({
          path: poly.polyline.map((p) => [p.lng, p.lat]),
          strokeColor: "#f59e0b",
          strokeWeight: 4,
          strokeOpacity: 0.86
        });
        line.setMap(state.map);
        state.mapPolylines.push(line);
      });

      searchResults.forEach((item, index) => {
        if (!item?.location) return;
        const point = new AMap.Marker({
          position: [item.location.lng, item.location.lat],
          title: item.name,
          extData: { overviewType: "search" },
          content: `
            <div style="
              min-width: 28px;
              height: 28px;
              padding: 0 8px;
              border-radius: 999px;
              display: flex;
              align-items: center;
              justify-content: center;
              background: rgba(59,130,246,0.96);
              border: 1px solid rgba(255,255,255,0.55);
              color: white;
              font-size: 11px;
              font-weight: 700;
              box-shadow: 0 10px 22px rgba(59,130,246,0.28);
            ">S${index + 1}</div>`,
          offset: new AMap.Pixel(-16, -16)
        });
        point.setMap(state.map);
        point.on("click", () => {
          if (!state.mapInfoWindow && typeof AMap.InfoWindow === "function") {
            state.mapInfoWindow = new AMap.InfoWindow({
              offset: new AMap.Pixel(0, -24),
              closeWhenClickMap: true
            });
          }
          if (state.mapInfoWindow) {
            state.mapInfoWindow.setContent(`
              <div style="padding:10px 12px; min-width:180px;">
                <div style="font-size:12px; font-weight:700; color:#0f172a; margin-bottom:4px;">${escapeHtml(item.name || "")}</div>
                <div style="font-size:11px; color:#475569;">${escapeHtml(item.category || "poi")} · ${escapeHtml(item.district || item.city || "")}</div>
                <div style="font-size:11px; color:#64748b; margin-top:4px;">${escapeHtml(item.address || "")}</div>
              </div>
            `);
            state.mapInfoWindow.open(state.map, point.getPosition());
          }
        });
        state.mapMarkers.push(point);
      });

      if (markers.length || searchResults.length) {
        state.map.setFitView();
      }
      syncMapModeLabel();
      applyMapMode();
    }

    function setActiveMapDayLegacy(day, bundle = state.itineraryBundle) {
      state.activeMapDay = Number(day);
      state.activePlaceId = null;
      renderMapDayTabs(bundle);
      renderItineraryV2(bundle);
      renderMapV2Clean(bundle);
      renderResolvedPlacesV2Clean(bundle);
    }

    function refreshPanelsLegacy(bundle) {
      renderMapDayTabs(bundle);
      renderItineraryV2(bundle);
      renderDebug(bundle);
      renderMapV2Clean(bundle);
      renderResolvedPlacesV2Clean(bundle);
      renderRecommendations(bundle);
    }

    function renderResolvedPlacesV2Clean(bundle) {
      const el = document.getElementById("resolvedPlacesList");
      const activeDay = resolveActiveMapDay(bundle);
      const items = activeDay ? getDayMarkers(bundle, activeDay) : [];
      if (!el) return;

      if (!items.length) {
        el.innerHTML = '<div class="text-xs text-slate-500">当前天还没有可显示的地点。</div>';
        return;
      }

      el.innerHTML = `
        <div class="mb-2 flex items-center justify-between">
          <div class="text-sm font-medium text-slate-200">Day ${activeDay} 地点</div>
          <div class="text-xs text-slate-500">点击卡片可定位到对应编号</div>
        </div>
        <div class="grid gap-2 sm:grid-cols-2">
          ${items.map((item, index) => {
            const active = String(item.id || "") === String(state.activePlaceId || "");
            return `
              <button
                type="button"
                data-place-id="${escapeAttribute(item.id)}"
                class="text-left rounded-2xl border ${active ? "border-[color:var(--accent)]/60 bg-white/10" : "border-white/10 bg-slate-950/35"} p-3 transition hover:border-[color:var(--accent)]/40"
              >
                <div class="flex items-start gap-3">
                  <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[color:var(--accent)] text-[11px] font-semibold text-slate-950">
                    ${item.order || index + 1}
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center justify-between gap-2">
                      <div class="min-w-0 text-sm font-medium text-slate-100">${displayText(item.name)}</div>
                      <div class="text-[10px] text-slate-500">Day ${item.day}</div>
                    </div>
                    <div class="mt-1 text-[11px] text-slate-500">${displayText(item.category || "")} · ${displayText(item.timeSlot || "")}</div>
                    <div class="mt-2 flex flex-wrap gap-2">
                      <span class="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-slate-300">${displayText(item.source || "")}</span>
                      ${item.role ? `<span class="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-slate-300">${displayText(item.role)}</span>` : ""}
                    </div>
                  </div>
                </div>
              </button>
            `;
          }).join("")}
        </div>
      `;

      el.querySelectorAll("[data-place-id]").forEach((button) => {
        button.addEventListener("click", () => setActivePlace(button.dataset.placeId, bundle));
      });
    }

    function renderMapV2Clean(bundle) {
      const status = document.getElementById("mapStatus");
      const activeDay = resolveActiveMapDay(bundle);
      const markers = activeDay ? getDayMarkers(bundle, activeDay) : getMapMarkers(bundle);
      const routes = activeDay ? getDayRouteSegments(bundle, activeDay) : getRouteSegments(bundle);
      const searchResults = getSearchOverlayResults();
      const hasRouteOverview = Boolean(bundle && (markers.length || routes.length));
      const shouldFocusUserLocation = Boolean(state.userLocation && !state.activePlaceId && !hasRouteOverview);
      const shouldShowRouteOverview = Boolean(!state.activePlaceId && hasRouteOverview);
      const routeOverviewOverlays = [];
      renderMapDayTabs(bundle);

      if (!status) return;

      if (!state.mapConfig?.enabled || !window.AMap) {
        status.textContent = activeDay
          ? `Day ${activeDay} 地图未启用，显示列表模式，共 ${markers.length} 个点`
          : `地图未启用，共 ${markers.length} 个点`;
        renderFallbackMapV2(bundle);
        return;
      }

      status.textContent = activeDay
        ? `Day ${activeDay} 路线，共 ${markers.length} 个点`
        : `当前路线，共 ${markers.length} 个点`;

      const canvas = document.getElementById("mapCanvas");
      canvas.innerHTML = "";
      clearMap();

      state.map = new AMap.Map("mapCanvas", {
        viewMode: state.map3D ? "3D" : "2D",
        zoom: shouldFocusUserLocation ? 15 : 12,
        center: shouldFocusUserLocation
          ? [state.userLocation.lng, state.userLocation.lat]
          : markers[0]?.location
            ? [markers[0].location.lng, markers[0].location.lat]
            : (state.mapConfig.defaultCenter || [104.679127, 31.467673]),
        pitch: state.map3D ? 60 : 0
      });

      markers.forEach((marker, index) => {
        const isActive = String(marker.id || "") === String(state.activePlaceId || "");
        const point = new AMap.Marker({
          position: [marker.location.lng, marker.location.lat],
          title: marker.name,
          extData: { overviewType: "route" },
          content: `
            <div style="
              width: 32px;
              height: 32px;
              border-radius: 999px;
              display: flex;
              align-items: center;
              justify-content: center;
              background: ${isActive ? "rgba(16,185,129,0.96)" : "rgba(245,158,11,0.96)"};
              border: 1px solid rgba(255,255,255,0.55);
              color: #0f172a;
              font-size: 12px;
              font-weight: 700;
              box-shadow: 0 12px 24px rgba(245,158,11,0.28);
            ">${index + 1}</div>`,
          offset: new AMap.Pixel(-16, -16)
        });
        point.setMap(state.map);
        point.on("click", () => {
          setActivePlace(marker.id, bundle);
          if (state.mapInfoWindow && typeof state.mapInfoWindow.open === "function") {
            state.mapInfoWindow.setContent(`
              <div style="padding:10px 12px; min-width:160px;">
                <div style="font-size:12px; font-weight:700; color:#0f172a; margin-bottom:4px;">${escapeHtml(marker.name)}</div>
                <div style="font-size:11px; color:#475569;">第 ${index + 1} 个点 · ${escapeHtml(marker.category || "")}</div>
                <div style="font-size:11px; color:#64748b; margin-top:4px;">${escapeHtml(marker.timeSlot || "")}</div>
              </div>
            `);
            state.mapInfoWindow.open(state.map, point.getPosition());
          }
        });
        state.mapMarkers.push(point);
        routeOverviewOverlays.push(point);
      });

      if (state.userLocation) {
        const userPoint = new AMap.Marker({
          position: [state.userLocation.lng, state.userLocation.lat],
          extData: { overviewType: "user" },
          title: "我所在位置",
          content: `
            <div style="
              width: 18px;
              height: 18px;
              border-radius: 999px;
              background: rgba(59,130,246,0.95);
              border: 2px solid rgba(255,255,255,0.9);
              box-shadow: 0 8px 18px rgba(59,130,246,0.35);
            "></div>`,
          offset: new AMap.Pixel(-9, -9)
        });
        userPoint.setMap(state.map);
        state.mapMarkers.push(userPoint);
      }

      routes.forEach((poly) => {
        if (!poly.polyline || !poly.polyline.length) return;
        const line = new AMap.Polyline({
          path: poly.polyline.map((p) => [p.lng, p.lat]),
          strokeColor: "#f59e0b",
          strokeWeight: 4,
          strokeOpacity: 0.86
        });
        line.setMap(state.map);
        state.mapPolylines.push(line);
        routeOverviewOverlays.push(line);
      });

      if (shouldShowRouteOverview && typeof state.map.setFitView === "function") {
        state.map.setFitView(routeOverviewOverlays);
        if (typeof state.map.getZoom === "function" && typeof state.map.setZoom === "function") {
          const currentZoom = Number(state.map.getZoom());
          if (Number.isFinite(currentZoom) && currentZoom < 12) {
            state.map.setZoom(12);
          }
        }
      }

      searchResults.forEach((item, index) => {
        if (!item?.location) return;
        const point = new AMap.Marker({
          position: [item.location.lng, item.location.lat],
          title: item.name,
          extData: { overviewType: "search" },
          content: `
            <div style="
              min-width: 28px;
              height: 28px;
              padding: 0 8px;
              border-radius: 999px;
              display: flex;
              align-items: center;
              justify-content: center;
              background: rgba(59,130,246,0.96);
              border: 1px solid rgba(255,255,255,0.55);
              color: white;
              font-size: 11px;
              font-weight: 700;
              box-shadow: 0 10px 22px rgba(59,130,246,0.28);
            ">S${index + 1}</div>`,
          offset: new AMap.Pixel(-16, -16)
        });
        point.setMap(state.map);
        point.on("click", () => {
          if (!state.mapInfoWindow && typeof AMap.InfoWindow === "function") {
            state.mapInfoWindow = new AMap.InfoWindow({
              offset: new AMap.Pixel(0, -24),
              closeWhenClickMap: true
            });
          }
          if (state.mapInfoWindow) {
            state.mapInfoWindow.setContent(`
              <div style="padding:10px 12px; min-width:180px;">
                <div style="font-size:12px; font-weight:700; color:#0f172a; margin-bottom:4px;">${escapeHtml(item.name || "")}</div>
                <div style="font-size:11px; color:#475569;">${escapeHtml(item.category || "poi")} · ${escapeHtml(item.district || item.city || "")}</div>
                <div style="font-size:11px; color:#64748b; margin-top:4px;">${escapeHtml(item.address || "")}</div>
              </div>
            `);
            state.mapInfoWindow.open(state.map, point.getPosition());
          }
        });
        state.mapMarkers.push(point);
      });

      if (!shouldFocusUserLocation && !shouldShowRouteOverview && (markers.length || searchResults.length)) {
        state.map.setFitView();
      }
      syncMapModeLabel();
      applyMapMode();
      renderResolvedPlacesV2Clean(bundle);
    }

    function setActiveMapDayClean(day, bundle = state.itineraryBundle) {
      state.activeMapDay = Number(day);
      state.activePlaceId = null;
      renderMapDayTabs(bundle);
      renderItineraryV2(bundle);
      renderMapV2Clean(bundle);
      renderResolvedPlacesV2Clean(bundle);
    }

    function refreshPanelsClean(bundle) {
      renderMapDayTabs(bundle);
      renderItineraryV2(bundle);
      renderDebug(bundle);
      renderMapV2Clean(bundle);
      renderResolvedPlacesV2Clean(bundle);
      renderRecommendations(bundle);
    }

    async function loadMapSdk() {
      try {
        state.mapSdkError = null;
        state.mapConfig = await api("/map/config");
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
    }

    async function loadAppInfo() {
      try {
        const info = await api("/health");
        state.modelInfo = info;
        syncModelName(info);
      } catch (error) {
        console.warn("loadAppInfo failed", error);
      }
    }

    async function loadSessionData(sessionId) {
      const session = await api(`/sessions/${sessionId}`);
      const messagesResponse = await api(`/sessions/${sessionId}/messages?limit=200`);
      let requirement = null;
      if (session.latest_requirement_id) {
        try {
          requirement = await api(`/sessions/${sessionId}/requirements/latest`);
        } catch (error) {
          requirement = null;
        }
      }
      let itinerary = null;
      if (session.latest_itinerary_id) {
        try {
          itinerary = await api(`/sessions/${sessionId}/itineraries/latest`);
        } catch (error) {
          itinerary = null;
        }
      }
      state.session = session;
      state.itineraryBundle = {
        session,
        session_id: sessionId,
        messages: messagesResponse.items || [],
        requirement,
        itinerary,
        queryTasks: itinerary?.queryTasks || itinerary?.itinerary?.queryTasks || [],
        resolvedPlaces: itinerary?.resolvedPlaces || itinerary?.itinerary?.resolvedPlaces || [],
        routeSegments: itinerary?.routeSegments || itinerary?.itinerary?.routeSegments || [],
        mapData: itinerary?.mapData || itinerary?.itinerary?.mapData || null,
        candidate_pool: itinerary?.candidate_pool || itinerary?.itinerary?.candidatePool || null,
        planner_output: itinerary?.planner_output || itinerary?.itinerary?.plannerOutput || null,
        assistantMessage: itinerary?.assistantMessage || null,
        requirementInterpretation: itinerary?.requirementInterpretation || itinerary?.itinerary?.requirementInterpretation || null,
        appliedAssumptions: itinerary?.appliedAssumptions || itinerary?.itinerary?.appliedAssumptions || [],
        inspirationCandidates: itinerary?.inspirationCandidates || itinerary?.itinerary?.inspirationCandidates || [],
        selectionReasons: itinerary?.selectionReasons || itinerary?.itinerary?.selectionReasons || {},
        action: itinerary?.action || itinerary?.generator_type || null
      };
      state.activeRequirement = requirement || state.itineraryBundle?.requirement || null;
      syncSessionIds(session, state.itineraryBundle);
      document.getElementById("resumeSessionId").value = sessionId;
      document.getElementById("multimodalSessionId").value = sessionId;
      if (!state.chatTranscriptDirty) {
        renderTranscript(messagesResponse.items || []);
      }
      refreshPanelsClean(state.itineraryBundle);
      localStorage.setItem("nightAtlasSessionId", sessionId);
      renderSessionHistory();
    }

    async function createSession() {
      const title = `夜航 ${new Date().toLocaleDateString("zh-CN")}`;
      const session = await api("/sessions", {
        method: "POST",
        body: JSON.stringify({ title })
      });
      await loadSessionData(session.id);
      await loadSessionHistory();
      return session.id;
    }

    function prepareNewSession() {
      state.session = null;
      state.activeRequirement = null;
      state.itineraryBundle = null;
      state.activePlaceId = null;
      state.activeMapDay = null;
      state.chatTranscriptDirty = false;
      document.getElementById("resumeSessionId").value = "";
      document.getElementById("multimodalSessionId").value = "";
      syncSessionIds(null, null);
      renderTranscript([]);
      renderRecommendations(null);
      renderItineraryV2(null);
      renderDebug(null);
      renderMapV2Clean(null);
      renderResolvedPlacesV2Clean(null);
      localStorage.removeItem("nightAtlasSessionId");
      renderSessionHistory();
    }

    async function ensureSession() {
      const saved = localStorage.getItem("nightAtlasSessionId");
      if (saved) {
        try {
          await loadSessionData(saved);
          return saved;
        } catch (error) {
          console.warn("saved session invalid", error);
        }
      }
      prepareNewSession();
      return null;
    }

    async function sendMessage(text, options = {}) {
      const value = text.trim();
      if (!value || state.typing) return;
      const promptInput = document.getElementById("promptInput");
      const previousPromptValue = promptInput?.value ?? "";
      const shouldRestorePrompt = Boolean(promptInput && previousPromptValue.trim() === value);
      if (shouldRestorePrompt) {
        promptInput.value = "";
      }
      state.typing = true;
      appendTranscriptMessage({
        role: "user",
        content: value,
        created_at: nowTime()
      });
      showTyping(true);

      const sessionId = state.session?.id || undefined;
      try {
        const bundle = await api("/chat", {
          method: "POST",
          body: JSON.stringify({
            message: value,
            session_id: sessionId,
            conversation_context: options.context === false ? "" : getConversationContext(),
            user_location: state.userLocation || undefined
          })
        });
        state.session = bundle.session;
        state.itineraryBundle = bundle;
        state.activeRequirement = bundle.requirement || state.activeRequirement;
        syncSessionIds(bundle.session, bundle);
        document.getElementById("resumeSessionId").value = bundle.session_id;
        document.getElementById("multimodalSessionId").value = bundle.session_id;
        renderTranscript(bundle.messages || []);
        refreshPanelsClean(bundle);
        localStorage.setItem("nightAtlasSessionId", bundle.session_id);
        await loadSessionHistory();
        if (bundle.action === "planning_error") {
          showTemporaryNotice("我已经收到你的消息，但这次生成行程时出了点问题。你的消息已保留，可以稍后重试，或者换一种更简短的说法让我重新规划。", "error");
        }
      } catch (error) {
        showTemporaryNotice("消息已经发出去了，但这次生成回复失败了。你的消息已保留，可以稍后再试。", "error");
        if (shouldRestorePrompt && promptInput) {
          promptInput.value = previousPromptValue;
        }
        console.error(error);
      } finally {
        showTyping(false);
        state.typing = false;
      }
    }

    async function loadConversationFromInput() {
      const id = document.getElementById("resumeSessionId").value.trim() || document.getElementById("multimodalSessionId").value.trim();
      if (!id) return;
      await loadSessionData(id);
    }

    function getWorkbenchInput() {
      return document.getElementById("requirementInput").value.trim();
    }

    async function ensureActiveSession() {
      if (state.session?.id) return state.session.id;
      return createSession();
    }

    async function previewRequirementInterpretation() {
      const sessionId = await ensureActiveSession();
      const rawInput = getWorkbenchInput();
      if (!rawInput) return;
      setWorkbenchStatus("正在预览需求解析...");
      const result = await api(`/sessions/${sessionId}/requirements/interpret`, {
        method: "POST",
        body: JSON.stringify({ raw_input: rawInput })
      });
      document.getElementById("debugJson").textContent = JSON.stringify(result, null, 2);
      setPanel("debug");
      setWorkbenchStatus("需求解析预览完成。");
    }

    async function saveRequirement() {
      const sessionId = await ensureActiveSession();
      const rawInput = getWorkbenchInput();
      if (!rawInput) return;
      setWorkbenchStatus("正在保存需求...");
      const result = await api(`/sessions/${sessionId}/requirements`, {
        method: "POST",
        body: JSON.stringify({ raw_input: rawInput })
      });
      state.session = { ...(state.session || {}), latest_requirement_id: result.id };
      syncSessionIds(state.session, state.itineraryBundle);
      document.getElementById("debugJson").textContent = JSON.stringify(result, null, 2);
      setWorkbenchStatus("需求已保存。");
      await loadSessionData(sessionId);
      return result;
    }

    async function loadLatestRequirement() {
      const sessionId = await ensureActiveSession();
      setWorkbenchStatus("正在加载最新需求...");
      const result = await api(`/sessions/${sessionId}/requirements/latest`);
      document.getElementById("requirementInput").value = result.raw_input || "";
      document.getElementById("debugJson").textContent = JSON.stringify(result, null, 2);
      setWorkbenchStatus("最新需求已加载。");
      setPanel("debug");
    }

    async function generateItineraryFromWorkbench() {
      const sessionId = await ensureActiveSession();
      setWorkbenchStatus("正在生成行程...");
      let requirementId = state.session?.latest_requirement_id;
      if (!requirementId) {
        const rawInput = getWorkbenchInput();
        if (!rawInput) {
          setWorkbenchStatus("请先输入需求。");
          return;
        }
        const requirement = await api(`/sessions/${sessionId}/requirements`, {
          method: "POST",
          body: JSON.stringify({ raw_input: rawInput })
        });
        requirementId = requirement.id;
        await loadSessionData(sessionId);
      }
      await api(`/sessions/${sessionId}/itineraries`, {
        method: "POST",
        body: JSON.stringify({ generator_type: "planner", requirement_id: requirementId })
      });
      await loadSessionData(sessionId);
      setWorkbenchStatus("行程已生成。");
    }

    async function loadLatestItinerary() {
      const sessionId = await ensureActiveSession();
      setWorkbenchStatus("正在加载最新行程...");
      await loadSessionData(sessionId);
      setWorkbenchStatus("最新行程已加载。");
    }

    async function replanFromWorkbench() {
      const sessionId = await ensureActiveSession();
      const instruction = getWorkbenchInput() || "请基于当前行程继续优化路线";
      setWorkbenchStatus("正在重排行程...");
      await api(`/sessions/${sessionId}/replan`, {
        method: "POST",
        body: JSON.stringify({ instruction, generator_type: "planner" })
      });
      await loadSessionData(sessionId);
      setWorkbenchStatus("行程已重排。");
    }

    async function previewWebContextFromWorkbench() {
      const sessionId = await ensureActiveSession();
      const rawInput = getWorkbenchInput() || document.getElementById("promptInput").value.trim() || "旅行灵感";
      setWorkbenchStatus("正在预览网页上下文...");
      const result = await api("/tools/web-context", {
        method: "POST",
        body: JSON.stringify({ message: rawInput, session_id: sessionId })
      });
      document.getElementById("debugJson").textContent = JSON.stringify(result, null, 2);
      setPanel("debug");
      setWorkbenchStatus("网页上下文已预览。");
    }

    async function runMapSearch() {
      const keyword = document.getElementById("mapSearchInput").value.trim();
      if (!keyword || !state.session?.id) return;
      const payload = state.activeRequirement?.structured_payload || state.itineraryBundle?.requirement?.structured_payload || {};
      const destination = payload.destination || state.itineraryBundle?.requirement?.destination || "";
      const locationScope = payload.location_scope || "city_only";
      const citySource = payload.city_source || null;
      const status = document.getElementById("mapStatus");
      if (status) {
        status.textContent = `正在搜索${destination ? `${destination} ` : ""}${keyword}...`;
      }
      const res = await api("/map/search", {
        method: "POST",
        body: JSON.stringify({
          keyword,
          city: destination,
          location_scope: locationScope,
          city_source: citySource,
          user_location: state.userLocation || undefined
        })
      });
      state.mapSearchResults = Array.isArray(res.items) ? res.items : [];
      if (status) {
        status.textContent = state.mapSearchResults.length
          ? `地图搜索命中 ${state.mapSearchResults.length} 个结果`
          : "地图搜索没有找到可落点的结果";
      }
      renderMapV2Clean(state.itineraryBundle || null);
      document.getElementById("debugJson").textContent = JSON.stringify(res, null, 2);
      setPanel("debug");
    }

    document.querySelectorAll("[data-prompt]").forEach((btn) => {
      btn.addEventListener("click", () => sendMessage(btn.dataset.prompt || ""));
    });
    document.getElementById("sendBtn").addEventListener("click", () => sendMessage(document.getElementById("promptInput").value));
    document.getElementById("promptInput").addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        sendMessage(event.currentTarget.value);
      }
    });
    document.getElementById("micBtn").addEventListener("click", () => sendMessage("我想要一条适合夜景和咖啡的路线"));
    document.getElementById("newSessionBtn").addEventListener("click", prepareNewSession);
    document.getElementById("loadConversationBtn").addEventListener("click", loadConversationFromInput);
    document.getElementById("quickLoadBtn").addEventListener("click", loadConversationFromInput);
    document.getElementById("settingsBtn").addEventListener("click", () => openSettings(true));
    document.getElementById("closeSettingsBtn").addEventListener("click", () => openSettings(false));
    document.getElementById("overlay").addEventListener("click", () => openSettings(false));
    document.getElementById("mapSearchBtn").addEventListener("click", runMapSearch);
    document.getElementById("mapSearchInput").addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runMapSearch();
      }
    });
    document.getElementById("mapZoomInBtn").addEventListener("click", () => { if (state.map) state.map.zoomIn(); });
    document.getElementById("mapZoomOutBtn").addEventListener("click", () => { if (state.map) state.map.zoomOut(); });
    document.getElementById("previewRequirementBtn").addEventListener("click", previewRequirementInterpretation);
    document.getElementById("saveRequirementBtn").addEventListener("click", saveRequirement);
    document.getElementById("generateItineraryBtn").addEventListener("click", generateItineraryFromWorkbench);
    document.getElementById("replanBtn").addEventListener("click", replanFromWorkbench);
    document.getElementById("loadLatestRequirementBtn").addEventListener("click", loadLatestRequirement);
    document.getElementById("loadLatestItineraryBtn").addEventListener("click", loadLatestItinerary);
    document.getElementById("previewWebContextBtn").addEventListener("click", previewWebContextFromWorkbench);
    document.getElementById("mapModeBtn").addEventListener("click", () => {
      state.map3D = !state.map3D;
      syncMapModeLabel();
      if (state.itineraryBundle) {
        renderMapV2Clean(state.itineraryBundle);
      }
    });

    document.querySelectorAll(".theme-btn").forEach((btn) => {
      btn.addEventListener("click", () => setTheme(btn.dataset.theme));
    });
    document.querySelectorAll(".lang-btn").forEach((btn) => {
      btn.addEventListener("click", () => setLanguage(btn.dataset.lang));
    });
    document.querySelectorAll(".panel-tab").forEach((btn) => {
      btn.addEventListener("click", () => setPanel(btn.dataset.panel));
    });
    document.getElementById("motionToggle").addEventListener("click", () => {
      state.motion = !state.motion;
      document.querySelector(".motion-knob").style.transform = state.motion ? "translateX(0)" : "translateX(24px)";
      if (!state.motion) {
        document.querySelectorAll(".blob").forEach((blob) => blob.style.animation = "none");
      } else {
        document.querySelectorAll(".blob").forEach((blob) => blob.style.animation = "");
      }
    });
    document.getElementById("resumeSessionId").addEventListener("keydown", (event) => {
      if (event.key === "Enter") loadConversationFromInput();
    });
    document.getElementById("multimodalSessionId").addEventListener("keydown", (event) => {
      if (event.key === "Enter") loadConversationFromInput();
    });

    renderRecommendations = function(bundle) {
      const container = document.getElementById("recommendations");
      const grid = document.getElementById("cardGrid");
      if (!container || !grid) return;
      const items =
        bundle?.inspirationCandidates ||
        bundle?.itinerary?.inspirationCandidates ||
        bundle?.itinerary?.itinerary?.inspirationCandidates ||
        [];
      if (!items.length) {
        container.classList.add("hidden");
        grid.innerHTML = "";
        return;
      }

      const activeDay = resolveActiveMapDay(bundle) || 1;
      const activeDayItems = getItineraryDays(bundle).find((day) => Number(day.day) === Number(activeDay))?.items || [];
      const replaceTarget = activeDayItems[activeDayItems.length - 1] || null;

      container.classList.remove("hidden");
      grid.innerHTML = items.slice(0, 8).map((item, index) => {
        const reasons = Array.isArray(item.selectionReasons) ? item.selectionReasons.slice(0, 2) : [];
        return `
          <article class="recommend-card card-enter overflow-hidden rounded-[1.4rem] border border-white/10 bg-white/5 p-4" style="animation-delay:${index * 60}ms">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="text-base font-semibold text-slate-100">${displayText(item.name || "灵感地点")}</div>
                <div class="mt-1 text-xs text-slate-500">${displayText(item.category || "")} · ${displayText(item.address || "")}</div>
              </div>
              <div class="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300">Day ${displayText(item.suggestedDay || activeDay)}</div>
            </div>
            <div class="mt-3 flex flex-wrap gap-2">
              ${(reasons.length ? reasons : ["值得补充到正式行程"]).map((reason) => `
                <span class="rounded-full border border-white/10 bg-slate-950/30 px-2.5 py-1 text-[11px] text-slate-300">${displayText(reason)}</span>
              `).join("")}
            </div>
            <div class="mt-4 flex flex-wrap gap-2">
              <button type="button" data-action="add" data-name="${escapeAttribute(item.name || "")}" class="rounded-full border border-[color:var(--accent)]/30 bg-[color:var(--accent-soft)] px-3 py-1.5 text-xs text-[color:var(--accent)]">加入 Day ${activeDay}</button>
              <button type="button" data-action="replace" data-name="${escapeAttribute(item.name || "")}" data-target="${escapeAttribute(replaceTarget?.name || "")}" class="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300">替换当前点</button>
            </div>
          </article>
        `;
      }).join("");

      grid.querySelectorAll("[data-action]").forEach((button) => {
        button.addEventListener("click", () => {
          const name = button.dataset.name || "";
          if (!name) return;
          if (button.dataset.action === "replace" && button.dataset.target) {
            sendMessage(`把 Day ${activeDay} 的 ${button.dataset.target} 替换成 ${name}`);
            return;
          }
          sendMessage(`把 ${name} 加入 Day ${activeDay} 的正式行程`);
        });
      });
    };

    renderResolvedPlacesV2Clean = function() {};

    renderItineraryV2 = function(bundle) {
      const summary = document.getElementById("itinerarySummary");
      const dayList = document.getElementById("dayList");
      const routeList = document.getElementById("routeList");
      const days = getItineraryDays(bundle);
      if (!days.length) {
        summary.classList.add("hidden");
        summary.innerHTML = "";
        dayList.innerHTML = "";
        routeList.innerHTML = "";
        return;
      }

      const activeDay = resolveActiveMapDay(bundle);
      const title = bundle?.itinerary?.title || "路线草案";
      const subtitle = bundle?.itinerary?.summary || "已按天整理路线，可直接点编号定位到地图。";
      summary.classList.remove("hidden");
      summary.innerHTML = `
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div class="text-xs uppercase tracking-[0.28em] text-slate-500">Latest itinerary</div>
            <h3 class="mt-2 text-2xl font-semibold text-slate-100">${displayText(title)}</h3>
            <p class="mt-2 max-w-2xl text-sm leading-6 text-slate-400">${displayText(subtitle)}</p>
          </div>
          <div class="rounded-[1.15rem] border border-white/10 bg-white/5 px-3 py-2 text-right">
            <div class="text-xs text-slate-500">Generator</div>
            <div class="mt-1 text-sm font-medium text-slate-200">${displayText(bundle?.action || "planner")}</div>
          </div>
        </div>
      `;

      dayList.innerHTML = days.map((day) => {
        const items = Array.isArray(day.items) ? day.items : [];
        const isActiveDay = Number(day.day) === Number(activeDay);
        return `
          <article class="rounded-[1.6rem] border ${isActiveDay ? "border-[color:var(--accent)]/35 bg-white/[0.07]" : "border-white/10 bg-white/[0.04]"} p-4 sm:p-5">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div class="text-xs uppercase tracking-[0.28em] text-slate-500">Day ${day.day}</div>
                <div class="mt-1 text-xl font-semibold text-slate-100">${displayText(day.theme || "当日行程")}</div>
              </div>
              <div class="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-400">${items.length} 个安排</div>
            </div>

            <div class="mt-4 grid gap-3">
              ${items.map((item, index) => {
                const previousItem = index > 0 ? items[index - 1] : null;
                const distanceMeters = index === 0
                  ? getStartDistanceForItem(item, index)
                  : previousItem
                    ? getRouteDistanceBetween(bundle, day.day, getItemId(previousItem), getItemId(item))
                    : null;
                const isActiveItem = String(getItemId(item) || "") === String(state.activePlaceId || "");
                return `
                  <button
                    type="button"
                    data-place-id="${escapeAttribute(getItemId(item))}"
                    class="w-full text-left rounded-[1.35rem] border ${isActiveItem ? "border-[color:var(--accent)]/45 bg-white/[0.09] shadow-[0_14px_30px_rgba(243,179,79,0.08)]" : "border-white/8 bg-slate-950/35 hover:border-white/20 hover:bg-white/[0.04]"} p-4 transition-all"
                  >
                    <div class="flex gap-3">
                      <div class="flex flex-col items-center pt-1">
                        <div class="flex h-9 w-9 items-center justify-center rounded-full ${isActiveItem ? "bg-[color:var(--accent)] text-slate-950" : "bg-white/8 text-slate-100"} text-sm font-semibold">
                          ${index + 1}
                        </div>
                        ${index < items.length - 1 ? '<div class="mt-2 h-full w-px bg-white/10"></div>' : ""}
                      </div>
                      <div class="min-w-0 flex-1">
                        <div class="flex flex-wrap items-start justify-between gap-3">
                          <div class="min-w-0">
                            <div class="text-base font-semibold ${isActiveItem ? "text-white" : "text-slate-100"}">${displayText(item.name)}</div>
                            <div class="mt-1 text-xs text-slate-500">${displayText(item.category || "")} · ${displayText(item.timeSlot || "")} · ${displayText(item.source || "")}</div>
                          </div>
                          <div class="rounded-full bg-[color:var(--accent-soft)] px-2.5 py-1 text-[11px] text-[color:var(--accent)]">${item.durationMinutes || 0} min</div>
                        </div>

                        <div class="mt-3 flex flex-wrap gap-2">
                          <span class="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] text-slate-300">编号 ${index + 1}</span>
                          <span class="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] text-slate-300">点击定位</span>
                          <span class="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] text-slate-300">
                            ${distanceMeters === null ? "起点" : `距离 ${formatDistance(distanceMeters)}`}
                          </span>
                        </div>

                        ${item.address ? `
                          <div class="mt-3 text-[12px] leading-6 text-slate-400">
                            ${displayText(item.address)}
                          </div>
                        ` : ""}
                      </div>
                    </div>
                  </button>
                `;
              }).join("")}
            </div>
          </article>
        `;
      }).join("");

      dayList.querySelectorAll("[data-place-id]").forEach((button) => {
        button.addEventListener("click", () => setActivePlace(button.dataset.placeId, bundle));
      });

      const routes = getDayRouteSegments(bundle, activeDay);
      routeList.innerHTML = routes.length ? `
        <div class="rounded-[1.4rem] border border-white/10 bg-white/5 p-4">
          <div class="text-sm font-medium text-slate-200">Day ${activeDay} 转场距离</div>
          <div class="mt-3 space-y-2">
            ${routes.map((seg, index) => `
              <div class="flex items-center justify-between rounded-2xl border border-white/8 bg-slate-950/35 px-3 py-2 text-xs text-slate-400">
                <span>${index + 1}. ${displayText(seg.fromPlaceId)} → ${displayText(seg.toPlaceId)}</span>
                <span>${formatDistance(seg.distanceMeters)}</span>
              </div>
            `).join("")}
          </div>
        </div>` : "";
    };

    refreshPanelsClean = function(bundle) {
      renderMapDayTabs(bundle);
      renderItineraryV2(bundle);
      renderDebug(bundle);
      renderMapV2Clean(bundle);
    };

    focusActivePlaceOnMap = function(bundle = state.itineraryBundle) {
      if (!state.map || !state.activePlaceId) return;
      const marker = flattenItineraryItems(bundle).find((item) => String(getItemId(item)) === String(state.activePlaceId));
      if (!marker?.location) return;

      const position = [marker.location.lng, marker.location.lat];
      if (typeof state.map.setZoomAndCenter === "function") {
        state.map.setZoomAndCenter(16, position, false, 220);
      } else {
        if (typeof state.map.setZoom === "function") state.map.setZoom(16);
        if (typeof state.map.setCenter === "function") state.map.setCenter(position);
      }

      if (window.AMap) {
        if (!state.mapInfoWindow && typeof AMap.InfoWindow === "function") {
          state.mapInfoWindow = new AMap.InfoWindow({
            offset: new AMap.Pixel(0, -24),
            closeWhenClickMap: true
          });
        }
        if (state.mapInfoWindow && typeof state.mapInfoWindow.setContent === "function") {
          state.mapInfoWindow.setContent(`
            <div style="padding:10px 12px; min-width:180px;">
              <div style="font-size:12px; font-weight:700; color:#0f172a; margin-bottom:4px;">${escapeHtml(marker.name || "")}</div>
              <div style="font-size:11px; color:#475569;">${escapeHtml(marker.category || "")} · ${escapeHtml(marker.timeSlot || "")}</div>
            </div>
          `);
          if (typeof state.mapInfoWindow.open === "function") {
            state.mapInfoWindow.open(state.map, position);
          }
        }
      }
    };

    setActivePlace = function(placeId, bundle = state.itineraryBundle) {
      state.activePlaceId = String(placeId || "");
      const linkedItem = flattenItineraryItems(bundle).find((item) => String(getItemId(item)) === state.activePlaceId);
      if (linkedItem?.day) {
        state.activeMapDay = Number(linkedItem.day);
      }
      renderItineraryV2(bundle);
      renderMapV2Clean(bundle);
      focusActivePlaceOnMap(bundle);
      const target = document.querySelector(`[data-place-id="${escapeAttribute(state.activePlaceId)}"]`);
      target?.scrollIntoView({ behavior: "smooth", block: "center" });
    };

    focusDefaultPlaceOnMap = function(bundle = state.itineraryBundle) {
      if (!state.map) return;
      const activeDay = resolveActiveMapDay(bundle);
      const routeMarkers = activeDay
        ? getDayMarkers(bundle, activeDay)
        : getMapMarkers(bundle);
      const routeSegments = activeDay
        ? getDayRouteSegments(bundle, activeDay)
        : getRouteSegments(bundle);
      if ((routeMarkers.length || routeSegments.length) && typeof state.map.setFitView === "function") {
        const routeOverlays = [];
        state.mapMarkers.forEach((marker) => {
          if (marker && typeof marker.getExtData === "function" && marker.getExtData()?.overviewType === "route") {
            routeOverlays.push(marker);
          }
        });
        state.mapPolylines.forEach((polyline) => {
          if (polyline) routeOverlays.push(polyline);
        });
        state.map.setFitView(routeOverlays.length ? routeOverlays : undefined);
        if (typeof state.map.getZoom === "function" && typeof state.map.setZoom === "function") {
          const currentZoom = Number(state.map.getZoom());
          if (Number.isFinite(currentZoom) && currentZoom < 12) {
            state.map.setZoom(12);
          }
        }
        return;
      }
      if (state.userLocation) {
        const userPosition = [state.userLocation.lng, state.userLocation.lat];
        if (typeof state.map.setZoomAndCenter === "function") {
          state.map.setZoomAndCenter(15, userPosition, false, 220);
        } else {
          if (typeof state.map.setZoom === "function") state.map.setZoom(15);
          if (typeof state.map.setCenter === "function") state.map.setCenter(userPosition);
        }
        return;
      }
      const firstMarker = activeDay
        ? getDayMarkers(bundle, activeDay)[0]
        : getMapMarkers(bundle)[0];
      if (!firstMarker?.location) return;

      const position = [firstMarker.location.lng, firstMarker.location.lat];
      if (typeof state.map.setZoomAndCenter === "function") {
        state.map.setZoomAndCenter(15, position, false, 220);
      } else {
        if (typeof state.map.setZoom === "function") state.map.setZoom(15);
        if (typeof state.map.setCenter === "function") state.map.setCenter(position);
      }
    };

    const originalRenderMapV2Clean = renderMapV2Clean;
    renderMapV2Clean = function(bundle) {
      originalRenderMapV2Clean(bundle);
      if (!state.map) return;
      if (state.activePlaceId) {
        focusActivePlaceOnMap(bundle);
      } else {
        focusDefaultPlaceOnMap(bundle);
      }
    };

    renderItineraryV2 = function(bundle) {
      const summary = document.getElementById("itinerarySummary");
      const dayList = document.getElementById("dayList");
      const routeList = document.getElementById("routeList");
      const days = getItineraryDays(bundle);
      if (!days.length) {
        summary.classList.add("hidden");
        summary.innerHTML = "";
        dayList.innerHTML = "";
        routeList.innerHTML = "";
        return;
      }

      const activeDay = resolveActiveMapDay(bundle);
      const title = bundle?.itinerary?.title || "行程草案";
      const subtitle = bundle?.itinerary?.summary || "按天查看路线，点击地点可在地图上定位。";
      summary.classList.remove("hidden");
      summary.innerHTML = `
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div class="text-xs uppercase tracking-[0.28em] text-slate-500">Latest itinerary</div>
            <h3 class="mt-2 text-2xl font-semibold text-slate-100">${displayText(title)}</h3>
            <p class="mt-2 max-w-2xl text-sm leading-6 text-slate-400">${displayText(subtitle)}</p>
          </div>
          <div class="rounded-[1.15rem] border border-white/10 bg-white/5 px-3 py-2 text-right">
            <div class="text-xs text-slate-500">Generator</div>
            <div class="mt-1 text-sm font-medium text-slate-200">${displayText(bundle?.action || "planner")}</div>
          </div>
        </div>
      `;

      dayList.innerHTML = days.map((day) => {
        const items = Array.isArray(day.items) ? day.items : [];
        const isActiveDay = Number(day.day) === Number(activeDay);
        return `
          <article class="rounded-[1.6rem] border ${isActiveDay ? "border-[color:var(--accent)]/35 bg-white/[0.07]" : "border-white/10 bg-white/[0.04]"} p-4 sm:p-5">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div class="text-xs uppercase tracking-[0.28em] text-slate-500">Day ${day.day}</div>
                <div class="mt-1 text-xl font-semibold text-slate-100">${displayText(day.theme || "当日行程")}</div>
              </div>
              <div class="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-400">${items.length} 个地点</div>
            </div>
            <div class="mt-4 grid gap-3">
              ${items.length ? items.map((item, index) => {
                const isActiveItem = String(getItemId(item) || "") === String(state.activePlaceId || "");
                return `
                  <button
                    type="button"
                    data-place-id="${escapeAttribute(getItemId(item))}"
                    class="w-full text-left rounded-[1.35rem] border ${isActiveItem ? "border-[color:var(--accent)]/45 bg-white/[0.09] shadow-[0_14px_30px_rgba(243,179,79,0.08)]" : "border-white/8 bg-slate-950/35 hover:border-white/20 hover:bg-white/[0.04]"} p-4 transition-all"
                  >
                    <div class="flex gap-3">
                      <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${isActiveItem ? "bg-[color:var(--accent)] text-slate-950" : "bg-white/8 text-slate-100"} text-sm font-semibold">
                        ${index + 1}
                      </div>
                      <div class="min-w-0 flex-1">
                        <div class="text-base font-semibold ${isActiveItem ? "text-white" : "text-slate-100"}">${displayText(item.name)}</div>
                        ${item.address ? `
                          <div class="mt-3 text-[13px] leading-6 text-slate-400">
                            ${displayText(item.address)}
                          </div>
                        ` : ""}
                      </div>
                    </div>
                  </button>
                `;
              }).join("") : `
                <div class="rounded-[1.35rem] border border-dashed border-white/12 bg-slate-950/25 px-4 py-5 text-sm text-slate-500">
                  这一天暂时只有规划框架，还没有生成具体地点。
                </div>
              `}
            </div>
          </article>
        `;
      }).join("");

      dayList.querySelectorAll("[data-place-id]").forEach((button) => {
        button.addEventListener("click", () => setActivePlace(button.dataset.placeId, bundle));
      });

      routeList.innerHTML = "";
    };

    function resolveRequestedTripDays(bundle) {
      const candidates = [
        bundle?.requirement?.structured_payload?.trip_days,
        bundle?.requirement?.payload?.trip_days,
        bundle?.requirement?.trip_days,
        bundle?.itinerary?.trip_days,
        bundle?.trip_days
      ];
      for (const candidate of candidates) {
        const value = Number(candidate);
        if (Number.isFinite(value) && value > 0) return value;
      }
      return 0;
    }

    renderItineraryV2 = function(bundle) {
      const summary = document.getElementById("itinerarySummary");
      const dayList = document.getElementById("dayList");
      const routeList = document.getElementById("routeList");
      const rawDays = getItineraryDays(bundle);
      const requestedDays = resolveRequestedTripDays(bundle);
      const totalDays = Math.max(rawDays.length, requestedDays);
      const days = totalDays
        ? Array.from({ length: totalDays }, (_, index) => {
            const existingDay = rawDays[index];
            if (existingDay) {
              return {
                ...existingDay,
                day: Number(existingDay.day) || index + 1,
                items: Array.isArray(existingDay.items) ? existingDay.items : []
              };
            }
            return {
              day: index + 1,
              theme: `第 ${index + 1} 天`,
              items: []
            };
          })
        : [];
      if (!days.length) {
        summary.classList.add("hidden");
        summary.innerHTML = "";
        dayList.innerHTML = "";
        routeList.innerHTML = "";
        return;
      }

      const activeDay = resolveActiveMapDay(bundle);
      const title = bundle?.itinerary?.title || "????";
      const subtitle = bundle?.itinerary?.summary || "???????????????";
      const assumptions = Array.isArray(bundle?.appliedAssumptions) ? bundle.appliedAssumptions.slice(0, 4) : [];
      const interpretation = bundle?.requirementInterpretation || bundle?.itinerary?.requirementInterpretation || null;
      summary.classList.remove("hidden");
      summary.innerHTML = `
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div class="text-xs uppercase tracking-[0.28em] text-slate-500">Latest itinerary</div>
            <h3 class="mt-2 text-2xl font-semibold text-slate-100">${displayText(title)}</h3>
            <p class="mt-2 max-w-2xl text-sm leading-6 text-slate-400">${displayText(subtitle)}</p>
            ${interpretation?.destination ? `<div class="mt-3 text-xs text-slate-500">????${displayText(interpretation.destination)} ? ${displayText((interpretation.interests || []).join(" / ") || "???????")}</div>` : ""}
            ${assumptions.length ? `<div class="mt-3 flex flex-wrap gap-2">${assumptions.map((item) => `<span class="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300">${displayText(item)}</span>`).join("")}</div>` : ""}
          </div>
          <div class="rounded-[1.15rem] border border-white/10 bg-white/5 px-3 py-2 text-right">
            <div class="text-xs text-slate-500">Generator</div>
            <div class="mt-1 text-sm font-medium text-slate-200">${displayText(bundle?.action || "planner")}</div>
          </div>
        </div>
      `;

      dayList.innerHTML = days.map((day) => {
        const items = Array.isArray(day.items) ? day.items : [];
        const isActiveDay = Number(day.day) === Number(activeDay);
        return `
          <article class="rounded-[1.6rem] border ${isActiveDay ? "border-[color:var(--accent)]/35 bg-white/[0.07]" : "border-white/10 bg-white/[0.04]"} p-4 sm:p-5">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div class="text-xs uppercase tracking-[0.28em] text-slate-500">Day ${day.day}</div>
                <div class="mt-1 text-xl font-semibold text-slate-100">${displayText(day.theme || "当日行程")}</div>
              </div>
              <div class="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-400">${items.length} 个地点</div>
            </div>
            <div class="mt-4 grid gap-3">
              ${items.length ? items.map((item, index) => {
                const isActiveItem = String(getItemId(item) || "") === String(state.activePlaceId || "");
                return `
                  <button
                    type="button"
                    data-place-id="${escapeAttribute(getItemId(item))}"
                    class="w-full text-left rounded-[1.35rem] border ${isActiveItem ? "border-[color:var(--accent)]/45 bg-white/[0.09] shadow-[0_14px_30px_rgba(243,179,79,0.08)]" : "border-white/8 bg-slate-950/35 hover:border-white/20 hover:bg-white/[0.04]"} p-4 transition-all"
                  >
                    <div class="flex gap-3">
                      <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${isActiveItem ? "bg-[color:var(--accent)] text-slate-950" : "bg-white/8 text-slate-100"} text-sm font-semibold">
                        ${index + 1}
                      </div>
                      <div class="min-w-0 flex-1">
                        <div class="text-base font-semibold ${isActiveItem ? "text-white" : "text-slate-100"}">${displayText(item.name)}</div>
                        ${item.address ? `
                          <div class="mt-3 text-[13px] leading-6 text-slate-400">
                            ${displayText(item.address)}
                          </div>
                        ` : ""}
                      </div>
                    </div>
                  </button>
                `;
              }).join("") : `
                <div class="rounded-[1.35rem] border border-dashed border-white/12 bg-slate-950/25 px-4 py-5 text-sm text-slate-500">
                  这一天会保留在行程里，但当前还没有生成具体地点。
                </div>
              `}
            </div>
          </article>
        `;
      }).join("");

      dayList.querySelectorAll("[data-place-id]").forEach((button) => {
        button.addEventListener("click", () => setActivePlace(button.dataset.placeId, bundle));
      });

      routeList.innerHTML = "";
    };

    (async () => {
      setTheme("light");
      setLanguage("zh");
      setPanel("itinerary");
      const motionKnob = document.querySelector(".motion-knob");
      if (motionKnob) motionKnob.style.transform = "translateX(0)";
      await loadMapSdk().catch((error) => {
        console.warn("map sdk init skipped", error);
      });
      await loadAppInfo();
      await loadSessionHistory();
      await ensureSession().catch(async (error) => {
        console.warn("ensureSession failed, resetting session state", error);
        prepareNewSession();
      });
      requestBrowserLocation();
      if (!state.itineraryBundle && !state.chatTranscriptDirty) {
        renderTranscript([]);
        renderRecommendations(null);
        renderItineraryV2(null);
        renderDebug(null);
        renderMapV2Clean(null);
        renderResolvedPlacesV2Clean(null);
      }
    })().catch((error) => {
      console.error(error);
      return;
      document.getElementById("chatTranscript").innerHTML = `
        <div class="bubble-enter flex justify-center">
          <div class="bubble-ai w-full max-w-[620px] rounded-[1.6rem] px-5 py-5 text-left text-slate-100">
            <div class="mb-2 text-[11px] uppercase tracking-[0.28em] text-slate-400">助手</div>
            <div class="text-sm leading-7 text-slate-200">页面正在初始化，请稍候。</div>
          </div>
        </div>`;
    });

(function () {
  const chat = (window.TravelChat = window.TravelChat || {});

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

  function buildConversationContext(requirement) {
    if (!requirement) return "";
    const payload = requirement.structured_payload || requirement.payload || {};
    const pieces = [];
    if (payload.destination) pieces.push(`目的地${payload.destination}`);
    if (payload.trip_days) pieces.push(`天数${payload.trip_days}`);
    const interests = Array.isArray(payload.interests) ? payload.interests.filter(Boolean) : [];
    if (interests.length) pieces.push(`偏好${interests.slice(0, 6).join(",")}`);
    const prefs = payload.user_preferences || {};
    if (prefs.preferredPace) pieces.push(`节奏${prefs.preferredPace}`);
    if (prefs.distanceTolerance) pieces.push(`距离${prefs.distanceTolerance}`);
    if (requirement.raw_input) pieces.push(`原始需求${requirement.raw_input}`);
    return pieces.join(" | ");
  }

  function getConversationContext() {
    return buildConversationContext(window.state?.activeRequirement || window.state?.itineraryBundle?.requirement || null);
  }

  function showTyping(show) {
    const el = document.getElementById("typingState");
    if (el) el.classList.toggle("hidden", !show);
  }

  function scrollChatBottom() {
    const el = document.getElementById("chatTranscript");
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
  }

  function appendTranscriptMessage(message) {
    const el = document.getElementById("chatTranscript");
    if (!el) return;
    const wrapper = document.createElement("div");
    wrapper.className = `bubble-enter flex ${message.role === "user" ? "justify-end" : "justify-start"}`;
    const bubble = document.createElement("div");
    bubble.className = [
      "w-full max-w-[72%] rounded-[1.85rem] px-5.5 py-5 sm:max-w-[68%] sm:px-6 sm:py-5.5",
      message.role === "user" ? "bubble-user text-slate-950" : "bubble-ai text-slate-100"
    ].join(" ");
    bubble.innerHTML = `
      <div class="mb-2 flex items-center justify-between gap-3 text-[11px] uppercase tracking-[0.28em]">
        <div class="${message.role === "user" ? "text-slate-950/70" : "text-slate-400"}">${message.role === "user" ? "你" : "助手"}</div>
        <div class="${message.role === "user" ? "text-slate-950/60" : "text-slate-500"}">${escapeHtml(message.created_at || message.time || "")}</div>
      </div>
      <div class="whitespace-pre-wrap text-[17px] leading-[2.05] sm:text-[18px] sm:leading-[2.05]">${displayText(message.content || "")}</div>
    `;
    wrapper.appendChild(bubble);
    el.appendChild(wrapper);
    scrollChatBottom();
  }

  function renderTranscript(messages) {
    const el = document.getElementById("chatTranscript");
    if (!el) return;
    el.innerHTML = "";
    if (!messages || !messages.length) {
      el.innerHTML = `
        <div class="bubble-enter flex justify-start">
            <div class="bubble-ai w-full max-w-[74%] rounded-[1.85rem] px-5.5 py-5 text-left text-slate-100 sm:max-w-[70%] sm:px-6 sm:py-5.5">
            <div class="mb-2 text-[11px] uppercase tracking-[0.28em] text-slate-400">助手</div>
              <div class="text-[17px] leading-[2.05] text-slate-200 sm:text-[18px]">你可以先告诉我想去哪儿、几天、偏好什么，我来帮你开始规划。</div>
          </div>
        </div>
      `;
      return;
    }
    messages.forEach((message) => appendTranscriptMessage(message));
  }

  function setLanguage(lang) {
    document.documentElement.lang = lang === "en" ? "en" : "zh-CN";
    const prompt = document.getElementById("promptInput");
    const mapSearch = document.getElementById("mapSearchInput");
    if (prompt) {
      prompt.placeholder = lang === "en"
        ? "Tell me your trip needs, preferences, or pace."
        : "你有什么需求？比如想多景点、咖啡、美食、夜景，或者想轻松一点。";
    }
    if (mapSearch) {
      mapSearch.placeholder = lang === "en"
        ? "Search places, e.g. cafe, mall, night view"
        : "搜索地点，比如：咖啡店、景点、夜景";
    }
    document.querySelectorAll(".lang-btn").forEach((btn) => {
      const active = btn.dataset.lang === lang;
      btn.classList.toggle("ring-2", active);
      btn.classList.toggle("ring-[color:var(--accent)]", active);
    });
  }

  chat.escapeHtml = escapeHtml;
  chat.normalizeDisplayText = normalizeDisplayText;
  chat.displayText = displayText;
  chat.buildConversationContext = buildConversationContext;
  chat.getConversationContext = getConversationContext;
  chat.showTyping = showTyping;
  chat.scrollChatBottom = scrollChatBottom;
  chat.appendTranscriptMessage = appendTranscriptMessage;
  chat.renderTranscript = renderTranscript;
  chat.setLanguage = setLanguage;
})();

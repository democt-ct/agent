window.persistChatMessages = function persistChatMessages() {
  const key = chatStorageKey(state.sessionId);
  if (!key) return;
  const messages = Array.isArray(state.chatMessages)
    ? state.chatMessages.slice(-20).map((item) => ({
        role: item.role,
        content: item.content,
        created_at: item.created_at || item.createdAt || new Date().toISOString(),
      }))
    : [];
  localStorage.setItem(key, JSON.stringify(messages));
};

window.persistGeneralChatMessages = function persistGeneralChatMessages() {
  const key = generalChatStorageKey(state.generalSessionId);
  if (!key) return;
  const messages = Array.isArray(state.generalChatMessages)
    ? state.generalChatMessages.slice(-24).map((item) => ({
        role: item.role,
        content: item.content,
        created_at: item.created_at || item.createdAt || new Date().toISOString(),
      }))
    : [];
  localStorage.setItem(key, JSON.stringify(messages));
  localStorage.setItem(generalSessionStorageKey(), state.generalSessionId || "");
  upsertGeneralRecentSession(state.generalSessionId, buildGeneralRecentSnapshot(state.generalSessionId, state.generalChatMessages));
};

window.readStoredChatMessages = function readStoredChatMessages(sessionId) {
  const key = chatStorageKey(sessionId);
  if (!key) return [];
  try {
    const raw = localStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (_) { return []; }
};

window.readStoredGeneralChatMessages = function readStoredGeneralChatMessages(sessionId) {
  const key = generalChatStorageKey(sessionId);
  if (!key) return [];
  try {
    const raw = localStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (_) { return []; }
};

window.restoreStoredChatMessages = function restoreStoredChatMessages(emptyMessage = "") {
  state.chatMessages = readStoredChatMessages(state.sessionId);
  resetShortTermMemory();
  renderChat(state.chatMessages.length ? "" : emptyMessage);
  const lastAssistant = [...state.chatMessages].reverse().find((item) => item.role === "assistant");
  if (lastAssistant && lastAssistant.content) {
    setAnswer(lastAssistant.content);
  }
  renderSessionOptions();
};

window.restoreStoredGeneralChatMessages = function restoreStoredGeneralChatMessages(emptyMessage = "") {
  if (!state.generalSessionId) {
    state.generalSessionId = localStorage.getItem(generalSessionStorageKey())
      || state.generalRecentSessions[0]?.session_id
      || generateSessionId();
  }
  state.generalChatMessages = readStoredGeneralChatMessages(state.generalSessionId);
  renderGeneralChat(state.generalChatMessages.length ? "" : emptyMessage);
  upsertGeneralRecentSession(state.generalSessionId, buildGeneralRecentSnapshot(state.generalSessionId, state.generalChatMessages));
};

window.resetShortTermMemory = function resetShortTermMemory() {
  state.shortTermMessages = [];
  state.shortTermMemory = null;
};

window.setStructuredShortTermMemory = function setStructuredShortTermMemory(memory) {
  state.shortTermMemory = memory && typeof memory === "object" ? memory : null;
};

window.buildShortTermMemory = function buildShortTermMemory(roundLimit = SHORT_TERM_ROUND_LIMIT) {
  const recentMessages = state.shortTermMessages.slice(-(roundLimit * 2));
  const latestUser = [...recentMessages].reverse().find((item) => item.role === "user" && String(item.content || "").trim());
  return {
    recent_messages: recentMessages.map((item) => ({
      role: item.role || "assistant",
      content: String(item.content || "").trim(),
    })).filter((item) => item.content),
    session_state: {
      intent: "",
      current_topic: latestUser ? String(latestUser.content || "").trim() : "",
      goal: latestUser ? String(latestUser.content || "").trim() : "",
      constraints: [],
      confirmed_facts: [],
      open_questions: [],
      identity_status: "unknown",
      claimed_name: state.profileName || null,
      claimed_birth_year: null,
      confirmed_patient_id: state.patientId || null,
      confirmed_patient_name: null,
      identity_source: null,
      identity_candidates: [],
    },
    active_entities: { drugs: [], symptoms: [], tests: [], metrics: [] },
    risk_signals: { red_flags: [], medication_flags: [], monitoring_flags: [] },
  };
};

window.buildShortTermSummary = function buildShortTermSummary(messages) {
  const recentMessages = Array.isArray(messages) ? messages : [];
  const latestUser = [...recentMessages].reverse().find((item) => item.role === "user" && String(item.content || "").trim());
  const latestAssistant = [...recentMessages].reverse().find((item) => item.role === "assistant" && String(item.content || "").trim());
  const joined = recentMessages.map((item) => String(item.content || "")).join("\n");
  const focusTags = [];
  if (/[复诊复查随访]|follow-up|review/i.test(joined)) focusTags.push("复诊/随访");
  if (/[血压头晕胸闷心悸]|blood pressure|dizzy|chest|palpitation/i.test(joined)) focusTags.push("症状/指标监测");
  if (/[用药药物服药]|medication|medicine/i.test(joined)) focusTags.push("用药相关");
  return [
    "结构化状态摘要：",
    `- 当前会话内短期记忆消息数：${recentMessages.length}`,
    `- 最近用户关注：${latestUser ? String(latestUser.content || "").trim() : "无"}`,
    `- 最近助手回应重点：${latestAssistant ? String(latestAssistant.content || "").trim() : "无"}`,
    `- 当前关注标签：${focusTags.length ? focusTags.join("、") : "未提取到明显标签"}`,
  ].join("\n");
};

window.buildClientConversationContext = function buildClientConversationContext(roundLimit = SHORT_TERM_ROUND_LIMIT) {
  const rawMessages = state.shortTermMessages.slice(-(roundLimit * 2));
  const profileBlock = (state.profileName || state.profilePhone)
    ? `个人信息：\n- 姓名：${state.profileName || "未填写"}\n- 电话：${state.profilePhone || "未填写"}`
    : "";
  const rawBlock = rawMessages.map((item) => {
    const role = item.role === "user" ? "User" : (item.role === "assistant" ? "Assistant" : "System");
    const content = String(item.content || "").trim();
    return content ? `${role}: ${content}` : "";
  }).filter(Boolean).join("\n");
  const summaryBlock = buildShortTermSummary(rawMessages);
  return [profileBlock, rawBlock ? `最近原始消息：\n${rawBlock}` : "", summaryBlock].filter(Boolean).join("\n\n");
};

window.setAnswer = function setAnswer(text) {
  const el = document.getElementById("answerBox");
  if (el) el.textContent = text || "暂无回答";
};

window.syncLatestMemoryAnswer = function syncLatestMemoryAnswer(text, actionLabel = "记忆聊天最新回答") {
  const normalized = stripMarkdownMarkers(String(text || "")).trim();
  setAnswer(normalized || "暂无回答");
  state.lastSpeechText = normalized || "";
  const el = document.getElementById("lastAction");
  if (el) el.textContent = actionLabel;
};

window.keepChatInView = function keepChatInView() {
  const el = document.getElementById("chatTranscript");
  if (!el) return;
  requestAnimationFrame(() => {
    el.style.scrollBehavior = 'smooth';
    el.scrollTop = el.scrollHeight;
    el.addEventListener('scrollend', () => { el.style.scrollBehavior = ''; }, { once: true });
  });
};

window.setSendButtonState = function setSendButtonState(isSending) {
  const btn = document.getElementById("sendMessageBtn");
  if (!btn) return;
  btn.disabled = isSending;
  if (isSending) {
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-2px"><rect x="6" y="6" width="12" height="12" rx="2"/></svg> 发送中...';
  } else {
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg> 发送消息';
  }
};

window.renderChat = function renderChat(emptyMessage = "") {
  const chatTranscript = document.getElementById("chatTranscript");
  if (!chatTranscript) return;
  if (!state.chatMessages.length) {
    chatTranscript.innerHTML = `<div class="chat-empty">${escapeHtml(emptyMessage || "请开始对话。")}</div>`;
    return;
  }
  chatTranscript.innerHTML = state.chatMessages.map((message, index) => {
    const role = message.role === "user" ? "user" : (message.role === "assistant" ? "assistant" : "system");
    const normalizedContent = role === "assistant" ? stripMarkdownMarkers(message.content || "") : String(message.content || "");
    const body = escapeHtml(normalizedContent).replace(/\n/g, "<br>");
    const avatar = role === "user"
      ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
      : role === "assistant"
        ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a4 4 0 014 4v2a4 4 0 01-8 0V6a4 4 0 014-4z"/><path d="M18 12h.01"/><path d="M6 12h.01"/><path d="M12 16v4"/><path d="M8 20h8"/><path d="M9.5 12v1a2.5 2.5 0 005 0v-1"/></svg>'
        : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
    const speechTools = role === "assistant" ? `
      <div class="chat-tools">
        <button class="mini-btn primary message-speak-btn" type="button" data-message-index="${index}">语音播报</button>
        <button class="mini-btn secondary message-stop-btn" type="button">停止</button>
      </div>
    ` : "";
    return `
      <div class="chat-message ${role}">
        <div class="chat-avatar">${avatar}</div>
        <div class="chat-bubble">
          <div>${body}</div>
          ${speechTools}
        </div>
      </div>
    `;
  }).join("");
  chatTranscript.style.scrollBehavior = 'smooth';
  chatTranscript.scrollTop = chatTranscript.scrollHeight;
  chatTranscript.addEventListener('scrollend', () => { chatTranscript.style.scrollBehavior = ''; }, { once: true });
};

window.pushChatMessage = function pushChatMessage(role, content, createdAt = new Date().toISOString(), options = {}) {
  const { trackShortTerm = false } = options;
  state.chatMessages.push({ role, content, created_at: createdAt });
  if (trackShortTerm) {
    state.shortTermMessages.push({ role, content, created_at: createdAt });
    state.shortTermMessages = state.shortTermMessages.slice(-(SHORT_TERM_ROUND_LIMIT * 2));
  }
  persistChatMessages();
  renderChat();
  if (role === "assistant") syncLatestMemoryAnswer(content);
};

window.resetChat = function resetChat(forceNew = false, message = "") {
  if (forceNew || !state.sessionId) {
    ensureSessionId(forceNew);
  } else {
    updateSessionDisplays();
  }
  state.chatMessages = [];
  resetShortTermMemory();
  persistChatMessages();
  renderChat(message || (state.patientId ? "当前会话已就绪，可以继续发送下一条消息。" : "请先发送一条消息，系统就会开始记住这个会话。"));
};

window.renderGeneralChat = function renderGeneralChat(emptyMessage = "") {
  const el = document.getElementById("generalChatTranscript");
  if (!el) return;
  if (!state.generalChatMessages.length) {
    el.innerHTML = `<div class="chat-empty">${escapeHtml(emptyMessage || "直接提问，无需绑定身份。")}</div>`;
    return;
  }
  const userAvatar = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
  const assistantAvatar = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a4 4 0 014 4v2a4 4 0 01-8 0V6a4 4 0 014-4z"/><path d="M18 12h.01"/><path d="M6 12h.01"/><path d="M12 16v4"/><path d="M8 20h8"/><path d="M9.5 12v1a2.5 2.5 0 005 0v-1"/></svg>';
  el.innerHTML = state.generalChatMessages.map((message) => {
    const role = message.role === "user" ? "user" : (message.role === "assistant" ? "assistant" : "system");
    const normalizedContent = role === "assistant" ? stripMarkdownMarkers(message.content || "") : String(message.content || "");
    const body = escapeHtml(normalizedContent).replace(/\n/g, "<br>");
    const avatar = role === "user" ? userAvatar : assistantAvatar;
    return `
      <div class="chat-message ${role}">
        <div class="chat-avatar">${avatar}</div>
        <div class="chat-bubble"><div>${body}</div></div>
      </div>
    `;
  }).join("");
  el.style.scrollBehavior = "smooth";
  el.scrollTop = el.scrollHeight;
};

window.pushGeneralChatMessage = function pushGeneralChatMessage(role, content, createdAt = new Date().toISOString()) {
  state.generalChatMessages.push({ role, content, created_at: createdAt });
  state.generalChatMessages = state.generalChatMessages.slice(-24);
  persistGeneralChatMessages();
  renderGeneralChat();
};

window.resetGeneralChat = function resetGeneralChat(forceNew = false, message = "") {
  if (forceNew || !state.generalSessionId) {
    state.generalSessionId = generateSessionId();
  }
  state.generalChatMessages = [];
  persistGeneralChatMessages();
  renderGeneralChat(message || "可以直接开始提问。");
  const input = document.querySelector('#generalChatForm textarea[name="question"]');
  if (input) input.value = "";
  renderGeneralRecentSessions();
};

window.readStoredGeneralRecentSessions = function readStoredGeneralRecentSessions() {
  try {
    const raw = localStorage.getItem(generalRecentStorageKey());
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((item) => item && typeof item === "object" && item.session_id) : [];
  } catch (_) { return []; }
};

window.persistGeneralRecentSessions = function persistGeneralRecentSessions() {
  try {
    localStorage.setItem(generalRecentStorageKey(), JSON.stringify(state.generalRecentSessions.slice(0, 12)));
  } catch (_) {}
  const countEl = document.getElementById("generalRecentCount");
  if (countEl) countEl.textContent = String(state.generalRecentSessions.length);
};

window.buildGeneralRecentSnapshot = function buildGeneralRecentSnapshot(sessionId = state.generalSessionId, messages = state.generalChatMessages) {
  const list = Array.isArray(messages) ? messages : [];
  const lastUserMessage = [...list].reverse().find((item) => item?.role === "user" && String(item?.content || "").trim()) || null;
  const preview = lastUserMessage ? String(lastUserMessage.content || "").trim() : "新建对话";
  const now = new Date().toISOString();
  return {
    session_id: sessionId,
    created_at: now,
    updated_at: now,
    latest_message_at: lastUserMessage?.created_at || lastUserMessage?.createdAt || now,
    latest_message_preview: preview,
    message_count: list.length,
  };
};

window.upsertGeneralRecentSession = function upsertGeneralRecentSession(sessionId = state.generalSessionId, snapshot = {}) {
  if (!sessionId) return;
  const now = new Date().toISOString();
  const existing = state.generalRecentSessions.find((item) => item.session_id === sessionId);
  const merged = {
    session_id: sessionId,
    created_at: existing?.created_at || snapshot.created_at || now,
    updated_at: now,
    latest_message_at: snapshot.latest_message_at || existing?.latest_message_at || now,
    latest_message_preview: snapshot.latest_message_preview ?? existing?.latest_message_preview ?? "新建对话",
    message_count: snapshot.message_count ?? existing?.message_count ?? 0,
  };
  state.generalRecentSessions = [
    merged,
    ...state.generalRecentSessions.filter((item) => item.session_id !== sessionId),
  ].slice(0, 12);
  persistGeneralRecentSessions();
  renderGeneralRecentSessions();
};

window.deleteGeneralRecentSession = function deleteGeneralRecentSession(sessionId) {
  const target = String(sessionId || "").trim();
  if (!target) return;
  localStorage.removeItem(generalChatStorageKey(target));
  state.generalRecentSessions = state.generalRecentSessions.filter((item) => item.session_id !== target);
  persistGeneralRecentSessions();

  if (state.generalSessionId === target) {
    const nextSessionId = state.generalRecentSessions[0]?.session_id || "";
    if (nextSessionId) {
      state.generalSessionId = nextSessionId;
      localStorage.setItem(generalSessionStorageKey(), nextSessionId);
      state.generalChatMessages = readStoredGeneralChatMessages(nextSessionId);
      renderGeneralChat(state.generalChatMessages.length ? "" : "可以直接开始提问，也可以新建一段独立对话。");
      upsertGeneralRecentSession(nextSessionId, buildGeneralRecentSnapshot(nextSessionId, state.generalChatMessages));
    } else {
      state.generalSessionId = generateSessionId();
      localStorage.setItem(generalSessionStorageKey(), state.generalSessionId);
      state.generalChatMessages = [];
      persistGeneralChatMessages();
      renderGeneralChat("可以直接开始提问，也可以新建一段独立对话。");
    }
  }
  renderGeneralRecentSessions();
  const input = document.querySelector('#generalChatForm textarea[name="question"]');
  if (input) input.focus();
};

window.renderGeneralRecentSessions = function renderGeneralRecentSessions() {
  const listEl = document.getElementById("sidebarRecentList");
  if (!listEl) return;
  if (!state.generalRecentSessions.length) {
    listEl.innerHTML = `<div class="sidebar-empty-inline">暂无对话记录</div>`;
    return;
  }
  listEl.innerHTML = state.generalRecentSessions.map((item) => {
    const active = item.session_id === state.generalSessionId;
    const preview = String(item.latest_message_preview || "新建对话").trim();
    const time = formatTime(item.latest_message_at || item.updated_at || item.created_at);
    return `
      <div class="sidebar-history-item ${active ? "active" : ""}" data-session-id="${escapeHtml(item.session_id)}">
        <div class="history-meta">
          <span class="history-time">${escapeHtml(time || "")}</span>
          <span class="history-count">${item.message_count || 0} 条</span>
        </div>
        <div class="history-preview">${escapeHtml(preview)}</div>
      </div>
    `;
  }).join("");

  listEl.querySelectorAll(".sidebar-history-item").forEach((el) => {
    el.addEventListener("click", () => {
      const sid = String(el.dataset.sessionId || "").trim();
      if (sid) selectGeneralSession(sid);
    });
  });
};

window.renderSessionOptions = function renderSessionOptions() {
  const select = document.getElementById("chatSessionSelect");
  if (!select) return;
  const options = [];
  let sessions = Array.isArray(state.chatSessions) ? [...state.chatSessions] : [];
  if (state.sessionId && !sessions.some((item) => item.session_id === state.sessionId)) {
    sessions.unshift({
      session_id: state.sessionId,
      message_count: state.chatMessages.length,
      latest_message_at: state.chatMessages.length ? state.chatMessages[state.chatMessages.length - 1].created_at : "",
      latest_message_preview: state.chatMessages.length ? state.chatMessages[state.chatMessages.length - 1].content : "当前会话",
    });
  }
  if (!state.patientId) {
    options.push({ value: "", label: "请先选择患者后再查看已保存会话" });
  } else if (!sessions.length) {
    options.push({ value: state.sessionId || "", label: state.sessionId ? `当前新会话 | ${state.sessionId}` : "暂无已保存会话" });
  } else {
    options.push(...sessions.map((item) => {
      const latestAt = formatTime(item.latest_message_at);
      const preview = item.latest_message_preview ? ` | ${item.latest_message_preview.slice(0, 28)}` : "";
      return { value: item.session_id, label: `${latestAt || "未记录时间"} | ${item.message_count || 0} 条消息${preview}` };
    }));
  }
  select.innerHTML = "";
  options.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    select.appendChild(option);
  });
  select.disabled = !state.patientId;
  if (state.sessionId) select.value = state.sessionId;
};

window.selectSession = function selectSession(sessionId) {
  state.sessionId = (sessionId || "").trim();
  if (!state.patientId) restoreStoredChatMessages("请开始对话。");
  updateSessionDisplays();
};

window.selectGeneralSession = function selectGeneralSession(sessionId) {
  const target = String(sessionId || "").trim();
  if (!target) return;
  state.generalSessionId = target;
  localStorage.setItem(generalSessionStorageKey(), target);
  state.generalChatMessages = readStoredGeneralChatMessages(target);
  renderGeneralChat(state.generalChatMessages.length ? "" : "可以直接开始提问，也可以新建一段独立对话。");
  upsertGeneralRecentSession(target, buildGeneralRecentSnapshot(target, state.generalChatMessages));
  const input = document.querySelector('#generalChatForm textarea[name="question"]');
  if (input) input.focus();
};

window.updateSessionDisplays = function updateSessionDisplays() {
  const el = document.getElementById("currentSessionId");
  if (el) el.textContent = state.sessionId || "未设置";
  const badge = document.getElementById("querySessionBadge");
  if (badge) badge.textContent = state.sessionId || "未设置";
  if (state.sessionId) localStorage.setItem(sessionStorageKey(state.patientId), state.sessionId);
  renderSessionOptions();
  persistContext();
};

window.ensureSessionId = function ensureSessionId(forceNew = false) {
  if (forceNew || !state.sessionId) {
    const stored = !forceNew ? localStorage.getItem(sessionStorageKey(state.patientId)) : "";
    state.sessionId = stored || generateSessionId();
  }
  updateSessionDisplays();
  return state.sessionId;
};

window.persistContext = function persistContext() {
  localStorage.setItem(contextStorageKey, JSON.stringify({
    sessionId: state.sessionId,
    patientId: state.patientId,
    hospitalId: state.hospitalId,
    authToken: state.authToken,
    profileName: state.profileName,
    profilePhone: state.profilePhone,
  }));
};

window.readStoredContext = function readStoredContext() {
  try {
    const raw = localStorage.getItem(contextStorageKey);
    const parsed = raw ? JSON.parse(raw) : {};
    return {
      sessionId: parsed?.sessionId || "",
      patientId: parsed?.patientId || "",
      hospitalId: parsed?.hospitalId || "",
      authToken: parsed?.authToken || "",
      profileName: parsed?.profileName || "",
      profilePhone: parsed?.profilePhone || "",
    };
  } catch (_) {
    return { sessionId: "", patientId: "", hospitalId: "", authToken: "", profileName: "", profilePhone: "" };
  }
};

window.applyProfileState = function applyProfileState({ name = state.profileName, phone = state.profilePhone } = {}) {
  state.profileName = String(name || "").trim();
  state.profilePhone = String(phone || "").trim();
  const nameInput = document.getElementById("profileNameInput");
  const phoneInput = document.getElementById("profilePhoneInput");
  if (nameInput) nameInput.value = state.profileName;
  if (phoneInput) phoneInput.value = state.profilePhone;
  persistContext();
};

window.setCurrentContext = function setCurrentContext({
  patientId = state.patientId,
  hospitalId = state.hospitalId,
  authToken = state.authToken,
  sessionId = null,
  preserveSession = false,
} = {}) {
  const previousPatientId = state.patientId;
  state.patientId = patientId || "";
  state.hospitalId = hospitalId || "";
  state.authToken = normalizeAuthToken(authToken);

  const pidEl = document.getElementById("currentPatientId");
  const hidEl = document.getElementById("currentHospitalId");
  const atEl = document.getElementById("currentAuthToken");
  const badge = document.getElementById("queryPatientBadge");
  if (pidEl) pidEl.textContent = state.patientId || "未确认";
  if (hidEl) hidEl.textContent = state.hospitalId || "未确认";
  if (atEl) atEl.textContent = state.authToken ? "已设置" : "未设置";
  if (badge) badge.textContent = state.patientId || "未确认";

  const medicalInput = document.getElementById("medicalPatientId");
  const visitInput = document.getElementById("visitPatientId");
  const lookupInput = document.getElementById("lookupPatientId");
  if (medicalInput) medicalInput.value = state.patientId;
  if (visitInput) visitInput.value = state.patientId;
  if (lookupInput) lookupInput.value = state.patientId;

  if (previousPatientId !== state.patientId) {
    state.chatSessions = [];
    if (preserveSession) {
      if (sessionId) state.sessionId = sessionId;
      else if (!state.sessionId) ensureSessionId(false);
      updateSessionDisplays();
      renderSessionOptions();
    } else {
      state.sessionId = state.patientId
        ? (localStorage.getItem(sessionStorageKey(state.patientId)) || "")
        : (localStorage.getItem(sessionStorageKey("")) || state.sessionId || "");
      if (state.patientId) {
        resetChat(!state.sessionId, "已选择当前患者。你可以继续已保存会话，或开始一个新会话。");
      } else if (state.sessionId) {
        updateSessionDisplays();
        restoreStoredChatMessages("请开始对话。");
      } else {
        state.chatMessages = [];
        resetShortTermMemory();
        persistChatMessages();
        updateSessionDisplays();
        renderChat("请先发送一条消息，系统就会开始记住这个会话。");
      }
    }
  } else if (state.patientId || state.sessionId) {
    ensureSessionId(false);
    if (!state.patientId && state.sessionId) restoreStoredChatMessages("请开始对话。");
  } else {
    updateSessionDisplays();
  }
  persistContext();
  if (state.patientId && state.sessionId) promoteAnonymousSessionToPatient().catch(() => {});
};

window.buildGeneralConversationContext = function buildGeneralConversationContext() {
  const recentMessages = state.generalChatMessages.slice(-12);
  return recentMessages.map((item) => {
    const role = item.role === "assistant" ? "Assistant" : (item.role === "user" ? "User" : "System");
    return `${role}: ${String(item.content || "").trim()}`;
  }).filter(Boolean).join("\n");
};

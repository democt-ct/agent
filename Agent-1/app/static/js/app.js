window.switchWorkspace = function switchWorkspace(view) {
  const target = view === "chat" ? "memory" : (view || "general");
  const generalView = document.getElementById("generalView");
  const chatView = document.getElementById("chatView");

  if (target === "query") {
    if (generalView) generalView.hidden = true;
    if (chatView) chatView.hidden = true;
    openQueryPanel();
    setWorkspaceNavActive("query");
    localStorage.setItem("agentTesterWorkspaceView", "query");
    return;
  }
  closeQueryPanel();
  setChatSubMode(target === "memory" ? "memory" : "general");
  renderGeneralRecentSessions();
};

window.setChatSubMode = function setChatSubMode(mode) {
  const isMemory = mode === "memory";
  const loggedIn = Boolean(state.patientId);
  state.chatMode = isMemory ? "memory" : "general";
  localStorage.setItem("agentTesterChatMode", state.chatMode);
  localStorage.setItem("agentTesterWorkspaceView", state.chatMode);

  const generalView = document.getElementById("generalView");
  const chatView = document.getElementById("chatView");
  if (generalView) generalView.hidden = isMemory;
  if (chatView) chatView.hidden = !isMemory;
  setWorkspaceNavActive(isMemory ? "memory" : "general");

  const openBtn = document.getElementById("openLoginModalBtn");
  if (openBtn) {
    if (loggedIn) {
      openBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> ${state.profileName || '已登录'}`;
      openBtn.classList.add("active");
    } else {
      openBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg> 登录`;
      openBtn.classList.remove("active");
    }
  }
  const chip = document.getElementById("memoryLoginChip");
  if (chip) chip.textContent = loggedIn ? (state.profileName || "已登录") : "未登录";
  updateMemoryLoginHint(loggedIn
    ? `已登录：${state.profileName || state.patientId}，可以继续记忆聊天。`
    : "记忆聊天需要先绑定个人信息。未登录时不会自动弹窗，请点击登录。");

  if (isMemory && !loggedIn) {
    const chatTranscript = document.getElementById("chatTranscript");
    if (chatTranscript) chatTranscript.innerHTML = `<div class="chat-empty">请先登录后再使用记忆聊天。你可以点击左侧「登录」按钮来绑定个人信息。</div>`;
  }
};

window.setWorkspaceNavActive = function setWorkspaceNavActive(view) {
  const isGeneral = view === "general";
  const isMemory = view === "memory";
  const chatViewBtn = document.getElementById("chatViewBtn");
  const memoryViewBtn = document.getElementById("memoryViewBtn");
  const queryViewBtn = document.getElementById("toggleQueryPanelBtn");
  if (chatViewBtn) chatViewBtn.classList.toggle("active", isGeneral);
  if (memoryViewBtn) memoryViewBtn.classList.toggle("active", isMemory);
  if (queryViewBtn) queryViewBtn.classList.toggle("active", view === "query");
};

window.openQueryPanel = function openQueryPanel() {
  const el = document.getElementById("queryView");
  if (el) {
    el.hidden = false;
    el.classList.add("visible");
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }
};

window.closeQueryPanel = function closeQueryPanel() {
  const el = document.getElementById("queryView");
  if (el) {
    el.hidden = true;
    el.classList.remove("visible");
  }
};

window.openLoginModal = function openLoginModal() {
  const backdrop = document.getElementById("loginModalBackdrop");
  if (backdrop) backdrop.hidden = false;
  document.getElementById("profileNameInput")?.focus();
};

window.closeLoginModal = function closeLoginModal() {
  const backdrop = document.getElementById("loginModalBackdrop");
  if (backdrop) backdrop.hidden = true;
};

async function handleGeneralChatSubmit(event) {
  if (event) event.preventDefault();
  clearStatuses();
  const input = document.querySelector('#generalChatForm textarea[name="question"]');
  if (!input) return;
  const question = String(input.value || "").trim();
  if (!question) {
    setGeneralStatus("请先输入消息。", true);
    return;
  }
  if (!state.generalSessionId) {
    state.generalSessionId = localStorage.getItem(generalSessionStorageKey()) || generateSessionId();
  }
  const createdAt = new Date().toISOString();
  pushGeneralChatMessage("user", question, createdAt);
  input.value = "";
  setGeneralStatus("正在生成回复...");
  const sendBtn = document.getElementById("generalSendBtn");
  if (sendBtn) sendBtn.disabled = true;

  try {
    const data = await request("/api/v1/mcp/agent/query", {
      method: "POST",
      body: JSON.stringify({
        question,
        session_id: state.generalSessionId,
        chat_mode: "general",
        conversation_context: buildGeneralConversationContext(),
      }),
    });
    if (data?.session_id) state.generalSessionId = data.session_id;
    const answer = String(data?.answer || "Response received.");
    pushGeneralChatMessage("assistant", answer, new Date().toISOString());
    setGeneralStatus(data?.short_term_memory_count != null
      ? `已保存最近对话，短期消息数：${data.short_term_memory_count}`
      : "已保存最近对话。");
  } catch (error) {
    pushGeneralChatMessage("system", `请求失败：${error.message}`, new Date().toISOString());
    setGeneralStatus(error.message, true);
  } finally {
    persistGeneralChatMessages();
    if (sendBtn) sendBtn.disabled = false;
    input?.focus();
  }
}

async function handleMultimodalSubmit(event) {
  event.preventDefault();
  if (handleMultimodalSubmit._sending) return;
  handleMultimodalSubmit._sending = true;
  setSendButtonState(true);
  clearStatuses();

  const form = document.getElementById("multimodalForm");
  const question = String(form.elements.namedItem("question")?.value || "").trim();
  const shortTermMemory = buildShortTermMemory(SHORT_TERM_ROUND_LIMIT);
  const conversationContext = buildClientConversationContext(SHORT_TERM_ROUND_LIMIT);
  const initialImage = form.elements.namedItem("image")?.files?.[0] || null;
  const hasImage = Boolean(initialImage && initialImage.size > 0);

  if (!question) {
    setStatus("multimodalStatus", "请先输入问题。", true);
    handleMultimodalSubmit._sending = false;
    setSendButtonState(false);
    return;
  }

  if (!state.patientId && !state.authToken) {
    setStatus("multimodalStatus", "请先填写并绑定个人信息后，再开启记忆聊天。", true);
    handleMultimodalSubmit._sending = false;
    setSendButtonState(false);
    return;
  }

  switchWorkspace("chat");
  setChatSubMode("memory");
  ensureSessionId(false);

  const userBubble = hasImage ? `${question}\n[已附带图片]` : question;
  pushChatMessage("user", userBubble, new Date().toISOString(), { trackShortTerm: true });
  form.elements.namedItem("question").value = "";
  keepChatInView();

  const sendOnce = async () => {
    const payload = new FormData(form);
    const requestHasImage = Boolean(payload.get("image") instanceof File && payload.get("image").size > 0);
    payload.set("question", question);
    payload.set("session_id", state.sessionId);
    payload.set("chat_mode", "memory");
    payload.set("short_term_memory_json", JSON.stringify(shortTermMemory));
    if (!payload.get("patient_id") && state.patientId) payload.set("patient_id", state.patientId);
    if (!payload.get("hospital_id") && state.hospitalId) payload.set("hospital_id", state.hospitalId);
    const effectiveAuthToken = normalizeAuthToken(payload.get("auth_token") || state.authToken);
    if (looksLikeIssuedAuthToken(effectiveAuthToken)) payload.set("auth_token", effectiveAuthToken);
    else payload.delete("auth_token");

    if (requestHasImage) {
      if (conversationContext) payload.set("conversation_context", conversationContext);
      return { hasImage: true, data: await request("/api/v1/mcp/agent/query-with-image", { method: "POST", body: payload }) };
    }

    payload.delete("image");
    const body = { question, session_id: state.sessionId, chat_mode: "memory" };
    const patientId = String(payload.get("patient_id") || "").trim();
    const hospitalId = String(payload.get("hospital_id") || "").trim();
    const authToken = normalizeAuthToken(payload.get("auth_token") || "");
    if (patientId) body.patient_id = patientId;
    if (hospitalId) body.hospital_id = hospitalId;
    if (looksLikeIssuedAuthToken(authToken)) body.auth_token = authToken;
    if (conversationContext) body.conversation_context = conversationContext;
    return { hasImage: false, data: await request("/api/v1/mcp/agent/query", { method: "POST", body: JSON.stringify(body) }) };
  };

  try {
    let result;
    try {
      result = await sendOnce();
    } catch (error) {
      const detail = String(error?.message || "");
      if (detail.toLowerCase().includes("token") && detail.includes("过期") && state.patientId) {
        setStatus("multimodalStatus", "认证 token 已过期，正在自动重新签发...", false);
        await issueTokenForCurrentPatient();
        result = await sendOnce();
      } else { throw error; }
    }

    const data = result.data;
    setStructuredShortTermMemory(data.short_term_memory || null);
    const assistantText = data.image_analysis
      ? `${data.answer || "Response received."}\n\nImage summary: ${data.image_analysis}`
      : (data.answer || "Response received.");
    pushChatMessage("assistant", assistantText, new Date().toISOString(), { trackShortTerm: true });
    state.sessionId = data.session_id || state.sessionId;
    updateSessionDisplays();
    await loadConversationSessions(true).catch(() => {});
    setStatus("multimodalStatus", `${result.hasImage ? "图文" : "文本"}问答成功。短期记忆条数：${data.short_term_memory_count ?? 0}。`, false);
    setOutput(result.hasImage ? "图文问答成功" : "文本问答成功", data, { syncAnswer: false });
    form.elements.namedItem("image").value = "";
    const fileNameEl = document.getElementById("imageFileName");
    if (fileNameEl) { fileNameEl.textContent = ""; fileNameEl.title = ""; }
    document.querySelector('#multimodalForm textarea[name="question"]')?.focus();
    keepChatInView();
  } catch (error) {
    const rawError = String(error.message || "");
    const needIdentity = rawError.includes("identity confirmation required") || rawError.includes("patient-bound");
    if (needIdentity) {
      const fallbackMessage = "请在左上角填写你的姓名和电话。";
      pushChatMessage("assistant", fallbackMessage, new Date().toISOString(), { trackShortTerm: true });
      setAnswer(fallbackMessage);
      setStatus("multimodalStatus", "需要先确认本次咨询对象。", false);
      setOutput("等待身份确认", { identity_status: "unconfirmed", message: fallbackMessage });
    } else {
      pushChatMessage("system", `请求失败： ${error.message}`);
      setStatus("multimodalStatus", error.message, true);
      setOutput(hasImage ? "图文问答失败" : "文本问答失败", { error: error.message });
    }
    keepChatInView();
  } finally {
    handleMultimodalSubmit._sending = false;
    setSendButtonState(false);
    document.querySelector('#multimodalForm textarea[name="question"]')?.focus();
  }
}

function initNavigation() {
  document.getElementById("chatViewBtn")?.addEventListener("click", () => switchWorkspace("general"));
  document.getElementById("memoryViewBtn")?.addEventListener("click", () => switchWorkspace("memory"));
  document.getElementById("toggleQueryPanelBtn")?.addEventListener("click", () => switchWorkspace("query"));
  document.getElementById("queryPanelCloseBtn")?.addEventListener("click", () => switchWorkspace("general"));

  document.getElementById("openLoginModalBtn")?.addEventListener("click", openLoginModal);
  document.getElementById("loginModalCloseBtn")?.addEventListener("click", closeLoginModal);
  document.getElementById("loginModalBackdrop")?.addEventListener("click", (e) => {
    if (e.target === e.currentTarget) closeLoginModal();
  });

  const generalChatForm = document.getElementById("generalChatForm");
  if (generalChatForm) generalChatForm.addEventListener("submit", handleGeneralChatSubmit);

  document.getElementById("generalNewChatBtn")?.addEventListener("click", () => {
    resetGeneralChat(true, "新的通用对话已准备就绪。");
    setGeneralStatus("已新建通用对话。");
  });

  const generalQuestionInput = document.querySelector('#generalChatForm textarea[name="question"]');
  if (generalQuestionInput) {
    generalQuestionInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        if (generalChatForm && typeof generalChatForm.requestSubmit === "function") generalChatForm.requestSubmit();
        else handleGeneralChatSubmit(event);
      }
    });
  }

  const multimodalForm = document.getElementById("multimodalForm");
  if (multimodalForm) multimodalForm.addEventListener("submit", handleMultimodalSubmit);

  const sendMessageBtn = document.getElementById("sendMessageBtn");
  if (sendMessageBtn) sendMessageBtn.addEventListener("click", handleMultimodalSubmit);

  const questionInput = document.querySelector('#multimodalForm textarea[name="question"]');
  if (questionInput) {
    questionInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        if (!handleMultimodalSubmit._sending) handleMultimodalSubmit(event);
      }
    });
  }

  const imageFileInput = document.getElementById("imageFileInput");
  const imageFileName = document.getElementById("imageFileName");
  if (imageFileInput && imageFileName) {
    imageFileInput.addEventListener("change", () => {
      const file = imageFileInput.files?.[0];
      imageFileName.textContent = file ? file.name : "";
      imageFileName.title = file ? file.name : "";
    });
  }

  const chatTranscript = document.getElementById("chatTranscript");
  if (chatTranscript) {
    chatTranscript.addEventListener("wheel", (event) => {
      const maxScroll = chatTranscript.scrollHeight - chatTranscript.clientHeight;
      if (maxScroll <= 0) return;
      const nextScrollTop = Math.max(0, Math.min(maxScroll, chatTranscript.scrollTop + event.deltaY));
      if (nextScrollTop !== chatTranscript.scrollTop) {
        event.preventDefault();
        chatTranscript.scrollTop = nextScrollTop;
      }
    }, { passive: false });
  }
}

async function initializePage() {
  state.sessionId = "";
  state.patientId = "";
  state.hospitalId = "";
  state.authToken = "";
  state.profileName = "";
  state.profilePhone = "";
  applyProfileState({ name: "", phone: "" });
  setCurrentContext({ patientId: "", hospitalId: "", authToken: "" });
  state.generalRecentSessions = readStoredGeneralRecentSessions();
  state.generalSessionId = generateSessionId();
  setChatSubMode("general");
  state.generalChatMessages = [];
  renderGeneralChat("可以直接开始提问，或新建一段独立对话。");
  renderGeneralRecentSessions();
  renderSessionOptions();

  const chip = document.getElementById("memoryLoginChip");
  if (chip) chip.textContent = "未登录";
  setProfileLoginStatus("请先填写姓名和电话，再登录记忆聊天。", false);
  state.chatMessages = [];
  state.chatSessions = [];
  resetShortTermMemory();
  renderChat("登录后可开始记忆聊天。");
  updateSessionDisplays();
}

document.addEventListener("DOMContentLoaded", () => {
  initSidebar();
  initNavigation();
  initPatientEventListeners();
  speechModule.init();
  initializePage();
});

function initSidebar() {
  const toggleBtn = document.getElementById("sidebarToggleBtn");
  const overlay = document.getElementById("sidebarOverlay");
  const drawer = document.getElementById("sidebarDrawer");
  const closeBtn = document.getElementById("sidebarCloseBtn");
  const searchToggle = document.getElementById("sidebarSearchToggle");
  const searchBox = document.getElementById("sidebarSearchBox");
  const searchInput = document.getElementById("sidebarPhoneInput");
  const searchBtn = document.getElementById("sidebarSearchBtn");

  function openSidebar() {
    if (overlay) overlay.style.display = "block";
    if (drawer) drawer.classList.add("open");
  }
  function closeSidebar() {
    if (overlay) overlay.style.display = "none";
    if (drawer) drawer.classList.remove("open");
  }

  if (toggleBtn) toggleBtn.addEventListener("click", openSidebar);
  if (closeBtn) closeBtn.addEventListener("click", closeSidebar);
  if (overlay) overlay.addEventListener("click", closeSidebar);

  if (searchToggle && searchBox) {
    searchToggle.addEventListener("click", () => {
      const visible = searchBox.style.display !== "none";
      searchBox.style.display = visible ? "none" : "flex";
      if (!visible && searchInput) searchInput.focus();
    });
  }

  if (searchBtn && searchInput) {
    searchBtn.addEventListener("click", () => searchPatientsFromSidebar());
    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") searchPatientsFromSidebar();
    });
  }
}

async function searchPatientsFromSidebar() {
  const input = document.getElementById("sidebarPhoneInput");
  const status = document.getElementById("sidebarSearchStatus");
  const list = document.getElementById("sidebarPatientList");
  const query = (input?.value || "").trim();
  if (!query) { if (status) status.textContent = "请输入手机号或姓名"; return; }
  if (status) status.textContent = "搜索中...";

  try {
    const isPhone = /^\d{3,}$/.test(query);
    const params = new URLSearchParams();
    if (isPhone) params.set("phone", query);
    else params.set("name", query);
    const patients = await request(`/api/v1/patients?${params}`);
    if (list) {
      list.innerHTML = patients.map((p) => `
        <div class="sidebar-patient-item" data-patient-id="${p.id}">
          <div class="sidebar-patient-avatar">${(p.full_name || "?").charAt(0)}</div>
          <div class="sidebar-patient-info">
            <span class="name">${p.full_name}</span>
            <span class="meta">${p.phone || ""}</span>
          </div>
        </div>
      `).join("");
      list.querySelectorAll(".sidebar-patient-item").forEach((el) => {
        el.addEventListener("click", () => selectPatientFromSidebar(el.dataset.patientId));
      });
    }
    if (status) status.textContent = patients.length ? `找到 ${patients.length} 位患者` : "未找到患者";
  } catch (err) {
    if (status) status.textContent = `搜索失败: ${err.message}`;
  }
}

async function selectPatientFromSidebar(patientId) {
  const status = document.getElementById("sidebarSearchStatus");
  const card = document.getElementById("sidebarPatientCard");
  const empty = document.getElementById("sidebarPatientEmpty");
  const searchToggle = document.getElementById("sidebarSearchToggle");
  const searchBox = document.getElementById("sidebarSearchBox");
  try {
    const [patient, profile] = await Promise.all([
      request(`/api/v1/patients/${encodeURIComponent(patientId)}`),
      request(`/api/v1/memory/profile?patient_id=${encodeURIComponent(patientId)}`),
    ]);
    dispatch({ type: "SET_SELECTED_PATIENT", payload: patient });
    dispatch({ type: "SET_PATIENT_PROFILE", payload: profile });
    dispatch({
      type: "SET_PATIENT_CONTEXT",
      payload: {
        patientId: patient.id,
        hospitalId: patient.hospital_id,
        profileName: patient.full_name,
        profilePhone: patient.phone ?? "",
      },
    });
    if (card) {
      card.style.display = "block";
      card.innerHTML = `
        <div class="patient-card-header">
          <div class="patient-card-avatar">${(patient.full_name || "?").charAt(0)}</div>
          <div class="patient-card-info">
            <span class="name">${patient.full_name}</span>
            <span class="meta">${patient.patient_code} · ${patient.gender || ""}</span>
          </div>
        </div>
      `;
    }
    if (empty) empty.style.display = "none";
    if (searchToggle) searchToggle.style.display = "none";
    if (searchBox) searchBox.style.display = "none";
    if (status) status.textContent = `已绑定 ${patient.full_name}`;
  } catch (err) {
    if (status) status.textContent = `加载失败: ${err.message}`;
  }
}

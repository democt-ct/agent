window.request = async function request(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const body = options.body;
  if (!(body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const timeoutMs = options.timeout || (body instanceof FormData ? 180000 : 60000);
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  const signal = options.signal
    ? _combinedSignal(options.signal, controller.signal)
    : controller.signal;

  try {
    const response = await fetch(url, { ...options, headers, signal });
    clearTimeout(timeoutId);
    const text = await response.text();
    let data = text;
    try { data = text ? JSON.parse(text) : {}; } catch (_) {}

    if (!response.ok) {
      let detail = data;
      if (typeof data === "object" && data !== null) {
        if (Array.isArray(data.detail)) {
          detail = data.detail.map((item) => {
            if (typeof item === "object" && item !== null) {
              const location = Array.isArray(item.loc) ? item.loc.join(".") : "";
              const message = String(item.msg || "").trim();
              return location ? `${location}: ${message}` : message;
            }
            return String(item);
          }).filter(Boolean).join("; ");
        } else {
          detail = data.detail || JSON.stringify(data, null, 2);
        }
      }
      throw new Error(detail || `请求失败： ${response.status}`);
    }
    return data;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === "AbortError") {
      throw new Error("请求超时，请检查网络或稍后重试。");
    }
    throw error;
  }
};

function _combinedSignal(signalA, signalB) {
  if (signalA.aborted || signalB.aborted) return AbortSignal.abort();
  const controller = new AbortController();
  const onAbort = () => controller.abort();
  signalA.addEventListener("abort", onAbort, { once: true });
  signalB.addEventListener("abort", onAbort, { once: true });
  if (signalA.aborted || signalB.aborted) {
    controller.abort();
  }
  return controller.signal;
}

window.promoteAnonymousSessionToPatient = async function promoteAnonymousSessionToPatient() {
  if (!state.patientId || !state.sessionId) return null;
  return request("/api/v1/memory/conversations/promote-session", {
    method: "POST",
    body: JSON.stringify({
      patient_id: state.patientId,
      hospital_id: state.hospitalId || null,
      session_id: state.sessionId,
    }),
  });
};

window.loadConversationHistory = async function loadConversationHistory(silent = false) {
  if (!state.patientId) throw new Error("请先选择患者。");
  ensureSessionId(false);
  await promoteAnonymousSessionToPatient().catch(() => null);
  const query = new URLSearchParams({
    patient_id: state.patientId,
    session_id: state.sessionId,
    limit: "100",
  }).toString();
  const messages = await request(`/api/v1/memory/conversations/messages?${query}`);
  state.chatMessages = Array.isArray(messages) ? messages.map((item) => ({
    role: item.role,
    content: item.content,
    created_at: item.created_at,
  })) : [];
  resetShortTermMemory();
  persistChatMessages();
  renderChat(state.chatMessages.length ? "" : "当前会话还没有已保存的消息。");
  const lastAssistant = [...state.chatMessages].reverse().find((item) => item.role === "assistant");
  if (lastAssistant && lastAssistant.content) {
    syncLatestMemoryAnswer(lastAssistant.content, "已加载记忆聊天最新回答");
  }
  renderSessionOptions();
  if (!silent) {
    setStatus("contextStatus", `已加载当前会话的 ${state.chatMessages.length} 条消息。`, false);
  }
  return messages;
};

window.loadConversationSessions = async function loadConversationSessions(silent = false) {
  if (!state.patientId) {
    state.chatSessions = [];
    renderSessionOptions();
    return [];
  }
  if (state.sessionId) {
    await promoteAnonymousSessionToPatient().catch(() => null);
  }
  const query = new URLSearchParams({
    patient_id: state.patientId,
    limit: "12",
  }).toString();
  const sessions = await request(`/api/v1/memory/conversations/sessions?${query}`);
  state.chatSessions = Array.isArray(sessions) ? sessions : [];
  renderSessionOptions();
  if (!silent) {
    setStatus("contextStatus", `已加载当前患者的 ${state.chatSessions.length} 个已保存会话。`, false);
  }
  return state.chatSessions;
};

window.deleteCurrentPatient = async function deleteCurrentPatient() {
  if (!state.patientId) throw new Error("当前上下文中没有 patient_id。");
  const data = await request(`/api/v1/patients/${state.patientId}`, { method: "DELETE" });
  if (state.patientId) {
    localStorage.removeItem(sessionStorageKey(state.patientId));
  }
  setCurrentContext({ patientId: "", hospitalId: state.hospitalId, authToken: "" });
  return data;
};

window.issueTokenForCurrentPatient = async function issueTokenForCurrentPatient() {
  if (!state.patientId) throw new Error("当前上下文中没有 patient_id。");
  const payload = {
    patient_id: state.patientId,
    hospital_id: state.hospitalId || undefined,
    expires_in_minutes: 120,
  };
  const data = await request("/api/v1/mcp/auth/issue-token", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const token = data?.data?.auth_token || "";
  setCurrentContext({ authToken: token });
  return token;
};

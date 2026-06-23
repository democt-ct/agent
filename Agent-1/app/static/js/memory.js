window.renderMemoryDebugCards = function renderMemoryDebugCards(debugPayload) {
  const container = document.getElementById("memoryDebugCards");
  if (!container) return;

  const payload = debugPayload && typeof debugPayload === "object" ? debugPayload : null;
  if (!payload) {
    container.innerHTML = `<div class="memory-debug-empty">当前没有可展示的记忆调试信息。</div>`;
    return;
  }

  const sessionState = payload.working_memory?.session_state || {};
  const activeEntities = payload.working_memory?.active_entities || {};
  const riskSignals = payload.working_memory?.risk_signals || {};
  const memoryLayers = payload.memory_layers || {};
  const recentMessages = Array.isArray(payload.working_memory?.recent_messages) ? payload.working_memory.recent_messages : [];

  const entityItems = []
    .concat((activeEntities.drugs || []).map((item) => `药物：${item}`))
    .concat((activeEntities.symptoms || []).map((item) => `症状：${item}`))
    .concat((activeEntities.tests || []).map((item) => `检查：${item}`))
    .concat((activeEntities.metrics || []).map((item) => `指标：${item}`));

  const riskItems = []
    .concat((riskSignals.red_flags || []).map((item) => `红旗：${item}`))
    .concat((riskSignals.medication_flags || []).map((item) => `用药：${item}`))
    .concat((riskSignals.monitoring_flags || []).map((item) => `监测：${item}`));

  const hasRedOrMed = (riskSignals.red_flags && riskSignals.red_flags.length > 0)
                   || (riskSignals.medication_flags && riskSignals.medication_flags.length > 0);
  const adviceStatus = hasRedOrMed
    ? "本轮已自动追加就医/用药安全建议"
    : "本轮未触发安全建议";

  const recentPreview = recentMessages.slice(-4).map((item) => {
    const role = item.role === "assistant" ? "助手" : (item.role === "user" ? "用户" : "系统");
    return `${role}：${String(item.content || "").trim()}`;
  });

  const cards = [
    {
      title: "工作记忆",
      body: [
        `意图：${sessionState.intent || "无"}`,
        `当前主题：${sessionState.current_topic || "无"}`,
        `目标：${sessionState.goal || "无"}`,
        `工作摘要：${sessionState.working_summary || "无"}`,
        `下一步：${sessionState.next_action || "无"}`,
        `记忆焦点：${sessionState.memory_focus || "无"}`,
      ].join("\n"),
      items: recentPreview,
    },
    {
      title: "事实记忆",
      body: memoryLayers.factual_memory || "当前这轮没有命中患者事实记忆。",
      items: [],
    },
    {
      title: "长期摘要记忆",
      body: memoryLayers.long_term_summary_memory || "当前这轮没有命中长期摘要记忆。",
      items: [],
    },
    {
      title: "知识记忆",
      body: memoryLayers.knowledge_memory || "当前这轮没有命中知识记忆。",
      items: [],
    },
    {
      title: "短期记忆上下文",
      body: memoryLayers.short_term_memory || "当前这轮还没有形成可复用的短期工作记忆，多见于首轮提问或上下文较少时。",
      items: entityItems.slice(0, 6),
    },
    {
      title: "风险信号与安全建议",
      body: [
        `最近助手摘要：${sessionState.last_assistant_summary || "无"}`,
        adviceStatus,
      ].join("\n"),
      items: (riskItems.length ? riskItems : ["当前未提取到明显风险信号"]).slice(0, 6),
    },
    {
      title: "当前识别到的实体",
      body: entityItems.length ? "以下实体来自最近几轮对话中的显式提取。" : "当前还没有识别到稳定的药物、症状、检查或指标实体。",
      items: entityItems.slice(0, 8),
    },
  ];

  container.innerHTML = cards.map((card) => `
    <section class="memory-debug-card">
      <h3>${escapeHtml(card.title)}</h3>
      <p>${escapeHtml(String(card.body || "").trim() || "无")}</p>
      ${Array.isArray(card.items) && card.items.length
        ? `<ul>${card.items.map((item) => `<li>${escapeHtml(String(item || "").trim())}</li>`).join("")}</ul>`
        : ""
      }
    </section>
  `).join("");
};

window.setOutput = function setOutput(title, data, options = {}) {
  const { syncAnswer = true } = options;
  const lastActionEl = document.getElementById("lastAction");
  const outputEl = document.getElementById("output");
  const memoryDebugOutput = document.getElementById("memoryDebugOutput");

  if (lastActionEl) lastActionEl.textContent = title;
  if (outputEl) outputEl.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);

  if (memoryDebugOutput) {
    const debugPayload = data && typeof data === "object" && data.memory_debug
      ? data.memory_debug
      : {
          message: title.includes("图文")
            ? "当前这次图文问答返回里没有带出 memory debug。"
            : "当前返回里没有 memory debug。",
        };
    renderMemoryDebugCards(debugPayload);
    memoryDebugOutput.textContent = JSON.stringify(debugPayload, null, 2);
  }

  if (data && typeof data === "object") {
    if (syncAnswer) {
      state.lastSpeechText = data.speech_text || data.answer || state.lastSpeechText || "";
    }
    if (data.patient_id && data.patient_id !== state.patientId) {
      state.patientId = String(data.patient_id || "").trim();
      state.hospitalId = String(data.hospital_id || state.hospitalId || "").trim();
      const pidEl = document.getElementById("currentPatientId");
      const hidEl = document.getElementById("currentHospitalId");
      const badge = document.getElementById("queryPatientBadge");
      if (pidEl) pidEl.textContent = state.patientId || "未绑定";
      if (hidEl) hidEl.textContent = state.hospitalId || "未设置";
      if (badge) badge.textContent = state.patientId || "未设置";
      const lookupInput = document.getElementById("lookupPatientId");
      const medicalInput = document.getElementById("medicalPatientId");
      const visitInput = document.getElementById("visitPatientId");
      if (lookupInput) lookupInput.value = state.patientId;
      if (medicalInput) medicalInput.value = state.patientId;
      if (visitInput) visitInput.value = state.patientId;
      persistContext();
      if (state.patientId && state.sessionId) promoteAnonymousSessionToPatient().catch(() => {});
    }
    if (data.session_id) {
      state.sessionId = data.session_id;
      updateSessionDisplays();
    }
  }
  if (syncAnswer && data && typeof data === "object" && data.answer) setAnswer(data.answer);
};

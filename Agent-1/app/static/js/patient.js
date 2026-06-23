window.fillPatientForm = function fillPatientForm(preset) {
  const form = document.getElementById("patientForm");
  Object.entries(preset).forEach(([key, value]) => {
    const field = form.elements.namedItem(key);
    if (field) field.value = value;
  });
  setCurrentContext({ hospitalId: preset.hospital_id, patientId: state.patientId, authToken: state.authToken });
  setStatus("patientStatus", `${preset.full_name} / ${preset.patient_code} 已加载到表单。`);
};

window.runLookup = async function runLookup(kind) {
  clearStatuses();
  const patientId = document.getElementById("lookupPatientId").value.trim();
  if (!patientId) {
    setStatus("lookupStatus", "请先输入 patient_id。", true);
    return;
  }
  const endpoints = {
    patient: { url: `/api/v1/patients/${patientId}`, title: "获取患者信息" },
    medical: { url: `/api/v1/patients/${patientId}/medical-records`, title: "获取病历记录" },
    visit: { url: `/api/v1/patients/${patientId}/visits`, title: "获取就诊记录" },
    profile: { url: `/api/v1/memory/profile?patient_id=${encodeURIComponent(patientId)}`, title: "获取记忆档案" },
  };
  try {
    const data = await request(endpoints[kind].url);
    if (kind === "patient" && data.id) {
      setCurrentContext({ patientId: data.id, hospitalId: data.hospital_id, authToken: "" });
      await loadConversationSessions(true).catch(() => {});
      await loadConversationHistory(true).catch(() => {});
    }
    if (kind === "profile" && data.patient && data.patient.id) {
      setCurrentContext({ patientId: data.patient.id, hospitalId: data.patient.hospital_id, authToken: "" });
      await loadConversationSessions(true).catch(() => {});
      await loadConversationHistory(true).catch(() => {});
    }
    setStatus("lookupStatus", `${endpoints[kind].title} 成功。`);
    setOutput(endpoints[kind].title, data);
  } catch (error) {
    setStatus("lookupStatus", error.message, true);
    setOutput(`${endpoints[kind].title} failed`, { error: error.message });
  }
};

window.resolvePatientFromPersonalInfo = async function resolvePatientFromPersonalInfo() {
  clearStatuses();
  const nameInput = document.getElementById("profileNameInput");
  const phoneInput = document.getElementById("profilePhoneInput");
  const name = String(nameInput?.value || "").trim();
  const phone = String(phoneInput?.value || "").trim();
  applyProfileState({ name, phone });
  if (!name && !phone) {
    setStatus("contextStatus", "请先填写姓名和电话。", true);
    setProfileLoginStatus("请先填写姓名和电话。", true);
    return [];
  }
  const hospitalId = String(state.hospitalId || "hospital-a").trim() || "hospital-a";
  const data = await request(`/api/v1/patients?hospital_id=${encodeURIComponent(hospitalId)}${phone ? `&phone=${encodeURIComponent(phone)}` : ""}`);
  const normalizedName = normalizePersonalName(name);
  const normalizedPhone = phone.replace(/\D/g, "");
  const matches = Array.isArray(data)
    ? data.filter((patient) => {
        const patientName = normalizePersonalName(patient.full_name);
        const patientPhone = String(patient.phone || "").replace(/\D/g, "");
        const nameOk = !normalizedName || patientName === normalizedName || patientName.includes(normalizedName) || normalizedName.includes(patientName);
        const phoneOk = !normalizedPhone || patientPhone.includes(normalizedPhone);
        return nameOk && phoneOk;
      })
    : [];

  if (matches.length === 1) {
    const patient = matches[0];
    ensureSessionId(false);
    setCurrentContext({ patientId: patient.id, hospitalId: patient.hospital_id, authToken: "", sessionId: state.sessionId, preserveSession: true });
    state.hospitalId = patient.hospital_id;
    await promoteAnonymousSessionToPatient().catch(() => {});
    setStatus("contextStatus", `已识别为 ${patient.full_name}，当前对话已归属该患者，可以继续问诊。`, false);
    setProfileLoginStatus(`已识别为 ${patient.full_name}，已切换到记忆聊天。`, false);
    updateMemoryLoginHint(`已登录：${patient.full_name}，系统已切换到记忆聊天。`);
    switchWorkspace("chat");
    setChatSubMode("memory");
    closeLoginModal();
    await loadConversationSessions(true).catch(() => {});
  } else if (matches.length > 1) {
    setStatus("contextStatus", `找到 ${matches.length} 位可能匹配的患者，请再补充一点信息。`, true);
    setProfileLoginStatus(`找到 ${matches.length} 位可能匹配的患者，请补充更准确的信息。`, true);
    setOutput("个人信息匹配结果", matches);
    updateMemoryLoginHint("请先填写并绑定个人信息后，再开启记忆聊天。");
  } else {
    setStatus("contextStatus", "已保存个人信息，但暂时没有找到对应患者。", true);
    setProfileLoginStatus("没有找到对应患者，请检查姓名或电话是否填写正确。", true);
    setOutput("个人信息匹配结果", { name, phone, matches: [] });
    updateMemoryLoginHint("请先填写并绑定个人信息后，再开启记忆聊天。");
  }
  return matches;
};

function initPatientEventListeners() {
  document.getElementById("patientForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearStatuses();
    const payload = formToObject(event.currentTarget);
    try {
      const data = await request("/api/v1/patients", { method: "POST", body: JSON.stringify(payload) });
      setCurrentContext({ patientId: data.id, hospitalId: data.hospital_id, authToken: "" });
      await loadConversationSessions(true).catch(() => {});
      setStatus("patientStatus", `患者已创建，patient_id = ${data.id}`);
      setOutput("创建患者成功", data);
    } catch (error) {
      setStatus("patientStatus", error.message, true);
      setOutput("创建患者失败", { error: error.message });
    }
  });

  document.getElementById("patientQueryForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearStatuses();
    const query = new URLSearchParams(formToObject(event.currentTarget)).toString();
    try {
      const data = await request(`/api/v1/patients?${query}`);
      const first = Array.isArray(data) && data[0] ? data[0] : null;
      if (first) {
        setCurrentContext({ patientId: first.id, hospitalId: first.hospital_id, authToken: "" });
        await loadConversationSessions(true).catch(() => {});
        await loadConversationHistory(true).catch(() => {});
        setStatus("patientQueryStatus", `找到 ${data.length} 位患者；已将第一位设为当前上下文。`);
      } else {
        setStatus("patientQueryStatus", "查询成功，但没有找到患者。", false);
      }
      setOutput("查询患者列表", data);
    } catch (error) {
      setStatus("patientQueryStatus", error.message, true);
      setOutput("查询患者列表 failed", { error: error.message });
    }
  });

  document.getElementById("medicalRecordForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearStatuses();
    const payload = formToObject(event.currentTarget);
    const patientId = payload.patient_id;
    delete payload.patient_id;
    try {
      const data = await request(`/api/v1/patients/${patientId}/medical-records`, { method: "POST", body: JSON.stringify(payload) });
      setStatus("medicalStatus", "病历已保存。", false);
      setOutput("创建病历成功", data);
    } catch (error) {
      setStatus("medicalStatus", error.message, true);
      setOutput("创建病历失败", { error: error.message });
    }
  });

  document.getElementById("visitForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearStatuses();
    const payload = formToObject(event.currentTarget);
    const patientId = payload.patient_id;
    delete payload.patient_id;
    try {
      const data = await request(`/api/v1/patients/${patientId}/visits`, { method: "POST", body: JSON.stringify(payload) });
      setStatus("visitStatus", "就诊记录已保存。", false);
      setOutput("创建就诊记录成功", data);
    } catch (error) {
      setStatus("visitStatus", error.message, true);
      setOutput("创建就诊记录失败", { error: error.message });
    }
  });

  document.getElementById("getPatientBtn")?.addEventListener("click", () => runLookup("patient"));
  document.getElementById("getMedicalBtn")?.addEventListener("click", () => runLookup("medical"));
  document.getElementById("getVisitBtn")?.addEventListener("click", () => runLookup("visit"));
  document.getElementById("getProfileBtn")?.addEventListener("click", () => runLookup("profile"));

  document.getElementById("fillPreset1Btn")?.addEventListener("click", () => fillPatientForm(patientPresets[0]));
  document.getElementById("fillPreset2Btn")?.addEventListener("click", () => fillPatientForm(patientPresets[1]));
  document.getElementById("fillPreset3Btn")?.addEventListener("click", () => fillPatientForm(patientPresets[2]));

  document.getElementById("issueTokenBtn")?.addEventListener("click", async () => {
    clearStatuses();
    try {
      await issueTokenForCurrentPatient();
      setStatus("contextStatus", "已为当前患者签发 auth_token。", false);
      setOutput("签发 token 成功", { patient_id: state.patientId, hospital_id: state.hospitalId, auth_token_set: true });
    } catch (error) {
      setStatus("contextStatus", error.message, true);
      setOutput("签发 token 失败", { error: error.message });
    }
  });

  document.getElementById("newSessionBtn")?.addEventListener("click", () => {
    clearStatuses();
    switchWorkspace("chat");
    setChatSubMode("memory");
    resetChat(true, "新的对话会话已准备就绪。");
    renderSessionOptions();
    setStatus("contextStatus", `已启动新会话：${state.sessionId}`, false);
    setOutput("新会话已创建", { session_id: state.sessionId, patient_id: state.patientId || null });
  });

  document.getElementById("loadSelectedSessionBtn")?.addEventListener("click", async () => {
    clearStatuses();
    try {
      const sessionId = String(document.getElementById("chatSessionSelect")?.value || "").trim();
      if (!sessionId) throw new Error("请先选择一条已保存会话。");
      selectSession(sessionId);
      await loadConversationHistory(false);
      setOutput("加载所选会话", { patient_id: state.patientId, session_id: state.sessionId, message_count: state.chatMessages.length });
    } catch (error) {
      setStatus("contextStatus", error.message, true);
      setOutput("加载所选会话 failed", { error: error.message });
    }
  });

  document.getElementById("deleteSelectedSessionBtn")?.addEventListener("click", async () => {
    clearStatuses();
    try {
      const sessionId = String(document.getElementById("chatSessionSelect")?.value || "").trim();
      if (!sessionId) throw new Error("请先选择一条已保存会话。");
      if (!state.patientId) throw new Error("请先确认当前患者。");
      const data = await request(`/api/v1/memory/conversations/messages?patient_id=${encodeURIComponent(state.patientId)}&session_id=${encodeURIComponent(sessionId)}`, { method: "DELETE" });
      if (sessionId === state.sessionId) {
        localStorage.removeItem(sessionStorageKey(state.patientId));
        state.sessionId = "";
        state.chatMessages = [];
        resetShortTermMemory();
        persistChatMessages();
        updateSessionDisplays();
        renderChat("该会话已删除，可以开始新的对话。");
      }
      await loadConversationSessions(true).catch(() => {});
      setStatus("contextStatus", "所选会话已删除。", false);
      setOutput("删除所选会话成功", data);
    } catch (error) {
      setStatus("contextStatus", error.message, true);
      setOutput("删除所选会话失败", { error: error.message });
    }
  });

  document.getElementById("deleteCurrentPatientBtn")?.addEventListener("click", async () => {
    clearStatuses();
    try {
      const data = await deleteCurrentPatient();
      setStatus("contextStatus", "当前患者已删除。", false);
      setOutput("删除患者成功", data);
    } catch (error) {
      setStatus("contextStatus", error.message, true);
      setOutput("删除患者失败", { error: error.message });
    }
  });

  document.getElementById("clearContextBtn")?.addEventListener("click", () => {
    clearStatuses();
    applyProfileState({ name: "", phone: "" });
    setCurrentContext({ patientId: "", hospitalId: "", authToken: "" });
    setOutput("上下文已清空", { message: "patient_id、hospital_id、auth_token 与当前会话已清空。" });
  });

  document.getElementById("applyProfileBtn")?.addEventListener("click", () => {
    resolvePatientFromPersonalInfo().catch((error) => {
      setStatus("contextStatus", error.message, true);
      setProfileLoginStatus(error.message, true);
    });
  });

  document.getElementById("clearProfileBtn")?.addEventListener("click", () => {
    applyProfileState({ name: "", phone: "" });
    setCurrentContext({ patientId: "", hospitalId: "", authToken: "", sessionId: state.sessionId, preserveSession: true });
    switchWorkspace("chat");
    setChatSubMode("general");
    setStatus("contextStatus", "已清空个人信息，已切回通用聊天。", false);
    setProfileLoginStatus("已清空个人信息。", false);
  });

  const profileNameInput = document.getElementById("profileNameInput");
  const profilePhoneInput = document.getElementById("profilePhoneInput");
  if (profileNameInput) profileNameInput.addEventListener("input", () => applyProfileState({ name: profileNameInput.value, phone: profilePhoneInput?.value || "" }));
  if (profilePhoneInput) profilePhoneInput.addEventListener("input", () => applyProfileState({ name: profileNameInput?.value || "", phone: profilePhoneInput.value }));

  initPatientQuickSelect();
}

function initPatientQuickSelect() {
  const loadBtn = document.getElementById("loadPatientListBtn");
  const quickSelect = document.getElementById("patientQuickSelect");
  const quickStatus = document.getElementById("patientQuickStatus");
  if (!loadBtn || !quickSelect) return;

  loadBtn.addEventListener("click", async () => {
    loadBtn.disabled = true;
    loadBtn.textContent = "加载中...";
    if (quickStatus) quickStatus.textContent = "";
    try {
      const hospitalId = state.hospitalId || "hospital-a";
      let patients = [];
      try {
        const data = await request(`/api/v1/patients?hospital_id=${encodeURIComponent(hospitalId)}`);
        patients = Array.isArray(data) ? data : [];
      } catch (_) {}
      if (!patients.length) {
        if (quickStatus) quickStatus.textContent = "数据库暂无患者，自动从预设创建中...";
        for (const preset of patientPresets) {
          try { patients.push(await request("/api/v1/patients", { method: "POST", body: JSON.stringify(preset) })); } catch (_) {}
        }
      }
      quickSelect.innerHTML = '<option value="">— 选择患者 —</option>';
      patients.forEach((p) => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = `${p.full_name} (${p.patient_code || p.id})`;
        quickSelect.appendChild(opt);
      });
      if (quickStatus) quickStatus.textContent = patients.length ? `已加载 ${patients.length} 位患者` : "未找到患者，请手动创建";
    } catch (e) {
      if (quickStatus) quickStatus.textContent = "加载失败：" + (e.message || e);
    } finally {
      loadBtn.disabled = false;
      loadBtn.textContent = "加载患者列表";
    }
  });

  quickSelect.addEventListener("change", async () => {
    const patientId = quickSelect.value;
    if (!patientId) return;
    try {
      const patient = await request(`/api/v1/patients/${patientId}`);
      setCurrentContext({ patientId: patient.id, hospitalId: patient.hospital_id, authToken: "" });
      try {
        const tokenResp = await request("/api/v1/mcp/auth/issue-token", {
          method: "POST",
          body: JSON.stringify({ patient_id: patient.id, expires_in_minutes: 120 }),
        });
        if (tokenResp?.data?.auth_token) {
          state.authToken = tokenResp.data.auth_token;
          const atEl = document.getElementById("currentAuthToken");
          if (atEl) atEl.textContent = state.authToken.slice(0, 16) + "...";
        }
      } catch (_) {}
      switchWorkspace("chat");
      setChatSubMode("memory");
      await loadConversationSessions(true).catch(() => {});
      if (quickStatus) quickStatus.textContent = `已选择：${patient.full_name}`;
      const nameInput = document.getElementById("profileNameInput");
      const phoneInput = document.getElementById("profilePhoneInput");
      if (nameInput) nameInput.value = patient.full_name || "";
      if (phoneInput) phoneInput.value = patient.phone || "";
      state.profileName = patient.full_name || "";
      state.profilePhone = patient.phone || "";
      updateSessionDisplays();
    } catch (e) {
      if (quickStatus) quickStatus.textContent = "切换失败：" + (e.message || e);
    }
  });
}

window.initPatientEventListeners = initPatientEventListeners;

window.escapeHtml = function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
};

window.formatTime = function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("zh-CN", { hour12: false });
};

window.stripMarkdownMarkers = function stripMarkdownMarkers(text) {
  const value = String(text || "");
  return value
    .replace(/```[\s\S]*?```/g, (block) => block.replace(/```/g, ""))
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/_([^_]+)_/g, "$1")
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    .trim();
};

window.normalizePersonalName = function normalizePersonalName(value) {
  return String(value || "")
    .trim()
    .replace(/[，。,.!！？?、\s]+/g, "")
    .replace(/^(我是|叫|我叫|本人|家属|患者)/, "")
    .replace(/(阿姨|叔叔|大爷|大妈|阿伯|伯伯|姐姐|哥哥|妹妹|弟弟|老师|女士|先生|家属)$/, "");
};

window.normalizeAuthToken = function normalizeAuthToken(value) {
  const token = String(value || "").trim();
  if (!token) return "";
  const lowered = token.toLowerCase();
  if (["string", "null", "none", "undefined", "nil", "set", "not set", "???", "???"].includes(lowered)) return "";
  return token;
};

window.looksLikeIssuedAuthToken = function looksLikeIssuedAuthToken(value) {
  const token = normalizeAuthToken(value);
  if (!token) return false;
  const parts = token.split(".");
  return parts.length === 2 && Boolean(parts[0]) && Boolean(parts[1]);
};

window.generateSessionId = function generateSessionId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  return `session-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
};

window.formToObject = function formToObject(form) {
  const formData = new FormData(form);
  const result = {};
  for (const [key, value] of formData.entries()) {
    const trimmed = typeof value === "string" ? value.trim() : value;
    if (trimmed === "") continue;
    result[key] = trimmed;
  }
  return result;
};

window.setStatus = function setStatus(id, message, isError = false) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = message || "";
  el.className = isError ? "status error" : "status";
};

window.clearStatuses = function clearStatuses() {
  ["patientStatus", "patientQueryStatus", "medicalStatus", "visitStatus", "lookupStatus", "contextStatus", "multimodalStatus"].forEach((id) => setStatus(id, ""));
};

window.setGeneralStatus = function setGeneralStatus(message, isError = false) {
  const el = document.getElementById("generalChatStatus");
  if (!el) return;
  el.textContent = message || "";
  el.classList.toggle("error", Boolean(isError));
};

window.setProfileLoginStatus = function setProfileLoginStatus(message, isError = false) {
  const el = document.getElementById("profileLoginStatus");
  if (!el) return;
  el.textContent = message || "";
  el.className = isError ? "status error full" : "status full";
};

window.updateMemoryLoginHint = function updateMemoryLoginHint(text) {
  const hint = document.getElementById("chatSubModeHint");
  const chip = document.getElementById("memoryLoginChip");
  if (hint) hint.textContent = text;
  if (chip) chip.textContent = state.patientId ? "已登录" : "未登录";
};

window.sessionStorageKey = function sessionStorageKey(patientId) {
  return patientId ? `agentTesterSession:${patientId}` : "agentTesterSession:anonymous";
};

window.chatStorageKey = function chatStorageKey(sessionId) {
  return sessionId ? `agentTesterChat:${sessionId}` : "";
};

window.generalChatStorageKey = function generalChatStorageKey(sessionId) {
  return sessionId ? `agentTesterGeneralChat:${sessionId}` : "";
};

window.generalSessionStorageKey = function generalSessionStorageKey() {
  return "agentTesterGeneralSessionId";
};

window.generalRecentStorageKey = function generalRecentStorageKey() {
  return "agentTesterGeneralRecentSessions";
};

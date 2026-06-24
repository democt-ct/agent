// ── Token 管理 ────────────────────────────────────────────

export function getToken() {
  return window.__authToken || '';
}

export function setToken(token) {
  window.__authToken = token;
  localStorage.setItem('auth_token', token);
}

export function clearToken() {
  window.__authToken = '';
  localStorage.removeItem('auth_token');
  localStorage.removeItem('auth_user');
  window.__authUser = null;
}

export function getUser() {
  if (!window.__authUser) {
    try { window.__authUser = JSON.parse(localStorage.getItem('auth_user') || 'null'); } catch { window.__authUser = null; }
  }
  return window.__authUser;
}

export function setUser(user) {
  window.__authUser = user;
  localStorage.setItem('auth_user', JSON.stringify(user));
}

export function authHeaders(json = true) {
  const h = json ? { 'Content-Type': 'application/json' } : {};
  const tok = getToken();
  if (tok) h['Authorization'] = 'Bearer ' + tok;
  return h;
}

// ── JWT 自动刷新 ───────────────────────────────────────────
let _refreshTimer = null;

function decodeJwtPayload(token) {
  try { return JSON.parse(atob(token.split('.')[1])); }
  catch (e) { return null; }
}

export function scheduleTokenRefresh() {
  if (_refreshTimer) { clearTimeout(_refreshTimer); _refreshTimer = null; }
  const token = getToken();
  if (!token) return;
  const payload = decodeJwtPayload(token);
  if (!payload || !payload.exp) return;
  const msUntilExpiry = payload.exp * 1000 - Date.now();
  const refreshAt = msUntilExpiry - 120000; // 过期前 2 分钟
  if (refreshAt <= 0) {
    refreshToken();
    return;
  }
  _refreshTimer = setTimeout(refreshToken, refreshAt);
}

async function refreshToken() {
  if (!getToken()) return;
  try {
    const r = await fetch('/api/auth/refresh', { method: 'POST', headers: authHeaders() });
    if (!r.ok) return;
    const d = await r.json();
    setToken(d.token);
    scheduleTokenRefresh();
  } catch (e) { /* 网络错误，下次再试 */ }
}

export function startAutoRefresh() {
  if (getToken()) scheduleTokenRefresh();
}

export function stopAutoRefresh() {
  if (_refreshTimer) { clearTimeout(_refreshTimer); _refreshTimer = null; }
}

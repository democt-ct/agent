// ── API 基础配置 ──────────────────────────────────────────
export const API_BASE = window.location.origin + '/api';

// ── 通用 fetch 封装 ───────────────────────────────────────
export async function apiGet(path, options = {}) {
  const tok = window.__authToken;
  const headers = options.headers || {};
  if (tok) headers['Authorization'] = 'Bearer ' + tok;
  return fetch(API_BASE + path, { ...options, headers });
}

export async function apiPost(path, body, options = {}) {
  const tok = window.__authToken;
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (tok) headers['Authorization'] = 'Bearer ' + tok;
  return fetch(API_BASE + path, { method: 'POST', headers, body: JSON.stringify(body), ...options });
}

// ── SSE 流式请求 ───────────────────────────────────────────
export async function sseStream(urlPath, onEvent, timeoutMs = 60000) {
  const tok = window.__authToken;
  const url = API_BASE + urlPath;
  const headers = {};
  if (tok) headers['Authorization'] = 'Bearer ' + tok;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const resp = await fetch(url, { headers, signal: controller.signal });
    if (!resp.ok) return false;
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) { clearTimeout(timer); return true; }
      buf += decoder.decode(value, { stream: true });
      const events = buf.split('\n\n');
      buf = events.pop();

      for (const raw of events) {
        const lines = raw.split('\n');
        let eventType = '', dataStr = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) eventType = line.slice(7);
          else if (line.startsWith('data: ')) dataStr = line.slice(6);
        }
        if (!eventType || !dataStr) continue;
        try {
          const d = JSON.parse(dataStr);
          if (onEvent(eventType, d) === false) { clearTimeout(timer); return true; }
        } catch (e) { /* skip malformed */ }
      }
    }
  } catch (e) {
    clearTimeout(timer);
    return false;
  }
}

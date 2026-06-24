// ── 共享图标和辅助函数 ────────────────────────────────────
export const I = {
  user: '👤', assistant: '🤖', robot: '🤖', sparkles: '✨',
  hr: '🏥', it: '💻', legal: '⚖️', finance: '💰',
};

export const AGENTS = {
  'HR 专家': { icon: I.hr, label: 'HR' },
  'IT 专家': { icon: I.it, label: 'IT' },
  '法务专家': { icon: I.legal, label: '法务' },
  '财务专家': { icon: I.finance, label: '财务' },
};

export function agentIcon(name) {
  if (!name) return I.robot;
  const a = AGENTS[name];
  if (a) return a.icon;
  if (name.includes('HR')) return I.hr;
  if (name.includes('IT')) return I.it;
  if (name.includes('法务')) return I.legal;
  if (name.includes('财务')) return I.finance;
  return I.robot;
}

export function agentLabel(name) {
  const a = AGENTS[name];
  return a ? a.label : (name || '').split(' ')[0];
}

export function esc(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

export function fmtDate(s) {
  return s ? String(s).slice(0, 10) : '-';
}

export function md(text) {
  return typeof window !== 'undefined' && window.marked
    ? window.marked.parse(text || '')
    : (text || '');
}

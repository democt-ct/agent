/* ═══════════════════════════════════════════════════════════════
   Slate Blue Professional — Chat Logic
   SSE streaming + POST fallback · localStorage sessions · markdown
   ═══════════════════════════════════════════════════════════════ */

import { API_BASE, sseStream, apiPost } from './modules/api.js';
import { getToken } from './modules/auth.js';
import { I, AGENTS, agentIcon, agentLabel, esc, fmtDate, md } from './modules/shared.js';

(function() {
  'use strict';

  // ── Config ────────────────────────────────────────────────
  const STORAGE_KEY_PREFIX = 'ea_sessions_';
  const CURRENT_ID_KEY_PREFIX = 'ea_current_';

  function storageKey() {
    var u = window.__authUser;
    return STORAGE_KEY_PREFIX + (u ? u.user_id : 'anon');
  }
  function currentIdKey() {
    var u = window.__authUser;
    return CURRENT_ID_KEY_PREFIX + (u ? u.user_id : 'anon');
  }

  // ── DOM refs ──────────────────────────────────────────────
  const $ = s => document.querySelector(s);
  const elChat       = $('#chat-messages');
  const elInput      = $('#chat-input');
  const elSend       = $('#btn-send');
  const elSessions   = $('#session-list');
  const elTitle      = $('#topbar-title');
  const elBadge      = $('#topbar-agent-badge');
  const elBadgeName  = $('#topbar-agent-name');
  const elSidebar    = $('#sidebar');
  const elStatus     = $('#agent-status-bar');

  // ── SVG icons ─────────────────────────────────────────────
  const I = {
    sparkles: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3l1.91 5.09L19 10l-5.09 1.91L12 17l-1.91-5.09L5 10l5.09-1.91z"/><path d="M18 14l.91 2.09L21 17l-2.09.91L18 20l-.91-2.09L15 17l2.09-.91z"/></svg>',
    user:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    users:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>',
    monitor: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
    shield:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>',
    chat:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>',
    database:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>',
    wrench:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>',
    brain:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9.5 2A2.5 2.5 0 0112 4.5V15a2.5 2.5 0 01-2.5 2.5H4.5A2.5 2.5 0 012 15V4.5A2.5 2.5 0 014.5 2zm5 0A2.5 2.5 0 0022 4.5V15a2.5 2.5 0 01-2.5 2.5H15"/><path d="M12 6h.01"/><path d="M9 10h6"/></svg>',
  };

  const AGENTS = {
    'HR 专家': { color: 'var(--agent-hr)', bg: 'var(--agent-hr-bg)', icon: 'users',  label: '🏥' },
    'IT 专家': { color: 'var(--agent-it)', bg: 'var(--agent-it-bg)', icon: 'monitor',label: '💻' },
    '法务专家': { color: 'var(--agent-legal)', bg: 'var(--agent-legal-bg)', icon: 'shield', label: '⚖️' },
    '财务专家': { color: '#D97706', bg: '#FFF3D7', icon: 'database', label: '💰' },
    fallback:  { color: 'var(--agent-fallback)', bg: 'var(--agent-fallback-bg)', icon: 'sparkles', label: '🤖' },
  };

  function agentIcon(name) { return I[(AGENTS[name] || AGENTS.fallback).icon]; }
  function agentLabel(name) { return (AGENTS[name] || AGENTS.fallback).label + ' ' + (name || ''); }

  // ── State ─────────────────────────────────────────────────
  let currentId = null, sending = false, sessions = {}, messages = [];

  // ── Storage ───────────────────────────────────────────────
  function loadSessions() { try { sessions = JSON.parse(localStorage.getItem(storageKey())) || {}; } catch { sessions = {}; } }
  function saveSessions() { try { localStorage.setItem(storageKey(), JSON.stringify(sessions)); } catch {} }
  function loadCurrent() { try { currentId = localStorage.getItem(currentIdKey()); } catch {} }
  function saveCurrent() { if (currentId) try { localStorage.setItem(currentIdKey(), currentId); } catch {} }

  function genId() { return 's_' + Date.now().toString(36) + Math.random().toString(36).slice(2,6); }
  function ensureSession(id) { return (id && sessions[id]) ? id : genId(); }

  function switchSession(id) {
    currentId = id; messages = sessions[id] || [];
    saveCurrent(); renderSessions(); renderMessages(); updateTopbar();
  }
  function newSession() { const id = genId(); sessions[id] = []; switchSession(id); saveSessions(); }
  function clearSession() {
    if (currentId && sessions[currentId]) { sessions[currentId] = []; messages = []; renderMessages(); saveSessions(); updateTopbar(); }
  }
  function deleteSession(id) {
    if (!sessions[id]) return;
    if (id === currentId) {
      delete sessions[id]; saveSessions();
      const keys = Object.keys(sessions);
      if (keys.length) { switchSession(keys[keys.length-1]); }
      else { currentId = genId(); sessions[currentId] = []; messages = []; saveCurrent(); renderSessions(); renderMessages(); updateTopbar(); }
    } else {
      delete sessions[id]; saveSessions(); renderSessions();
    }
  }

  // ── Render: session list ─────────────────────────────────
  function renderSessions() {
    const keys = Object.keys(sessions);
    if (!keys.length) { elSessions.innerHTML = '<div class="session-item session-title" style="opacity:.4;cursor:default">暂无会话</div>'; return; }
    let h = '';
    for (const id of keys) {
      let preview = '新对话';
      const msgs = sessions[id] || [];
      for (let i = msgs.length - 1; i >= 0; i--) { if (msgs[i].role === 'user') { preview = msgs[i].content.slice(0,24) + (msgs[i].content.length > 24 ? '…' : ''); break; } }
      h += `<div class="session-item${id===currentId?' active':''}" data-sid="${id}"><div class="session-title">${esc(preview)}</div><div class="session-meta">${msgs.length} 条</div><button class="session-delete" data-del="${id}" title="删除对话" aria-label="删除对话"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button></div>`;
    }
    elSessions.innerHTML = h;
    elSessions.querySelectorAll('.session-item').forEach(el => el.addEventListener('click', (e) => { if (e.target.closest('.session-delete')) return; if (el.dataset.sid !== currentId) { switchSession(el.dataset.sid); saveSessions(); } }));
    elSessions.querySelectorAll('.session-delete').forEach(btn => btn.addEventListener('click', (e) => { e.stopPropagation(); deleteSession(btn.dataset.del); }));
  }

  // ── Render: messages ─────────────────────────────────────
  function renderMessages() {
    const loggedIn = !!(typeof window !== 'undefined' && window.__authToken);
    if (!loggedIn) {
      elChat.innerHTML = loginPromptHTML();
      elInput.disabled = true;
      elInput.placeholder = '请先登录后再输入问题';
      elSend.disabled = true;
      return;
    }
    elInput.disabled = false;
    elInput.placeholder = '输入问题，例如：我的年假余额和报销标准分别是多少';
    elChat.innerHTML = messages.length ? '' : welcomeHTML();
    messages.forEach(appendMsg);
    scrollDown();
  }

  function loginPromptHTML() {
    return `<div class="message assistant welcome"><div class="message-avatar">${I.sparkles}</div><div class="message-content">
      <p class="welcome-title">企业多专家 Agent 工作台</p>
      <p class="welcome-subtitle">请点击左下角 👤 登录按钮，使用企业账号登录后开始使用。</p>
    </div></div>`;
  }

  function welcomeHTML() {
    return `<div class="message assistant welcome"><div class="message-avatar">${I.sparkles}</div><div class="message-content">
      <p class="welcome-title">企业多专家 Agent 工作台</p>
      <p class="welcome-subtitle">统一入口处理 HR、IT、法务、财务问题，自动路由到最合适的专家，并展示知识检索、工具调用和推理过程。</p>
      <ul><li><strong>🏥 HR 专家</strong> — 年假余额、请假申请、考勤与人事政策</li><li><strong>💻 IT 专家</strong> — 设备报修、软件安装、网络与账号问题</li><li><strong>⚖️ 法务专家</strong> — 合同条款、合规要求、数据保护与知识产权</li><li><strong>💰 财务专家</strong> — 报销、预算、差旅、薪资社保与审批</li></ul>
      <div class="suggestions">
        <button class="suggestion-chip" data-query="我今年年假还剩几天？">📅 查年假余额</button>
        <button class="suggestion-chip" data-query="我的笔记本电脑开不了机了，帮我报修。">🛠 电脑报修</button>
        <button class="suggestion-chip" data-query="工程部的预算还剩多少？部门ID: dept-eng">💰 查部门预算</button>
        <button class="suggestion-chip" data-query="请帮查一下保密协议里关于竞业限制的规定">🔒 查保密协议</button>
      </div>
    </div></div>`;
  }

  function appendMsg(msg) {
    const el = document.createElement('div');
    el.className = `message ${msg.role}`;
    if (msg.role === 'error') el.classList.add('error');
    if (msg.agentName) el.setAttribute('data-agent', msg.agentName);

    const av = msg.role === 'user' ? I.user : agentIcon(msg.agentName);
    const label = msg.agentName && AGENTS[msg.agentName] ? `<div class="message-agent-label">${agentLabel(msg.agentName)}</div>` : '';
    const cards = msg.thinkingCards ? msg.thinkingCards.join('\n') : '';
    const cardHtml = msg.actionCard ? renderActionCard(msg.actionCard) : '';

    let footer = '';
    if (msg.tokens || msg.time) {
      const p = []; if (msg.tokens) p.push(`🪙 ${msg.tokens} tokens`); if (msg.time) p.push(`⏱ ${msg.time}ms`);
      footer = `<div class="message-footer">${p.join(' · ')}</div>`;
    }

    let retry = '';
    if (msg.role === 'error' && msg.retryQuery) retry = `<button class="retry-btn" data-q="${esc(msg.retryQuery)}">🔄 重试</button>`;

    el.innerHTML = `<div class="message-avatar">${av}</div><div class="message-content">${label}${cards}<div class="msg-body">${md(msg.content)}</div>${cardHtml}${retry}${footer}</div>`;
    elChat.appendChild(el);
    el.querySelectorAll('.thinking-header').forEach(h => h.addEventListener('click', () => h.parentElement.classList.toggle('expanded')));
    const rb = el.querySelector('.retry-btn');
    if (rb) rb.addEventListener('click', () => { elInput.value = rb.dataset.q; elSend.disabled = false; elInput.focus(); sendMessage(); });

    if (msg.actionCard) {
      bindCardEvents(el);
    }
  }

  function addMessage(msg) {
    messages.push(msg);
    if (currentId && sessions[currentId]) { sessions[currentId] = messages; saveSessions(); }
    appendMsg(msg);
    renderSessions(); updateTopbar(); scrollDown();
  }

  function scrollDown() { requestAnimationFrame(() => setTimeout(() => elChat.scrollTo({ top: elChat.scrollHeight, behavior: 'smooth' }), 10)); }
  function updateTopbar() {
    let title = '新对话', agent = null;
    for (let i = (messages||[]).length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') { title = messages[i].content.slice(0,32) + (messages[i].content.length>32?'…':''); }
      if (!agent && messages[i].agentName) agent = messages[i].agentName;
      if (title !== '新对话' && agent) break;
    }
    elTitle.textContent = title;
    elBadgeName.textContent = agent || '智能助手';
    elBadge.classList.toggle('active', !!agent);
  }

  // ── Markdown ─────────────────────────────────────────────
  function md(text) {
    if (!text) return '';
    if (typeof marked !== 'undefined' && marked.parse) return marked.parse(text, { breaks: true, gfm: true });

    const codeBlocks = [];
    let source = String(text).replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
      const i = codeBlocks.push(`<pre><code${lang ? ` class="language-${esc(lang)}"` : ''}>${esc(code)}</code></pre>`) - 1;
      return `\n@@CODE_BLOCK_${i}@@\n`;
    });

    source = esc(source)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    const lines = source.split(/\r?\n/);
    const out = [];
    let para = [];
    let list = null;

    function flushPara() {
      if (para.length) {
        out.push(`<p>${para.join('<br>')}</p>`);
        para = [];
      }
    }
    function flushList() {
      if (list) {
        out.push(`<${list.type}>${list.items.map(item => `<li>${item}</li>`).join('')}</${list.type}>`);
        list = null;
      }
    }

    for (const line of lines) {
      const trimmed = line.trim();
      const codeMatch = trimmed.match(/^@@CODE_BLOCK_(\d+)@@$/);
      if (codeMatch) {
        flushPara(); flushList();
        out.push(codeBlocks[Number(codeMatch[1])] || '');
        continue;
      }
      if (!trimmed) {
        flushPara(); flushList();
        continue;
      }
      const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
      if (heading) {
        flushPara(); flushList();
        const level = heading[1].length;
        out.push(`<h${level}>${heading[2]}</h${level}>`);
        continue;
      }
      const ul = trimmed.match(/^[-*+]\s+(.+)$/);
      if (ul) {
        flushPara();
        if (!list || list.type !== 'ul') { flushList(); list = { type: 'ul', items: [] }; }
        list.items.push(ul[1]);
        continue;
      }
      const ol = trimmed.match(/^\d+[.)]\s+(.+)$/);
      if (ol) {
        flushPara();
        if (!list || list.type !== 'ol') { flushList(); list = { type: 'ol', items: [] }; }
        list.items.push(ol[1]);
        continue;
      }
      flushList();
      para.push(trimmed);
    }
    flushPara(); flushList();
    return out.join('');
  }

  // ── Thinking cards ───────────────────────────────────────
  function buildCards(data) {
    const cards = [];
    const r = data.routing || {};
    if (r.primary) {
      const ml = {keyword:'关键词匹配',llm:'LLM 路由',greeting:'寒暄检测'};
      let c = `<div><strong>目标:</strong> ${r.primary}</div>` + (r.secondary?`<div><strong>次要:</strong> ${r.secondary}</div>`:'') + `<div><strong>置信度:</strong> ${Math.round((r.confidence||0)*100)}%</div><div><strong>方式:</strong> ${ml[r.method]||r.method}</div>` + (r.matched_keywords?`<div><strong>命中:</strong> ${r.matched_keywords.join('、')}</div>`:'');
      cards.push(card(I.chat, '路由', c));
    }
    const chunks = data.retrieved_chunks || [];
    if (chunks.length) {
      let c = `<div>检索到 <strong>${chunks.length}</strong> 段知识</div>`;
      const fst = chunks[0] || {};
      if (fst.method) c += `<div style="font-size:11px;color:var(--color-text-muted)">方法: ${fst.method}</div>`;
      for (const ch of chunks.slice(0,5)) c += `<div class="source-item"><div class="source-label">📄 ${esc(ch.source||'?')}</div><div class="source-score">相关度: ${ch.score?ch.score.toFixed(2):'-'}</div><div>${esc((ch.content||'').slice(0,120))}${(ch.content||'').length>120?'…':''}</div></div>`;
      cards.push(card(I.database, '知识检索', c));
    }
    const tools = data.tool_calls || [];
    if (tools.length) {
      let c = `<div>调用 ${tools.length} 个工具</div>`;
      for (const t of tools) { c += `<div class="source-item"><div class="source-label">🛠 ${esc(t.name)}</div><div>参数: ${esc(Object.entries(t.arguments||{}).map(([k,v])=>`${k}:${v}`).join(', '))}</div><pre><code>${esc(JSON.stringify(t.result||{},null,2).slice(0,200))}</code></pre></div>`; }
      cards.push(card(I.wrench, '工具调用', c));
    }
    if (data.reasoning) cards.push(card(I.brain, '推理过程', `<div class="reasoning-block"><pre><code>${esc(data.reasoning)}</code></pre></div>`));
    return cards;
  }

  function card(icon, label, body) {
    return `<div class="thinking-card"><div class="thinking-header" role="button" tabindex="0"><span class="thinking-icon">${icon}</span><span class="thinking-label">${label}</span><span class="thinking-arrow">▶</span></div><div class="thinking-body">${body}</div></div>`;
  }

  function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

  // ── SSE cards (partial data) ──────────────────────────────
  function sseCards(routing, tools, reasoning, retrieval) {
    const cards = [];
    if (routing && routing.primary) {
      let c = `<div><strong>目标:</strong> ${routing.primary}</div>` + (routing.secondary?`<div><strong>次要:</strong> ${routing.secondary}</div>`:'') + `<div><strong>置信度:</strong> ${Math.round((routing.confidence||0)*100)}%</div>`;
      cards.push(card(I.chat, '路由', c));
    }
    if (retrieval) {
      cards.push(card(I.database, '知识检索', buildRetrievalCard(retrieval)));
    }
    if (tools && tools.length) {
      let c = `<div>调用 ${tools.length} 个工具</div>`;
      tools.forEach(t => { c += `<div class="source-item"><div class="source-label">🛠 ${esc(t.name)}</div><div>参数: ${esc(Object.entries(t.arguments||{}).map(([k,v])=>`${k}:${v}`).join(', '))}</div></div>`; });
      cards.push(card(I.wrench, '工具调用', c));
    }
    if (reasoning) cards.push(card(I.brain, '推理过程', `<div class="reasoning-block"><pre><code>${esc(reasoning)}</code></pre></div>`));
    return cards;
  }

  function buildRetrievalCard(ret) {
    let c = '';
    if (ret.rewritten_query && ret.rewrite_used) {
      c += `<div><strong>改写后:</strong> ${esc(ret.rewritten_query)}</div>`;
    }
    if (ret.cache_hit) c += `<div>⚡ 缓存命中</div>`;
    c += `<div>检索到 <strong>${ret.count||0}</strong> 段知识</div>`;
    c += `<div style="font-size:11px;color:var(--color-text-muted)">`;
    c += `向量: ${ret.vector_count||0} | BM25: ${ret.bm25_count||0} | 融合: ${ret.fused_count||0}`;
    if (ret.fusion_method) c += ` | 方法: ${ret.fusion_method}`;
    if (ret.rerank_used) c += ` | 已重排`;
    c += `</div>`;
    if (ret.sources && ret.sources.length) {
      for (const s of ret.sources) {
        c += `<div class="source-item"><div class="source-label">📄 ${esc(s.source||'?')}</div><div class="source-score">匹配度: ${s.score?s.score.toFixed(2):'-'}</div></div>`;
      }
    }
    return c;
  }

  // ── Send message ─────────────────────────────────────────
  async function sendMessage() {
    const loggedIn = !!(typeof window !== 'undefined' && window.__authToken);
    if (!loggedIn) return;
    const q = elInput.value.trim();
    if (!q || sending) return;
    currentId = ensureSession(currentId); messages = sessions[currentId]; saveCurrent();
    elInput.value = ''; elSend.disabled = true; elInput.style.height = 'auto';
    addMessage({ role: 'user', content: q });
    sending = true;

    const wait = document.createElement('div');
    wait.className = 'message assistant';
    wait.innerHTML = `<div class="message-avatar">${I.sparkles}</div><div class="message-content"><div class="msg-body">正在思考，请稍候…</div></div>`;
    elChat.appendChild(wait); scrollDown();

    let ok = false;
    try { ok = await sse(q, wait); } catch {}
    if (!ok) { try { await post(q, wait); } catch(e) { wait.remove(); addMessage({ role:'error', content:`❌ ${e.message||'请求失败'}`, retryQuery:q }); } }
    sending = false; elSend.disabled = !elInput.value.trim(); renderSessions(); saveSessions();
  }

  // ── SSE streaming (fetch + ReadableStream, token in Authorization header) ──
  async function sse(q, wait) {
    const tok = typeof window !== 'undefined' && window.__authToken;
    const url = `${API_BASE}/chat/stream?query=${encodeURIComponent(q)}&session_id=${encodeURIComponent(currentId)}`;
    let routing = null, answer = null, reasoning = null, tools = null, retrieval = null, done = false, hasChunks = false;

    const headers = {};
    if (tok) headers['Authorization'] = 'Bearer ' + tok;

    let controller = new AbortController();
    const timer = setTimeout(() => { if(!done){controller.abort();fin(false);} }, 60000);

    const fin = (success) => {
      if(done)return; done=true; clearTimeout(timer); controller.abort();
      if(success&&answer){
        replace(wait,{content:answer.content||'',agentName:answer.agent_name||'',thinkingCards:sseCards(routing,tools,reasoning,retrieval),tokens:answer.tokens,time:answer.time,actionCard:answer.action_card||null}); return true;
      } else if(success&&hasChunks){
        const body=wait.querySelector('.msg-body');
        const content=body?body._raw||body.textContent:'';
        replace(wait,{content,agentName:'',thinkingCards:sseCards(routing,tools,reasoning,retrieval),tokens:0,time:0,actionCard:null}); return true;
      } else return false;
    };

    try {
      const resp = await fetch(url, { headers, signal: controller.signal });
      if (!resp.ok) { fin(false); return false; }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { value, done: streamDone } = await reader.read();
        if (streamDone) { fin(hasChunks || !!answer); return hasChunks || !!answer; }
        buf += decoder.decode(value, { stream: true });
        const events = buf.split('\n\n');
        buf = events.pop();  // 最后一个可能不完整

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
            switch (eventType) {
              case 'routing': routing = d; upCards(wait, sseCards(routing, null, null, retrieval)); break;
              case 'retrieval': retrieval = d; upCards(wait, sseCards(routing, tools, reasoning, retrieval)); break;
              case 'tool_call': {
                const calls = d.calls || (d.name ? [d] : []);
                tools = calls.map(function(c) { return { name: c.name, arguments: c.arguments || {}, result: c.result || null }; });
                upCards(wait, sseCards(routing, tools, reasoning, retrieval));
                break;
              }
              case 'confirm_tool': {
                tools = (tools || []).concat({ name: d.name, arguments: d.arguments || {}, pending: true });
                upCards(wait, sseCards(routing, tools, reasoning, retrieval));
                break;
              }
              case 'reasoning': reasoning = d.content; upCards(wait, sseCards(routing, tools, reasoning, retrieval)); break;
              case 'answer_chunk': {
                hasChunks = true;
                let body = wait.querySelector('.msg-body');
                if (!body) { body = document.createElement('div'); body.className = 'msg-body'; wait.querySelector('.message-content').appendChild(body); }
                body._raw = (body._raw || '') + (d.chunk || '');
                body.innerHTML = md(body._raw);
                scrollDown();
                break;
              }
              case 'answer': answer = d; break;
              case 'done': fin(true); return true;
              case 'error': fin(false); return false;
            }
          } catch (e) { /* malformed event, skip */ }
        }
      }
    } catch (e) {
      fin(false); return false;
    }
  }

  // ── POST fallback ────────────────────────────────────────
  async function post(q, wait) {
    const h = messages.filter(m=>m.role==='user'||(m.role==='assistant'&&m.content)).slice(-20).map(m=>({role:m.role,content:m.content}));
    const tok = typeof window !== 'undefined' && window.__authToken;
    const headers = { 'Content-Type': 'application/json' };
    if (tok) headers['Authorization'] = 'Bearer ' + tok;
    const r = await fetch(`${API_BASE}/chat`,{method:'POST',headers,body:JSON.stringify({query:q,session_id:currentId,history:h.slice(0,-2)})});
    if(!r.ok){ const e = await r.json().catch(()=>({error:'请求失败'})); throw new Error(e.error||`HTTP ${r.status}`); }
    const d = await r.json(); wait.remove();
    addMessage({role:'assistant',content:d.answer||'',agentName:d.agent_name||'',thinkingCards:buildCards(d),tokens:d.tokens_used,time:d.processing_time_ms,actionCard:d.action_card||null});
  }

  // ── SSE helpers ──────────────────────────────────────────
  function upCards(wait, cards) {
    let ctr = wait.querySelector('.thinking-cards');
    if(!ctr){
      ctr=document.createElement('div'); ctr.className='thinking-cards';
      const cd=wait.querySelector('.message-content');
      if(cd){
        const body=cd.querySelector('.msg-body');
        body ? cd.insertBefore(ctr, body) : cd.appendChild(ctr);
      }
    }
    ctr.innerHTML = cards.join('\n');
    ctr.querySelectorAll('.thinking-header').forEach(h=>h.addEventListener('click',()=>h.parentElement.classList.toggle('expanded')));
  }
  function replace(wait, msg) {
    const a = msg.agentName||'';
    const cardHtml = msg.actionCard ? renderActionCard(msg.actionCard) : '';
    wait.innerHTML = `<div class="message-avatar">${agentIcon(a)}</div><div class="message-content">${a&&AGENTS[a]?`<div class="message-agent-label">${agentLabel(a)}</div>`:''}${(msg.thinkingCards||[]).join('\n')}<div class="msg-body">${md(msg.content||'')}</div>${cardHtml}${msg.tokens||msg.time?`<div class="message-footer">${[msg.tokens?`🪙 ${msg.tokens} tokens`:'',msg.time?`⏱ ${msg.time}ms`:''].filter(Boolean).join(' · ')}</div>`:''}</div>`;
    if(a) wait.setAttribute('data-agent', a);
    wait.querySelectorAll('.thinking-header').forEach(h=>h.addEventListener('click',()=>h.parentElement.classList.toggle('expanded')));
    bindCardEvents(wait);
    messages.push({role:'assistant',content:msg.content||'',agentName:a,thinkingCards:msg.thinkingCards||[],tokens:msg.tokens,time:msg.time,actionCard:msg.actionCard||null});
    scrollDown();
  }

  // ── Agent status ─────────────────────────────────────────
  const elStatusList = $('#status-list');
  const elStatusToggle = $('#status-toggle');
  const elStatusFooter = $('#agent-status-bar');
  function renderStatus(agents) {
    if (!agents || !agents.length) { if (elStatusList) elStatusList.innerHTML = '<div class="agent-status-item"><span class="agent-status-dot offline"></span><span class="agent-status-name">后端未连接</span><span class="agent-status-label">离线</span></div>'; return; }
    const order = ['HR 专家','IT 专家','法务专家','财务专家']; let h = '';
    for (const name of order) {
      const online = agents.some(a => a.display_name === name);
      h += `<div class="agent-status-item"><span class="agent-status-dot ${online?'online':'offline'}"></span><span class="agent-status-name">${AGENTS[name]?AGENTS[name].label+' ':''}${name}</span><span class="agent-status-label">${online?'在线':'离线'}</span></div>`;
    }
    if (elStatusList) elStatusList.innerHTML = h;
  }

  // ── Modal ────────────────────────────────────────────────
  function showConfirm(icon, text, onOk) {
    const ov = $('#modal-overlay'), ic = $('#modal-icon'), tx = $('#modal-text'), cb = $('#modal-cancel'), cf = $('#modal-confirm');
    if(!ov) return;
    ic.textContent = icon||'⚠️'; tx.textContent = text||'确定？'; ov.classList.remove('hidden');
    function clean(){ ov.classList.add('hidden'); cb.removeEventListener('click',no); cf.removeEventListener('click',yes); ov.removeEventListener('click',out); }
    function no(){clean();}
    function yes(){clean();if(onOk)onOk();}
    function out(e){if(e.target===ov)clean();}
    cb.addEventListener('click',no); cf.addEventListener('click',yes); ov.addEventListener('click',out);
  }

  // ── Init ─────────────────────────────────────────────────
  async function init() {
    loadSessions(); loadCurrent();
    if (!currentId || !sessions[currentId]) { currentId = genId(); sessions[currentId] = []; messages = []; saveCurrent(); saveSessions(); }
    else { messages = sessions[currentId]; }
    renderSessions(); renderMessages(); updateTopbar();

    // 暴露全局刷新函数（登录/切换用户时调用）
    window.__reloadSessions = function() {
      loadSessions();  // 加载当前用户的已有会话列表
      currentId = genId(); messages = [];  // 但始终新建一个空白对话
      sessions[currentId] = [];
      saveCurrent(); saveSessions();
      renderSessions(); renderMessages(); updateTopbar();
    };

    try { const r = await fetch(`${API_BASE}/agents`); if(r.ok) renderStatus(await r.json()); else renderStatus([]); } catch { renderStatus([]); }

    // 专家状态折叠（默认收起）
    if (localStorage.getItem('status_collapsed') !== '0') { elStatusFooter?.classList.add('collapsed'); }
    elStatusToggle?.addEventListener('click', () => {
      elStatusFooter?.classList.toggle('collapsed');
      localStorage.setItem('status_collapsed', elStatusFooter?.classList.contains('collapsed') ? '1' : '0');
    });

    elSend.addEventListener('click', sendMessage);
    elInput.addEventListener('keydown', e => { if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();} });
    elInput.addEventListener('input', () => { elSend.disabled = !elInput.value.trim()||sending; elInput.style.height='auto'; elInput.style.height=Math.min(elInput.scrollHeight,120)+'px'; });
    const toggleSidebar = () => {
      const collapsed = elSidebar?.classList.toggle('collapsed');
      const title = collapsed ? '展开对话历史' : '折叠对话历史';
      $('#btn-toggle-sidebar')?.setAttribute('title', title);
      $('#btn-collapse-sidebar')?.setAttribute('title', title);
      localStorage.setItem('sidebar_collapsed', collapsed ? '1' : '0');
    };
    $('#btn-toggle-sidebar')?.addEventListener('click', toggleSidebar);
    $('#btn-collapse-sidebar')?.addEventListener('click', toggleSidebar);

    // 恢复折叠状态
    if (localStorage.getItem('sidebar_collapsed') === '1') {
      elSidebar?.classList.add('collapsed');
      const title = '展开对话历史';
      $('#btn-toggle-sidebar')?.setAttribute('title', title);
      $('#btn-collapse-sidebar')?.setAttribute('title', title);
    }
    $('#btn-new-chat')?.addEventListener('click', newSession);
    $('#btn-clear-chat')?.addEventListener('click', () => { if(messages.length) showConfirm('🗑️','清空当前对话？所有消息将被移除。',clearSession); });

    // 主题切换
    if (localStorage.getItem('dark_mode') === '1') document.documentElement.classList.add('dark');
    const btnDark = document.createElement('button');
    const syncThemeTitle = () => {
      const isDark = document.documentElement.classList.contains('dark');
      btnDark.title = isDark ? '切换到暖色浅色模式' : '切换到深色模式';
      btnDark.setAttribute('aria-label', btnDark.title);
    };
    btnDark.className = 'btn-icon'; btnDark.id = 'btn-dark';
    btnDark.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>';
    syncThemeTitle();
    const clearBtn = $('#btn-clear-chat');
    if (clearBtn) clearBtn.insertAdjacentElement('afterend', btnDark);
    btnDark.addEventListener('click', () => {
      document.documentElement.classList.toggle('dark');
      localStorage.setItem('dark_mode', document.documentElement.classList.contains('dark') ? '1' : '0');
      syncThemeTitle();
    });
    elChat.addEventListener('click', e => {
      const chip = e.target.closest('.suggestion-chip'); if(chip){ elInput.value=chip.dataset.query; elSend.disabled=false; elInput.focus(); }
      if(window.innerWidth<=768 && elSidebar) elSidebar.classList.add('hidden');
    });
  }

  document.addEventListener('DOMContentLoaded', init);
  // Expose for cross-script access
  window.__showConfirm = showConfirm;

  // ── Action Card 渲染引擎 ─────────────────────────────────
  function renderActionCard(card) {
    if (!card || !card.type) return '';
    const p = card.prefill || {};
    const today = new Date().toISOString().slice(0,10);

    // ── 动态渲染：card.fields 存在时按字段定义生成表单 ──────
    if (card.fields) {
      return renderDynamicCard(card, p, today);
    }

    // ── 回退：硬编码表单（兼容旧后端）─────────────────────────
    if (card.type === 'leave_form') {
      return `<div class="action-card" data-card="leave_form">
        <div class="ac-title">📅 申请请假</div>
        <div class="ac-row">
          <label>类型</label>
          <select class="ac-input" name="leave_type">
            <option ${p.leave_type==='年假'?'selected':''}>年假</option>
            <option ${p.leave_type==='病假'?'selected':''}>病假</option>
            <option ${p.leave_type==='事假'?'selected':''}>事假</option>
          </select>
        </div>
        <div class="ac-row">
          <label>开始</label>
          <input class="ac-input" type="date" name="start_date" value="${p.start_date||today}">
        </div>
        <div class="ac-row">
          <label>结束</label>
          <input class="ac-input" type="date" name="end_date" value="${p.end_date||today}">
        </div>
        <div class="ac-row">
          <label>原因</label>
          <input class="ac-input" type="text" name="reason" placeholder="可选">
        </div>
        <button class="ac-btn" data-action="submit_leave">提交申请</button>
      </div>`;
    }

    if (card.type === 'expense_form') {
      return `<div class="action-card" data-card="expense_form">
        <div class="ac-title">💰 提交报销</div>
        <div class="ac-row">
          <label>类型</label>
          <select class="ac-input" name="expense_type">
            <option>差旅</option><option>办公</option><option>招待</option><option>培训</option><option>其他</option>
          </select>
        </div>
        <div class="ac-row">
          <label>金额</label>
          <input class="ac-input" type="number" name="amount" placeholder="元" min="0" step="0.01">
        </div>
        <div class="ac-row">
          <label>说明</label>
          <input class="ac-input" type="text" name="description" placeholder="费用说明">
        </div>
        <button class="ac-btn" data-action="submit_expense">提交报销</button>
      </div>`;
    }

    if (card.type === 'ticket_form') {
      return `<div class="action-card" data-card="ticket_form">
        <div class="ac-title">🛠 IT 维修工单</div>
        <div class="ac-row">
          <label>问题类型</label>
          <select class="ac-input" name="issue_type">
            <option ${p.issue_type==='硬件报修'?'selected':''}>硬件报修</option>
            <option ${p.issue_type==='软件安装'?'selected':''}>软件安装</option>
            <option ${p.issue_type==='网络问题'?'selected':''}>网络问题</option>
            <option ${p.issue_type==='账号问题'?'selected':''}>账号问题</option>
            <option ${p.issue_type==='其他'?'selected':''}>其他</option>
          </select>
        </div>
        <div class="ac-row">
          <label>优先级</label>
          <select class="ac-input" name="priority">
            <option ${p.priority==='高'?'selected':''}>高</option>
            <option ${!p.priority||p.priority==='中'?'selected':''}>中</option>
            <option ${p.priority==='低'?'selected':''}>低</option>
          </select>
        </div>
        <div class="ac-row">
          <label>问题描述</label>
          <input class="ac-input" type="text" name="description" value="${esc(p.description||'')}" placeholder="例如：电脑开不了机、蓝屏、键盘损坏……">
        </div>
        <button class="ac-btn" data-action="submit_ticket">提交工单</button>
      </div>`;
    }

    if (card.type === 'attendance_punch') {
      return `<div class="action-card" data-card="attendance_punch">
        <div class="ac-title">⏰ 考勤打卡</div>
        <div class="ac-punch-btns">
          <button class="ac-btn ac-btn-punch" data-action="punch_in">上班打卡</button>
          <button class="ac-btn ac-btn-punch ac-btn-out" data-action="punch_out">下班打卡</button>
        </div>
      </div>`;
    }

    if (card.type === 'overtime_form') {
      return `<div class="action-card" data-card="overtime_form">
        <div class="ac-title">🕐 申请加班</div>
        <div class="ac-row"><label>日期</label><input class="ac-input" type="date" name="date" value="${today}"></div>
        <div class="ac-row"><label>时长(h)</label><input class="ac-input" type="number" name="hours" min="1" max="12" value="2"></div>
        <div class="ac-row"><label>原因</label><input class="ac-input" type="text" name="reason" placeholder="加班原因"></div>
        <button class="ac-btn" data-action="submit_overtime">提交申请</button>
      </div>`;
    }

    if (card.type === 'trip_form') {
      return `<div class="action-card" data-card="trip_form">
        <div class="ac-title">✈️ 申请出差</div>
        <div class="ac-row"><label>目的地</label><input class="ac-input" type="text" name="destination" placeholder="城市"></div>
        <div class="ac-row"><label>开始</label><input class="ac-input" type="date" name="start_date" value="${today}"></div>
        <div class="ac-row"><label>结束</label><input class="ac-input" type="date" name="end_date" value="${today}"></div>
        <div class="ac-row"><label>预估费用</label><input class="ac-input" type="number" name="amount" min="1" step="0.01" placeholder="元"></div>
        <div class="ac-row"><label>事由</label><input class="ac-input" type="text" name="reason" placeholder="出差目的"></div>
        <button class="ac-btn" data-action="submit_trip">提交申请</button>
      </div>`;
    }

    if (card.type === 'approval_check') {
      // 触发加载待审批列表
      setTimeout(() => { if(window.__loadApprovals) window.__loadApprovals(); }, 100);
      return `<div class="action-card" data-card="approval_check">
        <div class="ac-title">✅ 待审批事项</div>
        <div class="ac-approval-list" id="inline-approval-list"><div style="color:var(--color-text-muted);font-size:13px">加载中...</div></div>
      </div>`;
    }

    return '';
  }

  // ── 动态 Action Card 渲染（按 fields 数组生成表单）──────────
  function renderDynamicCard(card, p, today) {
    const fields = card.fields || [];
    const title = card.title || card.type;
    const submitAction = card.submit_action || '';

    // 打卡特殊处理
    if (card.punch_buttons) {
      return `<div class="action-card" data-card="${esc(card.type)}" data-action="punch">
        <div class="ac-title">⏰ ${esc(title)}</div>
        <div class="ac-punch-btns">
          <button class="ac-btn ac-btn-punch" data-action="punch_in">上班打卡</button>
          <button class="ac-btn ac-btn-punch ac-btn-out" data-action="punch_out">下班打卡</button>
        </div>
      </div>`;
    }

    // 无字段卡片（如 approval_check）— 只显示标题
    if (fields.length === 0) {
      return `<div class="action-card" data-card="${esc(card.type)}" data-action="${esc(submitAction)}">
        <div class="ac-title">${esc(title)}</div>
      </div>`;
    }

    // 生成表单行
    let rows = '';
    for (const f of fields) {
      const name = esc(f.name);
      const label = esc(f.label);
      const req = f.required ? ' required' : '';
      const ph = f.placeholder ? ` placeholder="${esc(f.placeholder)}"` : '';
      const val = esc(p[f.name] || '');

      if (f.type === 'select') {
        const opts = (f.options || []).map(function(o) {
          const sel = (p[f.name] === o || (!p[f.name] && f.options.indexOf(o) === 0)) ? ' selected' : '';
          return `<option${sel}>${esc(o)}</option>`;
        }).join('');
        rows += `<div class="ac-row"><label>${label}</label><select class="ac-input" name="${name}"${req}>${opts}</select></div>`;
      } else if (f.type === 'date') {
        const dval = val || today;
        rows += `<div class="ac-row"><label>${label}</label><input class="ac-input" type="date" name="${name}" value="${dval}"${req}>`;
      } else if (f.type === 'number') {
        rows += `<div class="ac-row"><label>${label}</label><input class="ac-input" type="number" name="${name}" value="${val}" min="0" step="0.01"${ph}${req}>`;
      } else if (f.type === 'textarea') {
        rows += `<div class="ac-row"><label>${label}</label><textarea class="ac-input" name="${name}"${ph}${req}>${val}</textarea></div>`;
      } else {
        // text / default
        rows += `<div class="ac-row"><label>${label}</label><input class="ac-input" type="text" name="${name}" value="${val}"${ph}${req}>`;
      }
    }

    const btnLabel = submitAction ? '提交' : '确认';
    return `<div class="action-card" data-card="${esc(card.type)}" data-action="${esc(submitAction)}">
      <div class="ac-title">${esc(title)}</div>
      ${rows}
      ${submitAction ? `<button class="ac-btn" data-action="${esc(submitAction)}">${btnLabel}</button>` : ''}
    </div>`;
  }

  function bindCardEvents(el) {
    const btn = el.querySelector('[data-action]');
    if (!btn) return;
    const card = el.querySelector('.action-card');
    if (!card) return;

    btn.addEventListener('click', async () => {
      const action = btn.dataset.action;
      const tok = window.__authToken;
      if (!tok) return alert('请先登录');

      const get = name => { const f = card.querySelector(`[name="${name}"]`); return f ? f.value : ''; };

      try {
        if (action === 'submit_leave') {
          const r = await fetch('/api/leaves', {
            method: 'POST',
            headers: {'Content-Type':'application/json','Authorization':'Bearer '+tok},
            body: JSON.stringify({leave_type:get('leave_type'),start_date:get('start_date'),end_date:get('end_date'),reason:get('reason')}),
          });
          const d = await r.json();
          if (d.error) return alert('提交失败: ' + d.error);
          card.innerHTML = `<div class="ac-success">✅ 申请已提交，等待审批（ID: ${d.request_id}）</div>`;
          if(window.__loadApprovals) window.__loadApprovals();

        } else if (action === 'submit_expense') {
          const r = await fetch('/api/expenses', {
            method: 'POST',
            headers: {'Content-Type':'application/json','Authorization':'Bearer '+tok},
            body: JSON.stringify({expense_type:get('expense_type'),amount:parseFloat(get('amount')),description:get('description')}),
          });
          const d = await r.json();
          if (d.error) return alert('提交失败: ' + d.error);
          card.innerHTML = `<div class="ac-success">✅ 报销已提交（ID: ${d.expense_id}）</div>`;

        } else if (action === 'submit_ticket') {
          const r = await fetch('/api/tickets', {
            method: 'POST',
            headers: {'Content-Type':'application/json','Authorization':'Bearer '+tok},
            body: JSON.stringify({issue_type:get('issue_type'),description:get('description'),priority:get('priority')}),
          });
          const d = await r.json();
          if (d.error) return alert('提交失败: ' + d.error);
          card.innerHTML = `<div class="ac-success">✅ 工单已提交（ID: ${d.ticket_id}）</div>`;

        } else if (action === 'punch_in' || action === 'punch_out') {
          const r = await fetch('/api/attendance/punch', {
            method: 'POST',
            headers: {'Content-Type':'application/json','Authorization':'Bearer '+tok},
            body: JSON.stringify({type: action === 'punch_in' ? 'in' : 'out'}),
          });
          const d = await r.json();
          if (d.error) return alert('打卡失败: ' + d.error);
          card.innerHTML = `<div class="ac-success">✅ ${action==='punch_in'?'上班':'下班'}打卡成功（${d.time}）</div>`;

        } else if (action === 'submit_overtime') {
          const date = get('date');
          const hours = parseFloat(get('hours'));
          const reason = get('reason') || '';
          if (!hours || hours <= 0) throw new Error('请填写加班时长');
          const amount = Math.round(hours * 50 * 100) / 100; // 按 50元/h 估算
          const desc = `加班-${date} (${hours}h): ${reason}`;
          const meta = JSON.stringify({type:'overtime',date,hours,reason});
          const r = await fetch('/api/expenses', {
            method: 'POST',
            headers: {'Content-Type':'application/json','Authorization':'Bearer '+tok},
            body: JSON.stringify({expense_type:'其他',amount,description:desc,metadata:meta}),
          });
          const d = await r.json();
          if (!r.ok) throw new Error(d.error||'提交失败');
          card.innerHTML = `<div class="ac-success">✅ 加班申请已提交（${d.expense_id}），等待审批</div>`;

        } else if (action === 'submit_trip') {
          const dest = get('destination') || '未填写';
          const start = get('start_date');
          const end = get('end_date');
          const reason = get('reason') || '';
          const amount = parseFloat(get('amount'));
          if (!amount || amount <= 0) throw new Error('请填写预估费用');
          const desc = `出差-${dest}${start?' ('+start:''}${end?' ~ '+end:''}${end?')':''}: ${reason}`;
          const meta = JSON.stringify({type:'trip',destination:dest,start_date:start,end_date:end,reason});
          const r = await fetch('/api/expenses', {
            method: 'POST',
            headers: {'Content-Type':'application/json','Authorization':'Bearer '+tok},
            body: JSON.stringify({expense_type:'差旅',amount,description:desc,metadata:meta}),
          });
          const d = await r.json();
          if (!r.ok) throw new Error(d.error||'提交失败');
          card.innerHTML = `<div class="ac-success">✅ 出差申请已提交（${d.expense_id}），等待审批</div>`;
        }
      } catch(e) { alert('操作失败: ' + e.message); }
    });
  }
})();

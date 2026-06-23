/**
 * 质量评估控制台 — 核心逻辑 (evaluate.js)
 *
 * 评估用例从后端 API 加载（单一数据源），启动时由 loadCases() 填充。
 * 不再硬编码副本，所有用例数据由 GET /api/v1/evaluation/cases 提供。
 */

// ═══════════════════════════════════════════════════════════
// 评估用例：从后端 API 加载（单一数据源）
// ═══════════════════════════════════════════════════════════
let EVALUATION_CASES = [];

async function loadCases() {
  try {
    const resp = await fetch(`${getBase()}/api/v1/evaluation/cases`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (data.cases && data.cases.length > 0) {
      EVALUATION_CASES = data.cases;
    } else {
      console.warn('评估用例 API 返回空列表');
    }
  } catch (err) {
    console.warn('无法从 API 加载评估用例:', err.message);
    $('serverText').textContent += '（用例加载失败）';
  }
  renderCases();
  updateStats();
}

const state = {
  results: {}, running: new Set(), filter: 'all',
  isRunningAll: false, abortController: null,
};

const $ = id => document.getElementById(id);
const tableBody = $('tableBody');
const filterBar = $('filterBar');
const progressFill = $('progressFill');

function getBase() { return ($('apiBase').value.trim()) || ''; }

async function callAgent(question, patientId) {
  const payload = { question, chat_mode: patientId ? 'memory' : 'general' };
  if (patientId) payload.patient_id = patientId;
  if (state.abortController) { try { state.abortController.abort(); } catch {} }
  state.abortController = new AbortController();
  const signal = state.abortController.signal;
  const timeoutId = setTimeout(() => { try { state.abortController?.abort(); } catch {} }, 180_000);
  try {
    const resp = await fetch(`${getBase()}/api/v1/mcp/agent/query`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload), signal,
    });
    clearTimeout(timeoutId);
    if (!resp.ok) { const err = await resp.text(); throw new Error(`HTTP ${resp.status}: ${err}`); }
    return resp.json();
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') throw new Error('请求超时 (180s)');
    throw err;
  }
}

async function resolvePatientCode(code) {
  if (!code) return null;
  try {
    const resp = await fetch(`${getBase()}/api/v1/patients?patient_code=${encodeURIComponent(code)}`);
    if (!resp.ok) return null;
    const patients = await resp.json();
    return patients.length > 0 ? patients[0].id : null;
  } catch { return null; }
}

async function callRAGASJudge(question, answer, context, reference) {
  try {
    const resp = await fetch(`${getBase()}/api/v1/mcp/evaluate/ragas-judge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, answer, context: context || '', reference: reference || '' }),
      signal: AbortSignal.timeout(120_000),
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

function calculateScore(caseData, result) {
  const w = caseData.scoring || { intent_weight: 0.3, keyword_weight: 0.4, safety_weight: 0.3 };
  const answer = (result.answer || '').toLowerCase();

  const intentScore = result.intentOk ? 100 : 0;

  const expected = caseData.expected_keywords || [];
  const found = expected.filter(kw => answer.includes(kw.toLowerCase()));
  const keywordScore = expected.length > 0 ? (found.length / expected.length) * 100 : 100;

  const forbidden = caseData.forbidden_keywords || [];
  const foundForbidden = forbidden.filter(kw => answer.includes(kw.toLowerCase()));
  let safetyScore = 100;
  if (forbidden.length > 0 && foundForbidden.length > 0) {
    safetyScore = Math.max(0, 100 - (foundForbidden.length / forbidden.length) * 100);
  }

  const total = Math.round(
    intentScore * (w.intent_weight || 0.3) +
    keywordScore * (w.keyword_weight || 0.4) +
    safetyScore * (w.safety_weight || 0.3)
  );

  return { intentScore, keywordScore, safetyScore, total, found, foundForbidden, expected, forbidden };
}

function _extractContextFromMemoryDebug(memoryDebug) {
  if (!memoryDebug) return '';
  const blocks = [];
  const mb = memoryDebug.memory_layers || {};
  if (mb.short_term_memory) blocks.push(mb.short_term_memory);
  if (mb.factual_memory) blocks.push(mb.factual_memory);
  if (mb.long_term_summary_memory) blocks.push(mb.long_term_summary_memory);
  if (mb.knowledge_memory) blocks.push(mb.knowledge_memory);
  const cb = memoryDebug.context_blocks || {};
  if (cb.merged_conversation_context) blocks.push(cb.merged_conversation_context);
  return blocks.filter(Boolean).join('\n\n');
}

async function runCase(caseData) {
  const id = caseData.id;
  if (state.running.has(id)) return;
  state.running.add(id);
  renderCases();

  const startTime = Date.now();
  try {
    let patientId = null;
    if (caseData.patient_code) {
      patientId = await resolvePatientCode(caseData.patient_code);
    }
    const raw = await callAgent(caseData.question, patientId);
    const duration = ((Date.now() - startTime) / 1000).toFixed(2);

    const answer = raw.answer || '';
    const intent = raw.intent || '';
    const intentOk = (caseData.expected_intents || []).includes(intent);
    const missingKeywords = (caseData.expected_keywords || []).filter(kw => !answer.toLowerCase().includes(kw.toLowerCase()));
    const foundForbidden = (caseData.forbidden_keywords || []).filter(kw => answer.toLowerCase().includes(kw.toLowerCase()));

    const result = {
      passed: false, answer, intent, intentOk, missingKeywords, foundForbidden,
      duration, error: null,
      intent_confidence: raw.intent_confidence || null,
      planning_strategy: raw.planning_strategy || null,
      chosen_tool: raw.chosen_tool || null,
      chosen_tools: raw.chosen_tools || [],
      tool_arguments: raw.tool_arguments || {},
      tool_result: raw.tool_result || null,
      execution_trace: raw.execution_trace || [],
      planning: raw.planning || null,
      memory_debug: raw.memory_debug || null,
      patient_id: raw.patient_id || patientId,
      session_id: raw.session_id || null,
    };

    const score = calculateScore(caseData, result);
    result.score = score;
    result.passed = score.total >= 60;

    state.results[id] = result;
    renderCases();

    // RAGAS LLM-as-Judge evaluation
    const ragasContext = _extractContextFromMemoryDebug(raw.memory_debug);
    const ragasResult = await callRAGASJudge(caseData.question, answer, ragasContext, caseData.evaluation_hint || '');
    if (ragasResult) {
      result.ragas = ragasResult;
      state.results[id] = result;
      renderCases();
    }

    state.running.delete(id);
    renderCases();
  } catch (err) {
    state.results[id] = {
      passed: false, answer: '', intent: '', intentOk: false,
      missingKeywords: [], foundForbidden: [],
      duration: ((Date.now() - startTime) / 1000).toFixed(2),
      error: err.message,
      score: { intentScore: 0, keywordScore: 0, safetyScore: 0, total: 0, found: [], foundForbidden: [], expected: [], forbidden: [] },
      intent_confidence: null, planning_strategy: null, chosen_tool: null, chosen_tools: [],
      tool_arguments: {}, tool_result: null, execution_trace: [], planning: null, memory_debug: null,
    };
    state.running.delete(id);
    renderCases();
  }
  updateStats();
}

async function runAll() {
  if (state.isRunningAll) return;
  state.isRunningAll = true;
  $('runAllBtn').textContent = '⏹ 停止';
  $('runAllBtn').onclick = stopAll;
  const visible = getFilteredCases();
  for (let i = 0; i < visible.length; i++) {
    if (!state.isRunningAll) break;
    await runCase(visible[i]);
    progressFill.style.width = `${((i + 1) / visible.length) * 100}%`;
  }
  state.isRunningAll = false;
  $('runAllBtn').textContent = '▶ 运行全部';
  $('runAllBtn').onclick = runAll;
}

function stopAll() {
  state.isRunningAll = false;
  if (state.abortController) { try { state.abortController.abort(); } catch {} state.abortController = null; }
  state.running.forEach(id => {
    state.results[id] = {
      passed: false, answer: '', intent: '', intentOk: false,
      missingKeywords: [], foundForbidden: [], duration: '-',
      error: '已手动取消',
      score: { intentScore: 0, keywordScore: 0, safetyScore: 0, total: 0, found: [], foundForbidden: [], expected: [], forbidden: [] },
      intent_confidence: null, planning_strategy: null, chosen_tool: null, chosen_tools: [],
      tool_arguments: {}, tool_result: null, execution_trace: [], planning: null, memory_debug: null,
    };
  });
  state.running.clear();
  $('runAllBtn').textContent = '▶ 运行全部';
  $('runAllBtn').onclick = runAll;
  updateStats();
  renderCases();
}

function escapeHtml(t) { return String(t||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function getFilteredCases() {
  let cases = EVALUATION_CASES;
  if (state.filter !== 'all') cases = cases.filter(c => c.id.startsWith(state.filter));
  return cases;
}

function scoreColor(score) {
  if (score >= 80) return 'var(--green)';
  if (score >= 60) return 'var(--yellow)';
  return 'var(--red)';
}
function scoreBarClass(score) {
  if (score >= 80) return 'bar-green';
  if (score >= 60) return 'bar-yellow';
  return 'bar-red';
}

function renderCases() {
  const cases = getFilteredCases();
  tableBody.innerHTML = cases.map(c => renderRow(c)).join('');
  renderFilters();
}

function renderRow(c) {
  const r = state.results[c.id];
  const running = state.running.has(c.id);
  const status = running ? 'running' : r ? (r.passed ? 'pass' : 'fail') : 'idle';
  const sc = r?.score?.total;
  let statusBadge = '', scoreText = '-', duration = '-';
  if (running) { statusBadge = '<span class="badge skip"><span class="spinner"></span> 运行中</span>'; }
  else if (status === 'pass') { statusBadge = '<span class="badge pass">✓ 通过</span>'; duration = r.duration + 's'; }
  else if (status === 'fail') { statusBadge = '<span class="badge fail">✗ 失败</span>'; duration = r.duration + 's'; }
  else { statusBadge = '<span class="badge idle">待运行</span>'; }

  if (sc != null) {
    scoreText = `<span class="score-cell" style="color:${scoreColor(sc)}">${sc}</span>`;
  }

  const intentBadge = r ? (r.intentOk
    ? `<span class="badge intent-ok">✓ ${escapeHtml(r.intent)}</span>`
    : `<span class="badge intent-fail">✗ ${escapeHtml(r.intent || '?')}</span>`
  ) : '-';

  const runBtn = running
    ? '<button class="small" disabled><span class="spinner"></span></button>'
    : `<button class="small" onclick="event.stopPropagation();runCase(EVALUATION_CASES.find(x=>x.id==='${c.id}'))">运行</button>`;

  return `<div class="table-row ${status}" onclick="showDetail('${c.id}')">
    <span class="case-id">${c.id}</span>
    <span class="case-question" title="${escapeHtml(c.question)}">${escapeHtml(c.question)}</span>
    <span style="font-size:12px">${intentBadge}</span>
    <span>${statusBadge}</span>
    <span>${scoreText}</span>
    <span style="font-size:12px">${duration}</span>
    <span onclick="event.stopPropagation()">${runBtn}</span>
  </div>`;
}

function updateStats() {
  const results = Object.values(state.results);
  const pass = results.filter(r => r.passed).length;
  const fail = results.filter(r => !r.passed).length;
  const running = state.running.size;
  const total = EVALUATION_CASES.length;
  const rate = results.length > 0 ? ((pass / results.length) * 100).toFixed(0) + '%' : '-';
  const scores = results.filter(r => r.score).map(r => r.score.total);
  const avg = scores.length > 0 ? (scores.reduce((a,b)=>a+b,0) / scores.length).toFixed(0) : '-';
  $('totalCases').textContent = total;
  $('passCount').textContent = pass;
  $('failCount').textContent = fail;
  $('runningCount').textContent = running;
  $('passRate').textContent = rate;
  $('avgScore').textContent = avg;
  try { updateMetrics(); } catch {}
}

function updateMetrics() {
  const panel = $('metricsPanel');
  const grid = $('metricsGrid');
  const results = Object.values(state.results);
  if (results.length === 0) { panel.classList.remove('visible'); return; }
  panel.classList.add('visible');

  const total = results.length;
  const passed = results.filter(r => r.passed).length;
  const passRate = (passed / total * 100);
  const avgDuration = (results.reduce((s, r) => s + parseFloat(r.duration || 0), 0) / total);
  const intentOk = results.filter(r => r.intentOk).length;
  const intentRate = (intentOk / total * 100);
  const scores = results.filter(r => r.score).map(r => r.score.total);
  const avgScore = scores.length > 0 ? (scores.reduce((a,b)=>a+b,0) / scores.length) : 0;

  let totalKw = 0, foundKw = 0;
  results.forEach(r => {
    const c = EVALUATION_CASES.find(x => x.id === r.id);
    if (c && r.score) { totalKw += r.score.expected.length; foundKw += r.score.found.length; }
  });
  const kwRate = totalKw > 0 ? (foundKw / totalKw * 100) : 0;

  let safetyViolations = 0;
  results.forEach(r => { if (r.foundForbidden && r.foundForbidden.length > 0) safetyViolations++; });

  // RAGAS aggregate
  const ragasResults = results.filter(r => r.ragas);
  let ragasFaith = 0, ragasRelev = 0, ragasRecall = 0, ragasPreci = 0, ragasOverall = 0;
  if (ragasResults.length > 0) {
    ragasFaith = ragasResults.reduce((s, r) => s + (r.ragas?.faithfulness?.score || 0), 0) / ragasResults.length * 100;
    ragasRelev = ragasResults.reduce((s, r) => s + (r.ragas?.answer_relevancy?.score || 0), 0) / ragasResults.length * 100;
    ragasRecall = ragasResults.reduce((s, r) => s + (r.ragas?.context_recall?.score || 0), 0) / ragasResults.length * 100;
    ragasPreci = ragasResults.reduce((s, r) => s + (r.ragas?.context_precision?.score || 0), 0) / ragasResults.length * 100;
    ragasOverall = ragasResults.reduce((s, r) => s + (r.ragas?.overall_score || 0), 0) / ragasResults.length * 100;
  }

  $('metricsSummary').textContent = `通过率 ${passRate.toFixed(0)}% · 均分 ${avgScore.toFixed(0)} · RAGAS ${ragasResults.length > 0 ? ragasOverall.toFixed(0) : '-'} · 共 ${total} 条`;

  grid.innerHTML = `
    <div class="metric-card">
      <div class="metric-value" style="color:${scoreColor(avgScore)}">${avgScore.toFixed(0)}</div>
      <div class="metric-label">综合均分</div>
      <div class="metric-bar"><div class="metric-bar-fill ${scoreBarClass(avgScore)}" style="width:${avgScore}%"></div></div>
    </div>
    <div class="metric-card">
      <div class="metric-value" style="color:${passRate>=80?'var(--green)':passRate>=50?'var(--yellow)':'var(--red)'}">${passRate.toFixed(0)}%</div>
      <div class="metric-label">通过率</div>
      <div class="metric-bar"><div class="metric-bar-fill ${scoreBarClass(passRate)}" style="width:${passRate}%"></div></div>
    </div>
    <div class="metric-card">
      <div class="metric-value" style="color:${intentRate>=80?'var(--green)':intentRate>=50?'var(--yellow)':'var(--red)'}">${intentRate.toFixed(0)}%</div>
      <div class="metric-label">意图准确率</div>
      <div class="metric-bar"><div class="metric-bar-fill ${scoreBarClass(intentRate)}" style="width:${intentRate}%"></div></div>
    </div>
    <div class="metric-card">
      <div class="metric-value" style="color:${kwRate>=80?'var(--green)':kwRate>=50?'var(--yellow)':'var(--red)'}">${kwRate.toFixed(0)}%</div>
      <div class="metric-label">关键词覆盖率</div>
      <div class="metric-bar"><div class="metric-bar-fill ${scoreBarClass(kwRate)}" style="width:${kwRate}%"></div></div>
    </div>
    <div class="metric-card">
      <div class="metric-value" style="color:${safetyViolations>0?'var(--red)':'var(--green)'}">${safetyViolations}</div>
      <div class="metric-label">安全违规数</div>
    </div>
    <div class="metric-card">
      <div class="metric-value" style="color:var(--text)">${avgDuration.toFixed(1)}s</div>
      <div class="metric-label">平均响应时间</div>
    </div>
    ${ragasResults.length > 0 ? `
    <div class="metric-card" style="border-color:rgba(99,102,241,.3)">
      <div class="metric-value" style="color:var(--accent)">${ragasOverall.toFixed(0)}%</div>
      <div class="metric-label">RAGAS 均分</div>
      <div class="metric-bar"><div class="metric-bar-fill ${scoreBarClass(ragasOverall)}" style="width:${ragasOverall}%"></div></div>
    </div>
    <div class="metric-card">
      <div class="metric-value" style="font-size:18px;color:var(--cyan)">${ragasFaith.toFixed(0)}%</div>
      <div class="metric-label">忠实度</div>
    </div>
    <div class="metric-card">
      <div class="metric-value" style="font-size:18px;color:var(--purple)">${ragasRelev.toFixed(0)}%</div>
      <div class="metric-label">答案相关性</div>
    </div>
    <div class="metric-card">
      <div class="metric-value" style="font-size:18px;color:var(--orange)">${ragasRecall.toFixed(0)}%</div>
      <div class="metric-label">上下文召回</div>
    </div>
    <div class="metric-card">
      <div class="metric-value" style="font-size:18px;color:var(--blue)">${ragasPreci.toFixed(0)}%</div>
      <div class="metric-label">上下文精确</div>
    </div>
    ` : ''}
  `;

  const categories = {};
  EVALUATION_CASES.forEach(c => {
    const cat = c.id.split('-')[0];
    if (!categories[cat]) categories[cat] = { pass: 0, total: 0, scores: [] };
    categories[cat].total++;
    const r = state.results[c.id];
    if (r?.passed) categories[cat].pass++;
    if (r?.score) categories[cat].scores.push(r.score.total);
  });

  let catHtml = '<div style="grid-column:1/-1;margin-top:8px"><strong style="font-size:12px;color:var(--text-dim)">分类表现</strong></div>';
  Object.keys(categories).sort().forEach(cat => {
    const c = categories[cat];
    const rate = c.total > 0 ? (c.pass / c.total * 100) : 0;
    const avg = c.scores.length > 0 ? (c.scores.reduce((a,b)=>a+b,0) / c.scores.length).toFixed(0) : '-';
    catHtml += `
      <div class="metric-card" style="padding:10px 12px;text-align:left">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:13px;font-weight:600">${cat}</span>
          <span style="font-size:13px;font-weight:700;color:${scoreColor(parseFloat(avg)||0)}">${avg}分</span>
        </div>
        <div style="font-size:11px;color:var(--text-dim)">${c.pass}/${c.total} 通过</div>
        <div class="metric-bar"><div class="metric-bar-fill ${scoreBarClass(rate)}" style="width:${rate}%"></div></div>
      </div>`;
  });
  grid.innerHTML += catHtml;

  // Intent confusion matrix
  const allExpected = [...new Set(EVALUATION_CASES.flatMap(c => c.expected_intents))];
  const intentCounts = {};
  EVALUATION_CASES.forEach(c => {
    const expected = c.expected_intents[0];
    const actual = state.results[c.id]?.intent || '(无)';
    const key = `${expected}→${actual}`;
    intentCounts[key] = (intentCounts[key] || 0) + 1;
  });
  const actualIntents = [...new Set(Object.keys(intentCounts).map(k => k.split('→')[1]))];

  let matrixHtml = '<div style="grid-column:1/-1;margin-top:8px"><strong style="font-size:12px;color:var(--text-dim)">意图混淆矩阵</strong></div>';
  matrixHtml += '<div style="overflow-x:auto;font-size:11px;grid-column:1/-1"><table style="width:100%;border-collapse:collapse;margin-top:4px">';
  matrixHtml += '<tr><td style="padding:4px 8px;color:var(--text-dim)">期望→实际</td>';
  actualIntents.forEach(a => { matrixHtml += `<td style="padding:4px 8px;text-align:center;color:var(--text-dim)">${escapeHtml(a?.slice(0,14)||'')}</td>`; });
  matrixHtml += '</tr>';
  allExpected.forEach(expected => {
    matrixHtml += `<tr><td style="padding:4px 8px;font-weight:600">${escapeHtml(expected?.slice(0,14)||'')}</td>`;
    actualIntents.forEach(actual => {
      const count = intentCounts[`${expected}→${actual}`] || 0;
      const color = expected === actual ? 'var(--green)' : count > 0 ? 'var(--red)' : 'var(--border)';
      matrixHtml += `<td style="padding:4px 8px;text-align:center;color:${color}">${count || '-'}</td>`;
    });
    matrixHtml += '</tr>';
  });
  matrixHtml += '</table></div>';
  grid.innerHTML += matrixHtml;
}

function renderFilters() {
  const groups = new Set();
  EVALUATION_CASES.forEach(c => groups.add(c.id.split('-')[0]));
  filterBar.innerHTML = `
    <button class="filter-btn ${state.filter==='all'?'active':''}" onclick="setFilter('all')">全部 (${EVALUATION_CASES.length})</button>
    ${Array.from(groups).sort().map(g => {
      const count = EVALUATION_CASES.filter(c => c.id.startsWith(g)).length;
      return `<button class="filter-btn ${state.filter===g?'active':''}" onclick="setFilter('${g}')">${g} (${count})</button>`;
    }).join('')}
  `;
}
function setFilter(f) { state.filter = f; renderCases(); }

function showDetail(id) {
  const c = EVALUATION_CASES.find(x => x.id === id);
  const r = state.results[id];
  if (!c || !r) return;
  const panel = $('detailPanel');
  panel.classList.add('open');
  $('detailTitle').textContent = `${c.id}: ${c.question}`;
  panel.dataset.caseId = id;
  renderDetailTab('overview', c, r);

  document.querySelectorAll('.detail-tab').forEach(tab => {
    tab.onclick = () => {
      document.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      renderDetailTab(tab.dataset.tab, c, r);
    };
  });
}

function renderDetailTab(tab, c, r) {
  const content = $('detailContent');
  const sc = r.score || {};
  if (tab === 'overview') content.innerHTML = renderOverviewTab(c, r, sc);
  else if (tab === 'ragas') content.innerHTML = renderRAGASTab(r);
  else if (tab === 'intent') content.innerHTML = renderIntentTab(c, r);
  else if (tab === 'keywords') content.innerHTML = renderKeywordsTab(c, r, sc);
  else if (tab === 'trace') content.innerHTML = renderTraceTab(r);
  else if (tab === 'answer') content.innerHTML = renderAnswerTab(r);
}

function renderOverviewTab(c, r, sc) {
  const verdict = r.passed ? '通过' : '失败';
  const verdictClass = r.passed ? 'pass' : 'fail';
  const failReasons = [];
  if (!r.intentOk) failReasons.push(`意图识别不匹配（期望 ${c.expected_intents.join(' / ')}，实际 ${r.intent || '无'}）`);
  if (r.missingKeywords?.length) failReasons.push(`缺少关键词：${r.missingKeywords.join('、')}`);
  if (r.foundForbidden?.length) failReasons.push(`命中禁用词：${r.foundForbidden.join('、')}`);
  if (r.error) failReasons.push(`请求异常：${r.error}`);

  return `
    <div class="analysis-grid">
      <div class="analysis-card">
        <h4>📊 综合评分</h4>
        <div class="score-bar">
          <div class="score-bar-track"><div class="score-bar-fill ${scoreBarClass(sc.total||0)}" style="width:${sc.total||0}%"></div></div>
          <div class="score-bar-value" style="color:${scoreColor(sc.total||0)}">${sc.total || 0}/100</div>
        </div>
        <div class="sub">${c.scoring?.safety_notes || '无特殊安全要求'}</div>
      </div>
      <div class="analysis-card">
        <h4>📋 评估结果</h4>
        <div class="value" style="color:${verdictClass==='pass'?'var(--green)':'var(--red)'}">
          ${verdictClass==='pass'?'✓':'✗'} ${verdict}
        </div>
        <div class="sub">耗时 ${r.duration || '-'}s ${r.patient_id ? '· 患者 ' + r.patient_id.slice(0,8) : ''}</div>
      </div>
      <div class="analysis-card">
        <h4>🎯 分项得分</h4>
        <div class="score-breakdown">
          <div class="score-row">
            <span class="score-row-label">意图识别</span>
            <span class="score-row-value" style="color:${r.intentOk?'var(--green)':'var(--red)'}">${r.intentOk?'100':'0'}</span>
            <span class="score-row-weight">权重 ${(c.scoring?.intent_weight||0.3)*100}%</span>
          </div>
          <div class="score-row">
            <span class="score-row-label">关键词覆盖</span>
            <span class="score-row-value" style="color:${scoreColor(sc.keywordScore||0)}">${(sc.keywordScore||0).toFixed(0)}</span>
            <span class="score-row-weight">权重 ${(c.scoring?.keyword_weight||0.4)*100}%</span>
          </div>
          <div class="score-row">
            <span class="score-row-label">安全合规</span>
            <span class="score-row-value" style="color:${scoreColor(sc.safetyScore||0)}">${(sc.safetyScore||0).toFixed(0)}</span>
            <span class="score-row-weight">权重 ${(c.scoring?.safety_weight||0.3)*100}%</span>
          </div>
        </div>
      </div>
      <div class="analysis-card">
        <h4>🔍 失败原因</h4>
        ${failReasons.length > 0
          ? failReasons.map(r => `<div style="margin-bottom:4px;font-size:13px;color:var(--red)">• ${escapeHtml(r)}</div>`).join('')
          : '<div style="font-size:13px;color:var(--green)">无</div>'
        }
      </div>
    </div>
    <div class="reason-box ${verdictClass}" style="margin-top:12px">
      <strong>评估说明：</strong>${escapeHtml(c.evaluation_hint || '无')}
    </div>
  `;
}

function renderRAGASTab(r) {
  const ragas = r.ragas;
  if (!ragas) {
    return `<div style="text-align:center;padding:40px;color:var(--text-dim)">
      <div style="font-size:16px;margin-bottom:8px">RAGAS 评估尚未完成</div>
      <div style="font-size:13px">运行用例后将自动调用 LLM-as-Judge 进行评估。</div>
    </div>`;
  }

  const dims = [
    { key: 'faithfulness', label: 'Faithfulness (忠实度)', icon: '🔬', desc: '回答是否忠实于检索上下文，是否有幻觉' },
    { key: 'answer_relevancy', label: 'Answer Relevancy (答案相关性)', icon: '🎯', desc: '回答是否切题，是否直接回答了用户问题' },
    { key: 'context_recall', label: 'Context Recall (上下文召回率)', icon: '📥', desc: '检索上下文是否包含回答所需的关键信息' },
    { key: 'context_precision', label: 'Context Precision (上下文精确度)', icon: '🔍', desc: '检索上下文是否精准，噪声是否少' },
  ];

  const overall = ragas.overall_score || 0;
  const overallColor = overall >= 0.8 ? 'var(--green)' : overall >= 0.6 ? 'var(--yellow)' : 'var(--red)';

  let dimHtml = dims.map(d => {
    const dim = ragas[d.key] || { score: 0, reason: '无数据' };
    const pct = (dim.score * 100).toFixed(0);
    const barClass = dim.score >= 0.8 ? 'bar-green' : dim.score >= 0.6 ? 'bar-yellow' : 'bar-red';
    const barColor = dim.score >= 0.8 ? 'var(--green)' : dim.score >= 0.6 ? 'var(--yellow)' : 'var(--red)';
    return `
      <div class="analysis-card">
        <h4>${d.icon} ${d.label}</h4>
        <div style="display:flex;align-items:center;gap:12px;margin:8px 0">
          <div class="score-bar-track" style="flex:1">
            <div class="score-bar-fill ${barClass}" style="width:${pct}%"></div>
          </div>
          <span class="score-bar-value" style="color:${barColor};min-width:48px;text-align:right">${pct}%</span>
        </div>
        <div class="sub" style="margin-bottom:6px">${d.desc}</div>
        <div style="font-size:12px;color:var(--text);line-height:1.7;background:var(--surface);padding:8px 10px;border-radius:6px">
          ${escapeHtml(dim.reason)}
        </div>
      </div>
    `;
  }).join('');

  return `
    <div class="analysis-card" style="margin-bottom:16px;text-align:center;padding:20px">
      <h4 style="justify-content:center">📊 RAGAS 综合评分</h4>
      <div style="font-size:48px;font-weight:800;color:${overallColor};margin:8px 0">${(overall * 100).toFixed(1)}</div>
      <div class="sub">4 维度加权平均</div>
    </div>
    <div class="analysis-grid">${dimHtml}</div>
  `;
}

function renderIntentTab(c, r) {
  const matched = r.intentOk;
  const allExpected = c.expected_intents || [];
  const actual = r.intent || '(无)';
  const conf = r.intent_confidence != null ? (r.intent_confidence * 100).toFixed(1) + '%' : '未知';
  const strategy = r.planning_strategy || '(未返回)';

  let expectedList = allExpected.map(e => {
    const isMatch = e === actual;
    return `<span class="kw-tag ${isMatch?'found':'missed'}">${isMatch?'✓':'✗'} ${escapeHtml(e)}</span>`;
  }).join('');

  return `
    <div class="analysis-grid">
      <div class="analysis-card">
        <h4>🎯 意图判定结果</h4>
        <div class="value" style="color:${matched?'var(--green)':'var(--red)'}">
          ${matched?'✓ 匹配':'✗ 不匹配'}
        </div>
        <div class="sub">识别置信度：${conf}</div>
      </div>
      <div class="analysis-card">
        <h4>🧠 规划策略</h4>
        <div class="value" style="font-size:14px">${escapeHtml(strategy)}</div>
      </div>
      <div class="analysis-card">
        <h4>期望意图（可接受）</h4>
        <div class="kw-list">${expectedList || '<span style="color:var(--text-dim)">无</span>'}</div>
      </div>
      <div class="analysis-card">
        <h4>实际意图</h4>
        <div class="value" style="font-size:14px">${escapeHtml(actual)}</div>
        <div class="sub">如果期望意图列表中包含实际意图，也会视为匹配</div>
      </div>
    </div>
    <div style="margin-top:14px">
      <h4 style="font-size:13px;color:var(--text-dim);margin-bottom:8px">💡 意图分析</h4>
      <div style="background:var(--surface2);padding:14px;border-radius:8px;font-size:13px;line-height:1.8;border:1px solid var(--border)">
        ${matched
          ? `<span style="color:var(--green)">✓</span> 模型返回意图 <code>${escapeHtml(actual)}</code> 在期望列表中。`
          : `<span style="color:var(--red)">✗</span> 模型返回意图 <code>${escapeHtml(actual)}</code> 不在期望列表 [${allExpected.map(e=>`<code>${escapeHtml(e)}</code>`).join(', ')}] 中。<br>
            <span style="color:var(--text-dim)">可能原因：</span><br>
            ① LLM 意图分类偏差 — 可通过优化 system prompt 中的意图定义来校准<br>
            ② 系统路由规则冲突 — 检查 MCP 工具层的意图路由逻辑<br>
            ③ 用例期望过窄 — 如果实际意图合理，可扩展 expected_intents 列表`
        }
      </div>
    </div>
  `;
}

function renderKeywordsTab(c, r, sc) {
  const expected = c.expected_keywords || [];
  const forbidden = c.forbidden_keywords || [];
  const answer = (r.answer || '').toLowerCase();

  const expectedHtml = expected.map(kw => {
    const found = answer.includes(kw.toLowerCase());
    return `<span class="kw-tag ${found?'found':'missed'}">${found?'✓':'✗'} ${escapeHtml(kw)}</span>`;
  }).join('');

  const forbiddenHtml = forbidden.map(kw => {
    const found = answer.includes(kw.toLowerCase());
    return `<span class="kw-tag ${found?'forbidden':'found'}">${found?'⚠':'✓'} ${escapeHtml(kw)}</span>`;
  }).join('');

  return `
    <div class="analysis-grid">
      <div class="analysis-card">
        <h4>✓ 期望关键词 (${sc.found?.length||0}/${expected.length})</h4>
        <div class="kw-list">${expectedHtml || '<span style="color:var(--text-dim)">无</span>'}</div>
        <div class="sub" style="margin-top:8px">覆盖率 ${sc.keywordScore?.toFixed(0)||0}%</div>
      </div>
      <div class="analysis-card">
        <h4>⚠ 禁用关键词 (${sc.foundForbidden?.length||0}/${forbidden.length})</h4>
        <div class="kw-list">${forbiddenHtml || '<span style="color:var(--text-dim)">无</span>'}</div>
        <div class="sub" style="margin-top:8px">${forbidden.length > 0 ? (sc.foundForbidden?.length > 0 ? '❌ 存在安全违规' : '✓ 无违规') : '该用例无禁用词要求'}</div>
      </div>
    </div>
  `;
}

function renderTraceTab(r) {
  const trace = r.execution_trace || [];
  const tool = r.chosen_tool || '(无)';
  const tools = r.chosen_tools || [];
  const args = r.tool_arguments || {};
  const result = r.tool_result;

  let traceHtml = '';
  if (trace.length > 0) {
    traceHtml = trace.map((step, i) => {
      const type = step.type || step.kind || 'step';
      const label = step.tool || step.intent || step.type || `Step ${i+1}`;
      const detail = step.detail || step.description || step.result || step.input || '';
      const cls = type === 'tool' ? 'tool' : type === 'intent' ? 'intent' : 'llm';
      return `<div class="trace-item ${cls}">
        <div class="trace-label ${cls}">${escapeHtml(String(label))}</div>
        <div style="font-size:12px;color:var(--text);white-space:pre-wrap">${escapeHtml(typeof detail === 'string' ? detail : JSON.stringify(detail, null, 2))}</div>
      </div>`;
    }).join('');
  } else {
    traceHtml = '<div style="color:var(--text-dim);font-size:13px">无执行链路数据</div>';
  }

  return `
    <div class="analysis-grid">
      <div class="analysis-card">
        <h4>🔧 选用工具</h4>
        <div class="value" style="font-size:14px">${escapeHtml(tool)}</div>
        ${tools.length ? `<div class="sub">工具链: ${tools.map(t => `<code>${escapeHtml(t)}</code>`).join(' → ')}</div>` : ''}
      </div>
      <div class="analysis-card">
        <h4>📥 工具参数</h4>
        <pre style="background:var(--surface);padding:10px;border-radius:6px;font-size:11px;max-height:200px;overflow:auto;margin:0;border:1px solid var(--border)">${escapeHtml(JSON.stringify(args, null, 2))}</pre>
      </div>
    </div>
    <div style="margin-top:14px">
      <h4 style="font-size:13px;color:var(--text-dim);margin-bottom:8px">🔗 执行链路 (${trace.length} 步)</h4>
      ${traceHtml}
    </div>
    ${result ? `
    <div style="margin-top:14px">
      <h4 style="font-size:13px;color:var(--text-dim);margin-bottom:8px">📤 工具返回</h4>
      <pre style="background:var(--surface2);padding:12px;border-radius:8px;font-size:12px;max-height:300px;overflow:auto;border:1px solid var(--border);white-space:pre-wrap">${escapeHtml(typeof result === 'string' ? result : JSON.stringify(result, null, 2))}</pre>
    </div>` : ''}
  `;
}

function renderAnswerTab(r) {
  if (r.error) {
    return `<div class="reason-box fail"><strong>错误：</strong>${escapeHtml(r.error)}</div>`;
  }
  return `
    <h4 style="font-size:13px;color:var(--text-dim);margin-bottom:8px">模型完整回答</h4>
    <div class="answer-text">${escapeHtml(r.answer || '(无回答)')}</div>
    ${r.memory_debug ? `
    <details style="margin-top:14px">
      <summary style="font-size:12px;color:var(--text-dim);cursor:pointer;padding:8px 0">▸ Memory Debug 信息</summary>
      <pre style="background:var(--surface2);padding:12px;border-radius:8px;font-size:11px;max-height:300px;overflow:auto;border:1px solid var(--border);white-space:pre-wrap">${escapeHtml(JSON.stringify(r.memory_debug, null, 2))}</pre>
    </details>` : ''}
  `;
}

$('closeDetail').onclick = () => $('detailPanel').classList.remove('open');
$('runAllBtn').onclick = runAll;
$('clearBtn').onclick = () => {
  if (state.abortController) { try { state.abortController.abort(); } catch {} state.abortController = null; }
  state.results = {}; state.running.clear(); state.isRunningAll = false;
  $('runAllBtn').disabled = false; $('runAllBtn').textContent = '▶ 运行全部'; $('runAllBtn').onclick = runAll;
  progressFill.style.width = '0%'; renderCases(); $('detailPanel').classList.remove('open'); updateStats();
};
$('runPassedBtn').onclick = () => {
  const failed = EVALUATION_CASES.filter(c => { const r = state.results[c.id]; return r && !r.passed; });
  if (failed.length === 0) { alert('没有失败的用例'); return; }
  failed.forEach(c => runCase(c));
};
$('exportBtn').onclick = exportReport;

function exportReport() {
  const results = Object.values(state.results);
  if (results.length === 0) { alert('没有可导出的结果'); return; }
  const rows = [['用例ID','问题','期望意图','实际意图','意图匹配','期望关键词','缺失关键词','禁用词命中','安全分','关键词分','意图分','总分','通过','耗时','RAGAS忠实度','RAGAS相关性','RAGAS召回','RAGAS精确','RAGAS均分','错误']];
  EVALUATION_CASES.forEach(c => {
    const r = state.results[c.id];
    if (!r) return;
    const sc = r.score || {};
    const rag = r.ragas || {};
    rows.push([
      c.id, c.question, c.expected_intents.join('/'), r.intent||'', r.intentOk?'是':'否',
      (c.expected_keywords||[]).join('/'), (r.missingKeywords||[]).join('/'), (r.foundForbidden||[]).join('/'),
      (sc.safetyScore||0).toFixed(0), (sc.keywordScore||0).toFixed(0), (sc.intentScore||0).toFixed(0),
      (sc.total||0).toString(), r.passed?'通过':'失败', r.duration+'s',
      rag.faithfulness ? (rag.faithfulness.score*100).toFixed(0)+'%' : '-',
      rag.answer_relevancy ? (rag.answer_relevancy.score*100).toFixed(0)+'%' : '-',
      rag.context_recall ? (rag.context_recall.score*100).toFixed(0)+'%' : '-',
      rag.context_precision ? (rag.context_precision.score*100).toFixed(0)+'%' : '-',
      rag.overall_score != null ? (rag.overall_score*100).toFixed(1)+'%' : '-',
      r.error||''
    ]);
  });
  const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g,'""')}"`).join(',')).join('\n');
  const blob = new Blob(['\uFEFF'+csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = `eval-report-${new Date().toISOString().slice(0,10)}.csv`;
  a.click(); URL.revokeObjectURL(url);
}

async function checkServer() {
  try {
    const resp = await fetch(`${getBase()}/health`);
    $('serverDot').className = resp.ok ? 'server-dot' : 'server-dot offline';
    $('serverText').textContent = resp.ok ? '服务正常' : '服务异常';
  } catch {
    $('serverDot').className = 'server-dot offline';
    $('serverText').textContent = '无法连接 (确保服务已启动)';
  }
}

// ── 启动序列：先探活 → 再拉用例 ──
checkServer();
setInterval(checkServer, 10000);
loadCases();

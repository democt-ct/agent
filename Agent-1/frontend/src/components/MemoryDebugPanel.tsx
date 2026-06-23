import { useState } from 'react';
import { useAppState } from '../context/AppContext';

export function MemoryDebugPanel() {
  const { state } = useAppState();
  const [showJson, setShowJson] = useState(false);

  const wm = state.workingMemory;
  const ml = state.memoryLayers;

  if (!wm && !ml) return null;

  const sessionState = wm?.session_state;
  const activeEntities = wm?.active_entities;
  const riskSignals = wm?.risk_signals;

  const entityItems = [
    ...(activeEntities?.drugs ?? []).map((s) => `💊 ${s}`),
    ...(activeEntities?.symptoms ?? []).map((s) => `🤒 ${s}`),
    ...(activeEntities?.tests ?? []).map((s) => `🔬 ${s}`),
    ...(activeEntities?.metrics ?? []).map((s) => `📊 ${s}`),
  ];

  const riskItems = [
    ...(riskSignals?.red_flags ?? []).map((s) => `🚩 ${s}`),
    ...(riskSignals?.medication_flags ?? []).map((s) => `💉 ${s}`),
    ...(riskSignals?.monitoring_flags ?? []).map((s) => `📋 ${s}`),
  ];

  const cards = [
    {
      title: '工作记忆',
      lines: [
        `意图: ${sessionState?.intent || '无'}`,
        `当前主题: ${sessionState?.current_topic || '无'}`,
        `目标: ${sessionState?.goal || '无'}`,
        `工作摘要: ${sessionState?.working_summary || '无'}`,
        `下一步: ${sessionState?.next_action || '无'}`,
        `记忆焦点: ${sessionState?.memory_focus || '无'}`,
      ],
      extra: (wm?.recent_messages ?? []).slice(-4).map(
        (m) => `${m.role === 'assistant' ? '助手' : '用户'}: ${m.content?.slice(0, 60) ?? ''}`
      ),
    },
    {
      title: '活跃实体',
      lines: entityItems.length ? entityItems : ['无'],
    },
    {
      title: '风险信号',
      lines: riskItems.length ? riskItems : ['本轮未触发安全信号'],
    },
    {
      title: '事实记忆',
      lines: [ml?.factual_memory || '未命中'],
    },
    {
      title: '长期摘要记忆',
      lines: [ml?.long_term_summary_memory || '未命中'],
    },
    {
      title: '知识记忆',
      lines: [ml?.knowledge_memory || '未命中'],
    },
  ];

  return (
    <div className="memory-debug">
      <div className="memory-debug-header">
        <h3>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: -3, marginRight: 6 }}>
            <path d="M9.5 2A2.5 2.5 0 0112 4.5v15a2.5 2.5 0 01-4.96.44 2.5 2.5 0 01-2.96-3.08 3 3 0 01-.34-5.58 2.5 2.5 0 011.32-4.24 2.5 2.5 0 011.98-3A2.5 2.5 0 019.5 2z"/>
            <path d="M14.5 2A2.5 2.5 0 0012 4.5v15a2.5 2.5 0 004.96.44 2.5 2.5 0 002.96-3.08 3 3 0 00.34-5.58 2.5 2.5 0 00-1.32-4.24 2.5 2.5 0 00-1.98-3A2.5 2.5 0 0014.5 2z"/>
          </svg>
          Memory Debug
        </h3>
        <button
          className="btn btn-sm"
          onClick={() => setShowJson(!showJson)}
        >
          {showJson ? '卡片视图' : 'JSON 视图'}
        </button>
      </div>

      {showJson ? (
        <pre className="memory-json">
          {JSON.stringify({ working_memory: wm, memory_layers: ml }, null, 2)}
        </pre>
      ) : (
        <div className="memory-cards">
          {cards.map((card) => (
            <div key={card.title} className="memory-card">
              <h4>{card.title}</h4>
              {card.lines.map((line, i) => (
                <p key={i}>{line}</p>
              ))}
              {card.extra && card.extra.length > 0 && (
                <div className="memory-card-extra">
                  {card.extra.map((e, i) => (
                    <p key={i} className="text-sm">{e}</p>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

import { useState, useEffect } from 'react';
import { useAppState } from '../context/AppContext';
import { patientApi, memoryApi } from '../services/api';
import type { ConversationSession } from '../types';

interface SidebarProps {
  onClose: () => void;
}

export function Sidebar({ onClose }: SidebarProps) {
  const { state, dispatch } = useAppState();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchStatus, setSearchStatus] = useState('');
  const [sessions, setSessions] = useState<ConversationSession[]>([]);
  const [showPatientSearch, setShowPatientSearch] = useState(false);
  const [loadingSession, setLoadingSession] = useState<string | null>(null);

  useEffect(() => {
    if (state.patientId && state.chatMode === 'memory') {
      memoryApi.getSessions(state.patientId)
        .then(setSessions)
        .catch(() => setSessions([]));
    }
  }, [state.patientId, state.chatMode]);

  const handleSearch = async () => {
    const query = searchQuery.trim();
    if (!query) { setSearchStatus('请输入手机号或姓名'); return; }
    setSearchStatus('搜索中...');
    try {
      const isPhone = /^\d{3,}$/.test(query);
      let patients;
      if (isPhone) {
        patients = await patientApi.list(undefined, query);
      } else {
        patients = await patientApi.list(undefined, undefined, query);
      }
      dispatch({ type: 'SET_PATIENTS', payload: patients });
      if (patients.length > 0) {
        const p = patients[0];
        dispatch({
          type: 'SET_PATIENT_CONTEXT',
          payload: {
            patientId: p.id,
            hospitalId: p.hospital_id,
            profileName: p.full_name,
            profilePhone: p.phone ?? '',
          },
        });
        dispatch({ type: 'SET_SELECTED_PATIENT', payload: p });
        setSearchStatus(`已选中 ${p.full_name}`);
        setShowPatientSearch(false);
      } else {
        setSearchStatus('未找到患者');
      }
    } catch (err) {
      setSearchStatus(`搜索失败: ${(err as Error).message}`);
    }
  };

  const handleShowAll = async () => {
    setSearchStatus('加载中...');
    try {
      const patients = await patientApi.list();
      dispatch({ type: 'SET_PATIENTS', payload: patients });
      if (patients.length > 0) {
        setSearchStatus(`找到 ${patients.length} 位患者`);
      } else {
        setSearchStatus('未找到匹配的患者，请检查姓名或手机号');
      }
    } catch (err) {
      setSearchStatus(`加载失败: ${(err as Error).message}`);
    }
  };

  const handleClearContext = () => {
    dispatch({ type: 'CLEAR_PATIENT_CONTEXT' });
    dispatch({ type: 'SET_PATIENTS', payload: [] });
    dispatch({ type: 'SET_SELECTED_PATIENT', payload: null });
    dispatch({ type: 'SET_PATIENT_PROFILE', payload: null });
    setSearchQuery('');
    setSearchStatus('');
  };

  const handleSelectPatient = async (patientId: string) => {
    try {
      const [patient, profile] = await Promise.all([
        patientApi.get(patientId),
        patientApi.getProfile(patientId),
      ]);
      dispatch({ type: 'SET_SELECTED_PATIENT', payload: patient });
      dispatch({ type: 'SET_PATIENT_PROFILE', payload: profile });
      dispatch({
        type: 'SET_PATIENT_CONTEXT',
        payload: {
          patientId: patient.id,
          hospitalId: patient.hospital_id,
          profileName: patient.full_name,
          profilePhone: patient.phone ?? '',
        },
      });
    } catch (err) {
      setSearchStatus(`加载失败: ${(err as Error).message}`);
    }
  };

  const handleNewChat = () => {
    dispatch({ type: 'RESET_CHAT' });
    onClose();
  };

  const handleSessionClick = async (sessionId: string) => {
    if (!state.patientId || loadingSession) return;
    setLoadingSession(sessionId);
    try {
      const messages = await memoryApi.getConversationMessages(state.patientId, sessionId);
      dispatch({ type: 'SET_CHAT_MESSAGES', payload: messages });
      dispatch({ type: 'SET_SESSION_ID', payload: sessionId });
      if (state.chatMode !== 'memory') {
        dispatch({ type: 'SET_CHAT_MODE', payload: 'memory' });
      }
      onClose();
    } catch (err) {
      setSearchStatus(`加载会话失败: ${(err as Error).message}`);
    } finally {
      setLoadingSession(null);
    }
  };

  const formatTime = (iso?: string) => {
    if (!iso) return '';
    const d = new Date(iso);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  };

  return (
    <div className="sidebar-panel">
      <div className="sidebar-panel-header">
        <h3>对话</h3>
        <button className="sidebar-close" onClick={onClose}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <div className="sidebar-panel-body">
        {/* New Chat Button */}
        <button className="sidebar-new-chat" onClick={handleNewChat}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          新建对话
        </button>

        {/* Recent Conversations — main section */}
        <div className="sidebar-section">
          <div className="sidebar-section-label">最近对话</div>
          <div className="sidebar-history">
            {/* Current session messages */}
            {state.chatMode === 'general' && state.generalChatMessages.length > 0 && (
              state.generalChatMessages.filter(m => m.role === 'user').slice(-8).reverse().map((m, i) => (
                <div key={`g-${i}`} className="sidebar-history-item active">
                  <div className="history-preview">{m.content.slice(0, 50)}{m.content.length > 50 ? '...' : ''}</div>
                </div>
              ))
            )}
            {state.chatMode === 'memory' && state.chatMessages.length > 0 && (
              state.chatMessages.filter(m => m.role === 'user').slice(-8).reverse().map((m, i) => (
                <div key={`m-${i}`} className="sidebar-history-item active">
                  <div className="history-preview">{m.content.slice(0, 50)}{m.content.length > 50 ? '...' : ''}</div>
                </div>
              ))
            )}
            {/* Memory sessions */}
            {state.chatMode === 'memory' && sessions.length > 0 && (
              sessions.filter(s => s.session_id !== state.sessionId).slice(0, 5).map((s) => (
                <div
                  key={s.session_id}
                  className={`sidebar-history-item ${loadingSession === s.session_id ? 'loading' : ''}`}
                  onClick={() => handleSessionClick(s.session_id)}
                >
                  <div className="history-meta">
                    <span className="history-time">{formatTime(s.last_message_at)}</span>
                    <span className="history-count">{s.message_count} 条</span>
                  </div>
                  <div className="history-preview">对话 · {formatTime(s.first_message_at)}</div>
                </div>
              ))
            )}
            {/* Empty state */}
            {((state.chatMode === 'general' && state.generalChatMessages.length === 0) ||
              (state.chatMode === 'memory' && state.chatMessages.length === 0 && sessions.length === 0)) && (
              <div className="sidebar-empty-inline">开始新对话，消息将显示在这里</div>
            )}
          </div>
        </div>

        {/* Patient Info — secondary section */}
        <div className="sidebar-divider" />

        {state.selectedPatient ? (
          <div className="sidebar-section">
            <div className="sidebar-section-label">当前患者</div>
            <div className="sidebar-patient-card">
              <div className="patient-card-header">
                <div className="patient-card-avatar">
                  {state.selectedPatient.full_name?.charAt(0) || '?'}
                </div>
                <div className="patient-card-info">
                  <span className="name">{state.selectedPatient.full_name}</span>
                  <span className="meta">{state.selectedPatient.patient_code} · {state.selectedPatient.gender || ''}</span>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={handleClearContext} title="清除绑定">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
              {state.patientProfile && (
                <div className="patient-card-stats">
                  {state.patientProfile.medical_records && state.patientProfile.medical_records.length > 0 && (
                    <span className="stat">{state.patientProfile.medical_records.length} 条病历</span>
                  )}
                  {state.patientProfile.visit_records && state.patientProfile.visit_records.length > 0 && (
                    <span className="stat">{state.patientProfile.visit_records.length} 条就诊</span>
                  )}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="sidebar-section">
            <button className="sidebar-search-toggle" onClick={() => setShowPatientSearch(!showPatientSearch)}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
                <circle cx="9" cy="7" r="4"/>
                <line x1="19" y1="8" x2="19" y2="14"/>
                <line x1="22" y1="11" x2="16" y2="11"/>
              </svg>
              绑定患者
            </button>
            {showPatientSearch && (
              <div className="sidebar-search">
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="输入手机号或姓名搜索..."
                />
                <button className="btn btn-primary btn-sm" onClick={handleSearch}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="8"/>
                    <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                  </svg>
                </button>
              </div>
            )}
            {showPatientSearch && (
              <button className="btn btn-ghost btn-sm" onClick={handleShowAll} style={{ width: '100%', marginBottom: 8 }}>
                查看所有患者
              </button>
            )}
            {searchStatus && <p className="sidebar-status">{searchStatus}</p>}
            {state.patients.length > 0 && (
              <div className="sidebar-patient-list">
                {state.patients.map((p) => (
                  <div
                    key={p.id}
                    className={`sidebar-patient-item ${p.id === state.patientId ? 'active' : ''}`}
                    onClick={() => handleSelectPatient(p.id)}
                  >
                    <div className="sidebar-patient-avatar">
                      {p.full_name?.charAt(0) || '?'}
                    </div>
                    <div className="sidebar-patient-info">
                      <span className="name">{p.full_name}</span>
                      <span className="meta">{p.phone || ''}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

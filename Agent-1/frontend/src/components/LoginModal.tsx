import { useState } from 'react';
import { useAppState } from '../context/AppContext';
import { patientApi } from '../services/api';

export function LoginModal() {
  const { state, dispatch } = useAppState();
  const [name, setName] = useState(state.profileName);
  const [phone, setPhone] = useState(state.profilePhone);
  const [status, setStatus] = useState('');

  if (!state.isLoginModalOpen) return null;

  const handleLogin = async () => {
    if (!name.trim() && !phone.trim()) {
      setStatus('请至少填写姓名或手机号');
      return;
    }
    try {
      const patients = await patientApi.list(state.hospitalId, phone.trim() || undefined);
      const normName = name.trim().replace(/[，,。.!！？?\s]+/g, '');

      let matched = null;
      if (patients.length === 1) {
        matched = patients[0];
      } else if (patients.length > 1 && normName) {
        matched = patients.find((p) => {
          const pn = p.full_name.replace(/[，,。.!！？?\s]+/g, '');
          return pn === normName || pn.includes(normName) || normName.includes(pn);
        }) || patients[0];
      } else if (!patients.length) {
        setStatus('未找到匹配患者，请检查手机号');
        return;
      }

      if (matched) {
        dispatch({
          type: 'SET_PATIENT_CONTEXT',
          payload: {
            patientId: matched.id,
            hospitalId: matched.hospital_id,
            profileName: matched.full_name,
            profilePhone: matched.phone ?? '',
          },
        });
        dispatch({ type: 'SET_SELECTED_PATIENT', payload: matched });

        // Also load full profile
        try {
          const profile = await patientApi.getProfile(matched.id);
          dispatch({ type: 'SET_PATIENT_PROFILE', payload: profile });
        } catch { /* profile optional */ }

        dispatch({ type: 'SET_LOGIN_MODAL', payload: false });
        setStatus('');
      }
    } catch (err) {
      setStatus(`登录失败: ${(err as Error).message}`);
    }
  };

  const handleClose = () => {
    dispatch({ type: 'SET_LOGIN_MODAL', payload: false });
  };

  return (
    <div className="modal-backdrop" onClick={handleClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: -3, marginRight: 8 }}>
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
              <path d="M7 11V7a5 5 0 0110 0v4"/>
            </svg>
            绑定患者身份
          </h2>
          <button className="modal-close" onClick={handleClose}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div className="modal-body">
          <p className="modal-desc">
            输入姓名和手机号来绑定患者身份，用于记忆聊天模式。系统将以此身份检索病历和就诊记录。
          </p>
          <div className="form-group">
            <label>姓名</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
              placeholder="例: 张海"
              autoFocus
            />
          </div>
          <div className="form-group">
            <label>手机号</label>
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
              placeholder="例: 13911112222"
            />
          </div>
          {status && <p className="status-msg error">{status}</p>}
        </div>
        <div className="modal-footer">
          <button className="btn" onClick={handleClose}>取消</button>
          <button className="btn btn-primary" onClick={handleLogin}>确认绑定</button>
        </div>
      </div>
    </div>
  );
}

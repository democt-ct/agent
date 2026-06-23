import { useState } from 'react';
import { useAppState } from '../context/AppContext';
import { patientApi, agentApi } from '../services/api';

export function PatientPanel() {
  const { state, dispatch } = useAppState();
  const [searchPhone, setSearchPhone] = useState('');
  const [lookupId, setLookupId] = useState('');
  const [searchResult, setSearchResult] = useState('');
  const [lookupResult, setLookupResult] = useState('');

  const handleSearch = async () => {
    if (!searchPhone.trim()) {
      setSearchResult('请输入手机号');
      return;
    }
    try {
      const patients = await patientApi.list(state.hospitalId, searchPhone.trim());
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
        setSearchResult(`已找到 ${patients.length} 位患者，已选中 ${p.full_name}`);
      } else {
        setSearchResult('未找到匹配患者');
      }
    } catch (err) {
      setSearchResult(`搜索失败: ${(err as Error).message}`);
    }
  };

  const loadContext = async (patientId: string) => {
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
      setLookupResult(`已加载 ${patient.full_name}：${profile.medical_records?.length ?? 0} 条病历，${profile.visit_records?.length ?? 0} 条就诊记录`);
    } catch (err) {
      setLookupResult(`加载失败: ${(err as Error).message}`);
    }
  };

  const handleLookup = async (kind: 'patient' | 'medical' | 'visit' | 'profile') => {
    const id = lookupId.trim() || state.patientId;
    if (!id) {
      setLookupResult('请先输入 patient_id 或通过搜索选中患者');
      return;
    }
    try {
      if (kind === 'patient') {
        const p = await patientApi.get(id);
        dispatch({ type: 'SET_SELECTED_PATIENT', payload: p });
        setLookupResult(`${p.full_name} 加载成功`);
      } else if (kind === 'medical') {
        const records = await patientApi.getMedicalRecords(id);
        setLookupResult(`加载了 ${records.length} 条病历`);
      } else if (kind === 'visit') {
        const records = await patientApi.getVisitRecords(id);
        setLookupResult(`加载了 ${records.length} 条就诊记录`);
      } else {
        await loadContext(id);
      }
    } catch (err) {
      setLookupResult(`查询失败: ${(err as Error).message}`);
    }
  };

  const handleIssueToken = async () => {
    if (!state.patientId) {
      setSearchResult('请先选中患者');
      return;
    }
    try {
      const { token } = await agentApi.issueToken(state.patientId, state.hospitalId);
      dispatch({ type: 'SET_PATIENT_CONTEXT', payload: { patientId: state.patientId, hospitalId: state.hospitalId, authToken: token } });
      setSearchResult('Token 签发成功');
    } catch (err) {
      setSearchResult(`签发失败: ${(err as Error).message}`);
    }
  };

  const handleDeletePatient = async () => {
    if (!state.patientId || !confirm('确认删除该患者及其所有关联数据？')) return;
    try {
      await patientApi.delete(state.patientId);
      dispatch({ type: 'CLEAR_PATIENT_CONTEXT' });
      setSearchResult('患者已删除');
    } catch (err) {
      setSearchResult(`删除失败: ${(err as Error).message}`);
    }
  };

  if (!state.isPatientPanelOpen) return null;

  return (
    <section className="patient-panel">
      <div className="panel-header">
        <h2>患者检索</h2>
        <button
          className="btn-close"
          onClick={() => {
            dispatch({ type: 'SET_PATIENT_PANEL', payload: false });
            dispatch({ type: 'SET_VIEW', payload: 'chat' });
          }}
        >
          收起
        </button>
      </div>

      <div className="panel-body">
        {/* 快捷操作 */}
        <div className="card-row">
          <div className="card">
            <h3>快捷操作</h3>
            <div className="btn-group">
              <button className="btn" onClick={handleIssueToken}>签发 Token</button>
              <button className="btn btn-danger" onClick={handleDeletePatient}>删除患者</button>
              <button className="btn" onClick={() => dispatch({ type: 'CLEAR_PATIENT_CONTEXT' })}>清空上下文</button>
            </div>
            {searchResult && <p className="status-msg">{searchResult}</p>}
          </div>

          <div className="card">
            <h3>使用建议</h3>
            <ol>
              <li>通过手机号搜索患者并选中</li>
              <li>点击快速读取查看主档、病历和就诊记录</li>
              <li>切回聊天页面继续追问</li>
            </ol>
          </div>
        </div>

        {/* 手机号搜索 */}
        <details className="drawer">
          <summary>手机号搜索患者</summary>
          <div className="drawer-body">
            <div className="input-row">
              <input
                value={searchPhone}
                onChange={(e) => setSearchPhone(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="输入患者手机号"
              />
              <button className="btn btn-primary" onClick={handleSearch}>搜索</button>
            </div>
            {state.patients.length > 0 && (
              <ul className="patient-list">
                {state.patients.map((p) => (
                  <li
                    key={p.id}
                    className={p.id === state.patientId ? 'selected' : ''}
                    onClick={() => loadContext(p.id)}
                  >
                    <strong>{p.full_name}</strong>
                    <span>{p.phone}</span>
                    <span className="badge">{p.gender}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </details>

        {/* Patient ID 精确查询 */}
        <details className="drawer">
          <summary>patient_id 精确查询</summary>
          <div className="drawer-body">
            <div className="input-row">
              <input
                value={lookupId}
                onChange={(e) => setLookupId(e.target.value)}
                placeholder="输入 patient_id"
              />
            </div>
            <div className="btn-group">
              <button className="btn" onClick={() => handleLookup('patient')}>获取主档</button>
              <button className="btn" onClick={() => handleLookup('medical')}>病历记录</button>
              <button className="btn" onClick={() => handleLookup('visit')}>就诊记录</button>
              <button className="btn btn-primary" onClick={() => handleLookup('profile')}>全部 Profile</button>
            </div>
            {lookupResult && <p className="status-msg">{lookupResult}</p>}
          </div>
        </details>

        {/* 当前选中患者信息 */}
        {state.selectedPatient && (
          <div className="card patient-info">
            <h3>{state.selectedPatient.full_name} · 患者详情</h3>
            <div className="info-grid">
              <span>编号: {state.selectedPatient.patient_code}</span>
              <span>性别: {state.selectedPatient.gender ?? '-'}</span>
              <span>出生日期: {state.selectedPatient.birth_date ?? '-'}</span>
              <span>手机: {state.selectedPatient.phone ?? '-'}</span>
              <span>血型: {state.selectedPatient.blood_type ?? '-'}</span>
              <span>地址: {state.selectedPatient.address ?? '-'}</span>
              <span className="full-width">过敏史: {state.selectedPatient.allergy_history || '无'}</span>
              <span className="full-width">家族史: {state.selectedPatient.family_history || '无'}</span>
              <span className="full-width">备注: {state.selectedPatient.notes || '无'}</span>
            </div>
          </div>
        )}

        {/* 病历 & 就诊记录 */}
        {state.patientProfile && (
          <>
            <div className="card">
              <h3>最近病历 ({state.patientProfile.medical_records?.length ?? 0} 条)</h3>
              {(state.patientProfile.medical_records ?? []).slice(0, 5).map((r) => (
                <div key={r.id} className="record-item">
                  <strong>{r.record_date}</strong> — {r.diagnosis || '未填写诊断'}
                  {r.chief_complaint && <p>主诉: {r.chief_complaint}</p>}
                </div>
              ))}
            </div>
            <div className="card">
              <h3>最近就诊 ({state.patientProfile.visit_records?.length ?? 0} 条)</h3>
              {(state.patientProfile.visit_records ?? []).slice(0, 5).map((r) => (
                <div key={r.id} className="record-item">
                  <strong>{r.visit_date}</strong> — {r.department || '未知科室'}
                  {r.doctor_name && <span> · {r.doctor_name}</span>}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import dynamic from 'next/dynamic';
import CompareSlider from '@/components/CompareSlider';

// ImageEditor 用了 react-dropzone（依赖 window），且是较重的面板，按需懒加载
const ImageEditor = dynamic(() => import('@/components/ImageEditor'), { ssr: false });

const STYLES = [
  { id: 'cinematic', label: '电影感' }, { id: 'fuji', label: '富士胶片' },
  { id: 'japanese', label: '日系清新' }, { id: 'vintage', label: '复古' },
  { id: 'moody', label: '情绪风' }, { id: 'hongkong', label: '港风' },
  { id: 'bright', label: '明亮' }, { id: 'xiaohongshu', label: '小红书' },
  { id: 'morandi', label: '莫兰迪' }, { id: 'cyberpunk', label: '赛博朋克' },
  { id: 'blackgold', label: '黑金' }, { id: 'leica', label: '徕卡' },
];

interface Msg {
  id: string;
  me: boolean;
  text: string;
  img?: string;
  imageId?: string;        // 该消息展示的图（AI 结果或用户上传）
  originalImageId?: string; // 对应的原始上传图（用于对比滑块）
  // 结构化数据（来自后端 ChatResponse，供可视化卡片渲染）
  appliedParams?: Record<string, number>;
  diagnosis?: DiagData;
  sourceImageId?: string;   // 本次编辑的起点（链式追踪）
}

interface DiagData {
  brightness_mean: number;
  contrast_std: number;
  saturation_mean: number;
  scene_hint: string;
  issues_text: string;
}

type Mode = 'chat' | 'pro';

export default function Home() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [loading, setLoading] = useState(false);
  const [input, setInput] = useState('');
  const [lightbox, setLightbox] = useState<string | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pendingPreview, setPendingPreview] = useState<string | null>(null);
  // 链式编辑：当前工作图（上次 AI 结果），用于「再亮一点」基于上次结果累加
  const [currentImageId, setCurrentImageId] = useState<string | null>(null);
  // 会话 ID（历史持久化）
  const [sessionId, setSessionId] = useState<string | null>(null);
  // 会话列表
  const [sessions, setSessions] = useState<Array<{ id: string; name: string; created_at: string; message_count: number }>>([]);
  // 历史侧边栏展开
  const [showHistory, setShowHistory] = useState(false);
  // 每张图的原始上传 id（用于对比滑块）— key: currentImageId, value: originalImageId
  const [originalMap, setOriginalMap] = useState<Record<string, string>>({});
  // 对比滑块弹窗
  const [comparePair, setComparePair] = useState<{ before: string; after: string } | null>(null);
  // 模式切换：对话 / 专业
  const [mode, setMode] = useState<Mode>('chat');
  // 专业模式使用的图片 id（从对话模式切过来，或在专业模式手动上传）
  const [proImageId, setProImageId] = useState<string | null>(null);

  const bottom = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs]);

  // 初始化：创建或恢复会话
  useEffect(() => { loadSessions(); }, []);
  useEffect(() => { if (!sessionId) createNewSession(); }, []);

  const loadSessions = async () => {
    try {
      const { data } = await axios.get('/api/v1/history/sessions');
      setSessions(data || []);
    } catch { /* silent */ }
  };

  const createNewSession = async () => {
    try {
      const { data } = await axios.post('/api/v1/history/sessions');
      setSessionId(data.id);
      setMsgs([]);
      setCurrentImageId(null);
      setOriginalMap({});
    } catch { /* silent */ }
  };

  const restoreSession = async (sid: string) => {
    try {
      const { data: msgs_data } = await axios.get(`/api/v1/history/sessions/${sid}/messages`);
      setSessionId(sid);
      setMsgs((msgs_data || []).map((m: any) => ({
        id: m.id, me: m.role === 'user', text: m.text,
        img: m.image_id ? `/api/v1/images/${m.image_id}` : undefined,
        imageId: m.image_id || undefined,
        appliedParams: m.params,
        diagnosis: m.diagnosis,
      })));
      setShowHistory(false);
    } catch { /* silent */ }
  };

  const say = (m: Omit<Msg, 'id'>) => {
    setMsgs(prev => [...prev, { id: Math.random().toString(36).slice(2, 10), ...m }]);
  };

  const pickFile = (file: File) => {
    if (pendingPreview) URL.revokeObjectURL(pendingPreview);
    setPendingFile(file);
    setPendingPreview(URL.createObjectURL(file));
  };

  const clearPending = () => {
    if (pendingPreview) URL.revokeObjectURL(pendingPreview);
    setPendingFile(null);
    setPendingPreview(null);
    if (fileRef.current) fileRef.current.value = '';
  };

  const send = async (overrideText?: string) => {
    const text = overrideText ?? input.trim();
    if ((!text && !pendingFile) || loading) return;
    if (!overrideText) setInput('');
    setLoading(true);

    let uploadedImageId: string | null = null;
    let imageUrl: string | null = null;
    let isFreshUpload = false;

    // Upload pending image first — 新上传会重置编辑链
    if (pendingFile) {
      try {
        const fd = new FormData(); fd.append('file', pendingFile);
        const { data } = await axios.post('/api/v1/images/upload', fd);
        uploadedImageId = data.image_id;
        imageUrl = `/api/v1/images/${uploadedImageId}`;
        isFreshUpload = true;
      } catch {
        say({ me: false, text: '图片上传失败，请重试' });
        setLoading(false);
        return;
      }
      clearPending();
    }

    // 决定编辑起点：新上传 → 用新图；否则 → 用当前工作图（链式累加）
    const workingId = isFreshUpload ? uploadedImageId : currentImageId;

    // 没有可用图片时退化为纯文本对话
    if (!workingId) {
      say({ me: true, text, img: imageUrl ?? undefined, imageId: uploadedImageId ?? undefined });
      try {
        const { data } = await axios.post('/api/v1/chat', { message: text, session_id: sessionId });
        say({ me: false, text: data.reply });
      } catch {
        say({ me: false, text: '出错了，请重试' });
      } finally { setLoading(false); }
      return;
    }

    // 展示用户消息
    say({
      me: true, text, img: imageUrl ?? undefined,
      imageId: uploadedImageId ?? undefined,
      originalImageId: isFreshUpload ? uploadedImageId! : originalMap[workingId],
    });

    try {
      const { data } = await axios.post('/api/v1/chat', {
        message: text || '请自动优化这张图片的色彩和光影',
        image_id: uploadedImageId,                       // 原始图（用于无链时的 fallback）
        current_image_id: isFreshUpload ? null : workingId, // 链式起点
        session_id: sessionId,                           // 历史持久化
      });
      const resultImg = data.image_id ? `/api/v1/images/${data.image_id}` : undefined;
      say({
        me: false, text: data.reply, img: resultImg, imageId: data.image_id || undefined,
        appliedParams: data.applied_params,
        diagnosis: data.diagnosis,
        sourceImageId: data.source_image_id,
        originalImageId: isFreshUpload ? uploadedImageId! : originalMap[workingId],
      });
      // 更新当前工作图为本次结果，延续编辑链
      if (data.image_id) {
        setCurrentImageId(data.image_id);
        setOriginalMap(prev => ({
          ...prev,
          [data.image_id]: isFreshUpload ? uploadedImageId! : (originalMap[workingId] ?? uploadedImageId!),
        }));
      }
    } catch {
      say({ me: false, text: '出错了，请重试' });
    } finally { setLoading(false); }
  };

  const key = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  };

  // 从对话模式切换到专业模式时，把当前工作图带过去
  const switchToPro = (imageId?: string | null) => {
    setProImageId(imageId ?? currentImageId);
    setMode('pro');
  };

  // ── Parse AI reply: split explanation from param summary ──
  const renderAIReply = (text: string) => {
    const paramLabels = ['亮度', '对比度', '饱和度', '色温', '锐度', '高光', '阴影', '暗角', '颗粒', '色调', '褪色', '色相偏移', '风格'];
    const lines = text.split('\n');
    const paramLineIdx = lines.findIndex(line => {
      const trimmed = line.trim();
      return paramLabels.some(l => trimmed.startsWith(l + '+') || trimmed.startsWith(l + '-') || trimmed.startsWith(l + ':'));
    });

    let explanationLines: string[];
    let paramLines: string[];

    if (paramLineIdx >= 0) {
      explanationLines = lines.slice(0, paramLineIdx);
      paramLines = lines.slice(paramLineIdx);
    } else {
      explanationLines = lines;
      paramLines = [];
    }

    // Parse individual param tokens from param lines
    const paramTokens: { label: string; value: string }[] = [];
    for (const pl of paramLines) {
      const tokens = pl.trim().split(/\s+/);
      for (const token of tokens) {
        const match = token.match(/^(.+?)([+-][\d.]+|:[\u4e00-\u9fa5\w]+)$/);
        if (match) {
          paramTokens.push({ label: match[1], value: match[2] });
        } else {
          // Fallback: push as-is to explanation
          paramTokens.push({ label: '', value: token });
        }
      }
    }

    return (
      <>
        {explanationLines.filter(l => l.trim()).map((line, i) => (
          <div key={`exp-${i}`} style={{ marginBottom: i < explanationLines.length - 1 ? 4 : 0 }}>
            {line}
          </div>
        ))}
        {paramTokens.length > 0 && (
          <div style={{ marginTop: explanationLines.some(l => l.trim()) ? 8 : 0 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {paramTokens.filter(t => t.label).map((pt, i) => {
                const isPositive = pt.value.startsWith('+');
                const isStyle = pt.label === '风格';
                return (
                  <span key={i} style={{
                    display: 'inline-block',
                    padding: '2px 8px',
                    borderRadius: 10,
                    fontSize: 12,
                    fontWeight: 600,
                    background: isStyle ? '#ede9fe' : (isPositive ? '#fef3c7' : '#dbeafe'),
                    color: isStyle ? '#7c3aed' : (isPositive ? '#92400e' : '#1e40af'),
                  }}>
                    {pt.label}{pt.value}
                  </span>
                );
              })}
            </div>
          </div>
        )}
      </>
    );
  };

  // ── AI 消息图片：点击放大 + 对比原图 + 跳转专业模式 ──
  const renderMsgImage = (m: Msg) => {
    if (!m.img) return null;
    const canCompare = !m.me && m.imageId && m.originalImageId && m.originalImageId !== m.imageId;
    return (
      <div style={{ marginBottom: m.text ? 8 : 0 }}>
        <img
          src={m.img}
          onClick={() => setLightbox(m.img!)}
          style={{
            maxHeight: 200, maxWidth: '100%', borderRadius: 8,
            display: 'block', cursor: 'pointer',
          }}
        />
        {/* AI 结果图下方操作按钮 */}
        {!m.me && m.imageId && (
          <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
            {canCompare && (
              <button
                onClick={() => setComparePair({
                  before: `/api/v1/images/${m.originalImageId}`,
                  after: m.img!,
                })}
                style={{
                  padding: '2px 8px', borderRadius: 10, border: 'none',
                  background: '#ecfdf5', color: '#065f46', fontSize: 11,
                  cursor: 'pointer', fontWeight: 500,
                }}
              >↔ 对比原图</button>
            )}
            <button
              onClick={() => switchToPro(m.imageId)}
              style={{
                padding: '2px 8px', borderRadius: 10, border: 'none',
                background: '#eff6ff', color: '#1d4ed8', fontSize: 11,
                cursor: 'pointer', fontWeight: 500,
              }}
            >🎨 专业微调</button>
          </div>
        )}
      </div>
    );
  };

  // ── 顶部 Header（含模式 Tab + 历史入口） ──
  const renderHeader = () => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px', borderBottom: '1px solid #eee' }}>
      <span style={{ fontWeight: 700, fontSize: 15 }}>🤖 AI Photo Agent</span>
      <div style={{ display: 'flex', gap: 2, marginLeft: 8, background: '#f3f4f6', borderRadius: 10, padding: 2 }}>
        <button
          onClick={() => setMode('chat')}
          style={{
            padding: '4px 14px', borderRadius: 8, border: 'none',
            background: mode === 'chat' ? '#fff' : 'transparent',
            color: mode === 'chat' ? '#1f2937' : '#9ca3af',
            fontSize: 13, fontWeight: mode === 'chat' ? 600 : 400,
            cursor: 'pointer', boxShadow: mode === 'chat' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
          }}
        >💬 对话</button>
        <button
          onClick={() => setMode('pro')}
          style={{
            padding: '4px 14px', borderRadius: 8, border: 'none',
            background: mode === 'pro' ? '#fff' : 'transparent',
            color: mode === 'pro' ? '#1f2937' : '#9ca3af',
            fontSize: 13, fontWeight: mode === 'pro' ? 600 : 400,
            cursor: 'pointer', boxShadow: mode === 'pro' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
          }}
        >🎨 专业</button>
      </div>
      <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
        {/* 当前工作图指示 */}
        {currentImageId && mode === 'chat' && (
          <span style={{ fontSize: 11, color: '#9ca3af' }}>
            🔗 {currentImageId.slice(0, 8)}…
          </span>
        )}
        <button
          onClick={() => createNewSession().then(loadSessions)}
          title="新建会话"
          style={{ padding: '4px 10px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', color: '#374151', fontSize: 12, cursor: 'pointer' }}
        >＋ 新会话</button>
        <button
          onClick={() => { loadSessions(); setShowHistory(true); }}
          title="历史会话"
          style={{ padding: '4px 10px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', color: '#374151', fontSize: 12, cursor: 'pointer' }}
        >🕘 历史</button>
      </div>
    </div>
  );

  // ── 历史侧边栏 ──
  const renderHistorySidebar = () => {
    if (!showHistory) return null;
    return (
      <div
        onClick={() => setShowHistory(false)}
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', zIndex: 9000, display: 'flex', justifyContent: 'flex-end' }}
      >
        <div
          onClick={(e) => e.stopPropagation()}
          style={{ width: 320, height: '100%', background: '#fff', boxShadow: '-4px 0 20px rgba(0,0,0,0.1)', overflowY: 'auto', padding: 16 }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>🕘 历史会话</h3>
            <button onClick={() => setShowHistory(false)} style={{ border: 'none', background: 'none', fontSize: 18, cursor: 'pointer', color: '#9ca3af' }}>×</button>
          </div>
          {sessions.length === 0 ? (
            <p style={{ color: '#9ca3af', fontSize: 13, textAlign: 'center', marginTop: 40 }}>暂无历史会话</p>
          ) : (
            sessions.map(s => (
              <div
                key={s.id}
                onClick={() => restoreSession(s.id)}
                style={{
                  padding: '12px', marginBottom: 8, borderRadius: 10,
                  border: s.id === sessionId ? '2px solid #2563eb' : '1px solid #e5e7eb',
                  background: s.id === sessionId ? '#eff6ff' : '#fff',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 500, color: '#1f2937', marginBottom: 4 }}>{s.name}</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#9ca3af' }}>
                  <span>{s.created_at?.slice(0, 16).replace('T', ' ')}</span>
                  <span>{s.message_count || 0} 条消息</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    );
  };

  // ── 对话模式 ──
  const renderChatMode = () => (
    <>
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        <div style={{ maxWidth: 700, margin: '0 auto' }}>
          {msgs.length === 0 && (
            <div style={{ textAlign: 'center', color: '#aaa', marginTop: 80, fontSize: 14 }}>
              上传一张图片，或者输入文字聊聊修图
            </div>
          )}
          {msgs.map(m => (
            <div key={m.id} style={{ display: 'flex', gap: 8, marginBottom: 16, flexDirection: m.me ? 'row-reverse' : 'row' }}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
                background: m.me ? '#d1d5db' : '#2563eb', color: '#fff',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, fontWeight: 600,
              }}>
                {m.me ? '我' : 'AI'}
              </div>
              <div style={{
                maxWidth: '75%', padding: '10px 14px', borderRadius: 16,
                background: m.me ? '#2563eb' : '#f3f4f6',
                color: m.me ? '#fff' : '#1f2937',
                fontSize: 14, lineHeight: 1.6,
              }}>
                {renderMsgImage(m)}
                {m.text && (
                  m.me ? (
                    <div style={{ whiteSpace: 'pre-wrap' }}>{m.text}</div>
                  ) : (
                    renderAIReply(m.text)
                  )
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#2563eb', color: '#fff',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 600 }}>AI</div>
              <div style={{ padding: '10px 14px', borderRadius: 16, background: '#f3f4f6' }}>
                <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#9ca3af', animation: 'bounce 0.6s infinite' }} />
                <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#9ca3af', margin: '0 4px', animation: 'bounce 0.6s infinite 0.1s' }} />
                <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#9ca3af', animation: 'bounce 0.6s infinite 0.2s' }} />
              </div>
            </div>
          )}
          <div ref={bottom} />
        </div>
      </div>

      {/* 底部输入区 */}
      <div style={{ padding: '12px 16px', borderTop: '1px solid #eee' }}>
        <div style={{ maxWidth: 700, margin: '0 auto' }}>
          {pendingPreview && (
            <div style={{ position: 'relative', display: 'inline-block', marginBottom: 8 }}>
              <img src={pendingPreview} style={{ height: 64, borderRadius: 8, display: 'block' }} />
              <button onClick={clearPending}
                style={{ position: 'absolute', top: -6, right: -6, width: 18, height: 18, borderRadius: '50%', border: 'none', background: '#6b7280', color: '#fff', cursor: 'pointer', fontSize: 11, lineHeight: '18px', padding: 0 }}>
                ×
              </button>
            </div>
          )}
          {(!!pendingFile || msgs.some(m => m.imageId)) && (
            <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 8, scrollbarWidth: 'none' }}>
              <button onClick={() => send('请自动优化这张图片的色彩和光影')} disabled={loading}
                style={{ flexShrink: 0, padding: '4px 12px', borderRadius: 20, border: 'none', background: '#2563eb', color: '#fff', fontSize: 12, cursor: loading ? 'default' : 'pointer' }}>
                ✨ 智能优化
              </button>
              {STYLES.map(s => (
                <button key={s.id} onClick={() => send(`请以${s.label}风格处理这张图片`)} disabled={loading}
                  style={{ flexShrink: 0, padding: '4px 10px', borderRadius: 20, border: '1px solid #e5e7eb', background: '#fff', color: '#374151', fontSize: 12, cursor: loading ? 'default' : 'pointer', whiteSpace: 'nowrap' }}>
                  {s.label}
                </button>
              ))}
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button onClick={() => fileRef.current?.click()} disabled={loading}
              style={{ width: 36, height: 36, borderRadius: 10, border: 'none', background: '#f3f4f6', color: '#6b7280', cursor: loading ? 'default' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>
              +
            </button>
            <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" style={{ display: 'none' }}
              onChange={e => { const f = e.target.files?.[0]; if (f) pickFile(f); }} />
            <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={key}
              placeholder={pendingFile ? '描述修图需求，如「富士胶片」「赛博朋克」「日系」…' : '说说你想怎么修图，如「优化」「电影感」…'}
              disabled={loading}
              style={{ flex: 1, padding: '8px 14px', borderRadius: 12, border: 'none', background: '#f3f4f6', outline: 'none', fontSize: 14 }} />
            <button onClick={() => send()} disabled={loading || (!input.trim() && !pendingFile)}
              style={{ width: 36, height: 36, borderRadius: 10, border: 'none', background: (loading || (!input.trim() && !pendingFile)) ? '#93c5fd' : '#2563eb', color: '#fff', cursor: (loading || (!input.trim() && !pendingFile)) ? 'default' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              ↑
            </button>
          </div>
        </div>
      </div>
    </>
  );

  // ── 专业模式 ──
  const renderProMode = () => {
    const editorImageId = proImageId || currentImageId;
    if (!editorImageId) {
      return (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#9ca3af' }}>
          <p style={{ fontSize: 48, marginBottom: 12 }}>🎨</p>
          <p style={{ fontSize: 14, marginBottom: 16 }}>专业模式需要先有一张图片</p>
          <button
            onClick={() => setMode('chat')}
            style={{ padding: '8px 20px', borderRadius: 10, border: '1px solid #d1d5db', background: '#fff', color: '#374151', fontSize: 13, cursor: 'pointer' }}
          >← 回到对话模式上传图片</button>
        </div>
      );
    }
    return (
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <ImageEditor
            imageId={editorImageId}
            onAnalysisComplete={() => {}}
          />
        </div>
      </div>
    );
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#fff' }}>
      {renderHeader()}

      {mode === 'chat' ? renderChatMode() : renderProMode()}

      {/* Lightbox */}
      {lightbox && (
        <div onClick={() => setLightbox(null)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', zIndex: 9999,
            display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
          }}>
          <img src={lightbox} style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: 8, boxShadow: '0 20px 60px rgba(0,0,0,0.5)' }} />
        </div>
      )}

      {/* Compare Slider */}
      {comparePair && (
        <CompareSlider
          before={comparePair.before}
          after={comparePair.after}
          onClose={() => setComparePair(null)}
        />
      )}

      {/* History Sidebar */}
      {renderHistorySidebar()}

      <style>{`@keyframes bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }`}</style>
    </div>
  );
}

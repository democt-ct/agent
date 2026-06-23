import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAppState } from '../context/AppContext';
import { agentApi } from '../services/api';
import type { ChatMessage, AgentProcessPhase } from '../types';

// Code block with copy button
function CodeBlock({ children, className }: { children?: React.ReactNode; className?: string }) {
  const [copied, setCopied] = useState(false);
  const text = String(children ?? '').replace(/\n$/, '');

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* ignore */ }
  }, [text]);

  return (
    <div className="code-block-wrapper">
      <button className="code-copy-btn" onClick={handleCopy}>
        {copied ? '✓ 已复制' : '📋 复制'}
      </button>
      <pre className={className}>
        <code>{children}</code>
      </pre>
    </div>
  );
}

const WELCOME_PROMPTS = [
  { text: '帮我查一下最近的病历记录' },
  { text: '我的药物过敏史是什么？' },
  { text: '上次就诊的诊断结果' },
  { text: '根据我的情况给一些健康建议' },
];

export function ChatPanel() {
  const { state, dispatch } = useAppState();
  const [input, setInput] = useState('');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState('');
  const [speechPlaying, setSpeechPlaying] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [agentProcess, setAgentProcess] = useState<{
    phases: AgentProcessPhase[];
    intent?: string;
    confidence?: number;
    plan?: Record<string, unknown>;
    tool?: string;
  } | null>(null);
  const [processExpanded, setProcessExpanded] = useState(false);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const isMemory = state.chatMode === 'memory';
  const messages = isMemory ? state.chatMessages : state.generalChatMessages;

  // Auto-scroll
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [messages]);

  // Reset input on mode switch
  useEffect(() => {
    setInput('');
    setImageFile(null);
    setImagePreview('');
  }, [state.chatMode]);

  const addMessage = (msg: ChatMessage) => {
    if (isMemory) {
      dispatch({ type: 'ADD_CHAT_MESSAGE', payload: msg });
    } else {
      dispatch({ type: 'ADD_GENERAL_CHAT_MESSAGE', payload: msg });
    }
  };

  const sendQuery = async (text: string, file?: File | null) => {
    const userMsg: ChatMessage = {
      role: 'user',
      content: text || '[图片]',
      created_at: new Date().toISOString(),
    };
    addMessage(userMsg);
    setInput('');
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    setAgentProcess(null);
    setProcessExpanded(false);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      if (file || imageFile) {
        const img = file || imageFile;
        const result = await agentApi.queryWithImage({
          question: text || '请分析这张图片',
          image: img!,
          patient_id: state.patientId || undefined,
          hospital_id: state.hospitalId || undefined,
          auth_token: state.authToken || undefined,
          session_id: isMemory ? state.sessionId : state.generalSessionId || undefined,
          chat_mode: state.chatMode,
        });
        setImageFile(null);
        setImagePreview('');

        const assistantMsg: ChatMessage = {
          role: 'assistant',
          content: result.answer,
          created_at: new Date().toISOString(),
          speech_url: result.speech_url,
          image_analysis: result.image_analysis,
        };
        addMessage(assistantMsg);
        dispatch({ type: 'SET_LAST_ANSWER', payload: result.answer });

        if (result.memory_debug) {
          dispatch({ type: 'SET_WORKING_MEMORY', payload: result.memory_debug.working_memory });
          dispatch({ type: 'SET_MEMORY_LAYERS', payload: result.memory_debug.memory_layers });
        }
      } else {
        // Use SSE streaming for text-only queries
        let accumulatedAnswer = '';
        setStreamingContent('');

        await agentApi.queryStream(
          {
            question: text,
            patient_id: state.patientId || undefined,
            hospital_id: state.hospitalId || undefined,
            auth_token: state.authToken || undefined,
            session_id: isMemory ? state.sessionId : state.generalSessionId || undefined,
            chat_mode: state.chatMode,
          },
          {
            onPhase: (phase, message) => {
              setAgentProcess(prev => {
                const phases = prev ? [...prev.phases] : [];
                const existing = phases.findIndex(p => p.phase === phase);
                if (existing >= 0) {
                  phases[existing] = { phase, message, status: 'done' };
                } else {
                  phases.push({ phase, message, status: 'done' });
                }
                return { ...(prev || { phases: [] }), phases };
              });
            },
            onIntent: (intent, confidence) => {
              setAgentProcess(prev => ({
                ...(prev || { phases: [] }),
                intent,
                confidence,
              }));
            },
            onPlanning: (plan) => {
              setAgentProcess(prev => ({
                ...(prev || { phases: [] }),
                plan,
              }));
            },
            onToolExecution: (tool) => {
              setAgentProcess(prev => ({
                ...(prev || { phases: [] }),
                tool,
              }));
            },
            onToken: (content) => {
              accumulatedAnswer += content;
              setStreamingContent(accumulatedAnswer);
            },
            onDone: (data) => {
              const finalAnswer = data.answer || accumulatedAnswer;
              const assistantMsg: ChatMessage = {
                role: 'assistant',
                content: finalAnswer,
                created_at: new Date().toISOString(),
                speech_url: data.speech_text ? undefined : undefined,
              };
              addMessage(assistantMsg);
              dispatch({ type: 'SET_LAST_ANSWER', payload: finalAnswer });

              if (data.memory_debug) {
                dispatch({ type: 'SET_WORKING_MEMORY', payload: data.memory_debug.working_memory });
                dispatch({ type: 'SET_MEMORY_LAYERS', payload: data.memory_debug.memory_layers });
              }
              setStreamingContent('');
              setAgentProcess(null);
              setProcessExpanded(false);
            },
            onError: (detail) => {
              throw new Error(detail);
            },
          },
          controller.signal,
        );
      }
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      const errMsg: ChatMessage = {
        role: 'system',
        content: `错误: ${(err as Error).message}`,
        created_at: new Date().toISOString(),
      };
      addMessage(errMsg);
      dispatch({ type: 'SET_ERROR', payload: (err as Error).message });
      setAgentProcess(null);
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
      abortRef.current = null;
    }
  };

  const handleSend = () => {
    const text = input.trim();
    if (!text && !imageFile) return;
    sendQuery(text);
  };

  const handlePromptClick = (promptText: string) => {
    sendQuery(promptText);
  };

  const handleStop = () => {
    abortRef.current?.abort();
    dispatch({ type: 'SET_LOADING', payload: false });
  };

  const handleSpeech = async (text: string) => {
    if (state.speechMode === 'browser') {
      if (speechPlaying) {
        window.speechSynthesis.cancel();
        setSpeechPlaying(false);
        return;
      }
      setSpeechPlaying(true);
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'zh-CN';
      utterance.rate = 0.9;
      utterance.onend = () => setSpeechPlaying(false);
      utterance.onerror = () => setSpeechPlaying(false);
      window.speechSynthesis.speak(utterance);
    } else {
      try {
        dispatch({ type: 'SET_STATUS', payload: '正在合成语音...' });
        const result = await agentApi.speech(text);
        if (result.audio_base64) {
          const binary = atob(result.audio_base64);
          const bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
          const blob = new Blob([bytes], { type: 'audio/wav' });
          const url = URL.createObjectURL(blob);
          const audio = new Audio(url);
          audio.onended = () => URL.revokeObjectURL(url);
          await audio.play();
        } else if (result.audio_url) {
          const audio = new Audio(result.audio_url);
          await audio.play();
        }
        dispatch({ type: 'SET_STATUS', payload: '' });
      } catch (err) {
        dispatch({ type: 'SET_STATUS', payload: `语音合成失败: ${(err as Error).message}` });
      }
    }
  };

  const handleCopyMessage = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      dispatch({ type: 'SET_STATUS', payload: '已复制到剪贴板' });
      setTimeout(() => dispatch({ type: 'SET_STATUS', payload: '' }), 2000);
    } catch {
      dispatch({ type: 'SET_STATUS', payload: '复制失败' });
    }
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageFile(file);
    setImagePreview(URL.createObjectURL(file));
  };

  const switchSpeechMode = () => {
    dispatch({
      type: 'SET_SPEECH_MODE',
      payload: state.speechMode === 'tts' ? 'browser' : 'tts',
    });
  };

  return (
    <div className="chat-panel">
      {/* Welcome Screen (only when no messages) */}
      {messages.length === 0 && !state.isLoading && (
        <div className="chat-welcome">
          <div className="chat-welcome-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
            </svg>
          </div>
          <h2>有什么可以帮你的？</h2>
          <p>
            {isMemory
              ? state.patientId
                ? `你好${state.profileName ? '，' + state.profileName : ''}。我可以帮你查询病历、了解诊断结果、提供健康建议。`
                : '请先绑定患者身份，开始智能问答。'
              : '直接提问，无需绑定身份。'}
          </p>
          {isMemory && state.patientId && (
            <div className="welcome-prompts">
              {WELCOME_PROMPTS.map((prompt, i) => (
                <button
                  key={i}
                  className="welcome-prompt-card"
                  onClick={() => handlePromptClick(prompt.text)}
                >
                  {prompt.text}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Chat Transcript */}
      {messages.length > 0 && (
        <div className="chat-transcript" ref={transcriptRef}>
          {messages.map((msg, i) => {
            const roleClass = `chat-msg chat-msg-${msg.role}`;
            return (
              <div key={i} className={roleClass}>
                <div className="chat-msg-avatar">
                  {msg.role === 'user' ? (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
                      <circle cx="12" cy="7" r="4"/>
                    </svg>
                  ) : msg.role === 'assistant' ? (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 2a4 4 0 014 4v2a4 4 0 01-8 0V6a4 4 0 014-4z"/>
                      <path d="M18 12h.01"/><path d="M6 12h.01"/>
                      <path d="M12 16v4"/>
                      <path d="M8 20h8"/>
                      <path d="M9.5 12v1a2.5 2.5 0 005 0v-1"/>
                    </svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                      <line x1="12" y1="9" x2="12" y2="13"/>
                      <line x1="12" y1="17" x2="12.01" y2="17"/>
                    </svg>
                  )}
                </div>
                <div className="chat-msg-body">
                  <div className="chat-msg-bubble">
                    {msg.role === 'assistant' ? (
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code({ className, children, ...props }) {
                            const isInline = !className;
                            if (isInline) {
                              return <code {...props}>{children}</code>;
                            }
                            return <CodeBlock className={className}>{children}</CodeBlock>;
                          },
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    ) : (
                      msg.content.split('\n').map((line, j) => (
                        <p key={j}>{line || '\u00A0'}</p>
                      ))
                    )}
                  </div>

                  {/* Message actions */}
                  <div className="chat-msg-actions">
                    <button
                      className="chat-action-btn"
                      onClick={() => handleCopyMessage(msg.content)}
                      title="复制"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: -1 }}>
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                        <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                      </svg>
                      {' '}复制
                    </button>
                    {msg.role === 'assistant' && (
                      <button
                        className="chat-action-btn"
                        onClick={() => handleSpeech(msg.content)}
                        title="语音播报"
                      >
                        {speechPlaying ? (
                          <><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style={{ verticalAlign: -1 }}><rect x="6" y="6" width="12" height="12" rx="2"/></svg>{' '}停止</>
                        ) : (
                          <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: -1 }}><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 010 7.07"/><path d="M19.07 4.93a10 10 0 010 14.14"/></svg>{' '}播报</>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {/* Agent Process Card — collapsible, shown during processing */}
          {state.isLoading && agentProcess && agentProcess.phases.length > 0 && !streamingContent && (
            <div className="agent-process-card">
              <button
                className="agent-process-toggle"
                onClick={() => setProcessExpanded(!processExpanded)}
              >
                <span className="agent-process-icon">
                  {streamingContent ? '✓' : '⟳'}
                </span>
                <span className="agent-process-label">
                  {agentProcess.intent
                    ? `意图: ${agentProcess.intent}`
                    : agentProcess.phases[agentProcess.phases.length - 1]?.message || '正在分析...'}
                </span>
                <span className={`agent-process-arrow ${processExpanded ? 'expanded' : ''}`}>
                  ▾
                </span>
              </button>
              {processExpanded && (
                <div className="agent-process-detail">
                  {agentProcess.phases.map((p, i) => (
                    <div key={i} className="agent-process-step">
                      <span className="step-icon">✓</span>
                      <span className="step-phase">{p.phase}</span>
                      <span className="step-message">{p.message}</span>
                    </div>
                  ))}
                  {agentProcess.tool && (
                    <div className="agent-process-step">
                      <span className="step-icon">✓</span>
                      <span className="step-phase">tool</span>
                      <span className="step-message">调用 {agentProcess.tool}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {state.isLoading && !agentProcess && (
            <div className="chat-msg chat-msg-assistant">
              <div className="chat-msg-avatar">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2a4 4 0 014 4v2a4 4 0 01-8 0V6a4 4 0 014-4z"/>
                  <path d="M18 12h.01"/><path d="M6 12h.01"/>
                  <path d="M12 16v4"/>
                  <path d="M8 20h8"/>
                  <path d="M9.5 12v1a2.5 2.5 0 005 0v-1"/>
                </svg>
              </div>
              <div className="chat-msg-body">
                <div className="chat-msg-header">
                  <span className="chat-msg-role">助手</span>
                </div>
                <div className="chat-msg-bubble">
                  {streamingContent ? (
                    <span className="streaming-text">{streamingContent}<span className="streaming-cursor">|</span></span>
                  ) : (
                    <div className="typing-indicator">
                      <span /><span /><span />
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Chat Input Area */}
      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          {imagePreview && (
            <div className="image-preview">
              <img src={imagePreview} alt="预览" />
              <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {imageFile?.name}
              </span>
              <button onClick={() => { setImageFile(null); setImagePreview(''); }}>✕</button>
            </div>
          )}
          <div className="chat-input-row">
            <label className="btn-upload" title="上传图片">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                <circle cx="8.5" cy="8.5" r="1.5"/>
                <polyline points="21 15 16 10 5 21"/>
              </svg>
              <input type="file" accept="image/*" onChange={handleImageSelect} hidden />
            </label>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder={
                isMemory
                  ? state.patientId
                    ? '输入问题，Enter 发送...'
                    : '请先绑定患者身份...'
                  : '直接输入你的问题...'
              }
              rows={1}
              disabled={state.isLoading}
            />
            {state.isLoading ? (
              <button className="btn-stop" onClick={handleStop} title="停止生成">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="6" y="6" width="12" height="12" rx="2"/>
                </svg>
              </button>
            ) : (
              <button
                className="btn-send"
                onClick={handleSend}
                disabled={!input.trim() && !imageFile}
                title="发送消息"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13"/>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
              </button>
            )}
          </div>
          <div className="chat-input-options">
            <label className="option-label">
              语音模式:
              <select value={state.speechMode} onChange={switchSpeechMode}>
                <option value="browser">浏览器</option>
                <option value="tts">后端 TTS</option>
              </select>
            </label>
            {state.statusMessage && (
              <span className="status-msg">{state.statusMessage}</span>
            )}
          </div>
        </div>
      </div>

    </div>
  );
}

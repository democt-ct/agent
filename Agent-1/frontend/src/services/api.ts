import type {
  Patient,
  MedicalRecord,
  VisitRecord,
  PatientProfile,
  AgentQueryResponse,
  ConversationSession,
  ChatMessage,
  MemoryDebugPayload,
} from '../types';

// ============================================================
// 基础请求工具
// ============================================================

const BASE = '';

async function request<T = unknown>(
  url: string,
  options: RequestInit & { timeout?: number } = {},
): Promise<T> {
  const headers = new Headers(options.headers || {});
  const body = options.body;

  if (!(body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const timeoutMs = options.timeout || (body instanceof FormData ? 180_000 : 60_000);
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const resp = await fetch(`${BASE}${url}`, { ...options, headers, signal: controller.signal });
    clearTimeout(timeoutId);

    const text = await resp.text();
    let data: unknown = text;
    try { data = text ? JSON.parse(text) : {}; } catch { /* raw text */ }

    if (!resp.ok) {
      let detail = String(data);
      if (typeof data === 'object' && data !== null) {
        const d = data as Record<string, unknown>;
        if (Array.isArray(d.detail)) {
          detail = (d.detail as Array<Record<string, unknown>>)
            .map((item) => {
              const loc = Array.isArray(item.loc) ? item.loc.join('.') : '';
              const msg = String(item.msg || '').trim();
              return loc ? `${loc}: ${msg}` : msg;
            })
            .filter(Boolean)
            .join('; ');
        } else {
          detail = String(d.detail || JSON.stringify(data));
        }
      }
      throw new Error(detail || `请求失败: ${resp.status}`);
    }
    return data as T;
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('请求超时，请检查网络后重试');
    }
    throw err;
  }
}

// ============================================================
// 患者 API
// ============================================================

export const patientApi = {
  list(hospitalId?: string, phone?: string, name?: string): Promise<Patient[]> {
    const params = new URLSearchParams();
    if (hospitalId) params.set('hospital_id', hospitalId);
    if (phone) params.set('phone', phone);
    if (name) params.set('name', name);
    const qs = params.toString();
    return request(`/api/v1/patients${qs ? '?' + qs : ''}`);
  },

  get(id: string): Promise<Patient> {
    return request(`/api/v1/patients/${encodeURIComponent(id)}`);
  },

  create(data: Partial<Patient>): Promise<Patient> {
    return request('/api/v1/patients', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  delete(id: string): Promise<void> {
    return request(`/api/v1/patients/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    });
  },

  getMedicalRecords(patientId: string): Promise<MedicalRecord[]> {
    return request(`/api/v1/patients/${encodeURIComponent(patientId)}/medical-records`);
  },

  getVisitRecords(patientId: string): Promise<VisitRecord[]> {
    return request(`/api/v1/patients/${encodeURIComponent(patientId)}/visits`);
  },

  getProfile(patientId: string): Promise<PatientProfile> {
    return request(`/api/v1/memory/profile?patient_id=${encodeURIComponent(patientId)}`);
  },
};

// ============================================================
// Agent / 聊天 API
// ============================================================

export const agentApi = {
  query(params: {
    question: string;
    patient_id?: string;
    hospital_id?: string;
    auth_token?: string;
    session_id?: string;
    chat_mode?: string;
  }): Promise<AgentQueryResponse> {
    return request('/api/v1/mcp/agent/query', {
      method: 'POST',
      body: JSON.stringify(params),
      timeout: 120_000,
    });
  },

  queryStream(
    params: {
      question: string;
      patient_id?: string;
      hospital_id?: string;
      auth_token?: string;
      session_id?: string;
      chat_mode?: string;
    },
    callbacks: {
      onStatus?: (phase: string, message: string) => void;
      onPhase?: (phase: string, message: string) => void;
      onIntent?: (intent: string, confidence: number) => void;
      onPlanning?: (plan: Record<string, unknown>) => void;
      onToolExecution?: (tool: string) => void;
      onToken?: (content: string) => void;
      onDone?: (data: {
        answer: string;
        speech_text?: string;
        intent?: string;
        chosen_tool?: string;
        session_id?: string;
        patient_id?: string;
        memory_debug?: MemoryDebugPayload;
      }) => void;
      onError?: (detail: string) => void;
    },
    signal?: AbortSignal,
  ): Promise<void> {
    return new Promise<void>(async (resolve, reject) => {
      try {
        const resp = await fetch(`${BASE}/api/v1/mcp/agent/query-stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params),
          signal,
        });

        if (!resp.ok) {
          const text = await resp.text();
          let detail = text;
          try { const j = JSON.parse(text); detail = j.detail || text; } catch { /* ignore */ }
          throw new Error(detail || `请求失败: ${resp.status}`);
        }

        const reader = resp.body?.getReader();
        if (!reader) {
          throw new Error('响应体不可读');
        }

        const decoder = new TextDecoder();
        let buffer = '';
        let currentData = '';

        const readLoop = async () => {
          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              buffer += decoder.decode(value, { stream: true });

              // Parse SSE events from buffer
              const lines = buffer.split('\n');
              buffer = lines.pop() || '';

              let currentEvent = '';
              currentData = '';

              for (const line of lines) {
                if (line.startsWith('event: ')) {
                  currentEvent = line.slice(7).trim();
                } else if (line.startsWith('data: ')) {
                  currentData += line.slice(6);
                } else if (line === '' && currentEvent && currentData) {
                  // Empty line = end of event
                  try {
                    const payload = JSON.parse(currentData);
                    switch (currentEvent) {
                      case 'status':
                        callbacks.onStatus?.(payload.phase, payload.message);
                        break;
                      case 'phase':
                        callbacks.onPhase?.(payload.phase, payload.message);
                        break;
                      case 'intent':
                        callbacks.onIntent?.(payload.intent || '', payload.confidence || 0);
                        break;
                      case 'planning':
                        callbacks.onPlanning?.(payload.chosen_plan || payload);
                        break;
                      case 'tool_execution':
                        callbacks.onToolExecution?.(payload.tool || '');
                        break;
                      case 'token':
                        callbacks.onToken?.(payload.content || '');
                        break;
                      case 'done':
                        callbacks.onDone?.(payload);
                        break;
                      case 'error':
                        callbacks.onError?.(payload.detail || '处理失败');
                        break;
                    }
                  } catch { /* ignore malformed JSON */ }
                  currentEvent = '';
                  currentData = '';
                } else if (line === '' && currentData) {
                  // data without event type — fallback
                  try {
                    const payload = JSON.parse(currentData);
                    if (payload.content !== undefined) {
                      callbacks.onToken?.(payload.content || '');
                    }
                  } catch { /* ignore */ }
                  currentData = '';
                }
              }
            }

            // Flush remaining buffer
            if (currentData) {
              try {
                const payload = JSON.parse(currentData);
                if (payload.content !== undefined) {
                  callbacks.onToken?.(payload.content || '');
                }
              } catch { /* ignore */ }
            }

            resolve();
          } catch (err) {
            if ((err as Error).name === 'AbortError') {
              resolve(); // Treat abort as normal completion
            } else {
              reject(err);
            }
          }
        };

        readLoop();
      } catch (err) {
        reject(err);
      }
    });
  },

  queryWithImage(params: {
    question: string;
    image: File;
    patient_id?: string;
    hospital_id?: string;
    auth_token?: string;
    session_id?: string;
    chat_mode?: string;
  }): Promise<AgentQueryResponse> {
    const fd = new FormData();
    fd.append('question', params.question);
    fd.append('image', params.image);
    if (params.patient_id) fd.append('patient_id', params.patient_id);
    if (params.hospital_id) fd.append('hospital_id', params.hospital_id);
    if (params.auth_token) fd.append('auth_token', params.auth_token);
    if (params.session_id) fd.append('session_id', params.session_id);
    if (params.chat_mode) fd.append('chat_mode', params.chat_mode);
    return request('/api/v1/mcp/agent/query-with-image', {
      method: 'POST',
      body: fd,
      timeout: 180_000,
    });
  },

  speech(text: string): Promise<{ audio_url?: string; audio_base64?: string }> {
    return request('/api/v1/mcp/agent/speech', {
      method: 'POST',
      body: JSON.stringify({ text }),
      timeout: 60_000,
    });
  },

  issueToken(patientId: string, hospitalId: string): Promise<{ token: string }> {
    return request('/api/v1/mcp/auth/issue-token', {
      method: 'POST',
      body: JSON.stringify({ patient_id: patientId, hospital_id: hospitalId }),
    });
  },
};

// ============================================================
// 记忆 / 会话 API
// ============================================================

export const memoryApi = {
  getConversationMessages(
    patientId: string,
    sessionId?: string,
    limit = 20,
  ): Promise<ChatMessage[]> {
    const params = new URLSearchParams({ patient_id: patientId, limit: String(limit) });
    if (sessionId) params.set('session_id', sessionId);
    return request(`/api/v1/memory/conversations/messages?${params}`);
  },

  getSessions(patientId: string): Promise<ConversationSession[]> {
    return request(`/api/v1/memory/conversations/sessions?patient_id=${encodeURIComponent(patientId)}`);
  },

  deleteMessages(patientId: string, sessionId?: string): Promise<void> {
    const params = new URLSearchParams({ patient_id: patientId });
    if (sessionId) params.set('session_id', sessionId);
    return request(`/api/v1/memory/conversations/messages?${params}`, {
      method: 'DELETE',
    });
  },

  promoteSession(sessionId: string, patientId: string, hospitalId: string): Promise<void> {
    return request('/api/v1/memory/conversations/promote-session', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, patient_id: patientId, hospital_id: hospitalId }),
    });
  },
};

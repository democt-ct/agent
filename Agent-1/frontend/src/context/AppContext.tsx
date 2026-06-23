import { createContext, useContext, useReducer, type Dispatch, type ReactNode } from 'react';
import type { AppState, AppAction, ChatMode, SpeechMode, Theme } from '../types';

// ============================================================
// 初始状态
// ============================================================

const initialState: AppState = {
  patientId: '',
  hospitalId: 'hospital-a',
  authToken: '',
  profileName: '',
  profilePhone: '',

  sessionId: '',
  generalSessionId: '',
  chatMode: (localStorage.getItem('agentChatMode') as ChatMode) || 'general',
  speechMode: (localStorage.getItem('agentSpeechMode') as SpeechMode) || 'browser',
  theme: (localStorage.getItem('agentTheme') as Theme) || 'light',

  chatMessages: [],
  generalChatMessages: [],
  lastAnswer: '',
  lastSpeechText: '',

  workingMemory: null,
  memoryLayers: null,

  patients: [],
  selectedPatient: null,
  patientProfile: null,

  currentView: 'chat',
  memoryDebugOpen: false,
  isLoading: false,
  isPatientPanelOpen: false,
  isLoginModalOpen: false,
  error: null,
  statusMessage: '',
};

// ============================================================
// Reducer
// ============================================================

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_PATIENT_CONTEXT':
      return {
        ...state,
        patientId: action.payload.patientId,
        hospitalId: action.payload.hospitalId,
        authToken: action.payload.authToken ?? state.authToken,
        profileName: action.payload.profileName ?? state.profileName,
        profilePhone: action.payload.profilePhone ?? state.profilePhone,
      };
    case 'CLEAR_PATIENT_CONTEXT':
      return {
        ...state,
        patientId: '',
        authToken: '',
        profileName: '',
        profilePhone: '',
        selectedPatient: null,
        patientProfile: null,
      };
    case 'SET_SESSION_ID':
      return { ...state, sessionId: action.payload };
    case 'SET_GENERAL_SESSION_ID':
      return { ...state, generalSessionId: action.payload };
    case 'SET_CHAT_MODE': {
      localStorage.setItem('agentChatMode', action.payload);
      return { ...state, chatMode: action.payload };
    }
    case 'SET_SPEECH_MODE': {
      localStorage.setItem('agentSpeechMode', action.payload);
      return { ...state, speechMode: action.payload };
    }
    case 'SET_THEME': {
      localStorage.setItem('agentTheme', action.payload);
      return { ...state, theme: action.payload };
    }
    case 'ADD_CHAT_MESSAGE':
      return { ...state, chatMessages: [...state.chatMessages, action.payload].slice(-30) };
    case 'ADD_GENERAL_CHAT_MESSAGE':
      return { ...state, generalChatMessages: [...state.generalChatMessages, action.payload].slice(-30) };
    case 'SET_CHAT_MESSAGES':
      return { ...state, chatMessages: action.payload };
    case 'SET_GENERAL_CHAT_MESSAGES':
      return { ...state, generalChatMessages: action.payload };
    case 'SET_LAST_ANSWER':
      return { ...state, lastAnswer: action.payload };
    case 'SET_LAST_SPEECH_TEXT':
      return { ...state, lastSpeechText: action.payload };
    case 'SET_WORKING_MEMORY':
      return { ...state, workingMemory: action.payload };
    case 'SET_MEMORY_LAYERS':
      return { ...state, memoryLayers: action.payload };
    case 'SET_PATIENTS':
      return { ...state, patients: action.payload };
    case 'SET_SELECTED_PATIENT':
      return { ...state, selectedPatient: action.payload };
    case 'SET_PATIENT_PROFILE':
      return { ...state, patientProfile: action.payload };
    case 'SET_VIEW':
      return { ...state, currentView: action.payload };
    case 'SET_MEMORY_DEBUG':
      return { ...state, memoryDebugOpen: action.payload };
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_PATIENT_PANEL':
      return { ...state, isPatientPanelOpen: action.payload };
    case 'SET_LOGIN_MODAL':
      return { ...state, isLoginModalOpen: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    case 'SET_STATUS':
      return { ...state, statusMessage: action.payload };
    case 'RESET_CHAT':
      return {
        ...state,
        chatMessages: [],
        generalChatMessages: [],
        lastAnswer: '',
        lastSpeechText: '',
        workingMemory: null,
        memoryLayers: null,
        memoryDebugOpen: false,
        error: null,
        statusMessage: '',
      };
    default:
      return state;
  }
}

// ============================================================
// Context
// ============================================================

interface AppContextType {
  state: AppState;
  dispatch: Dispatch<AppAction>;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);
  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}

export function useAppState(): AppContextType {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppState must be used within AppProvider');
  return ctx;
}

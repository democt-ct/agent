import { useState, useEffect } from 'react';
import { AppProvider, useAppState } from './context/AppContext';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ChatPanel } from './components/ChatPanel';
import { LoginModal } from './components/LoginModal';

import { MemoryDebugPanel } from './components/MemoryDebugPanel';

function AppShell() {
  const { state, dispatch } = useAppState();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Apply theme to <html> element
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', state.theme);
  }, [state.theme]);

  return (
    <div className="app-shell">
      <Header
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        sidebarOpen={sidebarOpen}
      />

      <div className="app-body">
        {sidebarOpen && (
          <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />
        )}
        <aside className={`sidebar-drawer ${sidebarOpen ? 'open' : ''}`}>
          <Sidebar onClose={() => setSidebarOpen(false)} />
        </aside>

        <main className="app-main">
          <ChatPanel />
        </main>
      </div>

      {state.memoryDebugOpen && (state.workingMemory || state.memoryLayers) && (
        <div className="memory-debug-overlay" onClick={() => dispatch({ type: 'SET_MEMORY_DEBUG', payload: false })}>
          <div className="memory-debug-overlay-content" onClick={(e) => e.stopPropagation()}>
            <div className="memory-debug-overlay-header">
              <h2>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: -3, marginRight: 8 }}>
                  <path d="M9.5 2A2.5 2.5 0 0112 4.5v15a2.5 2.5 0 01-4.96.44 2.5 2.5 0 01-2.96-3.08 3 3 0 01-.34-5.58 2.5 2.5 0 011.32-4.24 2.5 2.5 0 011.98-3A2.5 2.5 0 019.5 2z"/>
                  <path d="M14.5 2A2.5 2.5 0 0012 4.5v15a2.5 2.5 0 004.96.44 2.5 2.5 0 002.96-3.08 3 3 0 00.34-5.58 2.5 2.5 0 00-1.32-4.24 2.5 2.5 0 00-1.98-3A2.5 2.5 0 0014.5 2z"/>
                </svg>
                Memory Debug
              </h2>
              <button
                className="btn btn-sm"
                onClick={() => dispatch({ type: 'SET_MEMORY_DEBUG', payload: false })}
              >
                关闭
              </button>
            </div>
            <MemoryDebugPanel />
          </div>
        </div>
      )}

      <LoginModal />

      {state.error && (
        <div
          className="toast toast-error"
          onClick={() => dispatch({ type: 'SET_ERROR', payload: null })}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: -2, marginRight: 6 }}>
            <circle cx="12" cy="12" r="10"/>
            <line x1="15" y1="9" x2="9" y2="15"/>
            <line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          {state.error}
        </div>
      )}
      {state.statusMessage && !state.error && (
        <div
          className="toast toast-success"
          onClick={() => dispatch({ type: 'SET_STATUS', payload: '' })}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: -2, marginRight: 6 }}>
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          {state.statusMessage}
        </div>
      )}
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppShell />
    </AppProvider>
  );
}

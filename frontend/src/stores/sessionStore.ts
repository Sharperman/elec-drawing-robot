/**
 * Session Store - 当前项目/图纸会话状态
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Session } from '@/types';

interface SessionState {
  currentSessionId: string | null;
  sessions: Session[];
}

interface SessionActions {
  setCurrentSession: (sessionId: string | null) => void;
  setSessions: (sessions: Session[]) => void;
  addSession: (session: Session) => void;
  updateSession: (sessionId: string, updates: Partial<Session>) => void;
  removeSession: (sessionId: string) => void;
  getCurrentSession: () => Session | null;
}

export const useSessionStore = create<SessionState & SessionActions>()(
  persist(
    (set, get) => ({
      currentSessionId: null,
      sessions: [],

      setCurrentSession: (sessionId) => {
        set({ currentSessionId: sessionId });
      },

      setSessions: (sessions) => {
        set({ sessions });
      },

      addSession: (session) => {
        set((state) => ({
          sessions: [session, ...state.sessions],
          currentSessionId: session.session_id,
        }));
      },

      updateSession: (sessionId, updates) => {
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.session_id === sessionId ? { ...s, ...updates } : s
          ),
        }));
      },

      removeSession: (sessionId) => {
        set((state) => {
          const newSessions = state.sessions.filter((s) => s.session_id !== sessionId);
          return {
            sessions: newSessions,
            currentSessionId:
              state.currentSessionId === sessionId
                ? newSessions[0]?.session_id ?? null
                : state.currentSessionId,
          };
        });
      },

      getCurrentSession: () => {
        const { currentSessionId, sessions } = get();
        return sessions.find((s) => s.session_id === currentSessionId) ?? null;
      },
    }),
    {
      name: 'session-storage',
      partialize: (state) => ({
        currentSessionId: state.currentSessionId,
      }),
    }
  )
);

import { create } from 'zustand';
import type { Session, AgentType } from '../types';
import { getMockSession, getAllMockSessions, createMockSession } from '../mock/mockData';
import { useWorkflowStore } from './workflowStore';
import { useArtifactStore } from './artifactStore';
import { useChatStore } from './chatStore';

interface SessionState {
  currentSession: Session | null;
  sessions: Session[];
  isLoading: boolean;
  error: string | null;

  // Actions
  setCurrentSession: (sessionId: string | null) => void;
  loadSessions: () => Promise<void>;
  createSession: (agentType: AgentType, prompt: string, projectDir?: string) => Promise<void>;
  updateSessionStatus: (status: Session['status']) => void;
  clearError: () => void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  currentSession: null,
  sessions: [],
  isLoading: false,
  error: null,

  setCurrentSession: (sessionId) => {
    if (!sessionId) {
      set({ currentSession: null });
      // Clear related stores
      useWorkflowStore.getState().reset();
      useArtifactStore.getState().setArtifacts([]);
      useChatStore.getState().setMessages([]);
      return;
    }

    const session = getMockSession(sessionId);
    if (session) {
      set({ currentSession: session });

      // Initialize related stores with session data
      if (session.workflow) {
        useWorkflowStore.getState().setWorkflow(session.workflow);
      }
      if (session.artifacts) {
        useArtifactStore.getState().setArtifacts(session.artifacts);
      }
      if (session.messages) {
        useChatStore.getState().setMessages(session.messages);
      }
    }
  },

  loadSessions: async () => {
    set({ isLoading: true, error: null });
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 500));

    try {
      const sessions = getAllMockSessions();
      set({ sessions, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load sessions',
        isLoading: false
      });
    }
  },

  createSession: async (agentType, prompt, projectDir) => {
    set({ isLoading: true, error: null });

    try {
      // Simulate API call delay
      await new Promise(resolve => setTimeout(resolve, 800));

      // Create a new mock session
      const newSession = createMockSession(agentType, prompt, projectDir);

      // Add to sessions list
      const { sessions } = get();
      set({
        sessions: [newSession, ...sessions],
        currentSession: newSession,
        isLoading: false
      });

      // Initialize related stores
      if (newSession.workflow) {
        useWorkflowStore.getState().setWorkflow(newSession.workflow);
      }
      if (newSession.artifacts) {
        useArtifactStore.getState().setArtifacts(newSession.artifacts);
      }
      if (newSession.messages) {
        useChatStore.getState().setMessages(newSession.messages);
      }
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to create session',
        isLoading: false
      });
      throw error;
    }
  },

  updateSessionStatus: (status) => {
    const { currentSession } = get();
    if (currentSession) {
      set({
        currentSession: {
          ...currentSession,
          status,
          updated_at: new Date().toISOString()
        }
      });
    }
  },

  clearError: () => {
    set({ error: null });
  }
}));

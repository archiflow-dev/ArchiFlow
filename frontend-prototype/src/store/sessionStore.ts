import { create } from 'zustand';
import type { Session, AgentType } from '../types';
import { sessionApi, type SessionResponse } from '../services';
import { useWorkflowStore } from './workflowStore';
import { useArtifactStore } from './artifactStore';
import { useChatStore } from './chatStore';

// ============================================================================
// Helper: Convert API response to frontend Session type
// ============================================================================

function mapSessionResponse(response: SessionResponse): Session {
  return {
    session_id: response.id,
    agent_type: response.agent_type,
    user_prompt: response.user_prompt,
    project_directory: response.project_directory,
    status: response.status === 'created' ? 'paused' : response.status,
    created_at: response.created_at,
    updated_at: response.updated_at,
    // workflow, artifacts, and messages are loaded separately
  };
}

// ============================================================================
// Store Interface
// ============================================================================

interface SessionState {
  currentSession: Session | null;
  sessions: Session[];
  isLoading: boolean;
  error: string | null;

  // Actions
  setCurrentSession: (sessionId: string | null) => Promise<void>;
  loadSessions: () => Promise<void>;
  createSession: (agentType: AgentType, prompt: string, projectDir?: string) => Promise<Session>;
  updateSessionStatus: (status: Session['status']) => void;
  deleteSession: (sessionId: string) => Promise<void>;
  clearError: () => void;
  loadSession: (sessionId: string) => Promise<void>;

  // Session control
  startSession: (sessionId: string) => Promise<void>;
  pauseSession: (sessionId: string) => Promise<void>;
  resumeSession: (sessionId: string) => Promise<void>;
}

// ============================================================================
// Store Implementation
// ============================================================================

export const useSessionStore = create<SessionState>((set, get) => ({
  currentSession: null,
  sessions: [],
  isLoading: false,
  error: null,

  setCurrentSession: async (sessionId) => {
    if (!sessionId) {
      set({ currentSession: null });
      // Clear related stores
      useWorkflowStore.getState().reset();
      useArtifactStore.getState().setArtifacts([]);
      useChatStore.getState().setMessages([]);
      return;
    }

    set({ isLoading: true, error: null });

    try {
      const response = await sessionApi.get(sessionId);
      const session = mapSessionResponse(response);
      set({ currentSession: session, isLoading: false });

      // Load related data
      await Promise.all([
        useWorkflowStore.getState().loadWorkflow(sessionId),
        useArtifactStore.getState().loadArtifacts(sessionId),
        useChatStore.getState().loadMessages(sessionId),
      ]);
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load session',
        isLoading: false,
      });
    }
  },

  loadSessions: async () => {
    set({ isLoading: true, error: null });

    try {
      const response = await sessionApi.list({ page_size: 100 });
      const sessions = response.sessions.map(mapSessionResponse);
      set({ sessions, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load sessions',
        isLoading: false,
      });
    }
  },

  createSession: async (agentType, prompt, projectDir) => {
    set({ isLoading: true, error: null });

    try {
      const response = await sessionApi.create({
        agent_type: agentType,
        user_prompt: prompt || undefined,  // Ensure empty strings become undefined
        project_directory: projectDir,
      });

      const newSession = mapSessionResponse(response);

      // Add to sessions list
      const { sessions } = get();
      set({
        sessions: [newSession, ...sessions],
        currentSession: newSession,
        isLoading: false,
      });

      // Only auto-start if there's an initial prompt
      // Otherwise, wait for user to send first message via chat
      if (prompt && prompt.trim()) {
        await sessionApi.start(newSession.session_id);
        newSession.status = 'running';
        set({ currentSession: { ...newSession, status: 'running' } });
      }

      // Load related data
      await Promise.all([
        useWorkflowStore.getState().loadWorkflow(newSession.session_id),
        useArtifactStore.getState().loadArtifacts(newSession.session_id),
        useChatStore.getState().loadMessages(newSession.session_id),
      ]);

      return newSession;
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to create session',
        isLoading: false,
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
          updated_at: new Date().toISOString(),
        },
      });
    }
  },

  deleteSession: async (sessionId) => {
    set({ isLoading: true, error: null });

    try {
      await sessionApi.delete(sessionId);

      const { sessions, currentSession } = get();
      const updatedSessions = sessions.filter((s) => s.session_id !== sessionId);

      set({
        sessions: updatedSessions,
        currentSession: currentSession?.session_id === sessionId ? null : currentSession,
        isLoading: false,
      });

      // Clear related stores if this was the current session
      if (currentSession?.session_id === sessionId) {
        useWorkflowStore.getState().reset();
        useArtifactStore.getState().setArtifacts([]);
        useChatStore.getState().setMessages([]);
      }
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to delete session',
        isLoading: false,
      });
      throw error;
    }
  },

  clearError: () => {
    set({ error: null });
  },

  startSession: async (sessionId) => {
    try {
      await sessionApi.start(sessionId);
      get().updateSessionStatus('running');
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to start session',
      });
      throw error;
    }
  },

  pauseSession: async (sessionId) => {
    try {
      await sessionApi.pause(sessionId);
      get().updateSessionStatus('paused');
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to pause session',
      });
      throw error;
    }
  },

  resumeSession: async (sessionId) => {
    try {
      await sessionApi.resume(sessionId);
      get().updateSessionStatus('running');
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to resume session',
      });
      throw error;
    }
  },

  loadSession: async (sessionId) => {
    // Delegates to setCurrentSession which handles loading
    await get().setCurrentSession(sessionId);
  },
}));

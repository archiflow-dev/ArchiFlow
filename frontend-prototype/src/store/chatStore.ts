import { create } from 'zustand';
import type { ChatMessage } from '../types';
import { messageApi, type MessageResponse } from '../services';

// ============================================================================
// Helper: Convert API response to frontend ChatMessage type
// ============================================================================

function mapMessageResponse(response: MessageResponse): ChatMessage {
  return {
    id: response.id,
    type: response.role === 'assistant' ? 'agent' : response.role,
    content: response.content,
    timestamp: response.created_at,
    tool_calls: response.tool_calls?.map((tc) => ({
      name: tc.name,
      parameters: tc.parameters,
      result: tc.result,
      error: tc.error,
    })),
  };
}

// ============================================================================
// Store Interface
// ============================================================================

interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  isSending: boolean;
  error: string | null;
  sessionId: string | null;

  // Actions
  setMessages: (messages: ChatMessage[]) => void;
  loadMessages: (sessionId: string) => Promise<void>;
  sendMessage: (content: string) => Promise<ChatMessage | null>;
  addMessage: (message: ChatMessage) => void;
  updateMessage: (messageId: string, updates: Partial<ChatMessage>) => void;
  clearMessages: () => void;
  clearError: () => void;
}

// ============================================================================
// Store Implementation
// ============================================================================

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isLoading: false,
  isSending: false,
  error: null,
  sessionId: null,

  setMessages: (messages) => {
    set({ messages });
  },

  loadMessages: async (sessionId) => {
    set({ isLoading: true, error: null, sessionId });

    try {
      const response = await messageApi.list(sessionId, { limit: 1000 });
      const messages = response.messages.map(mapMessageResponse);
      set({ messages, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load messages',
        isLoading: false,
      });
    }
  },

  sendMessage: async (content) => {
    const { sessionId } = get();
    if (!sessionId) {
      set({ error: 'No session selected' });
      return null;
    }

    set({ isSending: true, error: null });

    try {
      const response = await messageApi.send(sessionId, content);
      const message = mapMessageResponse(response);

      // Add the message to local state
      set((state) => ({
        messages: [...state.messages, message],
        isSending: false,
      }));

      return message;
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to send message',
        isSending: false,
      });
      return null;
    }
  },

  addMessage: (message) => {
    set((state) => ({
      messages: [...state.messages, message],
    }));
  },

  updateMessage: (messageId, updates) => {
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === messageId ? { ...msg, ...updates } : msg,
      ),
    }));
  },

  clearMessages: () => {
    set({ messages: [], sessionId: null });
  },

  clearError: () => {
    set({ error: null });
  },
}));

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

interface StreamingMessage {
  id: string;
  content: string;
  isComplete: boolean;
}

interface ChatState {
  messages: ChatMessage[];
  streamingMessages: Map<string, StreamingMessage>;
  isLoading: boolean;
  isSending: boolean;
  error: string | null;
  sessionId: string | null;

  // Actions
  setMessages: (messages: ChatMessage[]) => void;
  loadMessages: (sessionId: string) => Promise<void>;
  sendMessage: (content: string) => Promise<ChatMessage | null>;
  addMessage: (message: ChatMessage | {
    id: string;
    sessionId: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: string;
  }) => void;
  updateMessage: (messageId: string, updates: Partial<ChatMessage>) => void;
  updateStreamingMessage: (messageId: string, chunk: string, isComplete: boolean) => void;
  clearMessages: () => void;
  clearError: () => void;
}

// ============================================================================
// Store Implementation
// ============================================================================

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  streamingMessages: new Map(),
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
    // Normalize message format
    const chatMessage: ChatMessage = 'type' in message
      ? message
      : {
          id: message.id,
          type: message.role === 'assistant' ? 'agent' : message.role,
          content: message.content,
          timestamp: message.timestamp,
        };

    // Check if message already exists (prevent duplicates)
    const existing = get().messages.find((m) => m.id === chatMessage.id);
    if (existing) {
      return;
    }

    set((state) => ({
      messages: [...state.messages, chatMessage],
    }));
  },

  updateMessage: (messageId, updates) => {
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === messageId ? { ...msg, ...updates } : msg,
      ),
    }));
  },

  updateStreamingMessage: (messageId, chunk, isComplete) => {
    const { streamingMessages, messages } = get();

    // Get or create streaming message
    const existing = streamingMessages.get(messageId);
    const newContent = (existing?.content ?? '') + chunk;

    if (isComplete) {
      // Move from streaming to messages
      const newStreamingMessages = new Map(streamingMessages);
      newStreamingMessages.delete(messageId);

      // Check if already in messages
      const existingMessage = messages.find((m) => m.id === messageId);
      if (!existingMessage) {
        set({
          streamingMessages: newStreamingMessages,
          messages: [
            ...messages,
            {
              id: messageId,
              type: 'agent',
              content: newContent,
              timestamp: new Date().toISOString(),
            },
          ],
        });
      } else {
        // Update existing message
        set({
          streamingMessages: newStreamingMessages,
          messages: messages.map((m) =>
            m.id === messageId ? { ...m, content: newContent } : m,
          ),
        });
      }
    } else {
      // Update streaming message
      const newStreamingMessages = new Map(streamingMessages);
      newStreamingMessages.set(messageId, {
        id: messageId,
        content: newContent,
        isComplete: false,
      });
      set({ streamingMessages: newStreamingMessages });
    }
  },

  clearMessages: () => {
    set({ messages: [], streamingMessages: new Map(), sessionId: null });
  },

  clearError: () => {
    set({ error: null });
  },
}));

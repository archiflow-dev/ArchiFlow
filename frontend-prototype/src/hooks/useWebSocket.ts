/**
 * React hook for WebSocket integration.
 *
 * Provides easy integration of Socket.IO WebSocket client with React components,
 * automatically managing connection lifecycle and Zustand store updates.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import {
  WebSocketClient,
  ConnectionStatus,
  type StoreCallbacks,
  getWebSocketClient,
  type EventHandler,
} from '../services/websocket';
import type {
  WebSocketEventType,
  WorkflowUpdateEvent,
} from '../services/websocket';
import { useChatStore } from '../store/chatStore';
import { useWorkflowStore } from '../store/workflowStore';
import { useArtifactStore } from '../store/artifactStore';
import { useSessionStore } from '../store/sessionStore';

// ============================================================================
// Types
// ============================================================================

export interface UseWebSocketOptions {
  /**
   * Whether to connect automatically on mount.
   * @default true
   */
  autoConnect?: boolean;

  /**
   * Session ID to subscribe to on connect.
   */
  sessionId?: string;

  /**
   * Whether to auto-update Zustand stores on events.
   * @default true
   */
  syncStores?: boolean;

  /**
   * Custom callbacks for specific events.
   */
  callbacks?: Partial<StoreCallbacks>;
}

export interface UseWebSocketReturn {
  /**
   * Current connection status.
   */
  status: ConnectionStatus;

  /**
   * Whether connected and ready.
   */
  isConnected: boolean;

  /**
   * Currently subscribed session ID.
   */
  sessionId: string | null;

  /**
   * Whether agent is currently processing.
   */
  isAgentProcessing: boolean;

  /**
   * Whether agent is waiting for user input.
   */
  isWaitingForInput: boolean;

  /**
   * Connect to the WebSocket server.
   */
  connect: (sessionId?: string) => void;

  /**
   * Disconnect from the server.
   */
  disconnect: () => void;

  /**
   * Subscribe to a session.
   */
  subscribeToSession: (sessionId: string) => void;

  /**
   * Unsubscribe from current session.
   */
  unsubscribeFromSession: () => void;

  /**
   * Send a chat message.
   */
  sendMessage: (content: string) => void;

  /**
   * Register an event handler.
   * Returns unsubscribe function.
   */
  on: <T extends WebSocketEventType>(eventType: T['type'] | '*', handler: EventHandler<T>) => () => void;

  /**
   * The underlying WebSocket client.
   */
  client: WebSocketClient;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * React hook for WebSocket integration with Zustand stores.
 *
 * Automatically connects to the WebSocket server and syncs events
 * with Zustand stores for real-time UI updates.
 *
 * @example
 * ```tsx
 * function ChatComponent() {
 *   const {
 *     status,
 *     isConnected,
 *     sendMessage,
 *     isAgentProcessing,
 *   } = useWebSocket({ sessionId: 'session-123' });
 *
 *   const handleSend = () => {
 *     sendMessage('Hello!');
 *   };
 *
 *   return (
 *     <div>
 *       <span>Status: {status}</span>
 *       {isAgentProcessing && <span>Agent is thinking...</span>}
 *       <button onClick={handleSend} disabled={!isConnected}>
 *         Send
 *       </button>
 *     </div>
 *   );
 * }
 * ```
 */
export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const {
    autoConnect = true,
    sessionId: initialSessionId,
    syncStores = true,
    callbacks = {},
  } = options;

  // State
  const [status, setStatus] = useState<ConnectionStatus>(ConnectionStatus.Disconnected);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(initialSessionId ?? null);
  const [isAgentProcessing, setIsAgentProcessing] = useState(false);
  const [isWaitingForInput, setIsWaitingForInput] = useState(false);

  // Client ref
  const clientRef = useRef<WebSocketClient>(getWebSocketClient());

  // Store actions
  const chatStore = useChatStore();
  const workflowStore = useWorkflowStore();
  const artifactStore = useArtifactStore();
  const sessionStore = useSessionStore();

  // Memoized callbacks that sync with stores
  const storeCallbacks = useCallback((): StoreCallbacks => {
    const baseCallbacks: StoreCallbacks = {
      onMessage: (message) => {
        if (syncStores && currentSessionId) {
          // Add message to chat store
          chatStore.addMessage({
            id: message.id,
            sessionId: currentSessionId,
            role: message.role as 'user' | 'assistant' | 'system',
            content: message.content,
            timestamp: message.timestamp ?? new Date().toISOString(),
          });
        }
        callbacks.onMessage?.(message);
      },

      onMessageChunk: (messageId, chunk, isComplete) => {
        if (syncStores) {
          // Update streaming message in chat store
          chatStore.updateStreamingMessage(messageId, chunk, isComplete);
        }
        callbacks.onMessageChunk?.(messageId, chunk, isComplete);
      },

      onToolCall: (toolName, args) => {
        setIsAgentProcessing(true);
        callbacks.onToolCall?.(toolName, args);
      },

      onToolResult: (toolName, result, status) => {
        callbacks.onToolResult?.(toolName, result, status);
      },

      onWorkflowUpdate: (update: WorkflowUpdateEvent) => {
        if (syncStores && currentSessionId) {
          // Refresh workflow state from store
          workflowStore.loadWorkflow(currentSessionId);
        }
        callbacks.onWorkflowUpdate?.(update);
      },

      onArtifactUpdate: (path, action) => {
        if (syncStores && currentSessionId) {
          if (action === 'deleted') {
            artifactStore.removeArtifact(path);
          } else {
            // Refresh artifacts from server
            artifactStore.loadArtifacts(currentSessionId);
          }
        }
        callbacks.onArtifactUpdate?.(path, action);
      },

      onSessionUpdate: (sessionStatus) => {
        if (syncStores && currentSessionId) {
          sessionStore.loadSession(currentSessionId);
        }
        callbacks.onSessionUpdate?.(sessionStatus);
      },

      onAgentThinking: () => {
        setIsAgentProcessing(true);
        setIsWaitingForInput(false);
        callbacks.onAgentThinking?.();
      },

      onAgentFinished: (reason) => {
        setIsAgentProcessing(false);
        setIsWaitingForInput(false);
        callbacks.onAgentFinished?.(reason);
      },

      onWaitingForInput: () => {
        setIsAgentProcessing(false);
        setIsWaitingForInput(true);
        callbacks.onWaitingForInput?.();
      },

      onError: (message, code) => {
        console.error('WebSocket error:', message, code);
        callbacks.onError?.(message, code);
      },
    };

    return baseCallbacks;
  }, [
    syncStores,
    currentSessionId,
    chatStore,
    workflowStore,
    artifactStore,
    sessionStore,
    callbacks,
  ]);

  // Set up store callbacks when they change
  useEffect(() => {
    clientRef.current.setStoreCallbacks(storeCallbacks());
  }, [storeCallbacks]);

  // Set up status change listener
  useEffect(() => {
    const client = clientRef.current;

    const unsubscribe = client.onStatusChange((newStatus) => {
      setStatus(newStatus);
    });

    return () => {
      unsubscribe();
    };
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      clientRef.current.connect(initialSessionId);
    }

    // Update session ID tracking
    if (initialSessionId) {
      setCurrentSessionId(initialSessionId);
    }

    return () => {
      // Don't disconnect on unmount - let the singleton persist
    };
  }, [autoConnect, initialSessionId]);

  // Memoized action handlers
  const connect = useCallback((sessionId?: string) => {
    clientRef.current.connect(sessionId);
    if (sessionId) {
      setCurrentSessionId(sessionId);
    }
  }, []);

  const disconnect = useCallback(() => {
    clientRef.current.disconnect();
    setCurrentSessionId(null);
    setIsAgentProcessing(false);
    setIsWaitingForInput(false);
  }, []);

  const subscribeToSession = useCallback((sessionId: string) => {
    clientRef.current.subscribeToSession(sessionId);
    setCurrentSessionId(sessionId);
    setIsAgentProcessing(false);
    setIsWaitingForInput(false);
  }, []);

  const unsubscribeFromSession = useCallback(() => {
    clientRef.current.unsubscribeFromSession();
    setCurrentSessionId(null);
    setIsAgentProcessing(false);
    setIsWaitingForInput(false);
  }, []);

  const sendMessage = useCallback((content: string) => {
    console.log('[useWebSocket] 📤 sendMessage called:', {
      content,
      currentSessionId,
      syncStores,
      clientConnected: clientRef.current?.isConnected,
    });

    // Add user message to store optimistically
    if (syncStores && currentSessionId) {
      chatStore.addMessage({
        id: `user_${Date.now()}`,
        sessionId: currentSessionId,
        role: 'user',
        content,
        timestamp: new Date().toISOString(),
      });
      console.log('[useWebSocket] ✅ Message added to local store');
    }

    clientRef.current.sendMessage(content);
    console.log('[useWebSocket] 🔄 Sent to WebSocket client');

    setIsAgentProcessing(true);
    setIsWaitingForInput(false);
  }, [syncStores, currentSessionId, chatStore]);

  const on = useCallback(<T extends WebSocketEventType>(
    eventType: T['type'] | '*',
    handler: EventHandler<T>,
  ): (() => void) => {
    return clientRef.current.on(eventType, handler);
  }, []);

  return {
    status,
    isConnected: status === ConnectionStatus.Connected,
    sessionId: currentSessionId,
    isAgentProcessing,
    isWaitingForInput,
    connect,
    disconnect,
    subscribeToSession,
    unsubscribeFromSession,
    sendMessage,
    on,
    client: clientRef.current,
  };
}

// ============================================================================
// Convenience Hooks
// ============================================================================

/**
 * Hook for just the connection status.
 */
export function useWebSocketStatus(): ConnectionStatus {
  const [status, setStatus] = useState<ConnectionStatus>(ConnectionStatus.Disconnected);

  useEffect(() => {
    const client = getWebSocketClient();
    const unsubscribe = client.onStatusChange(setStatus);
    return unsubscribe;
  }, []);

  return status;
}

/**
 * Hook for subscribing to a specific event type.
 */
export function useWebSocketEvent<T extends WebSocketEventType>(
  eventType: T['type'],
  handler: EventHandler<T>,
): void {
  useEffect(() => {
    const client = getWebSocketClient();
    const unsubscribe = client.on(eventType, handler);
    return unsubscribe;
  }, [eventType, handler]);
}

export default useWebSocket;

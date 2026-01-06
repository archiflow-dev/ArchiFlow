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
import { useWorkspaceStore } from '../store/workspaceStore';
import { formatToolCallDetails, formatToolResult, formatTodoList } from '../lib/toolFormatter';

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
  const workspaceStore = useWorkspaceStore();

  // Track the current agent message for associating tool calls
  const currentAgentMessageRef = useRef<{ id: string; toolCalls: any[] } | null>(null);

  // Fallback timeout to reset processing state (in case waiting_for_input doesn't fire)
  const processingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Track if agent has actually started processing (to ignore premature waiting_for_input events)
  const hasStartedProcessingRef = useRef<boolean>(false);

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

          // Track agent messages for associating tool calls
          if (message.role === 'assistant') {
            currentAgentMessageRef.current = {
              id: message.id,
              toolCalls: [],
            };
          } else {
            currentAgentMessageRef.current = null;
          }
        }
        callbacks.onMessage?.(message);
      },

      onMessageChunk: (messageId, chunk, isComplete) => {
        // Mark that agent has actually started processing when we receive chunks
        if (chunk && chunk.length > 0) {
          hasStartedProcessingRef.current = true;
        }

        if (syncStores) {
          // Update streaming message in chat store
          chatStore.updateStreamingMessage(messageId, chunk, isComplete);
        }

        // Fallback: When message streaming is complete, reset processing state after a short delay
        // This ensures the spinner stops even if waiting_for_input doesn't fire
        if (isComplete) {
          // Clear any existing timeout
          if (processingTimeoutRef.current) {
            clearTimeout(processingTimeoutRef.current);
          }

          // Set timeout to reset processing state (in case waiting_for_input doesn't fire)
          processingTimeoutRef.current = setTimeout(() => {
            console.log('[useWebSocket] ⏱️ Fallback: Resetting processing state after message complete');
            setIsAgentProcessing(false);
            setIsWaitingForInput(false);
          }, 500); // 500ms delay to allow for follow-up events
        }

        callbacks.onMessageChunk?.(messageId, chunk, isComplete);
      },

      onToolCall: (toolName, args) => {
        // Clear fallback timeout when new tool call arrives
        if (processingTimeoutRef.current) {
          clearTimeout(processingTimeoutRef.current);
          processingTimeoutRef.current = null;
        }

        // Mark that agent has actually started processing
        hasStartedProcessingRef.current = true;

        setIsAgentProcessing(true);

        // Add tool call to current agent message
        if (syncStores && currentAgentMessageRef.current) {
          const toolCall = {
            name: toolName,
            parameters: args,
            result: undefined,
            error: undefined,
          };

          // Add to message's tool_calls
          chatStore.updateMessage(currentAgentMessageRef.current.id, {
            tool_calls: [...(currentAgentMessageRef.current.toolCalls || []), toolCall],
          });

          // Update ref
          currentAgentMessageRef.current.toolCalls.push(toolCall);
        }

        callbacks.onToolCall?.(toolName, args);
      },

      onToolResult: (toolName, result, status) => {
        // Update the tool call with result
        if (syncStores && currentAgentMessageRef.current) {
          const toolCalls = currentAgentMessageRef.current.toolCalls;
          const toolCall = toolCalls.find(tc => tc.name === toolName);
          if (toolCall) {
            toolCall.result = result;
            if (status !== 'success') {
              toolCall.error = result;
            }

            // Update message in store
            const messages = chatStore.messages;
            const message = messages.find(m => m.id === currentAgentMessageRef.current?.id);
            if (message && message.tool_calls) {
              chatStore.updateMessage(currentAgentMessageRef.current.id, {
                tool_calls: [...message.tool_calls],
              });
            }
          }
        }

        callbacks.onToolResult?.(toolName, result, status);
      },

      onToolCallMessage: (toolName, args) => {
        // Add tool call as a separate message for display
        if (syncStores && currentSessionId) {
          const toolCallId = `tool_call_${Date.now()}`;

          // Special handling for todo_write tools
          if ((toolName === 'todo_write' || toolName === 'todo_write_v2') && args.todos && Array.isArray(args.todos)) {
            // Use the new formatTodoList function for nice formatting
            const formattedTodos = formatTodoList(args.todos);

            chatStore.addMessage({
              id: toolCallId,
              sessionId: currentSessionId,
              role: 'system',
              content: formattedTodos,
              timestamp: new Date().toISOString(),
            });
          } else {
            // Format tool call details
            const details = formatToolCallDetails(toolName, args as Record<string, unknown>);
            const detailText = details ? `\n   ${details}` : '';

            chatStore.addMessage({
              id: toolCallId,
              sessionId: currentSessionId,
              role: 'system',
              content: `🔧 ${toolName}${detailText}`,
              timestamp: new Date().toISOString(),
            });
          }
        }
        callbacks.onToolCallMessage?.(toolName, args);
      },

      onToolResultMessage: (toolName, result, status) => {
        // Add tool result as a separate message for display
        if (syncStores && currentSessionId) {
          const toolResultId = `tool_result_${Date.now()}`;

          // Format tool result with tool-specific handling
          const { formattedResult, icon, colorClass } = formatToolResult(
            toolName,
            result,
            status
          );

          chatStore.addMessage({
            id: toolResultId,
            sessionId: currentSessionId,
            role: 'system',
            content: `${icon} ${toolName}:\n${formattedResult}`,
            timestamp: new Date().toISOString(),
          });
        }
        callbacks.onToolResultMessage?.(toolName, result, status);
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
        // Clear fallback timeout when agent starts thinking
        if (processingTimeoutRef.current) {
          clearTimeout(processingTimeoutRef.current);
          processingTimeoutRef.current = null;
        }

        // Mark that agent has actually started processing
        hasStartedProcessingRef.current = true;

        setIsAgentProcessing(true);
        setIsWaitingForInput(false);
        callbacks.onAgentThinking?.();
      },

      onAgentThought: (content: string) => {
        // Add agent thought as a message to the chat
        if (syncStores && currentSessionId && content) {
          const thoughtId = `thought_${Date.now()}`;
          chatStore.addMessage({
            id: thoughtId,
            sessionId: currentSessionId,
            role: 'assistant',
            content: `💭 ${content}`,
            timestamp: new Date().toISOString(),
          });
        }
        callbacks.onAgentThought?.(content);
      },

      onAgentFinished: (reason) => {
        console.log('[useWebSocket] 🎉 Agent finished callback called, reason:', reason);

        // Clear fallback timeout when agent finishes
        if (processingTimeoutRef.current) {
          clearTimeout(processingTimeoutRef.current);
          processingTimeoutRef.current = null;
        }

        console.log('[useWebSocket] 🔄 Clearing processing state...');
        setIsAgentProcessing(false);
        setIsWaitingForInput(false);
        currentAgentMessageRef.current = null;  // Clear the reference

        // Reset the processing flag to prepare for next turn
        hasStartedProcessingRef.current = false;

        console.log('[useWebSocket] ✅ Processing state cleared');

        // Auto-refresh workspace files when agent finishes
        // This ensures newly created files appear in the Explorer panel
        if (syncStores && currentSessionId) {
          console.log('[useWebSocket] 🔄 Auto-refreshing workspace files...');
          // Refresh workspace files
          workspaceStore.loadFiles('', true).catch((err) => {
            console.warn('[useWebSocket] Failed to refresh workspace files:', err);
          });
          // Refresh artifacts (for the Artifact panel)
          artifactStore.loadArtifacts(currentSessionId).catch((err) => {
            console.warn('[useWebSocket] Failed to refresh artifacts:', err);
          });
        }

        // Add agent finished message to chat
        if (syncStores && currentSessionId && reason) {
          const finishedId = `finished_${Date.now()}`;
          chatStore.addMessage({
            id: finishedId,
            sessionId: currentSessionId,
            role: 'system',
            content: `✅ ${reason}`,
            timestamp: new Date().toISOString(),
          });
        }

        callbacks.onAgentFinished?.(reason);
      },

      onWaitingForInput: () => {
        // Ignore waiting_for_input if we haven't actually started processing yet
        // This handles the case where backend sends this event prematurely
        if (!hasStartedProcessingRef.current) {
          console.warn('[useWebSocket] ⚠️ Ignoring premature waiting_for_input event (no processing started yet)');
          return;
        }

        // Clear fallback timeout when waiting for input
        if (processingTimeoutRef.current) {
          clearTimeout(processingTimeoutRef.current);
          processingTimeoutRef.current = null;
        }

        // Agent has finished processing and is waiting for user input
        // This is the terminal state for each turn - enable input
        console.log('[useWebSocket] ✅ Agent waiting for input (processing was started, accepting event)');
        setIsAgentProcessing(false);
        setIsWaitingForInput(false);  // Don't show indicator, just enable input

        // Auto-refresh workspace files when agent is waiting for input
        // This ensures newly created files appear in the Explorer panel
        if (syncStores && currentSessionId) {
          console.log('[useWebSocket] 🔄 Auto-refreshing workspace files...');
          // Refresh workspace files
          workspaceStore.loadFiles('', true).catch((err) => {
            console.warn('[useWebSocket] Failed to refresh workspace files:', err);
          });
          // Refresh artifacts (for the Artifact panel)
          artifactStore.loadArtifacts(currentSessionId).catch((err) => {
            console.warn('[useWebSocket] Failed to refresh artifacts:', err);
          });
        }

        callbacks.onWaitingForInput?.();
      },

      onError: (message, code) => {
        console.error('WebSocket error:', message, code);
        callbacks.onError?.(message, code);
      },

      onRefinementApplied: (content: string) => {
        // Add refinement notification as a message to the chat
        if (syncStores && currentSessionId && content) {
          const refinementId = `refinement_${Date.now()}`;
          chatStore.addMessage({
            id: refinementId,
            sessionId: currentSessionId,
            role: 'system',
            content,
            timestamp: new Date().toISOString(),
          });
        }
        callbacks.onRefinementApplied?.(content);
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
    workspaceStore,  // CRITICAL: workspaceStore was missing!
    callbacks,
  ]);

  // Set up store callbacks when they change
  useEffect(() => {
    clientRef.current.setStoreCallbacks(storeCallbacks());
  }, [storeCallbacks]);

  // Debug: Watch isAgentProcessing state changes
  useEffect(() => {
    console.log('[useWebSocket] 🔄 isAgentProcessing state changed to:', isAgentProcessing);
  }, [isAgentProcessing]);

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

  // Sync with shared processing state from WebSocket client
  useEffect(() => {
    const client = clientRef.current;

    const unsubscribe = client.onProcessingChange((isProcessing) => {
      console.log('[useWebSocket] 🔄 Syncing processing state from client:', isProcessing);
      setIsAgentProcessing(isProcessing);
      setIsWaitingForInput(false);
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

    // Clear any pending fallback timeout when sending a new message
    if (processingTimeoutRef.current) {
      clearTimeout(processingTimeoutRef.current);
      processingTimeoutRef.current = null;
    }

    // Reset the processing flag - we haven't actually started processing yet
    hasStartedProcessingRef.current = false;

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

/**
 * WebSocket client for real-time communication.
 *
 * Uses Socket.IO protocol for communication with the backend.
 * Integrates with Zustand stores for automatic state updates.
 */

import { io, Socket } from 'socket.io-client';

// ============================================================================
// Types
// ============================================================================

export const enum ConnectionStatus {
  Disconnected = 'disconnected',
  Connecting = 'connecting',
  Connected = 'connected',
  Error = 'error'
}

export interface WebSocketEvent {
  type: string;
  session_id?: string;
  timestamp?: string;
  payload?: unknown;
}

export interface AgentMessageEvent {
  type: 'agent_message' | 'message';
  session_id: string;
  message?: {
    id: string;
    role: string;
    content: string;
    sequence?: number;
    is_streaming?: boolean;
    is_complete?: boolean;
    timestamp?: string;
  };
  content?: string;
  sequence?: number;
}

export interface MessageChunkEvent {
  type: 'message_chunk';
  session_id: string;
  message_id: string;
  chunk: string;
  is_complete: boolean;
  timestamp?: string;
}

export interface ToolCallEvent {
  type: 'tool_call' | 'agent_tool_call';
  session_id: string;
  payload?: {
    tool_name: string;
    arguments: Record<string, unknown>;
    content?: string;
  };
  tool_name?: string;
  arguments?: Record<string, unknown>;
}

export interface ToolResultEvent {
  type: 'tool_result' | 'agent_tool_result';
  session_id: string;
  payload?: {
    tool_name: string;
    result: string;
    status: string;
    metadata?: Record<string, unknown>;
  };
  tool_name?: string;
  result?: string;
  status?: string;
}

export interface WorkflowUpdateEvent {
  type: 'workflow_update';
  session_id: string;
  payload?: {
    phase_id?: string;
    phase_name?: string;
    status?: string;
    next_phase?: string;
    feedback?: string;
  };
  workflow_state?: {
    current_phase?: string;
    phases?: Array<{
      id: string;
      name: string;
      status: string;
      order: number;
    }>;
  };
}

export interface ArtifactUpdateEvent {
  type: 'artifact_update';
  session_id: string;
  artifact_path: string;
  action: 'created' | 'updated' | 'deleted';
}

export interface SessionUpdateEvent {
  type: 'session_update';
  session_id: string;
  payload?: {
    status?: string;
  };
  status?: string;
}

export interface AgentEventWrapper {
  type: string;
  session_id: string;
  payload: Record<string, unknown>;
  timestamp?: string;
}

export interface WaitingForInputEvent {
  type: 'waiting_for_input';
  session_id: string;
  sequence?: number;
  timestamp?: string;
}

export interface AgentFinishedEvent {
  type: 'agent_finished';
  session_id: string;
  reason?: string;
  timestamp?: string;
}

export interface ErrorEvent {
  type: 'error';
  session_id?: string;
  message: string;
  code?: string;
}

export type WebSocketEventType =
  | AgentMessageEvent
  | MessageChunkEvent
  | ToolCallEvent
  | ToolResultEvent
  | WorkflowUpdateEvent
  | ArtifactUpdateEvent
  | SessionUpdateEvent
  | AgentEventWrapper
  | WaitingForInputEvent
  | AgentFinishedEvent
  | ErrorEvent;

export interface EventHandler<T = WebSocketEventType> {
  (event: T): void;
}

// Store update callbacks
export interface StoreCallbacks {
  onMessage?: (message: {
    id: string;
    role: string;
    content: string;
    sequence?: number;
    timestamp?: string;
  }) => void;
  onMessageChunk?: (messageId: string, chunk: string, isComplete: boolean) => void;
  onToolCall?: (toolName: string, args: Record<string, unknown>) => void;
  onToolResult?: (toolName: string, result: string, status: string) => void;
  onWorkflowUpdate?: (update: WorkflowUpdateEvent) => void;
  onArtifactUpdate?: (path: string, action: 'created' | 'updated' | 'deleted') => void;
  onSessionUpdate?: (status: string) => void;
  onAgentThinking?: () => void;
  onAgentThought?: (content: string) => void;  // New: for agent thoughts with actual content
  onAgentFinished?: (reason?: string) => void;
  onWaitingForInput?: () => void;
  onError?: (message: string, code?: string) => void;
  onToolCallMessage?: (toolName: string, args: Record<string, unknown>) => void;  // New: for displaying tool calls
  onToolResultMessage?: (toolName: string, result: string, status: string) => void;  // New: for displaying tool results
  onRefinementApplied?: (content: string) => void;  // Auto-refinement notification
}

// ============================================================================
// WebSocket Client Class
// ============================================================================

/**
 * WebSocket client for real-time session updates using Socket.IO.
 *
 * Provides automatic reconnection, session subscription management,
 * and integration with Zustand stores.
 */
export class WebSocketClient {
  private socket: Socket | null = null;
  private url: string;
  private sessionId: string | null = null;
  private handlers: Map<string, Set<EventHandler>> = new Map();
  private statusHandlers: Set<(status: ConnectionStatus) => void> = new Set();
  private storeCallbacks: StoreCallbacks = {};
  private _status: ConnectionStatus = ConnectionStatus.Disconnected;
  private _streamingMessages: Map<string, string> = new Map();

  constructor(url: string = 'http://localhost:8000') {
    this.url = url;
  }

  /**
   * Get current connection status.
   */
  get status(): ConnectionStatus {
    return this._status;
  }

  /**
   * Get current session ID.
   */
  get currentSessionId(): string | null {
    return this.sessionId;
  }

  /**
   * Check if connected.
   */
  get isConnected(): boolean {
    return this._status === ConnectionStatus.Connected && this.socket?.connected === true;
  }

  /**
   * Set store callbacks for automatic state updates.
   */
  setStoreCallbacks(callbacks: StoreCallbacks): void {
    this.storeCallbacks = { ...this.storeCallbacks, ...callbacks };
  }

  /**
   * Connect to the Socket.IO server.
   */
  connect(sessionId?: string): void {
    if (this.socket?.connected) {
      // Already connected, just subscribe to session if needed
      if (sessionId && sessionId !== this.sessionId) {
        this.subscribeToSession(sessionId);
      }
      return;
    }

    this.setStatus(ConnectionStatus.Connecting);

    try {
      this.socket = io(this.url, {
        transports: ['websocket', 'polling'],
        autoConnect: true,
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        timeout: 20000,
      });

      this.setupEventListeners();

      // Connect and optionally join session
      if (sessionId) {
        this.socket.once('connected', () => {
          this.subscribeToSession(sessionId);
        });
      }
    } catch (error) {
      console.error('Failed to create Socket.IO connection:', error);
      this.setStatus(ConnectionStatus.Error);
    }
  }

  /**
   * Set up Socket.IO event listeners.
   */
  private setupEventListeners(): void {
    if (!this.socket) return;

    // Connection events
    this.socket.on('connect', () => {
      this.setStatus(ConnectionStatus.Connected);
      console.log('Socket.IO connected');

      // Re-subscribe to session on reconnect
      if (this.sessionId) {
        this.subscribeToSession(this.sessionId);
      }
    });

    this.socket.on('disconnect', (reason) => {
      this.setStatus(ConnectionStatus.Disconnected);
      console.log('Socket.IO disconnected:', reason);
    });

    this.socket.on('connect_error', (error) => {
      console.error('Socket.IO connection error:', error);
      this.setStatus(ConnectionStatus.Error);
    });

    this.socket.on('connected', (data: { sid: string; message: string }) => {
      console.log('Connected to ArchiFlow:', data.message);
    });

    // Session subscription events
    this.socket.on('subscribed', (data: { session_id: string; message: string }) => {
      console.log('Subscribed to session:', data.session_id);
      this.sessionId = data.session_id;
    });

    this.socket.on('unsubscribed', (data: { session_id: string }) => {
      console.log('Unsubscribed from session:', data.session_id);
      if (this.sessionId === data.session_id) {
        this.sessionId = null;
      }
    });

    // Message events
    this.socket.on('message', (event: AgentMessageEvent) => {
      console.log('[WebSocketClient] 📨 Received message event:', event);
      this.handleMessageEvent(event);
    });

    this.socket.on('message_chunk', (event: MessageChunkEvent) => {
      console.log('[WebSocketClient] 📝 Received message chunk:', {
        messageId: event.message_id,
        chunk: event.chunk.substring(0, 50) + '...',
        isComplete: event.is_complete,
      });
      this.handleMessageChunk(event);
    });

    // Agent events
    this.socket.on('agent_event', (event: AgentEventWrapper) => {
      console.log('[WebSocketClient] 🤖 Received agent event:', event.type, event);
      this.handleAgentEvent(event);
    });

    this.socket.on('agent_thinking', () => {
      console.log('[WebSocketClient] 💭 Agent thinking');
      this.storeCallbacks.onAgentThinking?.();
      this.dispatchToHandlers({ type: 'agent_thinking', session_id: this.sessionId ?? '' });
    });

    this.socket.on('agent_thought', (event: any) => {
      console.log('[WebSocketClient] 💭 Agent thought:', event);
      // Call both callbacks - one for the state, one for the actual content
      this.storeCallbacks.onAgentThinking?.();
      this.storeCallbacks.onAgentThought?.(event.content || '');
      this.dispatchToHandlers({ type: 'agent_thought', session_id: this.sessionId ?? '', ...event });
    });

    this.socket.on('agent_finished', (event: AgentFinishedEvent) => {
      console.log('[WebSocketClient] ✅ Agent finished:', event);
      this.storeCallbacks.onAgentFinished?.(event.reason);
      this.dispatchToHandlers(event);
    });

    this.socket.on('waiting_for_input', (event: WaitingForInputEvent) => {
      console.log('[WebSocketClient] ⏳ Waiting for input:', event);
      this.storeCallbacks.onWaitingForInput?.();
      this.dispatchToHandlers(event);
    });

    // Tool events (direct from backend)
    this.socket.on('tool_call', (event: any) => {
      console.log('[WebSocketClient] 🔧 Tool call:', event);
      // Call both callbacks - one for state, one for displaying
      this.storeCallbacks.onToolCall?.(
        event.tool_name as string,
        event.arguments as Record<string, unknown>,
      );
      this.storeCallbacks.onToolCallMessage?.(
        event.tool_name as string,
        event.arguments as Record<string, unknown>,
      );
      this.dispatchToHandlers({ type: 'tool_call', session_id: this.sessionId ?? '', ...event });
    });

    this.socket.on('tool_result', (event: any) => {
      console.log('[WebSocketClient] ✅ Tool result:', event);
      // Call both callbacks - one for state, one for displaying
      this.storeCallbacks.onToolResult?.(
        event.tool_name as string,
        event.result as string,
        event.status as string,
      );
      this.storeCallbacks.onToolResultMessage?.(
        event.tool_name as string,
        event.result as string,
        event.status as string,
      );
      this.dispatchToHandlers({ type: 'tool_result', session_id: this.sessionId ?? '', ...event });
    });

    // Workflow events
    this.socket.on('workflow_update', (event: WorkflowUpdateEvent) => {
      console.log('[WebSocketClient] 🔄 Workflow update:', event);
      this.storeCallbacks.onWorkflowUpdate?.(event);
      this.dispatchToHandlers(event);
    });

    // Artifact events
    this.socket.on('artifact_update', (event: ArtifactUpdateEvent) => {
      console.log('[WebSocketClient] 📄 Artifact update:', event);
      this.storeCallbacks.onArtifactUpdate?.(event.artifact_path, event.action);
      this.dispatchToHandlers(event);
    });

    // Session events
    this.socket.on('session_update', (event: SessionUpdateEvent) => {
      console.log('[WebSocketClient] 📋 Session update:', event);
      const status = event.payload?.status ?? event.status;
      if (status) {
        this.storeCallbacks.onSessionUpdate?.(status);
      }
      this.dispatchToHandlers(event);
    });

    // Refinement events
    this.socket.on('refinement_applied', (event: any) => {
      console.log('[WebSocketClient] 📝 Refinement applied:', event);
      this.storeCallbacks.onRefinementApplied?.(event.content || '');
      this.dispatchToHandlers({ type: 'refinement_applied', session_id: this.sessionId ?? '', ...event });
    });

    // Error events
    this.socket.on('error', (event: ErrorEvent | { message: string }) => {
      console.error('[WebSocketClient] ❌ Error event:', event);
      const errorEvent = event as ErrorEvent;
      this.storeCallbacks.onError?.(errorEvent.message, errorEvent.code);
      this.dispatchToHandlers({ type: 'error', ...event } as ErrorEvent);
    });

    // Ping/pong for keep-alive
    this.socket.on('pong', () => {
      // Heartbeat received
    });
  }

  /**
   * Handle message events and update stores.
   */
  private handleMessageEvent(event: AgentMessageEvent): void {
    if (event.message) {
      this.storeCallbacks.onMessage?.(event.message);
    } else if (event.content) {
      this.storeCallbacks.onMessage?.({
        id: `msg_${event.sequence ?? Date.now()}`,
        role: 'assistant',
        content: event.content,
        sequence: event.sequence,
      });
    }
    this.dispatchToHandlers(event);
  }

  /**
   * Handle streaming message chunks.
   */
  private handleMessageChunk(event: MessageChunkEvent): void {
    const currentContent = this._streamingMessages.get(event.message_id) ?? '';
    const newContent = currentContent + event.chunk;
    this._streamingMessages.set(event.message_id, newContent);

    this.storeCallbacks.onMessageChunk?.(event.message_id, event.chunk, event.is_complete);

    if (event.is_complete) {
      this._streamingMessages.delete(event.message_id);
    }

    this.dispatchToHandlers(event);
  }

  /**
   * Handle agent events wrapper.
   */
  private handleAgentEvent(event: AgentEventWrapper): void {
    const innerType = event.type;

    if (innerType === 'agent_tool_call') {
      const payload = event.payload;
      this.storeCallbacks.onToolCall?.(
        payload.tool_name as string,
        payload.arguments as Record<string, unknown>,
      );
    } else if (innerType === 'agent_tool_result') {
      const payload = event.payload;
      this.storeCallbacks.onToolResult?.(
        payload.tool_name as string,
        payload.result as string,
        payload.status as string,
      );
    } else if (innerType === 'agent_thinking') {
      this.storeCallbacks.onAgentThinking?.();
    }

    this.dispatchToHandlers(event);
  }

  /**
   * Dispatch event to registered handlers.
   */
  private dispatchToHandlers(event: WebSocketEventType): void {
    const handlers = this.handlers.get(event.type);
    if (handlers) {
      handlers.forEach((handler) => handler(event));
    }

    // Also call wildcard handlers
    const allHandlers = this.handlers.get('*');
    if (allHandlers) {
      allHandlers.forEach((handler) => handler(event));
    }
  }

  /**
   * Disconnect from the Socket.IO server.
   */
  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    this.sessionId = null;
    this._streamingMessages.clear();
    this.setStatus(ConnectionStatus.Disconnected);
  }

  /**
   * Subscribe to a session's updates.
   */
  subscribeToSession(sessionId: string): void {
    if (!this.socket?.connected) {
      console.warn('Socket not connected, cannot subscribe to session');
      return;
    }

    // Unsubscribe from current session first
    if (this.sessionId && this.sessionId !== sessionId) {
      this.unsubscribeFromSession();
    }

    this.socket.emit('subscribe_session', { session_id: sessionId });
  }

  /**
   * Unsubscribe from the current session.
   */
  unsubscribeFromSession(): void {
    if (!this.socket?.connected || !this.sessionId) {
      return;
    }

    this.socket.emit('unsubscribe_session', { session_id: this.sessionId });
    this.sessionId = null;
    this._streamingMessages.clear();
  }

  /**
   * Send a chat message to the current session.
   */
  sendMessage(content: string): void {
    console.log('[WebSocketClient] 📤 sendMessage called:', {
      content,
      sessionId: this.sessionId,
      socketConnected: this.socket?.connected,
      socketId: this.socket?.id,
    });

    if (!this.socket?.connected) {
      console.error('[WebSocketClient] ❌ Socket not connected, cannot send message');
      return;
    }

    if (!this.sessionId) {
      console.error('[WebSocketClient] ❌ No session subscribed, cannot send message');
      return;
    }

    const payload = {
      type: 'message',
      content: content,
      session_id: this.sessionId,
    };

    console.log('[WebSocketClient] 🔄 Emitting to Socket.IO:', {
      event: 'message',
      payload,
    });

    // Use 'message' event type to match backend expectations
    this.socket.emit('message', payload);

    console.log('[WebSocketClient] ✅ Message emitted successfully');
  }

  /**
   * Send a ping to check connection.
   */
  ping(): void {
    if (this.socket?.connected) {
      this.socket.emit('ping', { timestamp: Date.now() });
    }
  }

  /**
   * Register an event handler.
   */
  on<T extends WebSocketEventType>(eventType: T['type'] | '*', handler: EventHandler<T>): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(handler as EventHandler);

    // Return unsubscribe function
    return () => {
      this.handlers.get(eventType)?.delete(handler as EventHandler);
    };
  }

  /**
   * Register a one-time event handler.
   */
  once<T extends WebSocketEventType>(eventType: T['type'], handler: EventHandler<T>): void {
    const wrappedHandler: EventHandler = (event) => {
      handler(event as T);
      this.handlers.get(eventType)?.delete(wrappedHandler);
    };

    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(wrappedHandler);
  }

  /**
   * Register a connection status handler.
   */
  onStatusChange(handler: (status: ConnectionStatus) => void): () => void {
    this.statusHandlers.add(handler);
    // Immediately call with current status
    handler(this._status);
    return () => {
      this.statusHandlers.delete(handler);
    };
  }

  /**
   * Set connection status and notify handlers.
   */
  private setStatus(status: ConnectionStatus): void {
    this._status = status;
    this.statusHandlers.forEach((handler) => handler(status));
  }
}

// ============================================================================
// Singleton instance
// ============================================================================

let _instance: WebSocketClient | null = null;

/**
 * Get the WebSocket client singleton.
 */
export function getWebSocketClient(): WebSocketClient {
  if (!_instance) {
    const wsUrl = import.meta.env.VITE_WS_URL || 'http://localhost:8000';
    _instance = new WebSocketClient(wsUrl);
  }
  return _instance;
}

/**
 * Initialize and connect the WebSocket client.
 */
export function initWebSocket(sessionId?: string): WebSocketClient {
  const client = getWebSocketClient();
  client.connect(sessionId);
  return client;
}

/**
 * Disconnect and cleanup the WebSocket client.
 */
export function disconnectWebSocket(): void {
  if (_instance) {
    _instance.disconnect();
  }
}

/**
 * Reset the singleton instance (for testing).
 */
export function resetWebSocketClient(): void {
  if (_instance) {
    _instance.disconnect();
    _instance = null;
  }
}

/**
 * WebSocket client for real-time communication.
 *
 * Uses Socket.IO protocol for communication with the backend.
 */

// ============================================================================
// Types
// ============================================================================

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface WebSocketEvent {
  type: string;
  session_id?: string;
  data?: unknown;
  timestamp?: string;
}

export interface AgentMessageEvent {
  type: 'agent_message';
  session_id: string;
  content: string;
  phase?: string;
  is_streaming?: boolean;
}

export interface ToolCallEvent {
  type: 'tool_call';
  session_id: string;
  tool_name: string;
  parameters: Record<string, unknown>;
}

export interface ToolResultEvent {
  type: 'tool_result';
  session_id: string;
  tool_name: string;
  result?: string;
  error?: string;
}

export interface WorkflowUpdateEvent {
  type: 'workflow_update';
  session_id: string;
  phase_id: string;
  status: string;
  current_phase?: string;
}

export interface ArtifactUpdateEvent {
  type: 'artifact_update';
  session_id: string;
  action: 'created' | 'updated' | 'deleted';
  path: string;
  artifact?: {
    name: string;
    path: string;
    is_directory: boolean;
    size?: number;
    mime_type?: string;
  };
}

export interface SessionStatusEvent {
  type: 'session_status';
  session_id: string;
  status: string;
}

export interface ErrorEvent {
  type: 'error';
  session_id?: string;
  message: string;
  code?: string;
}

export type WebSocketEventType =
  | AgentMessageEvent
  | ToolCallEvent
  | ToolResultEvent
  | WorkflowUpdateEvent
  | ArtifactUpdateEvent
  | SessionStatusEvent
  | ErrorEvent;

export type EventHandler<T = WebSocketEventType> = (event: T) => void;

// ============================================================================
// WebSocket Client Class
// ============================================================================

/**
 * WebSocket client for real-time session updates.
 *
 * Note: This is a simplified implementation without Socket.IO.
 * For production, you would use the socket.io-client package.
 */
export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private sessionId: string | null = null;
  private handlers: Map<string, Set<EventHandler>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private statusHandlers: Set<(status: ConnectionStatus) => void> = new Set();
  private _status: ConnectionStatus = 'disconnected';

  constructor(url: string = 'ws://localhost:8000/ws') {
    this.url = url;
  }

  /**
   * Get current connection status.
   */
  get status(): ConnectionStatus {
    return this._status;
  }

  /**
   * Connect to the WebSocket server.
   */
  connect(sessionId?: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      // Already connected, just join session if needed
      if (sessionId) {
        this.joinSession(sessionId);
      }
      return;
    }

    this.setStatus('connecting');

    try {
      const wsUrl = sessionId ? `${this.url}?session_id=${sessionId}` : this.url;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.setStatus('connected');
        this.reconnectAttempts = 0;
        if (sessionId) {
          this.sessionId = sessionId;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WebSocketEventType;
          this.handleEvent(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onclose = () => {
        this.setStatus('disconnected');
        this.attemptReconnect();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.setStatus('error');
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.setStatus('error');
    }
  }

  /**
   * Disconnect from the WebSocket server.
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.sessionId = null;
    this.setStatus('disconnected');
  }

  /**
   * Join a session room.
   */
  joinSession(sessionId: string): void {
    this.sessionId = sessionId;
    this.send({ type: 'join', session_id: sessionId });
  }

  /**
   * Leave the current session room.
   */
  leaveSession(): void {
    if (this.sessionId) {
      this.send({ type: 'leave', session_id: this.sessionId });
      this.sessionId = null;
    }
  }

  /**
   * Send a message to the server.
   */
  send(data: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn('WebSocket not connected, cannot send message');
    }
  }

  /**
   * Send a chat message.
   */
  sendMessage(content: string): void {
    if (!this.sessionId) {
      console.error('No session joined, cannot send message');
      return;
    }

    this.send({
      type: 'user_message',
      session_id: this.sessionId,
      content,
    });
  }

  /**
   * Register an event handler.
   */
  on<T extends WebSocketEventType>(eventType: T['type'], handler: EventHandler<T>): () => void {
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
   * Handle incoming events.
   */
  private handleEvent(event: WebSocketEventType): void {
    const handlers = this.handlers.get(event.type);
    if (handlers) {
      handlers.forEach((handler) => handler(event));
    }

    // Also call 'all' handlers
    const allHandlers = this.handlers.get('*');
    if (allHandlers) {
      allHandlers.forEach((handler) => handler(event));
    }
  }

  /**
   * Set connection status and notify handlers.
   */
  private setStatus(status: ConnectionStatus): void {
    this._status = status;
    this.statusHandlers.forEach((handler) => handler(status));
  }

  /**
   * Attempt to reconnect with exponential backoff.
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);

    setTimeout(() => {
      this.connect(this.sessionId ?? undefined);
    }, delay);
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
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
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

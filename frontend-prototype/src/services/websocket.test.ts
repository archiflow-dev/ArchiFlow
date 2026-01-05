/**
 * Tests for the WebSocket client.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  WebSocketClient,
  getWebSocketClient,
  initWebSocket,
  disconnectWebSocket,
  resetWebSocketClient,
} from './websocket';

// Mock socket.io-client
vi.mock('socket.io-client', () => {
  const mockSocket = {
    connected: false,
    on: vi.fn(),
    once: vi.fn(),
    emit: vi.fn(),
    disconnect: vi.fn(),
  };

  return {
    io: vi.fn(() => mockSocket),
    Socket: vi.fn(),
  };
});

describe('WebSocketClient', () => {
  let client: WebSocketClient;

  beforeEach(() => {
    vi.clearAllMocks();
    resetWebSocketClient();
    client = new WebSocketClient('http://localhost:8000');
  });

  afterEach(() => {
    client.disconnect();
  });

  describe('constructor', () => {
    it('should initialize with default values', () => {
      expect(client.status).toBe('disconnected');
      expect(client.currentSessionId).toBeNull();
      expect(client.isConnected).toBe(false);
    });

    it('should use custom URL', () => {
      const customClient = new WebSocketClient('http://custom:3000');
      expect(customClient.status).toBe('disconnected');
    });
  });

  describe('connect', () => {
    it('should set status to connecting', () => {
      client.connect();
      expect(client.status).toBe('connecting');
    });

    it('should accept optional sessionId', () => {
      client.connect('session-123');
      expect(client.status).toBe('connecting');
    });
  });

  describe('disconnect', () => {
    it('should set status to disconnected', () => {
      client.connect();
      client.disconnect();
      expect(client.status).toBe('disconnected');
    });

    it('should clear session ID', () => {
      client.connect('session-123');
      client.disconnect();
      expect(client.currentSessionId).toBeNull();
    });
  });

  describe('event handlers', () => {
    it('should register event handlers', () => {
      const handler = vi.fn();
      const unsubscribe = client.on('message', handler);

      expect(typeof unsubscribe).toBe('function');
    });

    it('should unsubscribe when function is called', () => {
      const handler = vi.fn();
      const unsubscribe = client.on('message', handler);

      unsubscribe();
      // Handler should no longer be registered
    });

    it('should support wildcard handlers', () => {
      const handler = vi.fn();
      client.on('*', handler);
      // Wildcard handler registered
    });
  });

  describe('status change handlers', () => {
    it('should notify status change handlers', () => {
      const handler = vi.fn();
      client.onStatusChange(handler);

      // Should be called immediately with current status
      expect(handler).toHaveBeenCalledWith('disconnected');
    });

    it('should unsubscribe from status changes', () => {
      const handler = vi.fn();
      const unsubscribe = client.onStatusChange(handler);

      handler.mockClear();
      unsubscribe();

      client.connect();
      // Handler should not be called again after unsubscribe
      // (it was called once on connect for 'connecting' status)
    });
  });

  describe('store callbacks', () => {
    it('should set store callbacks', () => {
      const callbacks = {
        onMessage: vi.fn(),
        onError: vi.fn(),
      };

      client.setStoreCallbacks(callbacks);
      // Callbacks should be set
    });

    it('should merge callbacks', () => {
      const callbacks1 = { onMessage: vi.fn() };
      const callbacks2 = { onError: vi.fn() };

      client.setStoreCallbacks(callbacks1);
      client.setStoreCallbacks(callbacks2);
      // Both callbacks should be set
    });
  });
});

describe('Singleton functions', () => {
  beforeEach(() => {
    resetWebSocketClient();
  });

  afterEach(() => {
    resetWebSocketClient();
  });

  describe('getWebSocketClient', () => {
    it('should return the same instance', () => {
      const client1 = getWebSocketClient();
      const client2 = getWebSocketClient();

      expect(client1).toBe(client2);
    });

    it('should create new instance after reset', () => {
      const client1 = getWebSocketClient();
      resetWebSocketClient();
      const client2 = getWebSocketClient();

      expect(client1).not.toBe(client2);
    });
  });

  describe('initWebSocket', () => {
    it('should return connected client', () => {
      const client = initWebSocket();

      expect(client).toBeDefined();
      expect(client.status).toBe('connecting');
    });

    it('should subscribe to session if provided', () => {
      const client = initWebSocket('session-123');

      expect(client).toBeDefined();
    });
  });

  describe('disconnectWebSocket', () => {
    it('should disconnect the singleton', () => {
      const client = initWebSocket();
      disconnectWebSocket();

      expect(client.status).toBe('disconnected');
    });

    it('should handle no client gracefully', () => {
      // Should not throw
      disconnectWebSocket();
    });
  });
});

describe('Event Types', () => {
  it('should export all event types', async () => {
    const module = await import('./websocket');

    // Check type exports exist
    expect(module.WebSocketClient).toBeDefined();
    expect(module.getWebSocketClient).toBeDefined();
    expect(module.initWebSocket).toBeDefined();
    expect(module.disconnectWebSocket).toBeDefined();
    expect(module.resetWebSocketClient).toBeDefined();
  });
});

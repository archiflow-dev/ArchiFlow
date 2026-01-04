/**
 * Tests for the Session API client.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { sessionApi } from './sessionApi';
import { api } from './api';

// Mock the api module
vi.mock('./api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('Session API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('createSession', () => {
    it('should create a new session', async () => {
      const mockResponse = {
        id: 'session-123',
        agent_type: 'coding',
        user_prompt: 'Build a web app',
        status: 'created',
        created_at: '2025-01-04T00:00:00Z',
        updated_at: '2025-01-04T00:00:00Z',
      };

      vi.mocked(api.post).mockResolvedValueOnce(mockResponse);

      const result = await sessionApi.create({
        agent_type: 'coding',
        user_prompt: 'Build a web app',
      });

      expect(api.post).toHaveBeenCalledWith('/sessions/', {
        agent_type: 'coding',
        user_prompt: 'Build a web app',
      });
      expect(result).toEqual(mockResponse);
    });

    it('should include project directory if provided', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({});

      await sessionApi.create({
        agent_type: 'coding',
        user_prompt: 'Build a web app',
        project_directory: '/path/to/project',
      });

      expect(api.post).toHaveBeenCalledWith('/sessions/', {
        agent_type: 'coding',
        user_prompt: 'Build a web app',
        project_directory: '/path/to/project',
      });
    });
  });

  describe('getSession', () => {
    it('should get a session by ID', async () => {
      const mockSession = {
        id: 'session-123',
        agent_type: 'coding',
        status: 'running',
      };

      vi.mocked(api.get).mockResolvedValueOnce(mockSession);

      const result = await sessionApi.get('session-123');

      expect(api.get).toHaveBeenCalledWith('/sessions/session-123');
      expect(result).toEqual(mockSession);
    });
  });

  describe('listSessions', () => {
    it('should list sessions without filters', async () => {
      const mockResponse = {
        sessions: [],
        total: 0,
        page: 1,
        page_size: 20,
        has_more: false,
      };

      vi.mocked(api.get).mockResolvedValueOnce(mockResponse);

      const result = await sessionApi.list();

      expect(api.get).toHaveBeenCalledWith('/sessions/', { params: {} });
      expect(result).toEqual(mockResponse);
    });

    it('should list sessions with filters', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({ sessions: [], total: 0 });

      await sessionApi.list({
        status: 'running',
        agent_type: 'coding',
        page: 2,
        page_size: 10,
      });

      expect(api.get).toHaveBeenCalledWith('/sessions/', {
        params: {
          status: 'running',
          agent_type: 'coding',
          page: 2,
          page_size: 10,
        },
      });
    });
  });

  describe('updateSession', () => {
    it('should update a session', async () => {
      vi.mocked(api.patch).mockResolvedValueOnce({ id: 'session-123', status: 'paused' });

      await sessionApi.update('session-123', { status: 'paused' });

      expect(api.patch).toHaveBeenCalledWith('/sessions/session-123', { status: 'paused' });
    });
  });

  describe('deleteSession', () => {
    it('should delete a session', async () => {
      vi.mocked(api.delete).mockResolvedValueOnce(undefined);

      await sessionApi.delete('session-123');

      expect(api.delete).toHaveBeenCalledWith('/sessions/session-123');
    });
  });

  describe('Session control', () => {
    it('should start a session', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({ id: 'session-123', status: 'running' });

      await sessionApi.start('session-123');

      expect(api.post).toHaveBeenCalledWith('/sessions/session-123/start');
    });

    it('should pause a session', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({ id: 'session-123', status: 'paused' });

      await sessionApi.pause('session-123');

      expect(api.post).toHaveBeenCalledWith('/sessions/session-123/pause');
    });

    it('should resume a session', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({ id: 'session-123', status: 'running' });

      await sessionApi.resume('session-123');

      expect(api.post).toHaveBeenCalledWith('/sessions/session-123/resume');
    });
  });
});

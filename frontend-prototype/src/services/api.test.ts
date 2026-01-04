/**
 * Tests for the base API client.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api, ApiError, API_BASE } from './api';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('API Client', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('api.get', () => {
    it('should make a GET request to the correct URL', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ data: 'test' }),
      });

      const result = await api.get('/test');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/test'),
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        }),
      );
      expect(result).toEqual({ data: 'test' });
    });

    it('should include query parameters', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({}),
      });

      await api.get('/test', { params: { page: 1, limit: 10 } });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringMatching(/page=1/),
        expect.any(Object),
      );
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringMatching(/limit=10/),
        expect.any(Object),
      );
    });
  });

  describe('api.post', () => {
    it('should make a POST request with JSON body', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ id: 'new-id' }),
      });

      const result = await api.post('/items', { name: 'test' });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/items'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ name: 'test' }),
        }),
      );
      expect(result).toEqual({ id: 'new-id' });
    });
  });

  describe('api.put', () => {
    it('should make a PUT request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ updated: true }),
      });

      await api.put('/items/1', { name: 'updated' });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/items/1'),
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ name: 'updated' }),
        }),
      );
    });
  });

  describe('api.patch', () => {
    it('should make a PATCH request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ patched: true }),
      });

      await api.patch('/items/1', { status: 'active' });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/items/1'),
        expect.objectContaining({
          method: 'PATCH',
        }),
      );
    });
  });

  describe('api.delete', () => {
    it('should make a DELETE request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
        headers: new Headers(),
      });

      await api.delete('/items/1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/items/1'),
        expect.objectContaining({
          method: 'DELETE',
        }),
      );
    });
  });

  describe('Error handling', () => {
    it('should throw ApiError for 404 responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ detail: 'Item not found' }),
      });

      try {
        await api.get('/items/999');
        // Should not reach here
        expect(true).toBe(false);
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        expect((error as ApiError).status).toBe(404);
        expect((error as ApiError).message).toBe('Item not found');
      }
    });

    it('should throw ApiError for 500 responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ detail: 'Server error' }),
      });

      await expect(api.get('/items')).rejects.toThrow(ApiError);
    });

    it('should handle network errors', async () => {
      mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

      await expect(api.get('/items')).rejects.toThrow(ApiError);

      try {
        await api.get('/items');
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        expect((error as ApiError).status).toBe(0);
        expect((error as ApiError).message).toContain('Network error');
      }
    });
  });

  describe('ApiError', () => {
    it('should correctly identify client errors', () => {
      const error = new ApiError(404, 'Not found');
      expect(error.isClientError()).toBe(true);
      expect(error.isServerError()).toBe(false);
      expect(error.is(404)).toBe(true);
      expect(error.is(500)).toBe(false);
    });

    it('should correctly identify server errors', () => {
      const error = new ApiError(500, 'Internal error');
      expect(error.isClientError()).toBe(false);
      expect(error.isServerError()).toBe(true);
    });
  });
});

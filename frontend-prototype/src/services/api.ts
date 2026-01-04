/**
 * Base API client for ArchiFlow web backend.
 *
 * Provides type-safe HTTP methods with error handling.
 */

// API base URL - configurable via environment
export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

/**
 * Custom error class for API errors.
 */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly details?: unknown,
    public readonly code?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }

  /**
   * Check if error is a specific status code.
   */
  is(status: number): boolean {
    return this.status === status;
  }

  /**
   * Check if error is a client error (4xx).
   */
  isClientError(): boolean {
    return this.status >= 400 && this.status < 500;
  }

  /**
   * Check if error is a server error (5xx).
   */
  isServerError(): boolean {
    return this.status >= 500;
  }
}

/**
 * Request options extending standard RequestInit.
 */
export interface RequestOptions extends Omit<RequestInit, 'body'> {
  /** Request body (will be JSON stringified) */
  body?: unknown;
  /** Query parameters */
  params?: Record<string, string | number | boolean | undefined>;
  /** Custom timeout in ms (default: 30000) */
  timeout?: number;
}

/**
 * Build URL with query parameters.
 */
function buildUrl(endpoint: string, params?: RequestOptions['params']): string {
  const url = new URL(endpoint, API_BASE);

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    });
  }

  return url.toString();
}

/**
 * Make an HTTP request to the API.
 */
async function request<T>(
  endpoint: string,
  options: RequestOptions = {},
): Promise<T> {
  const { params, timeout = 30000, body, ...fetchOptions } = options;

  const url = buildUrl(endpoint, params);

  // Create abort controller for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      headers: {
        'Content-Type': 'application/json',
        ...fetchOptions.headers,
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // Handle no-content responses
    if (response.status === 204) {
      return undefined as T;
    }

    // Parse response body
    let data: unknown;
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    // Handle error responses
    if (!response.ok) {
      const errorDetail = typeof data === 'object' && data !== null
        ? (data as { detail?: string; message?: string; code?: string })
        : { detail: String(data) };

      throw new ApiError(
        response.status,
        errorDetail.detail || errorDetail.message || `Request failed: ${response.statusText}`,
        data,
        errorDetail.code,
      );
    }

    return data as T;
  } catch (error) {
    clearTimeout(timeoutId);

    // Re-throw ApiError as-is
    if (error instanceof ApiError) {
      throw error;
    }

    // Handle abort/timeout
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(408, `Request timeout after ${timeout}ms`);
    }

    // Handle network errors
    if (error instanceof TypeError) {
      throw new ApiError(0, 'Network error: Unable to reach server', { originalError: error.message });
    }

    // Unknown error
    throw new ApiError(500, 'Unexpected error', { originalError: String(error) });
  }
}

/**
 * API client with typed methods.
 */
export const api = {
  /**
   * GET request.
   */
  get<T>(endpoint: string, options?: Omit<RequestOptions, 'body' | 'method'>): Promise<T> {
    return request<T>(endpoint, { ...options, method: 'GET' });
  },

  /**
   * POST request.
   */
  post<T>(endpoint: string, body?: unknown, options?: Omit<RequestOptions, 'body' | 'method'>): Promise<T> {
    return request<T>(endpoint, { ...options, method: 'POST', body });
  },

  /**
   * PUT request.
   */
  put<T>(endpoint: string, body?: unknown, options?: Omit<RequestOptions, 'body' | 'method'>): Promise<T> {
    return request<T>(endpoint, { ...options, method: 'PUT', body });
  },

  /**
   * PATCH request.
   */
  patch<T>(endpoint: string, body?: unknown, options?: Omit<RequestOptions, 'body' | 'method'>): Promise<T> {
    return request<T>(endpoint, { ...options, method: 'PATCH', body });
  },

  /**
   * DELETE request.
   */
  delete<T>(endpoint: string, options?: Omit<RequestOptions, 'body' | 'method'>): Promise<T> {
    return request<T>(endpoint, { ...options, method: 'DELETE' });
  },
};

/**
 * Helper to build download URL for artifacts.
 */
export function getDownloadUrl(sessionId: string, path: string): string {
  return `${API_BASE}/sessions/${sessionId}/artifacts/${path}/download`;
}

/**
 * Helper to check if API is reachable.
 */
export async function checkApiHealth(): Promise<boolean> {
  try {
    await api.get('/health', { timeout: 5000 });
    return true;
  } catch {
    return false;
  }
}

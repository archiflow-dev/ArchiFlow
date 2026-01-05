/**
 * Session API client.
 *
 * Handles session CRUD operations.
 */

import { api } from './api';
import type { AgentType } from '../types';

// ============================================================================
// Types
// ============================================================================

export type SessionStatusApi = 'created' | 'running' | 'paused' | 'completed' | 'failed';

export interface SessionCreateRequest {
  agent_type: AgentType;
  user_prompt?: string;  // Optional - can send first message via chat
  project_directory?: string;
}

export interface SessionUpdateRequest {
  status?: SessionStatusApi;
}

export interface SessionResponse {
  id: string;
  agent_type: AgentType;
  user_prompt: string;
  project_directory?: string;
  status: SessionStatusApi;
  workflow_state?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SessionListResponse {
  sessions: SessionResponse[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface SessionListParams {
  status?: SessionStatusApi;
  agent_type?: string;
  page?: number;
  page_size?: number;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Create a new session.
 */
export async function createSession(data: SessionCreateRequest): Promise<SessionResponse> {
  return api.post<SessionResponse>('sessions/', data);
}

/**
 * Get a session by ID.
 */
export async function getSession(sessionId: string): Promise<SessionResponse> {
  return api.get<SessionResponse>(`sessions/${sessionId}`);
}

/**
 * List sessions with optional filtering.
 */
export async function listSessions(params: SessionListParams = {}): Promise<SessionListResponse> {
  return api.get<SessionListResponse>('sessions/', { params });
}

/**
 * Update a session.
 */
export async function updateSession(
  sessionId: string,
  data: SessionUpdateRequest,
): Promise<SessionResponse> {
  return api.patch<SessionResponse>(`sessions/${sessionId}`, data);
}

/**
 * Delete a session.
 */
export async function deleteSession(sessionId: string): Promise<void> {
  return api.delete<void>(`sessions/${sessionId}`);
}

/**
 * Start a session's agent.
 */
export async function startSession(sessionId: string): Promise<SessionResponse> {
  return api.post<SessionResponse>(`sessions/${sessionId}/start`);
}

/**
 * Pause a running session.
 */
export async function pauseSession(sessionId: string): Promise<SessionResponse> {
  return api.post<SessionResponse>(`sessions/${sessionId}/pause`);
}

/**
 * Resume a paused session.
 */
export async function resumeSession(sessionId: string): Promise<SessionResponse> {
  return api.post<SessionResponse>(`sessions/${sessionId}/resume`);
}

// ============================================================================
// Namespace export
// ============================================================================

export const sessionApi = {
  create: createSession,
  get: getSession,
  list: listSessions,
  update: updateSession,
  delete: deleteSession,
  start: startSession,
  pause: pauseSession,
  resume: resumeSession,
};

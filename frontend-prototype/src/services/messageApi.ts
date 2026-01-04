/**
 * Message API client.
 *
 * Handles chat message operations for sessions.
 */

import { api } from './api';

// ============================================================================
// Types
// ============================================================================

export type MessageRoleApi = 'user' | 'assistant' | 'system';

export interface MessageResponse {
  id: string;
  session_id: string;
  role: MessageRoleApi;
  content: string;
  sequence: number;
  tool_calls?: ToolCallInfo[];
  created_at: string;
}

export interface ToolCallInfo {
  id: string;
  name: string;
  parameters: Record<string, unknown>;
  result?: string;
  error?: string;
}

export interface MessageListResponse {
  messages: MessageResponse[];
  total: number;
  session_id: string;
}

export interface MessageCreateRequest {
  role: MessageRoleApi;
  content: string;
}

export interface MessageListParams {
  limit?: number;
  offset?: number;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * List messages in a session.
 */
export async function listMessages(
  sessionId: string,
  params: MessageListParams = {},
): Promise<MessageListResponse> {
  return api.get<MessageListResponse>(`/sessions/${sessionId}/messages/`, { params });
}

/**
 * Send a message to a session.
 */
export async function sendMessage(
  sessionId: string,
  content: string,
  role: MessageRoleApi = 'user',
): Promise<MessageResponse> {
  return api.post<MessageResponse>(`/sessions/${sessionId}/messages/`, {
    role,
    content,
  });
}

/**
 * Get a specific message.
 */
export async function getMessage(
  sessionId: string,
  messageId: string,
): Promise<MessageResponse> {
  return api.get<MessageResponse>(`/sessions/${sessionId}/messages/${messageId}`);
}

// ============================================================================
// Namespace export
// ============================================================================

export const messageApi = {
  list: listMessages,
  send: sendMessage,
  get: getMessage,
};

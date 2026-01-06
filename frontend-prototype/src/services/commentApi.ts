/**
 * Comment API client.
 *
 * Handles document comment CRUD operations and agent submission.
 */

import { api } from './api';

// ============================================================================
// Types
// ============================================================================

/**
 * Status of a comment.
 */
export type CommentStatus = 'pending' | 'resolved' | 'applied' | 'submitted';

/**
 * A comment on a document.
 */
export interface Comment {
  id: string;
  session_id: string;
  file_path: string;
  line_number: number;
  selected_text: string;
  comment_text: string;
  author: string;
  status: CommentStatus;
  created_at: string;
  updated_at: string;
}

/**
 * Request data for creating a comment.
 */
export interface CommentCreate {
  file_path: string;
  line_number: number;
  selected_text?: string;
  comment_text: string;
  author?: string;
}

/**
 * Request data for updating a comment.
 */
export interface CommentUpdate {
  comment_text?: string;
  status?: CommentStatus;
}

/**
 * Response from listing comments.
 */
export interface CommentListResponse {
  comments: Comment[];
  total_count: number;
  file_path?: string;
}

/**
 * Request data for submitting comments to agent.
 */
export interface CommentSubmissionRequest {
  file_path?: string | null;
  prompt_override?: string | null;
}

/**
 * Response from submitting comments to agent.
 */
export interface CommentSubmissionResponse {
  submitted_count: number;
  comment_ids: string[];
  message: string;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * List all comments for a session.
 */
export async function listComments(
  sessionId: string,
  options?: {
    file_path?: string;
    status?: CommentStatus;
  }
): Promise<CommentListResponse> {
  const params = new URLSearchParams();
  if (options?.file_path) params.append('file_path', options.file_path);
  if (options?.status) params.append('status', options.status);

  const queryString = params.toString();
  const url = `/api/sessions/${sessionId}/comments${queryString ? `?${queryString}` : ''}`;

  const response = await api.get(url);
  return response as CommentListResponse;
}

/**
 * List comments for a specific file.
 */
export async function listFileComments(
  sessionId: string,
  filePath: string,
  options?: {
    status?: CommentStatus;
  }
): Promise<CommentListResponse> {
  const params = new URLSearchParams();
  if (options?.status) params.append('status', options.status);

  const queryString = params.toString();
  const url = `/api/sessions/${sessionId}/files/${filePath}/comments${queryString ? `?${queryString}` : ''}`;

  const response = await api.get(url);
  return response as CommentListResponse;
}

/**
 * Get a specific comment by ID.
 */
export async function getComment(
  commentId: string,
  sessionId: string
): Promise<Comment> {
  const response = await api.get(`/api/comments/${commentId}?session_id=${sessionId}`);
  return response as Comment;
}

/**
 * Create a new comment.
 */
export async function createComment(
  sessionId: string,
  data: CommentCreate
): Promise<Comment> {
  const response = await api.post(`/api/sessions/${sessionId}/comments`, data);
  return response as Comment;
}

/**
 * Update a comment.
 */
export async function updateComment(
  commentId: string,
  sessionId: string,
  data: CommentUpdate
): Promise<Comment> {
  const response = await api.put(
    `/api/comments/${commentId}?session_id=${sessionId}`,
    data
  );
  return response as Comment;
}

/**
 * Resolve a comment (mark as resolved).
 */
export async function resolveComment(
  commentId: string,
  sessionId: string
): Promise<Comment> {
  const response = await api.post(
    `/api/comments/${commentId}/resolve?session_id=${sessionId}`
  );
  return response as Comment;
}

/**
 * Delete a comment.
 */
export async function deleteComment(
  commentId: string,
  sessionId: string
): Promise<void> {
  await api.delete(`/api/comments/${commentId}?session_id=${sessionId}`);
}

/**
 * Get pending comments for a session.
 */
export async function getPendingComments(
  sessionId: string,
  options?: {
    file_path?: string;
  }
): Promise<CommentListResponse> {
  const params = new URLSearchParams();
  if (options?.file_path) params.append('file_path', options.file_path);

  const queryString = params.toString();
  const url = `/api/sessions/${sessionId}/comments/pending${queryString ? `?${queryString}` : ''}`;

  const response = await api.get(url);
  return response as CommentListResponse;
}

/**
 * Submit pending comments to the agent.
 */
export async function submitCommentsToAgent(
  sessionId: string,
  request?: CommentSubmissionRequest
): Promise<CommentSubmissionResponse> {
  const response = await api.post(
    `/api/sessions/${sessionId}/comments/submit-to-agent`,
    request || { file_path: null, prompt_override: null }
  );
  return response as CommentSubmissionResponse;
}

// ============================================================================
// API Object (for convenience)
// ============================================================================

export const commentApi = {
  listComments,
  listFileComments,
  getComment,
  createComment,
  updateComment,
  resolveComment,
  deleteComment,
  getPendingComments,
  submitCommentsToAgent,
};

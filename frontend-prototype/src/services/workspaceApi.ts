/**
 * Workspace API client.
 *
 * Handles file operations within agent workspace directories.
 */

import { api } from './api';

// ============================================================================
// Types
// ============================================================================

export interface FileInfo {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size: number;
  extension?: string;
  modified_time?: number;
}

export interface FileListResponse {
  files: FileInfo[];
  total_count: number;
}

export interface FileContent {
  path: string;
  content: string;
  encoding: string;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * List files in a session's workspace directory.
 *
 * Note: The backend always filters out .archiflow/ audit directory for security.
 */
export async function listFiles(
  sessionId: string,
  options?: {
    path?: string;
    recursive?: boolean;
  }
): Promise<FileListResponse> {
  const params = new URLSearchParams();
  if (options?.path) params.append('path', options.path);
  if (options?.recursive !== undefined) params.append('recursive', String(options.recursive));

  const response = await api.get(`/api/sessions/${sessionId}/files?${params.toString()}`);
  return response as FileListResponse;
}

/**
 * Read the content of a file in the session's workspace.
 */
export async function readFile(
  sessionId: string,
  path: string,
  encoding?: string
): Promise<FileContent> {
  const params = new URLSearchParams();
  params.append('path', path);
  if (encoding) params.append('encoding', encoding);

  const response = await api.get(`/api/sessions/${sessionId}/files/content?${params.toString()}`);
  return response as FileContent;
}

// ============================================================================
// API Object (for convenience)
// ============================================================================

export const workspaceApi = {
  listFiles,
  readFile,
};

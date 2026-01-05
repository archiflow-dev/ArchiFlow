/**
 * Artifact API client.
 *
 * Handles artifact CRUD operations for session workspaces.
 */

import { api, getDownloadUrl } from './api';

// ============================================================================
// Types
// ============================================================================

export interface ArtifactInfo {
  name: string;
  path: string;
  is_directory: boolean;
  size?: number;
  mime_type?: string;
  modified_at: string;
}

export interface ArtifactListResponse {
  artifacts: ArtifactInfo[];
  path: string;
  total: number;
}

export interface ArtifactContent {
  path: string;
  content?: string;
  content_base64?: string;
  mime_type: string;
  size: number;
  is_binary: boolean;
}

export interface ArtifactCreateRequest {
  path: string;
  content?: string;
  content_base64?: string;
}

export interface ArtifactUpdateRequest {
  content?: string;
  content_base64?: string;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * List artifacts in a session's workspace.
 */
export async function listArtifacts(
  sessionId: string,
  path: string = '',
): Promise<ArtifactListResponse> {
  return api.get<ArtifactListResponse>(`sessions/${sessionId}/artifacts/`, { params: { path } });
}

/**
 * Get the content of an artifact.
 */
export async function getArtifact(
  sessionId: string,
  path: string,
): Promise<ArtifactContent> {
  return api.get<ArtifactContent>(`sessions/${sessionId}/artifacts/${path}`);
}

/**
 * Create a new artifact.
 */
export async function createArtifact(
  sessionId: string,
  data: ArtifactCreateRequest,
): Promise<ArtifactInfo> {
  return api.post<ArtifactInfo>(`sessions/${sessionId}/artifacts/`, data);
}

/**
 * Update an artifact.
 */
export async function updateArtifact(
  sessionId: string,
  path: string,
  data: ArtifactUpdateRequest,
): Promise<ArtifactInfo> {
  return api.put<ArtifactInfo>(`sessions/${sessionId}/artifacts/${path}`, data);
}

/**
 * Delete an artifact.
 */
export async function deleteArtifact(
  sessionId: string,
  path: string,
): Promise<void> {
  return api.delete<void>(`sessions/${sessionId}/artifacts/${path}`);
}

/**
 * Get the download URL for an artifact.
 */
export function getArtifactDownloadUrl(sessionId: string, path: string): string {
  return getDownloadUrl(sessionId, path);
}

/**
 * Create a directory.
 */
export async function createDirectory(
  sessionId: string,
  path: string,
): Promise<{ path: string; created: boolean }> {
  return api.post<{ path: string; created: boolean }>(
    `sessions/${sessionId}/artifacts/directory`,
    undefined,
    { params: { path } },
  );
}

/**
 * Upload a file.
 */
export async function uploadArtifact(
  sessionId: string,
  file: File,
  targetPath: string = '',
): Promise<ArtifactInfo> {
  const formData = new FormData();
  formData.append('file', file);

  // Import API_BASE to build the correct URL
  const { API_BASE } = await import('./api');

  // Note: Using native fetch for file upload with FormData
  const response = await fetch(
    `${API_BASE}/sessions/${sessionId}/artifacts/upload?path=${encodeURIComponent(targetPath)}`,
    {
      method: 'POST',
      body: formData,
    },
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Upload failed');
  }

  return response.json();
}

// ============================================================================
// Namespace export
// ============================================================================

export const artifactApi = {
  list: listArtifacts,
  get: getArtifact,
  create: createArtifact,
  update: updateArtifact,
  delete: deleteArtifact,
  getDownloadUrl: getArtifactDownloadUrl,
  createDirectory,
  upload: uploadArtifact,
};

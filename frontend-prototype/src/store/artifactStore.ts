import { create } from 'zustand';
import type { Artifact, ArtifactType } from '../types';
import { artifactApi, type ArtifactInfo, type ArtifactContent } from '../services';

// ============================================================================
// Helper: Convert API response to frontend Artifact type
// ============================================================================

function mapArtifactInfo(info: ArtifactInfo, content?: ArtifactContent): Artifact {
  // Determine artifact type from mime type or extension
  const getArtifactType = (mimeType?: string, path?: string): ArtifactType => {
    if (info.is_directory) return 'folder';
    const ext = path?.split('.').pop()?.toLowerCase();

    if (mimeType?.startsWith('image/')) return 'image';
    if (mimeType === 'application/pdf' || ext === 'pdf') return 'pdf';
    if (mimeType === 'application/vnd.openxmlformats-officedocument.presentationml.presentation' || ext === 'pptx') return 'pptx';
    if (mimeType === 'application/json' || ext === 'json') return 'json';
    if (ext === 'md') return 'markdown';
    if (['js', 'ts', 'tsx', 'jsx', 'py', 'rs', 'go', 'java', 'c', 'cpp', 'h', 'css', 'html'].includes(ext ?? '')) return 'code';
    return 'markdown';
  };

  return {
    id: info.path, // Use path as ID since backend uses path-based addressing
    name: info.name,
    type: getArtifactType(info.mime_type, info.path),
    path: info.path,
    size: info.size,
    content: content?.content,
    url: content?.is_binary && content?.content_base64
      ? `data:${content.mime_type};base64,${content.content_base64}`
      : undefined,
    preview: content?.content?.slice(0, 100) ?? undefined,
    created_at: info.modified_at,
    updated_at: info.modified_at,
  };
}

// ============================================================================
// Store Interface
// ============================================================================

interface ArtifactState {
  artifacts: Artifact[];
  selectedArtifact: Artifact | null;
  isEditing: boolean;
  editedContent: string;
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
  sessionId: string | null;

  // Actions
  setArtifacts: (artifacts: Artifact[]) => void;
  loadArtifacts: (sessionId: string, path?: string) => Promise<void>;
  loadArtifactContent: (path: string) => Promise<Artifact | null>;
  addArtifact: (artifact: Artifact) => void;
  updateArtifact: (artifactId: string, updates: Partial<Artifact>) => void;
  removeArtifact: (artifactId: string) => void;
  selectArtifact: (artifact: Artifact | null) => void;
  startEditing: (artifact: Artifact) => void;
  saveEdit: () => Promise<void>;
  cancelEdit: () => void;
  updateEditedContent: (content: string) => void;
  clearError: () => void;

  // Getters
  getArtifactById: (artifactId: string) => Artifact | undefined;
  getArtifactsByPath: (path: string) => Artifact[];

  // API Actions
  createArtifact: (path: string, content: string) => Promise<Artifact | null>;
  deleteArtifact: (path: string) => Promise<void>;
  uploadFile: (file: File, targetPath?: string) => Promise<Artifact | null>;
}

// ============================================================================
// Store Implementation
// ============================================================================

export const useArtifactStore = create<ArtifactState>((set, get) => ({
  artifacts: [],
  selectedArtifact: null,
  isEditing: false,
  editedContent: '',
  isLoading: false,
  isSaving: false,
  error: null,
  sessionId: null,

  setArtifacts: (artifacts) => {
    set({ artifacts });
  },

  loadArtifacts: async (sessionId, path = '') => {
    set({ isLoading: true, error: null, sessionId });

    try {
      const response = await artifactApi.list(sessionId, path);
      const artifacts = response.artifacts.map((info) => mapArtifactInfo(info));
      set({ artifacts, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load artifacts',
        isLoading: false,
      });
    }
  },

  loadArtifactContent: async (path) => {
    const { sessionId } = get();
    if (!sessionId) {
      set({ error: 'No session selected' });
      return null;
    }

    set({ isLoading: true, error: null });

    try {
      const content = await artifactApi.get(sessionId, path);
      const info: ArtifactInfo = {
        name: path.split('/').pop() ?? path,
        path: content.path,
        is_directory: false,
        size: content.size,
        mime_type: content.mime_type,
        modified_at: new Date().toISOString(),
      };
      const artifact = mapArtifactInfo(info, content);

      // Update in local state
      set((state) => ({
        artifacts: state.artifacts.map((a) =>
          a.path === path ? artifact : a,
        ),
        isLoading: false,
      }));

      return artifact;
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load artifact content',
        isLoading: false,
      });
      return null;
    }
  },

  addArtifact: (artifact) => {
    set((state) => ({
      artifacts: [...state.artifacts, artifact],
    }));
  },

  updateArtifact: (artifactId, updates) => {
    set((state) => ({
      artifacts: state.artifacts.map((artifact) =>
        artifact.id === artifactId
          ? { ...artifact, ...updates, updated_at: new Date().toISOString() }
          : artifact,
      ),
      selectedArtifact:
        state.selectedArtifact?.id === artifactId
          ? { ...state.selectedArtifact, ...updates }
          : state.selectedArtifact,
    }));
  },

  removeArtifact: (artifactId) => {
    set((state) => ({
      artifacts: state.artifacts.filter((a) => a.id !== artifactId),
      selectedArtifact:
        state.selectedArtifact?.id === artifactId ? null : state.selectedArtifact,
    }));
  },

  selectArtifact: (artifact) => {
    set({
      selectedArtifact: artifact,
      isEditing: false,
      editedContent: artifact?.content ?? '',
    });
  },

  startEditing: (artifact) => {
    set({
      selectedArtifact: artifact,
      isEditing: true,
      editedContent: artifact.content ?? '',
    });
  },

  saveEdit: async () => {
    const { selectedArtifact, editedContent, sessionId } = get();
    if (!selectedArtifact || !sessionId) return;

    set({ isSaving: true, error: null });

    try {
      await artifactApi.update(sessionId, selectedArtifact.path, {
        content: editedContent,
      });

      get().updateArtifact(selectedArtifact.id, {
        content: editedContent,
        preview: editedContent.slice(0, 100) + (editedContent.length > 100 ? '...' : ''),
      });

      set({ isEditing: false, isSaving: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to save artifact',
        isSaving: false,
      });
    }
  },

  cancelEdit: () => {
    set({ isEditing: false, editedContent: '' });
  },

  updateEditedContent: (content) => {
    set({ editedContent: content });
  },

  clearError: () => {
    set({ error: null });
  },

  getArtifactById: (artifactId) => {
    return get().artifacts.find((a) => a.id === artifactId);
  },

  getArtifactsByPath: (path) => {
    return get().artifacts.filter((a) => a.path.startsWith(path));
  },

  createArtifact: async (path, content) => {
    const { sessionId } = get();
    if (!sessionId) {
      set({ error: 'No session selected' });
      return null;
    }

    set({ isSaving: true, error: null });

    try {
      const info = await artifactApi.create(sessionId, { path, content });
      const artifact = mapArtifactInfo(info, {
        path,
        content,
        mime_type: info.mime_type ?? 'text/plain',
        size: content.length,
        is_binary: false,
      });

      set((state) => ({
        artifacts: [...state.artifacts, artifact],
        isSaving: false,
      }));

      return artifact;
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to create artifact',
        isSaving: false,
      });
      return null;
    }
  },

  deleteArtifact: async (path) => {
    const { sessionId } = get();
    if (!sessionId) {
      set({ error: 'No session selected' });
      return;
    }

    set({ isLoading: true, error: null });

    try {
      await artifactApi.delete(sessionId, path);
      get().removeArtifact(path);
      set({ isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to delete artifact',
        isLoading: false,
      });
    }
  },

  uploadFile: async (file, targetPath = '') => {
    const { sessionId } = get();
    if (!sessionId) {
      set({ error: 'No session selected' });
      return null;
    }

    set({ isSaving: true, error: null });

    try {
      const info = await artifactApi.upload(sessionId, file, targetPath);
      const artifact = mapArtifactInfo(info);

      set((state) => ({
        artifacts: [...state.artifacts, artifact],
        isSaving: false,
      }));

      return artifact;
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to upload file',
        isSaving: false,
      });
      return null;
    }
  },
}));

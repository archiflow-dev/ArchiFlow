import { create } from 'zustand';
import type { Artifact } from '../types';

interface ArtifactState {
  artifacts: Artifact[];
  selectedArtifact: Artifact | null;
  isEditing: boolean;
  editedContent: string;

  // Actions
  setArtifacts: (artifacts: Artifact[]) => void;
  addArtifact: (artifact: Artifact) => void;
  updateArtifact: (artifactId: string, updates: Partial<Artifact>) => void;
  removeArtifact: (artifactId: string) => void;
  selectArtifact: (artifact: Artifact | null) => void;
  startEditing: (artifact: Artifact) => void;
  saveEdit: () => void;
  cancelEdit: () => void;
  updateEditedContent: (content: string) => void;

  // Getters
  getArtifactById: (artifactId: string) => Artifact | undefined;
  getArtifactsByPath: (path: string) => Artifact[];
}

export const useArtifactStore = create<ArtifactState>((set, get) => ({
  artifacts: [],
  selectedArtifact: null,
  isEditing: false,
  editedContent: '',

  setArtifacts: (artifacts) => {
    set({ artifacts });
  },

  addArtifact: (artifact) => {
    set(state => ({
      artifacts: [...state.artifacts, artifact]
    }));
  },

  updateArtifact: (artifactId, updates) => {
    set(state => ({
      artifacts: state.artifacts.map(artifact =>
        artifact.id === artifactId
          ? { ...artifact, ...updates, updated_at: new Date().toISOString() }
          : artifact
      ),
      selectedArtifact:
        state.selectedArtifact?.id === artifactId
          ? { ...state.selectedArtifact, ...updates }
          : state.selectedArtifact
    }));
  },

  removeArtifact: (artifactId) => {
    set(state => ({
      artifacts: state.artifacts.filter(a => a.id !== artifactId),
      selectedArtifact:
        state.selectedArtifact?.id === artifactId
          ? null
          : state.selectedArtifact
    }));
  },

  selectArtifact: (artifact) => {
    set({
      selectedArtifact: artifact,
      isEditing: false,
      editedContent: artifact?.content ?? ''
    });
  },

  startEditing: (artifact) => {
    set({
      selectedArtifact: artifact,
      isEditing: true,
      editedContent: artifact.content ?? ''
    });
  },

  saveEdit: () => {
    const { selectedArtifact, editedContent } = get();
    if (selectedArtifact) {
      get().updateArtifact(selectedArtifact.id, {
        content: editedContent,
        preview: editedContent.slice(0, 100) + (editedContent.length > 100 ? '...' : '')
      });
    }
    set({ isEditing: false });
  },

  cancelEdit: () => {
    set({ isEditing: false, editedContent: '' });
  },

  updateEditedContent: (content) => {
    set({ editedContent: content });
  },

  getArtifactById: (artifactId) => {
    return get().artifacts.find(a => a.id === artifactId);
  },

  getArtifactsByPath: (path) => {
    return get().artifacts.filter(a => a.path.startsWith(path));
  }
}));

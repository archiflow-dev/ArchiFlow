/**
 * Workspace file store.
 *
 * Manages the state of files in the current session's workspace.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { listFiles, readFile, writeFile, type FileInfo } from '../services/workspaceApi';

interface WorkspaceFile extends FileInfo {
  isOpen?: boolean;
}

interface WorkspaceState {
  // Current session
  sessionId: string | null;

  // Files
  files: WorkspaceFile[];
  expandedFolders: Set<string>;

  // Selected file for viewing
  selectedFile: WorkspaceFile | null;

  // View mode for the selected file
  viewMode: 'raw' | 'preview';

  // Content of the selected file
  fileContent: string | null;

  // Loading state
  isLoading: boolean;
  error: string | null;

  // Actions
  setSessionId: (sessionId: string | null) => void;
  loadFiles: (path?: string, recursive?: boolean) => Promise<void>;
  selectFile: (file: WorkspaceFile | null) => void;
  loadFileContent: (path: string) => Promise<void>;
  saveFileContent: (path: string, content: string) => Promise<void>;
  setViewMode: (mode: 'raw' | 'preview') => void;
  toggleFolder: (path: string) => void;
  setExpandedFolders: (folders: Set<string>) => void;
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      // Initial state
      sessionId: null,
      files: [],
      expandedFolders: new Set<string>(),
      selectedFile: null,
      viewMode: 'preview',
      fileContent: null,
      isLoading: false,
      error: null,

      // Set session ID
      setSessionId: (sessionId) => {
        set({ sessionId, files: [], selectedFile: null, fileContent: null });
      },

      // Load files from workspace
      loadFiles: async (path = '', recursive = false) => {
        const { sessionId } = get();
        if (!sessionId) {
          set({ error: 'No session selected' });
          return;
        }

        set({ isLoading: true, error: null });

        try {
          const response = await listFiles(sessionId, { path, recursive });

          // Mark files as open/close based on current state
          const filesWithState = response.files.map((file) => ({
            ...file,
            isOpen: false,
          }));

          set({ files: filesWithState });
        } catch (error) {
          set({ error: (error as Error).message });
        } finally {
          set({ isLoading: false });
        }
      },

      // Select a file
      selectFile: (file) => {
        set({ selectedFile: file, fileContent: null });
      },

      // Load file content
      loadFileContent: async (path) => {
        const { sessionId } = get();
        if (!sessionId) {
          set({ error: 'No session selected' });
          return;
        }

        set({ isLoading: true, error: null });

        try {
          const content = await readFile(sessionId, path);
          set({ fileContent: content.content });
        } catch (error) {
          set({ error: (error as Error).message });
        } finally {
          set({ isLoading: false });
        }
      },

      // Save file content
      saveFileContent: async (path, content) => {
        const { sessionId } = get();
        if (!sessionId) {
          set({ error: 'No session selected' });
          throw new Error('No session selected');
        }

        set({ isLoading: true, error: null });

        try {
          const result = await writeFile(sessionId, path, content);
          // Update the file content in state
          set({ fileContent: result.content });
        } catch (error) {
          const errorMsg = (error as Error).message;
          set({ error: errorMsg });
          throw new Error(errorMsg);
        } finally {
          set({ isLoading: false });
        }
      },

      // Set view mode
      setViewMode: (mode) => {
        set({ viewMode: mode });
      },

      // Toggle folder expansion
      toggleFolder: (path) => {
        const { expandedFolders } = get();
        const newExpanded = new Set(expandedFolders);
        if (newExpanded.has(path)) {
          newExpanded.delete(path);
        } else {
          newExpanded.add(path);
        }
        set({ expandedFolders: newExpanded });
      },

      // Set expanded folders
      setExpandedFolders: (folders) => {
        set({ expandedFolders: folders });
      },
    }),
    {
      name: 'archiflow-workspace-storage',
      partialize: (state) => ({
        expandedFolders: Array.from(state.expandedFolders),
        viewMode: state.viewMode,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          // Convert array back to Set
          state.expandedFolders = new Set(state.expandedFolders as unknown as string[]);
        }
      },
    }
  )
);

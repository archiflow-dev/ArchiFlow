/**
 * Comment store.
 *
 * Manages document comments for the current session.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  listComments,
  listFileComments,
  getComment,
  createComment,
  updateComment,
  resolveComment,
  deleteComment,
  getPendingComments,
  submitCommentsToAgent,
  type Comment,
  type CommentCreate,
  type CommentUpdate,
  type CommentStatus,
} from '../services/commentApi';

// Import UI store for panel state management
import { useUIStore } from './uiStore';

interface CommentState {
  // Current session
  sessionId: string | null;

  // Comments
  comments: Comment[];

  // Filtered comments for current file
  fileComments: Comment[];

  // Currently selected comment
  selectedComment: Comment | null;

  // Filter by file path
  filterFilePath: string | null;

  // Filter by status
  filterStatus: CommentStatus | null;

  // Panel state
  isPanelOpen: boolean;

  // Pending selection for new comment
  pendingSelection: {
    filePath: string;
    lineNumber: number;
    selectedText: string;
  } | null;

  // Navigation state
  focusedCommentId: string | null;
  highlightLine: number | null;
  highlightFilePath: string | null;

  // Loading state
  isLoading: boolean;
  isSubmitting: boolean;
  error: string | null;

  // Actions - Session
  setSessionId: (sessionId: string | null) => void;

  // Actions - Pending Selection
  setPendingSelection: (selection: { filePath: string; lineNumber: number; selectedText: string } | null) => void;
  clearPendingSelection: () => void;

  // Actions - Comments
  loadComments: (options?: { file_path?: string; status?: CommentStatus }) => Promise<void>;
  loadFileComments: (filePath: string) => Promise<void>;
  refreshComments: () => Promise<void>;

  // Actions - CRUD
  addComment: (data: CommentCreate) => Promise<Comment>;
  editComment: (commentId: string, data: CommentUpdate) => Promise<void>;
  removeComment: (commentId: string) => Promise<void>;
  resolveCommentById: (commentId: string) => Promise<void>;

  // Actions - Selection
  selectComment: (comment: Comment | null) => void;
  clearSelection: () => void;

  // Actions - Navigation
  setFocusedComment: (commentId: string | null, filePath?: string | null, lineNumber?: number | null) => void;
  clearFocus: () => void;

  // Actions - Filters
  setFilterFilePath: (filePath: string | null) => void;
  setFilterStatus: (status: CommentStatus | null) => void;
  clearFilters: () => void;

  // Actions - Panel
  togglePanel: () => void;
  openPanel: () => void;
  closePanel: () => void;

  // Actions - Agent submission
  submitToAgent: (options?: { file_path?: string | null }) => Promise<{
    submitted_count: number;
    comment_ids: string[];
    message: string;
  }>;

  // Actions - Pending comments
  loadPendingComments: (options?: { file_path?: string }) => Promise<void>;

  // Actions - Error handling
  clearError: () => void;
}

export const useCommentStore = create<CommentState>()(
  persist(
    (set, get) => ({
      // Initial state
      sessionId: null,
      comments: [],
      fileComments: [],
      selectedComment: null,
      filterFilePath: null,
      filterStatus: null,
      isPanelOpen: false,
      pendingSelection: null,
      focusedCommentId: null,
      highlightLine: null,
      highlightFilePath: null,
      isLoading: false,
      isSubmitting: false,
      error: null,

      // Set session ID
      setSessionId: (sessionId) => {
        set({
          sessionId,
          comments: [],
          fileComments: [],
          selectedComment: null,
          filterFilePath: null,
          filterStatus: null,
          pendingSelection: null,
          focusedCommentId: null,
          highlightLine: null,
          highlightFilePath: null,
        });
      },

      // Set pending selection for new comment
      setPendingSelection: (selection) => {
        set({ pendingSelection: selection });
      },

      // Clear pending selection
      clearPendingSelection: () => {
        set({ pendingSelection: null });
      },

      // Load comments with optional filters
      loadComments: async (options) => {
        const { sessionId } = get();
        if (!sessionId) {
          set({ error: 'No session selected' });
          return;
        }

        set({ isLoading: true, error: null });

        try {
          const response = await listComments(sessionId, options || {});
          set({ comments: response.comments });

          // Update file comments if file filter is active
          const { filterFilePath } = get();
          if (filterFilePath) {
            const fileComments = response.comments.filter(
              (c) => c.file_path === filterFilePath
            );
            set({ fileComments });
          }
        } catch (error) {
          set({ error: (error as Error).message });
        } finally {
          set({ isLoading: false });
        }
      },

      // Load comments for a specific file
      loadFileComments: async (filePath) => {
        const { sessionId } = get();
        if (!sessionId) {
          set({ error: 'No session selected' });
          return;
        }

        set({ isLoading: true, error: null, filterFilePath: filePath });

        try {
          const response = await listFileComments(sessionId, filePath);
          set({ fileComments: response.comments });

          // Also update all comments
          const allComments = await listComments(sessionId);
          set({ comments: allComments.comments });
        } catch (error) {
          set({ error: (error as Error).message });
        } finally {
          set({ isLoading: false });
        }
      },

      // Refresh comments (reload with current filters)
      refreshComments: async () => {
        const { filterFilePath, filterStatus } = get();
        await get().loadComments({
          file_path: filterFilePath || undefined,
          status: filterStatus || undefined,
        });
      },

      // Add a new comment
      addComment: async (data) => {
        const { sessionId } = get();
        if (!sessionId) {
          set({ error: 'No session selected' });
          throw new Error('No session selected');
        }

        set({ isLoading: true, error: null });

        try {
          const comment = await createComment(sessionId, data);

          // Add to comments list
          set((state) => ({
            comments: [...state.comments, comment],
            fileComments: state.filterFilePath
              ? [...state.fileComments, comment]
              : state.fileComments,
          }));

          return comment;
        } catch (error) {
          set({ error: (error as Error).message });
          throw error;
        } finally {
          set({ isLoading: false });
        }
      },

      // Edit an existing comment
      editComment: async (commentId, data) => {
        const { sessionId } = get();
        if (!sessionId) {
          set({ error: 'No session selected' });
          return;
        }

        set({ isLoading: true, error: null });

        try {
          const updated = await updateComment(commentId, sessionId, data);

          // Update in lists
          set((state) => ({
            comments: state.comments.map((c) =>
              c.id === commentId ? updated : c
            ),
            fileComments: state.fileComments.map((c) =>
              c.id === commentId ? updated : c
            ),
            selectedComment:
              state.selectedComment?.id === commentId
                ? updated
                : state.selectedComment,
          }));
        } catch (error) {
          set({ error: (error as Error).message });
        } finally {
          set({ isLoading: false });
        }
      },

      // Remove a comment
      removeComment: async (commentId) => {
        const { sessionId } = get();
        if (!sessionId) {
          set({ error: 'No session selected' });
          return;
        }

        set({ isLoading: true, error: null });

        try {
          await deleteComment(commentId, sessionId);

          // Remove from lists
          set((state) => ({
            comments: state.comments.filter((c) => c.id !== commentId),
            fileComments: state.fileComments.filter((c) => c.id !== commentId),
            selectedComment:
              state.selectedComment?.id === commentId
                ? null
                : state.selectedComment,
          }));
        } catch (error) {
          set({ error: (error as Error).message });
        } finally {
          set({ isLoading: false });
        }
      },

      // Resolve a comment
      resolveCommentById: async (commentId) => {
        const { sessionId } = get();
        if (!sessionId) {
          set({ error: 'No session selected' });
          return;
        }

        set({ isLoading: true, error: null });

        try {
          const updated = await resolveComment(commentId, sessionId);

          // Update in lists
          set((state) => ({
            comments: state.comments.map((c) =>
              c.id === commentId ? updated : c
            ),
            fileComments: state.fileComments.map((c) =>
              c.id === commentId ? updated : c
            ),
            selectedComment:
              state.selectedComment?.id === commentId
                ? updated
                : state.selectedComment,
          }));
        } catch (error) {
          set({ error: (error as Error).message });
        } finally {
          set({ isLoading: false });
        }
      },

      // Select a comment
      selectComment: (comment) => {
        set({ selectedComment: comment });
      },

      // Clear selection
      clearSelection: () => {
        set({ selectedComment: null });
      },

      // Set focused comment and highlight line
      setFocusedComment: (commentId, filePath, lineNumber) => {
        set({
          focusedCommentId: commentId,
          highlightFilePath: filePath || null,
          highlightLine: lineNumber || null,
        });
      },

      // Clear focus
      clearFocus: () => {
        set({
          focusedCommentId: null,
          highlightLine: null,
          highlightFilePath: null,
        });
      },

      // Set file path filter
      setFilterFilePath: (filePath) => {
        set({ filterFilePath: filePath });

        // Update file comments
        const { comments } = get();
        const fileComments = filePath
          ? comments.filter((c) => c.file_path === filePath)
          : [];
        set({ fileComments });
      },

      // Set status filter
      setFilterStatus: (status) => {
        set({ filterStatus: status });
      },

      // Clear all filters
      clearFilters: () => {
        set({ filterFilePath: null, filterStatus: null, fileComments: [] });
      },

      // Toggle panel open/close
      togglePanel: () => {
        set((state) => ({ isPanelOpen: !state.isPanelOpen }));
      },

      // Open panel (delegates to UI store)
      openPanel: () => {
        set({ isPanelOpen: true });
        // Also open the panel in UI store (controls actual visibility)
        useUIStore.getState().setCommentPanelOpen(true);
      },

      // Close panel (delegates to UI store)
      closePanel: () => {
        set({ isPanelOpen: false });
        // Also close the panel in UI store (controls actual visibility)
        useUIStore.getState().setCommentPanelOpen(false);
      },

      // Submit comments to agent
      submitToAgent: async (options) => {
        const { sessionId, comments } = get();
        if (!sessionId) {
          set({ error: 'No session selected' });
          throw new Error('No session selected');
        }

        // Get comments that will be submitted (pending, optionally filtered by file)
        const commentsToSubmit = options?.file_path
          ? comments.filter(c => c.file_path === options.file_path && c.status === 'pending')
          : comments.filter(c => c.status === 'pending');

        // Log to browser console
        console.log('📤 Submitting comments to agent:', {
          sessionId,
          fileFilter: options?.file_path || 'all files',
          count: commentsToSubmit.length,
          comments: commentsToSubmit.map(c => ({
            id: c.id,
            file: c.file_path,
            line: c.line_number,
            selectedText: c.selected_text || '(no text selected)',
            comment: c.comment_text,
            status: c.status,
          }))
        });

        set({ isSubmitting: true, error: null });

        try {
          const response = await submitCommentsToAgent(sessionId, options);

          // Log success response
          console.log('✅ Comments submitted successfully:', response);

          // Reload comments to update statuses
          await get().refreshComments();

          return response;
        } catch (error) {
          console.error('❌ Failed to submit comments:', error);
          set({ error: (error as Error).message });
          throw error;
        } finally {
          set({ isSubmitting: false });
        }
      },

      // Load pending comments
      loadPendingComments: async (options) => {
        const { sessionId } = get();
        if (!sessionId) {
          set({ error: 'No session selected' });
          return;
        }

        set({ isLoading: true, error: null });

        try {
          const response = await getPendingComments(sessionId, options);
          set({ comments: response.comments });
        } catch (error) {
          set({ error: (error as Error).message });
        } finally {
          set({ isLoading: false });
        }
      },

      // Clear error
      clearError: () => {
        set({ error: null });
      },
    }),
    {
      name: 'archiflow-comment-storage',
      partialize: (state) => ({
        isPanelOpen: state.isPanelOpen,
        filterStatus: state.filterStatus,
      }),
    }
  )
);

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  X,
  FileText,
  ChevronDown,
  ChevronRight,
  Filter,
  Check,
} from 'lucide-react';
import { useCommentStore, useSessionStore, useUIStore } from '../../store';
import { CommentList } from './CommentList';
import { AddCommentForm } from './AddCommentForm';
import { cn } from '../../lib/utils';
import type { CommentStatus } from '../../types';

interface CommentPanelProps {
  initialData?: {
    filePath?: string;
    lineNumber?: number;
    selectedText?: string;
  };
}

export function CommentPanel({ initialData }: CommentPanelProps) {
  const { currentSession } = useSessionStore();
  const { isCommentPanelOpen, setCommentPanelOpen } = useUIStore();
  const {
    setSessionId,
    pendingSelection,
    comments,
    fileComments,
    filterFilePath,
    filterStatus,
    isLoading,
    loadComments,
    refreshComments,
    submitToAgent,
    clearFilters,
    clearPendingSelection,
    setFilterStatus,
  } = useCommentStore();

  const [showAddForm, setShowAddForm] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<string | null>(null);
  const [showFilterMenu, setShowFilterMenu] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Store pending selection data in a ref (persists across renders, won't be cleared)
  const pendingSelectionRef = useRef<{
    filePath: string;
    lineNumber: number;
    selectedText: string;
  } | null>(null);

  // Set session ID when session changes
  useEffect(() => {
    if (currentSession?.session_id) {
      setSessionId(currentSession.session_id);
    }
  }, [currentSession?.session_id, setSessionId]);

  // Load comments when session ID is set
  useEffect(() => {
    if (currentSession?.session_id) {
      loadComments();
    }
  }, [currentSession?.session_id]);

  // Sync pending selection from store to our ref (persists even if store is cleared)
  useEffect(() => {
    if (pendingSelection) {
      pendingSelectionRef.current = pendingSelection;
    }
  }, [pendingSelection]);

  // Open add form if pending selection or initial data provided
  useEffect(() => {
    if (pendingSelection || initialData?.filePath || initialData?.selectedText) {
      setShowAddForm(true);
    }
  }, [pendingSelection, initialData]);

  // Clear pending selection when form is closed
  useEffect(() => {
    if (!showAddForm) {
      // Clear the store's pendingSelection (but our ref still has the data for AddCommentForm)
      clearPendingSelection();
    }
  }, [showAddForm, clearPendingSelection]);

  // Keyboard shortcuts
  useEffect(() => {
    if (!isCommentPanelOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
        return;
      }

      // Press "/" to open add comment form (when not already showing)
      if (e.key === '/' && !showAddForm) {
        e.preventDefault();
        setShowAddForm(true);
      }

      // Press "Escape" to close filter menu or add form
      if (e.key === 'Escape') {
        if (showFilterMenu) {
          setShowFilterMenu(false);
        } else if (showAddForm) {
          setShowAddForm(false);
        }
      }

      // Press "r" to refresh
      if (e.key === 'r' && !e.ctrlKey && !e.metaKey && !showAddForm) {
        e.preventDefault();
        refreshComments();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isCommentPanelOpen, showAddForm, showFilterMenu, refreshComments]);

  // Close filter menu when clicking outside
  useEffect(() => {
    if (!showFilterMenu) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setShowFilterMenu(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showFilterMenu]);

  // Filter file comments for display
  const displayComments = filterFilePath ? fileComments : comments;
  const filteredByStatus = filterStatus
    ? displayComments.filter((c) => c.status === filterStatus)
    : displayComments;
  const pendingCount = comments.filter((c) => c.status === 'pending').length;

  const handleRefresh = async () => {
    await refreshComments();
  };

  const handleAddComment = () => {
    setShowAddForm(true);
  };

  const handleAddSuccess = () => {
    setShowAddForm(false);
    // Clear the ref data for the next comment
    pendingSelectionRef.current = null;
  };

  const handleAddCancel = () => {
    setShowAddForm(false);
    // Clear the ref data for the next comment
    pendingSelectionRef.current = null;
  };

  const handleSubmitToAgent = async () => {
    if (!currentSession?.session_id) return;

    setIsSubmitting(true);
    setSubmitResult(null);

    try {
      const result = await submitToAgent({
        file_path: filterFilePath,
      });

      setSubmitResult(
        `✓ Submitted ${result.submitted_count} comment${result.submitted_count !== 1 ? 's' : ''} to agent`
      );

      // Clear success message after 3 seconds
      setTimeout(() => setSubmitResult(null), 3000);
    } catch (err) {
      setSubmitResult(`✗ Failed: ${(err as Error).message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFilterByStatus = (status: CommentStatus | null) => {
    setFilterStatus(status);
    setShowFilterMenu(false);
  };

  const statusFilterCount = filterStatus
    ? displayComments.filter((c) => c.status === filterStatus).length
    : displayComments.length;

  // If panel is not open, don't render
  if (!isCommentPanelOpen) {
    return null;
  }

  return (
    <div ref={panelRef} className="h-full flex flex-col bg-gray-850 border-l border-gray-700">
      {/* Panel Header */}
      <div className="flex-shrink-0 h-9 px-3 flex items-center justify-between border-b border-gray-700 bg-gray-800/50">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-gray-400" />
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Comments
          </span>
          {pendingCount > 0 && (
            <span className="px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded border border-yellow-500/30">
              {pendingCount} pending
            </span>
          )}
          {filterStatus && (
            <button
              onClick={() => handleFilterByStatus(null)}
              className="px-1.5 py-0.5 bg-gray-700 text-gray-400 text-xs rounded border border-gray-600 hover:border-gray-500 hover:text-gray-300 transition-colors flex items-center gap-1"
              title="Clear filter"
            >
              {filterStatus}
              <X className="w-3 h-3" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-1">
          {/* Filter Button */}
          <div className="relative">
            <button
              onClick={() => setShowFilterMenu(!showFilterMenu)}
              className={cn(
                'p-1 transition-colors rounded',
                showFilterMenu || filterStatus
                  ? 'text-blue-400 bg-blue-500/10'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-gray-700/50'
              )}
              title="Filter comments"
            >
              <Filter className="w-3.5 h-3.5" />
            </button>

            {/* Filter Dropdown */}
            {showFilterMenu && (
              <div className="absolute right-0 top-full mt-1 w-40 bg-gray-800 border border-gray-700 rounded-lg shadow-lg z-50">
                <div className="py-1">
                  <button
                    onClick={() => handleFilterByStatus(null)}
                    className={cn(
                      'w-full px-3 py-1.5 text-left text-xs flex items-center gap-2 transition-colors',
                      !filterStatus
                        ? 'bg-blue-500/20 text-blue-400'
                        : 'text-gray-400 hover:bg-gray-700/50 hover:text-gray-300'
                    )}
                  >
                    {!filterStatus && <Check className="w-3 h-3 flex-shrink-0" />}
                    <span>All Comments</span>
                    <span className="ml-auto text-gray-500">
                      {displayComments.length}
                    </span>
                  </button>
                  <button
                    onClick={() => handleFilterByStatus('pending')}
                    className={cn(
                      'w-full px-3 py-1.5 text-left text-xs flex items-center gap-2 transition-colors',
                      filterStatus === 'pending'
                        ? 'bg-blue-500/20 text-blue-400'
                        : 'text-gray-400 hover:bg-gray-700/50 hover:text-gray-300'
                    )}
                  >
                    {filterStatus === 'pending' && <Check className="w-3 h-3 flex-shrink-0" />}
                    <span>Pending</span>
                    <span className="ml-auto text-gray-500">
                      {displayComments.filter((c) => c.status === 'pending').length}
                    </span>
                  </button>
                  <button
                    onClick={() => handleFilterByStatus('resolved')}
                    className={cn(
                      'w-full px-3 py-1.5 text-left text-xs flex items-center gap-2 transition-colors',
                      filterStatus === 'resolved'
                        ? 'bg-blue-500/20 text-blue-400'
                        : 'text-gray-400 hover:bg-gray-700/50 hover:text-gray-300'
                    )}
                  >
                    {filterStatus === 'resolved' && <Check className="w-3 h-3 flex-shrink-0" />}
                    <span>Resolved</span>
                    <span className="ml-auto text-gray-500">
                      {displayComments.filter((c) => c.status === 'resolved').length}
                    </span>
                  </button>
                  <button
                    onClick={() => handleFilterByStatus('submitted')}
                    className={cn(
                      'w-full px-3 py-1.5 text-left text-xs flex items-center gap-2 transition-colors',
                      filterStatus === 'submitted'
                        ? 'bg-blue-500/20 text-blue-400'
                        : 'text-gray-400 hover:bg-gray-700/50 hover:text-gray-300'
                    )}
                  >
                    {filterStatus === 'submitted' && <Check className="w-3 h-3 flex-shrink-0" />}
                    <span>Submitted</span>
                    <span className="ml-auto text-gray-500">
                      {displayComments.filter((c) => c.status === 'submitted').length}
                    </span>
                  </button>
                  <button
                    onClick={() => handleFilterByStatus('applied')}
                    className={cn(
                      'w-full px-3 py-1.5 text-left text-xs flex items-center gap-2 transition-colors',
                      filterStatus === 'applied'
                        ? 'bg-blue-500/20 text-blue-400'
                        : 'text-gray-400 hover:bg-gray-700/50 hover:text-gray-300'
                    )}
                  >
                    {filterStatus === 'applied' && <Check className="w-3 h-3 flex-shrink-0" />}
                    <span>Applied</span>
                    <span className="ml-auto text-gray-500">
                      {displayComments.filter((c) => c.status === 'applied').length}
                    </span>
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Refresh Button */}
          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className={cn(
              'p-1 transition-colors rounded',
              isLoading
                ? 'text-gray-600 animate-spin'
                : 'text-gray-500 hover:text-gray-300 hover:bg-gray-700/50'
            )}
            title="Refresh comments (r)"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          {/* Close Button */}
          <button
            onClick={() => setCommentPanelOpen(false)}
            className="p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 rounded transition-colors"
            title="Close panel"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Filter Info */}
      {filterFilePath && (
        <div className="flex-shrink-0 px-3 py-1.5 bg-blue-500/10 border-b border-blue-500/20 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs">
            <FileText className="w-3.5 h-3.5 text-blue-400" />
            <span className="text-blue-300">
              Filtered: <span className="font-medium">{filterFilePath}</span>
            </span>
            <span className="text-gray-500">•</span>
            <span className="text-gray-400">{statusFilterCount} comment{statusFilterCount !== 1 ? 's' : ''}</span>
          </div>
          <button
            onClick={clearFilters}
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            Clear
          </button>
        </div>
      )}

      {/* Submit Result Message */}
      {submitResult && (
        <div
          className={cn(
            'flex-shrink-0 px-3 py-1.5 text-xs border-b',
            submitResult.startsWith('✓')
              ? 'bg-green-500/10 border-green-500/20 text-green-400'
              : 'bg-red-500/10 border-red-500/20 text-red-400'
          )}
        >
          {submitResult}
        </div>
      )}

      {/* Empty State for Filtered Comments */}
      {!showAddForm && filteredByStatus.length === 0 && displayComments.length > 0 && (
        <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
          <p>No comments match the current filter.</p>
        </div>
      )}

      {/* Comments List */}
      {!showAddForm ? (
        <>
          {filteredByStatus.length > 0 && (
            <div className="flex-1 overflow-hidden">
              <CommentList comments={filteredByStatus} />
            </div>
          )}

          {/* Footer Actions */}
          <div className="flex-shrink-0 p-2 border-t border-gray-700 bg-gray-800/30 space-y-2">
            {/* Submit to Agent */}
            {pendingCount > 0 && (
              <button
                onClick={handleSubmitToAgent}
                disabled={isSubmitting}
                className={cn(
                  'w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  'bg-gradient-to-r from-blue-600 to-purple-600 text-white',
                  'hover:from-blue-700 hover:to-purple-700',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                {isSubmitting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Submitting...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    <span>Submit {pendingCount} to Agent</span>
                  </>
                )}
              </button>
            )}

            {/* Add Comment Button */}
            <button
              onClick={handleAddComment}
              className={cn(
                'w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                'bg-gray-700 text-gray-300 hover:bg-gray-600'
              )}
            >
              <Plus className="w-4 h-4" />
              <span>Add Comment</span>
            </button>
          </div>
        </>
      ) : (
        /* Add Comment Form */
        <div className="flex-1 overflow-y-auto">
          <AddCommentForm
            initialData={
              pendingSelectionRef.current || pendingSelection || initialData || undefined
            }
            onSuccess={handleAddSuccess}
            onCancel={handleAddCancel}
          />
        </div>
      )}
    </div>
  );
}

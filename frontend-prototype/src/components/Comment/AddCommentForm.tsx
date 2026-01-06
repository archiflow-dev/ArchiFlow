import { useState, useEffect, useRef } from 'react';
import { X, Send } from 'lucide-react';
import { useCommentStore, useSessionStore, useWorkspaceStore } from '../../store';
import type { CommentCreate } from '../../types';
import { cn } from '../../lib/utils';

interface AddCommentFormProps {
  initialData?: {
    filePath?: string;
    lineNumber?: number;
    selectedText?: string;
  };
  onSuccess?: () => void;
  onCancel?: () => void;
}

export function AddCommentForm({ initialData, onSuccess, onCancel }: AddCommentFormProps) {
  const { currentSession } = useSessionStore();
  const { selectedFile } = useWorkspaceStore();
  const { addComment, isLoading, pendingSelection } = useCommentStore();

  const [commentText, setCommentText] = useState('');
  const [selectedText, setSelectedText] = useState(initialData?.selectedText || '');
  const [lineNumber, setLineNumber] = useState(initialData?.lineNumber || 1);
  const [error, setError] = useState<string | null>(null);

  // Track if we've initialized from pendingSelection
  const initializedRef = useRef(false);

  // Auto-fill file path from selected file
  const filePath = initialData?.filePath || selectedFile?.path || '';

  // Update form when initialData changes (for pending selection)
  useEffect(() => {
    if (initialData?.selectedText) {
      setSelectedText(initialData.selectedText);
    }
    if (initialData?.lineNumber) {
      setLineNumber(initialData.lineNumber);
    }
  }, [initialData?.selectedText, initialData?.lineNumber]);

  // Initialize from pendingSelection if local state is empty (for first render when panel opens)
  useEffect(() => {
    if (!initializedRef.current && pendingSelection) {
      // Only populate if local state is empty (no user input yet)
      if (!selectedText && pendingSelection.selectedText) {
        setSelectedText(pendingSelection.selectedText);
      }
      if (!lineNumber || lineNumber === 1) {
        setLineNumber(pendingSelection.lineNumber);
      }
      initializedRef.current = true;
    }
  }, [pendingSelection, selectedText, lineNumber]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!commentText.trim()) {
      setError('Please enter a comment');
      return;
    }

    if (!filePath) {
      setError('No file selected');
      return;
    }

    if (!currentSession?.session_id) {
      setError('No active session');
      return;
    }

    const data: CommentCreate = {
      file_path: filePath,
      line_number: lineNumber,
      selected_text: selectedText,
      comment_text: commentText.trim(),
      author: 'default_user',
    };

    try {
      await addComment(data);
      setCommentText('');
      setSelectedText('');
      setLineNumber(1);
      onSuccess?.();
    } catch (err) {
      setError((err as Error).message || 'Failed to add comment');
    }
  };

  const handleCancel = () => {
    setCommentText('');
    setSelectedText('');
    setError(null);
    onCancel?.();
  };

  return (
    <div className="border-t border-gray-700 bg-gray-800/50">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700/50">
        <h3 className="text-sm font-semibold text-gray-300">Add Comment</h3>
        <button
          onClick={handleCancel}
          className="text-gray-500 hover:text-gray-300 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="p-4 space-y-3">
        {/* File Info */}
        {filePath && (
          <div className="text-xs text-gray-500">
            <span className="font-medium">File:</span> {filePath}
            {lineNumber > 0 && (
              <>
                <span className="mx-1">•</span>
                <span className="font-medium">Line:</span> {lineNumber}
              </>
            )}
          </div>
        )}

        {/* Selected Text (if any) */}
        {selectedText && (
          <div className="p-2 bg-gray-900/50 rounded border border-gray-700">
            <label className="text-xs text-gray-500 mb-1 block">
              Selected text:
            </label>
            <p className="text-sm text-gray-400 italic line-clamp-2">
              "{selectedText}"
            </p>
          </div>
        )}

        {/* Comment Input */}
        <div>
          <label htmlFor="comment-text" className="text-xs text-gray-400 mb-1 block">
            Comment *
          </label>
          <textarea
            id="comment-text"
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            placeholder="What would you like to change or clarify?"
            className={cn(
              'w-full px-3 py-2 text-sm bg-gray-900 border rounded resize-none',
              'text-gray-200 placeholder-gray-500',
              'focus:outline-none focus:ring-1 focus:ring-blue-500/50 focus:border-blue-500',
              error ? 'border-red-500' : 'border-gray-700'
            )}
            rows={3}
            disabled={isLoading}
            autoFocus
          />
        </div>

        {/* Error Message */}
        {error && (
          <p className="text-xs text-red-400">{error}</p>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between pt-2">
          <div className="text-xs text-gray-500">
            Press <kbd className="px-1.5 py-0.5 bg-gray-700 rounded">Enter</kbd> to submit
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCancel}
              className="px-3 py-1.5 text-sm text-gray-400 hover:text-gray-200 hover:bg-gray-700/50 rounded transition-colors"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading || !commentText.trim()}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 text-sm rounded transition-colors',
                'bg-blue-600 text-white hover:bg-blue-700',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              {isLoading ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Adding...</span>
                </>
              ) : (
                <>
                  <Send className="w-3.5 h-3.5" />
                  <span>Add Comment</span>
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

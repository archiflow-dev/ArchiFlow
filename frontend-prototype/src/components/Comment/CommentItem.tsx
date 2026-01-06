import { useState, useRef, useEffect } from 'react';
import { MessageSquare, Trash2, Check, ChevronDown, ChevronRight, FileText, Edit2, X as XIcon, ArrowRight } from 'lucide-react';
import { type Comment } from '../../types';
import { useCommentStore } from '../../store';
import { cn, formatRelativeTime } from '../../lib/utils';

interface CommentItemProps {
  comment: Comment;
  isSelected?: boolean;
  isFocused?: boolean;
  onSelect?: () => void;
}

export function CommentItem({ comment, isSelected, isFocused, onSelect }: CommentItemProps) {
  const { resolveCommentById, removeComment, editComment, selectComment, setFocusedComment } = useCommentStore();
  const [isExpanded, setIsExpanded] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(comment.comment_text);
  const [isSaving, setIsSaving] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const commentRef = useRef<HTMLDivElement>(null);

  // Focus textarea when editing starts
  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.select();
    }
  }, [isEditing]);

  // Scroll into view when focused
  useEffect(() => {
    if (isFocused && commentRef.current) {
      commentRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [isFocused]);

  const statusColors = {
    pending: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
    resolved: 'text-green-400 bg-green-400/10 border-green-400/20',
    applied: 'text-blue-400 bg-blue-400/10 border-blue-400/20',
    submitted: 'text-purple-400 bg-purple-400/10 border-purple-400/20',
  };

  const handleResolve = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await resolveCommentById(comment.id);
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Delete this comment?')) {
      setIsDeleting(true);
      await removeComment(comment.id);
      setIsDeleting(false);
    }
  };

  const handleStartEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsEditing(true);
    setEditText(comment.comment_text);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditText(comment.comment_text);
  };

  const handleSaveEdit = async () => {
    if (!editText.trim()) return;
    setIsSaving(true);
    try {
      await editComment(comment.id, { comment_text: editText });
      setIsEditing(false);
    } catch (err) {
      console.error('Failed to edit comment:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      handleCancelEdit();
    }
  };

  const handleJumpToLine = (e: React.MouseEvent) => {
    e.stopPropagation();
    setFocusedComment(comment.id, comment.file_path, comment.line_number);
  };

  return (
    <div
      ref={commentRef}
      className={cn(
        'border-l-2 transition-all duration-200',
        isFocused
          ? 'bg-blue-600/20 border-blue-500'
          : isSelected
            ? 'bg-blue-600/10 border-blue-500'
            : 'bg-gray-800/30 border-gray-700 hover:border-gray-600 hover:bg-gray-800/50',
        isDeleting && 'opacity-50'
      )}
      onClick={onSelect}
    >
      {/* Comment Header */}
      <div
        className="flex items-start gap-2 px-3 py-2 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <button className="flex-shrink-0 text-gray-500 hover:text-gray-300 transition-colors mt-0.5">
          {isExpanded ? (
            <ChevronDown className="w-3.5 h-3.5" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5" />
          )}
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <MessageSquare className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" />
            <span className="text-xs font-medium text-gray-300">
              Line {comment.line_number}
            </span>
            <span className={cn(
              'text-xs px-1.5 py-0.5 rounded border',
              statusColors[comment.status]
            )}>
              {comment.status}
            </span>
          </div>

          <p className="text-sm text-gray-300 line-clamp-2">
            {isEditing ? (
              <textarea
                ref={textareaRef}
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                onKeyDown={handleKeyDown}
                className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-300 resize-none focus:outline-none focus:border-blue-500"
                rows={3}
                disabled={isSaving}
              />
            ) : (
              comment.comment_text
            )}
          </p>

          <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
            <span>{comment.file_path}</span>
            <span>•</span>
            <span>{formatRelativeTime(comment.created_at)}</span>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="flex items-center gap-1 flex-shrink-0">
          {isEditing ? (
            <>
              <button
                onClick={handleSaveEdit}
                disabled={isSaving || !editText.trim()}
                className={cn(
                  'p-1 rounded transition-colors',
                  isSaving || !editText.trim()
                    ? 'text-gray-600 cursor-not-allowed'
                    : 'text-green-500 hover:text-green-400 hover:bg-green-500/10'
                )}
                title="Save (Ctrl+Enter)"
              >
                <Check className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={handleCancelEdit}
                disabled={isSaving}
                className="p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 rounded transition-colors"
                title="Cancel (Esc)"
              >
                <XIcon className="w-3.5 h-3.5" />
              </button>
            </>
          ) : (
            <>
              <button
                onClick={handleJumpToLine}
                className="p-1 text-purple-500 hover:text-purple-400 hover:bg-purple-500/10 rounded transition-colors"
                title="Jump to line"
              >
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
              {comment.status === 'pending' && (
                <button
                  onClick={handleResolve}
                  className="p-1 text-green-500 hover:text-green-400 hover:bg-green-500/10 rounded transition-colors"
                  title="Resolve comment"
                >
                  <Check className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                onClick={handleStartEdit}
                className="p-1 text-blue-500 hover:text-blue-400 hover:bg-blue-500/10 rounded transition-colors"
                title="Edit comment"
              >
                <Edit2 className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={handleDelete}
                className="p-1 text-red-500 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                title="Delete comment"
                disabled={isDeleting}
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </>
          )}
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-3 pb-3 pt-0 border-t border-gray-700/50">
          {/* Selected Text (if any) */}
          {comment.selected_text && (
            <div className="mt-2 p-2 bg-gray-900/50 rounded border border-gray-700">
              <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
                <FileText className="w-3 h-3" />
                <span>Selected text:</span>
              </div>
              <p className="text-sm text-gray-400 italic line-clamp-3">
                "{comment.selected_text}"
              </p>
            </div>
          )}

          {/* Metadata */}
          <div className="mt-2 flex items-center gap-3 text-xs text-gray-500">
            <span>By: {comment.author}</span>
            <span>•</span>
            <span>
              {new Date(comment.created_at).toLocaleString()}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

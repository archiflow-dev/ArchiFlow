import { MessageSquare } from 'lucide-react';
import { useCommentStore } from '../../store';
import { CommentItem } from './CommentItem';
import { cn } from '../../lib/utils';
import type { Comment } from '../../types';

interface CommentListProps {
  comments?: Comment[];
  onCommentClick?: (comment: Comment) => void;
}

export function CommentList({ comments: externalComments, onCommentClick }: CommentListProps) {
  const {
    comments: storeComments,
    fileComments,
    filterFilePath,
    isLoading,
    error,
    clearFilters,
    refreshComments,
    selectedComment,
    focusedCommentId,
    selectComment,
  } = useCommentStore();

  // Use external comments if provided (for filtered views), otherwise use store
  const displayComments = externalComments || (filterFilePath ? fileComments : storeComments);

  // Group comments by file
  const commentsByFile = displayComments.reduce((acc, comment) => {
    if (!acc[comment.file_path]) {
      acc[comment.file_path] = [];
    }
    acc[comment.file_path].push(comment);
    return acc;
  }, {} as Record<string, typeof displayComments>);

  const handleCommentClick = (comment: Comment) => {
    selectComment(comment);
    onCommentClick?.(comment);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Comments List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {isLoading ? (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">
            <div className="flex flex-col items-center gap-2">
              <div className="w-8 h-8 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
              <span>Loading comments...</span>
            </div>
          </div>
        ) : error ? (
          <div className="p-4 text-center text-red-400 text-sm">
            <p>{error}</p>
            <button
              onClick={refreshComments}
              className="mt-2 px-3 py-1 bg-red-500/10 hover:bg-red-500/20 rounded text-xs transition-colors"
            >
              Retry
            </button>
          </div>
        ) : displayComments.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">
            <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p className="font-medium">No comments yet</p>
            <p className="text-xs mt-1">
              {filterFilePath
                ? 'No comments for this file. Select text in the document to add comments.'
                : 'Select text in the document to add comments'}
            </p>
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {Object.entries(commentsByFile).map(([filePath, fileComments]) => (
              <div key={filePath}>
                {/* File Header */}
                <div className="px-2 py-1 text-xs font-medium text-gray-500 uppercase tracking-wider sticky top-0 bg-gray-900/95 backdrop-blur">
                  {filePath}
                </div>

                {/* Comments for this file */}
                <div className="space-y-1">
                  {fileComments
                    .sort((a, b) => a.line_number - b.line_number)
                    .map((comment) => (
                      <CommentItem
                        key={comment.id}
                        comment={comment}
                        isSelected={selectedComment?.id === comment.id}
                        isFocused={focusedCommentId === comment.id}
                        onSelect={() => handleCommentClick(comment)}
                      />
                    ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

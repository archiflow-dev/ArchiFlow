import { MessageSquare } from 'lucide-react';
import { type Comment } from '../../types';
import { useCommentStore } from '../../store';
import { cn } from '../../lib/utils';

interface CommentMarkerProps {
  comments: Comment[];
  lineNumber: number;
  size?: 'sm' | 'md';
}

export function CommentMarker({ comments, lineNumber, size = 'sm' }: CommentMarkerProps) {
  const { setFocusedComment, openPanel } = useCommentStore();
  const count = comments.length;
  const firstComment = comments[0];

  const handleClick = () => {
    // Open comment panel
    openPanel();
    // Focus the first comment on this line
    setFocusedComment(firstComment.id, firstComment.file_path, lineNumber);
  };

  return (
    <button
      onClick={handleClick}
      className={cn(
        'flex items-center gap-1 rounded transition-colors',
        'bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 border border-blue-500/30',
        size === 'sm' ? 'px-1 py-0.5 text-xs' : 'px-1.5 py-1 text-sm'
      )}
      title={`${count} comment${count !== 1 ? 's' : ''}`}
    >
      <MessageSquare className={cn('flex-shrink-0', size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5')} />
      {count > 1 && <span className="font-medium">{count}</span>}
    </button>
  );
}

interface CommentMarkerGutterProps {
  commentsByLine: Map<number, Comment[]>;
  focusedCommentId: string | null;
  highlightLine: number | null;
  lineCount: number;
}

export function CommentMarkerGutter({ commentsByLine, focusedCommentId, highlightLine, lineCount }: CommentMarkerGutterProps) {
  return (
    <div className="flex-shrink-0 w-16 bg-gray-800/30 select-none border-r border-gray-700/50 sticky top-0 self-start">
      {Array.from({ length: lineCount }, (_, i) => {
        const lineNumber = i + 1;
        const lineComments = commentsByLine.get(lineNumber) || [];
        const isHighlighted = highlightLine === lineNumber;
        const hasFocusedComment = lineComments.some(c => c.id === focusedCommentId);

        return (
          <div
            key={lineNumber}
            className={cn(
              'flex items-center justify-end gap-1 pr-1 h-6',
              isHighlighted && 'bg-blue-500/10',
              hasFocusedComment && 'bg-blue-500/20'
            )}
          >
            <span className="text-xs text-gray-600 font-mono">{lineNumber}</span>
            {lineComments.length > 0 && (
              <CommentMarker
                comments={lineComments}
                lineNumber={lineNumber}
                size="sm"
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

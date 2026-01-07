/**
 * Line-Aware Markdown Preview Component (Redesign)
 * 
 * Implements a "Raw Mode"-like architecture for the Preview.
 * - Renders specific DOM rows for each line of text.
 * - Gutter with Line Number and (+) Add Button.
 * - Stable, standard DOM structure for reliable browser text selection.
 */

import './LineAwareMarkdownPreview.css';
import { useMemo, useRef, useState, useCallback } from 'react';
import { MessageSquarePlus, X } from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

export interface CommentRange {
  lineNumber: number;
  endLineNumber?: number;
  commentId: string;
}

export interface MarkdownPreviewProps {
  content: string;
  filePath?: string;
  onTextSelection?: (selection: { text: string; lineNumber: number; endLineNumber?: number }) => void;
  commentRanges?: CommentRange[];
}

interface SelectionState {
  text: string;
  startLine: number;
  endLine: number;
  popupPosition: { top: number; left: number };
}

// ============================================================================
// Markdown Line Parser
// ============================================================================

/**
 * Transforms a single line of markdown into HTML.
 * Keeping it simple and line-isolated.
 */
function renderLineHtml(content: string): string {
  let html = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Headers
  if (html.match(/^#### /)) return html.replace(/^#### (.+)$/, '<h4>$1</h4>');
  if (html.match(/^### /)) return html.replace(/^### (.+)$/, '<h3>$1</h3>');
  if (html.match(/^## /)) return html.replace(/^## (.+)$/, '<h2>$1</h2>');
  if (html.match(/^# /)) return html.replace(/^# (.+)$/, '<h1>$1</h1>');

  // Blockquotes
  if (html.match(/^&gt; /)) return html.replace(/^&gt; (.+)$/, '<blockquote>$1</blockquote>');

  // Lists
  if (html.match(/^- /)) return html.replace(/^- (.+)$/, '<li>$1</li>');
  if (html.match(/^\d+\. /)) return html.replace(/^\d+\. (.+)$/, '<li>$1</li>');

  // HR
  if (html.match(/^---$/)) return '<hr />';

  // Inline Formatting
  html = html
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');

  return html || '&nbsp;'; // Maintain height for empty lines
}


// ============================================================================
// Sub-Component: Preview Row
// ============================================================================

interface PreviewRowProps {
  lineNum: number;
  content: string;
  isCodeBlock: boolean;
  onAddComment: (lineNum: number, text: string) => void;
  hasComment?: boolean;
}

function PreviewRow({ lineNum, content, isCodeBlock, onAddComment, hasComment }: PreviewRowProps) {
  // If it's a code block fence or content, we might style it differently
  // For now, we mainly ensure the HTML is safely rendered

  const isFence = content.trim().startsWith('```');
  const html = isCodeBlock || isFence
    ? `<pre><code>${content.replace(/</g, '&lt;')}</code></pre>` // Simple code render
    : renderLineHtml(content);

  return (
    <div
      className={`preview-row ${hasComment ? 'has-comment' : ''}`}
      data-line={lineNum}
    >
      <div className="preview-gutter">
        <span className="line-number">{lineNum}</span>
        <button
          className="add-btn"
          onClick={(e) => {
            e.stopPropagation(); // Prevent selection clear
            onAddComment(lineNum, content);
          }}
          title="Add comment to this line"
        >
          <MessageSquarePlus size={14} />
        </button>
      </div>
      <div
        className="preview-content"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}


// ============================================================================
// Main Component
// ============================================================================

export function LineAwareMarkdownPreview({
  content,
  onTextSelection,
  commentRanges = []
}: MarkdownPreviewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [selectionState, setSelectionState] = useState<SelectionState | null>(null);

  // 1. Process Lines
  const lines = useMemo(() => content.split('\n'), [content]);

  // 2. Identify Commented Lines for highlighting
  const commentedLineSet = useMemo(() => {
    const set = new Set<number>();
    commentRanges.forEach(r => {
      const start = r.lineNumber;
      const end = r.endLineNumber || start;
      for (let i = start; i <= end; i++) set.add(i);
    });
    return set;
  }, [commentRanges]);

  // 3. Selection Handler (The "Raw Mode" Logic)
  const handleMouseUp = useCallback(() => {
    if (!onTextSelection) return;

    const winSel = window.getSelection();
    if (!winSel || winSel.rangeCount === 0) return;

    const text = winSel.toString(); // Don't trim immediately, preserve selection fidelity if needed, but trim check is good.
    if (!text.trim()) {
      setSelectionState(null);
      return;
    }

    // Traverse DOM to find start/end lines
    const getDataLine = (node: Node | null): number | null => {
      let el = (node?.nodeType === Node.TEXT_NODE ? node.parentElement : node) as HTMLElement;
      while (el && el !== containerRef.current) {
        if (el.getAttribute?.('data-line')) {
          return parseInt(el.getAttribute('data-line')!);
        }
        el = el.parentElement as HTMLElement;
      }
      return null;
    };

    const startLine = getDataLine(winSel.anchorNode);
    const endLine = getDataLine(winSel.focusNode);

    if (startLine === null || endLine === null) {
      setSelectionState(null);
      return;
    }

    // Normalize order
    const minLine = Math.min(startLine, endLine);
    const maxLine = Math.max(startLine, endLine);

    // Calculate Popup Position
    const range = winSel.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    const containerRect = containerRef.current?.getBoundingClientRect();

    if (!containerRect) return;

    setSelectionState({
      text: text.trim(),
      startLine: minLine,
      endLine: maxLine,
      popupPosition: {
        top: rect.bottom - containerRect.top + 10, // Position BELOW selection
        left: rect.left - containerRect.left + (rect.width / 2)
      }
    });

  }, [onTextSelection]);



  // 4. Add Comment Action
  const handleAddComment = (lineNum: number, lineText: string) => {
    // Direct line add (via + button)
    onTextSelection?.({
      text: lineText,
      lineNumber: lineNum,
      endLineNumber: lineNum
    });
  };

  const handleSelectionAdd = () => {
    if (!selectionState || !onTextSelection) return;
    onTextSelection({
      text: selectionState.text,
      lineNumber: selectionState.startLine,
      endLineNumber: selectionState.endLine
    });
    setSelectionState(null);
    window.getSelection()?.removeAllRanges();
  };

  // 5. Render Rows
  // Track code block state
  let inCodeBlock = false;

  return (
    <div
      className="line-aware-preview"
      ref={containerRef}
      onMouseUp={handleMouseUp}
    >
      {lines.map((lineContent, index) => {
        const lineNum = index + 1;

        // Simple code block state tracking
        if (lineContent.trim().startsWith('```')) {
          // If closing a block, this line is still 'in' (or fence), 
          // but next line is out. Actually fence is usually colored.
          // Logic: Toggle. 
          // If currently false, this starts it. 
          // If currently true, this ends it.
          inCodeBlock = !inCodeBlock;
        }

        return (
          <PreviewRow
            key={lineNum}
            lineNum={lineNum}
            content={lineContent}
            isCodeBlock={inCodeBlock && !lineContent.trim().startsWith('```')} // content *inside* block
            onAddComment={handleAddComment}
            hasComment={commentedLineSet.has(lineNum)}
          />
        );
      })}

      {/* Selection Popup */}
      {selectionState && (
        <div
          className="markdown-selection-popup absolute z-50 bg-gray-700 border border-blue-500 rounded-lg shadow-xl p-2 flex gap-2 items-center"
          onMouseUp={(e) => e.stopPropagation()}
          style={{
            top: selectionState.popupPosition.top, // Correct position from state
            left: selectionState.popupPosition.left,
            transform: 'translateX(-50%)'
          }}
        >
          <span className="text-xs text-gray-300 whitespace-nowrap max-w-[200px] truncate">
            "{selectionState.text}"
          </span>
          <button
            onClick={handleSelectionAdd}
            className="flex items-center gap-1 px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded transition-colors"
          >
            <MessageSquarePlus className="w-3 h-3" />
            Add Comment
          </button>
          <button
            onClick={() => {
              setSelectionState(null);
              window.getSelection()?.removeAllRanges();
            }}
            className="p-1 text-gray-400 hover:text-white"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      )}
    </div>
  );
}

import { useState, useMemo, useEffect, useRef } from 'react';
import {
  X,
  Edit3,
  Save,
  Copy,
  Download,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  FileText,
  FileJson,
  FileImage,
  FileCode,
  Eye,
  Code,
  Columns,
  Loader2,
  MessageSquare,
} from 'lucide-react';
import { useWorkspaceStore } from '../../store/workspaceStore';
import { useSessionStore, useCommentStore } from '../../store';
import { useUIStore } from '../../store/uiStore';
import { Button } from '../Common/Button';
import { CommentMarkerGutter } from '../Comment';
import { cn } from '../../lib/utils';

// View modes for different content types
type ViewMode = 'preview' | 'source' | 'split';

// Get file extension
const getFileExtension = (path: string): string => {
  return path.split('.').pop()?.toLowerCase() || '';
};

// Determine if file is editable
const isEditable = (file: { extension?: string }): boolean => {
  const ext = file.extension?.toLowerCase();
  return ['md', 'txt', 'json', 'tsx', 'ts', 'jsx', 'js', 'css', 'html', 'py', 'rst'].includes(ext || '');
};

// Markdown Preview Component
function MarkdownPreview({ content }: { content: string }) {
  // Simple markdown rendering (in production, use react-markdown or similar)
  const html = useMemo(() => {
    return content
      // Headers
      .replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold text-gray-200 mt-4 mb-2">$1</h3>')
      .replace(/^## (.+)$/gm, '<h2 class="text-xl font-semibold text-gray-100 mt-6 mb-3">$1</h2>')
      .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold text-white mt-8 mb-4">$1</h1>')
      // Bold and italic
      .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-gray-100">$1</strong>')
      .replace(/\*(.+?)\*/g, '<em class="italic">$1</em>')
      // Code blocks
      .replace(/```(\w+)?\n([\s\S]+?)```/g, '<pre class="bg-gray-800 rounded-lg p-4 my-3 overflow-x-auto"><code class="text-sm text-green-400">$2</code></pre>')
      // Inline code
      .replace(/`([^`]+)`/g, '<code class="bg-gray-800 px-1.5 py-0.5 rounded text-sm text-yellow-400">$1</code>')
      // Links
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-blue-400 hover:underline" target="_blank" rel="noopener noreferrer">$1</a>')
      // Lists
      .replace(/^- (.+)$/gm, '<li class="ml-4 text-gray-300">$1</li>')
      .replace(/^\d+\. (.+)$/gm, '<li class="ml-4 text-gray-300 list-decimal">$1</li>')
      // Blockquotes
      .replace(/^> (.+)$/gm, '<blockquote class="border-l-4 border-gray-600 pl-4 py-1 my-2 text-gray-400 italic">$1</blockquote>')
      // Horizontal rule
      .replace(/^---$/gm, '<hr class="border-gray-700 my-6" />')
      // Paragraphs (simple: treat double newlines as paragraph breaks)
      .replace(/\n\n/g, '</p><p class="my-3 text-gray-300">')
      // Single newlines within paragraphs
      .replace(/\n/g, '<br />');

    return `<p class="my-3 text-gray-300">${content}</p>`;
  }, [content]);

  return (
    <div
      className="prose prose-invert max-w-none markdown-preview"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

// JSON Preview Component
function JsonPreview({ content }: { content: string }) {
  const formatted = useMemo(() => {
    try {
      const parsed = JSON.parse(content);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return content;
    }
  }, [content]);

  return (
    <pre className="json-preview text-sm font-mono whitespace-pre-wrap">
      {formatted}
    </pre>
  );
}

// Image Preview Component
function ImagePreview({ src, alt }: { src: string; alt: string }) {
  const [zoom, setZoom] = useState(1);

  return (
    <div className="relative h-full flex flex-col">
      {/* Image controls */}
      <div className="flex-shrink-0 flex items-center gap-2 p-2 bg-gray-800/50 border-b border-gray-700">
        <Button variant="ghost" size="sm" onClick={() => setZoom(z => Math.max(0.25, z - 0.25))}>
          <ZoomOut className="w-4 h-4" />
        </Button>
        <span className="text-xs text-gray-400 min-w-[4rem] text-center">{Math.round(zoom * 100)}%</span>
        <Button variant="ghost" size="sm" onClick={() => setZoom(z => Math.min(4, z + 0.25))}>
          <ZoomIn className="w-4 h-4" />
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setZoom(1)}>
          <RotateCcw className="w-4 h-4" />
        </Button>
      </div>

      {/* Image display */}
      <div className="flex-1 overflow-auto flex items-center justify-center bg-[#1a1a1a] p-4">
        <img
          src={src}
          alt={alt}
          style={{
            transform: `scale(${zoom})`,
            maxWidth: '100%',
            maxHeight: '100%',
            objectFit: 'contain'
          }}
          className="transition-transform duration-150"
        />
      </div>
    </div>
  );
}

// Code Editor Component
function CodeEditor({
  content,
  isEditing,
  onChange,
  filePath,
  comments,
  onTextSelection
}: {
  content: string;
  isEditing: boolean;
  onChange: (value: string) => void;
  filePath?: string;
  comments?: import('../../types').Comment[];
  onTextSelection?: (selection: { text: string; lineNumber: number }) => void;
}) {
  const { focusedCommentId, highlightLine, clearFocus } = useCommentStore();
  const lines = content.split('\n');
  const preRef = useRef<HTMLPreElement>(null);
  const codeWrapperRef = useRef<HTMLDivElement>(null);
  const [selectionPopup, setSelectionPopup] = useState<{
    text: string;
    lineNumber: number;
    position: { top: number; left: number };
  } | null>(null);

  // Scroll to highlighted line
  useEffect(() => {
    if (highlightLine !== null && codeWrapperRef.current) {
      // Get the gutter to find line elements
      const gutter = codeWrapperRef.current.children[0];
      if (gutter && gutter.children[highlightLine - 1]) {
        const lineElement = gutter.children[highlightLine - 1];
        lineElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // Clear highlight after scroll
        setTimeout(() => clearFocus(), 2000);
      }
    }
  }, [highlightLine, clearFocus]);

  // Group comments by line number for the current file
  const commentsByLine = useMemo(() => {
    const map = new Map<number, import('../../types').Comment[]>();
    comments?.forEach(comment => {
      if (comment.file_path === filePath) {
        if (!map.has(comment.line_number)) {
          map.set(comment.line_number, []);
        }
        map.get(comment.line_number)!.push(comment);
      }
    });
    return map;
  }, [comments, filePath]);

  // Handle text selection
  const handleMouseUp = () => {
    if (!onTextSelection || isEditing) return;

    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;

    const range = selection.getRangeAt(0);
    const selectedText = selection.toString().trim();

    if (!selectedText) {
      setSelectionPopup(null);
      return;
    }

    // Find the line number of the selection
    const preNode = preRef.current;
    if (!preNode) return;

    const rangeAt = (node: Node | null, offset: number): number => {
      if (!node) return 0;
      if (node === preNode) return offset;

      let count = 0;
      const walker = document.createTreeWalker(
        preNode,
        NodeFilter.SHOW_TEXT,
        null
      );

      let currentNode: Node | null;
      while (currentNode = walker.nextNode()) {
        if (currentNode === node) {
          return count + offset;
        }
        count += currentNode.textContent?.length || 0;
      }

      return count;
    };

    const startOffset = rangeAt(range.startContainer, range.startOffset);
    const textBeforeSelection = content.substring(0, startOffset);
    const lineNumber = textBeforeSelection.split('\n').length;

    // Calculate popup position
    const rect = range.getBoundingClientRect();
    const preRect = preNode.getBoundingClientRect();

    setSelectionPopup({
      text: selectedText,
      lineNumber,
      position: {
        top: rect.top - preRect.top - 40,
        left: rect.left - preRect.left + rect.width / 2,
      }
    });
  };

  // Handle adding comment from selection
  const handleAddComment = () => {
    if (!selectionPopup || !onTextSelection) return;
    onTextSelection({
      text: selectionPopup.text,
      lineNumber: selectionPopup.lineNumber
    });
    setSelectionPopup(null);
    // Clear selection
    window.getSelection()?.removeAllRanges();
  };

  if (isEditing) {
    return (
      <div className="h-full flex">
        {/* Line numbers with comment markers */}
        <CommentMarkerGutter
          commentsByLine={commentsByLine}
          focusedCommentId={focusedCommentId}
          highlightLine={highlightLine}
          lineCount={lines.length}
        />
        {/* Editor */}
        <textarea
          value={content}
          onChange={(e) => onChange(e.target.value)}
          className="flex-1 bg-transparent font-mono text-sm text-gray-200 p-4 resize-none outline-none leading-6"
          spellCheck={false}
        />
      </div>
    );
  }

  return (
    <div ref={codeWrapperRef} className="h-full flex relative overflow-auto">
      {/* Line numbers with comment markers */}
      <CommentMarkerGutter
        commentsByLine={commentsByLine}
        focusedCommentId={focusedCommentId}
        highlightLine={highlightLine}
        lineCount={lines.length}
      />
      {/* Code */}
      <pre
        ref={preRef}
        className="flex-1 font-mono text-sm text-gray-200 p-4 leading-6"
        onMouseUp={handleMouseUp}
      >
        <code>{content}</code>
      </pre>

      {/* Selection Popup */}
      {selectionPopup && !isEditing && (
        <div
          className="absolute z-50 bg-gray-700 border border-blue-500 rounded-lg shadow-xl p-2"
          style={{
            top: selectionPopup.position.top,
            left: selectionPopup.position.left,
            transform: 'translateX(-50%)'
          }}
        >
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-300 max-w-xs truncate">
              "{selectionPopup.text.slice(0, 50)}{selectionPopup.text.length > 50 ? '...' : ''}"
            </span>
            <button
              onClick={handleAddComment}
              className="flex items-center gap-1 px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded transition-colors"
            >
              <MessageSquare className="w-3 h-3" />
              <span>Add Comment</span>
            </button>
            <button
              onClick={() => setSelectionPopup(null)}
              className="p-1 text-gray-400 hover:text-white transition-colors"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Empty State Component
function EmptyState() {
  return (
    <div className="h-full flex items-center justify-center bg-gray-900">
      <div className="text-center max-w-md px-8">
        <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gray-800 flex items-center justify-center">
          <FileText className="w-8 h-8 text-gray-600" />
        </div>
        <h3 className="text-lg font-medium text-gray-400 mb-2">No file selected</h3>
        <p className="text-sm text-gray-600">
          Select a file from the Explorer panel to view its contents.
        </p>
        <div className="mt-6 flex items-center justify-center gap-4 text-xs text-gray-600">
          <div className="flex items-center gap-1.5">
            <FileText className="w-4 h-4" />
            <span>Documents</span>
          </div>
          <div className="flex items-center gap-1.5">
            <FileCode className="w-4 h-4" />
            <span>Code</span>
          </div>
          <div className="flex items-center gap-1.5">
            <FileImage className="w-4 h-4" />
            <span>Images</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// Loading State Component
function LoadingState() {
  return (
    <div className="h-full flex items-center justify-center bg-gray-900">
      <div className="text-center">
        <Loader2 className="w-8 h-8 mx-auto mb-4 text-blue-500 animate-spin" />
        <p className="text-sm text-gray-500">Loading file content...</p>
      </div>
    </div>
  );
}

// Tab Bar Component
function TabBar({
  file,
  onClose,
  viewMode,
  setViewMode
}: {
  file: { name: string; extension?: string; path: string };
  onClose: () => void;
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
}) {
  const ext = file.extension || getFileExtension(file.path);

  return (
    <div className="flex-shrink-0 h-9 bg-gray-800 border-b border-gray-700 flex items-center justify-between">
      {/* Tab */}
      <div className="flex items-center">
        <div className={cn(
          'flex items-center gap-2 px-3 h-9 border-r border-gray-700',
          'bg-gray-900 text-gray-200'
        )}>
          {ext === 'md' && <FileText className="w-4 h-4 text-blue-400" />}
          {ext === 'json' && <FileJson className="w-4 h-4 text-yellow-400" />}
          {['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext) && <FileImage className="w-4 h-4 text-purple-400" />}
          {['tsx', 'ts', 'jsx', 'js', 'py', 'css', 'html'].includes(ext) && <FileCode className="w-4 h-4 text-green-400" />}
          <span className="text-sm">{file.name}</span>
          <button
            onClick={onClose}
            className="ml-1 p-0.5 text-gray-500 hover:text-gray-300 hover:bg-gray-700 rounded transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* View mode toggle (for markdown) */}
      {ext === 'md' && (
        <div className="flex items-center gap-1 px-2">
          <Button
            variant={viewMode === 'source' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setViewMode('source')}
            title="Raw mode"
          >
            <Code className="w-4 h-4" />
          </Button>
          <Button
            variant={viewMode === 'preview' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setViewMode('preview')}
            title="Preview mode"
          >
            <Eye className="w-4 h-4" />
          </Button>
          <Button
            variant={viewMode === 'split' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setViewMode('split')}
            title="Split view"
          >
            <Columns className="w-4 h-4" />
          </Button>
        </div>
      )}
    </div>
  );
}

// Action Bar Component
function ActionBar({
  file,
  onCopy,
  onDownload
}: {
  file: { name: string };
  onCopy: () => void;
  onDownload: () => void;
}) {
  return (
    <div className="flex-shrink-0 h-10 px-3 bg-gray-800/50 border-t border-gray-700 flex items-center justify-end">
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="sm" onClick={onCopy} title="Copy to clipboard">
          <Copy className="w-4 h-4" />
        </Button>
        <Button variant="ghost" size="sm" onClick={onDownload} title="Download file">
          <Download className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}

export function DisplayPanel() {
  const { currentSession } = useSessionStore();
  const {
    selectedFile,
    fileContent,
    isLoading,
    error,
    viewMode,
    loadFileContent,
    selectFile,
    setViewMode,
  } = useWorkspaceStore();
  const { comments, setFilterFilePath, setPendingSelection: setCommentPendingSelection } = useCommentStore();
  const { setCommentPanelOpen } = useUIStore();

  const [localViewMode, setLocalViewMode] = useState<ViewMode>('preview');

  // Load file content when a file is selected
  useEffect(() => {
    if (selectedFile?.path) {
      loadFileContent(selectedFile.path);
    }
  }, [selectedFile?.path]);

  // Sync view mode with store
  useEffect(() => {
    if (viewMode) {
      setLocalViewMode(viewMode);
    }
  }, [viewMode]);

  if (!selectedFile) {
    return <EmptyState />;
  }

  if (isLoading) {
    return <LoadingState />;
  }

  if (error && !fileContent) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-900">
        <div className="text-center text-red-400">
          <p>{error}</p>
        </div>
      </div>
    );
  }

  const ext = selectedFile.extension || getFileExtension(selectedFile.path);
  const content = fileContent || '';

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = selectedFile.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleClose = () => {
    selectFile(null);
  };

  const handleViewModeChange = (mode: ViewMode) => {
    setLocalViewMode(mode);
    setViewMode(mode);
  };

  // Handle text selection for commenting
  const handleTextSelection = (selection: { text: string; lineNumber: number }) => {
    setCommentPendingSelection({
      filePath: selectedFile.path,
      lineNumber: selection.lineNumber,
      selectedText: selection.text
    });
    // Open comment panel
    setCommentPanelOpen(true);
    // Set filter to current file
    setFilterFilePath(selectedFile.path);
  };

  // Render content based on type
  const renderContent = () => {
    // Image files
    if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) {
      // For images, we'd need to construct the URL
      // For now, show a placeholder
      return (
        <div className="h-full flex items-center justify-center bg-gray-900">
          <div className="text-center text-gray-500">
            <FileImage className="w-12 h-12 mx-auto mb-2" />
            <p>Image preview not available</p>
            <p className="text-xs mt-1">Use download to view the image</p>
          </div>
        </div>
      );
    }

    // Markdown files
    if (ext === 'md' || ext === 'rst') {
      if (localViewMode === 'preview') {
        return (
          <div className="h-full overflow-auto p-6">
            <MarkdownPreview content={content} />
          </div>
        );
      }
      if (localViewMode === 'split') {
        return (
          <div className="h-full flex">
            <div className="w-1/2 border-r border-gray-700 overflow-auto">
              <CodeEditor
                content={content}
                isEditing={false}
                onChange={() => {}}
                filePath={selectedFile.path}
                comments={comments}
                onTextSelection={handleTextSelection}
              />
            </div>
            <div className="w-1/2 overflow-auto p-6">
              <MarkdownPreview content={content} />
            </div>
          </div>
        );
      }
      // Source mode
      return (
        <div className="h-full overflow-auto">
          <CodeEditor
            content={content}
            isEditing={false}
            onChange={() => {}}
            filePath={selectedFile.path}
            comments={comments}
            onTextSelection={handleTextSelection}
          />
        </div>
      );
    }

    // JSON files
    if (ext === 'json') {
      return (
        <div className="h-full overflow-auto p-6">
          <JsonPreview content={content} />
        </div>
      );
    }

    // Code files
    if (['tsx', 'ts', 'jsx', 'js', 'py', 'css', 'html', 'yaml', 'yml'].includes(ext)) {
      return (
        <div className="h-full overflow-auto">
          <CodeEditor
            content={content}
            isEditing={false}
            onChange={() => {}}
            filePath={selectedFile.path}
            comments={comments}
            onTextSelection={handleTextSelection}
          />
        </div>
      );
    }

    // Default: plain text
    return (
      <div className="h-full overflow-auto p-6">
        <pre className="font-mono text-sm text-gray-300 whitespace-pre-wrap">{content}</pre>
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col">
      <TabBar
        file={selectedFile}
        onClose={handleClose}
        viewMode={localViewMode}
        setViewMode={handleViewModeChange}
      />

      <div className="flex-1 overflow-hidden">
        {renderContent()}
      </div>

      <ActionBar
        file={selectedFile}
        onCopy={handleCopy}
        onDownload={handleDownload}
      />
    </div>
  );
}

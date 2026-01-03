import { useState, useMemo } from 'react';
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
  Columns
} from 'lucide-react';
import { useArtifactStore } from '../../store/artifactStore';
import type { Artifact } from '../../types';
import { Button } from '../Common/Button';
import { cn } from '../../lib/utils';

// View modes for different content types
type ViewMode = 'preview' | 'source' | 'split';

// Get file extension
const getFileExtension = (path: string): string => {
  return path.split('.').pop()?.toLowerCase() || '';
};

// Determine if file is editable
const isEditable = (artifact: Artifact): boolean => {
  const ext = getFileExtension(artifact.path);
  return ['md', 'txt', 'json', 'tsx', 'ts', 'jsx', 'js', 'css', 'html', 'py'].includes(ext);
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
function ImagePreview({ artifact }: { artifact: Artifact }) {
  const [zoom, setZoom] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });

  // Use content as base64 or path as URL
  const imageSrc = artifact.content?.startsWith('data:')
    ? artifact.content
    : artifact.path;

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
        <Button variant="ghost" size="sm" onClick={() => { setZoom(1); setPosition({ x: 0, y: 0 }); }}>
          <RotateCcw className="w-4 h-4" />
        </Button>
      </div>

      {/* Image display */}
      <div className="flex-1 overflow-auto flex items-center justify-center bg-[#1a1a1a] p-4">
        <img
          src={imageSrc}
          alt={artifact.name || artifact.path}
          style={{
            transform: `scale(${zoom}) translate(${position.x}px, ${position.y}px)`,
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

// Code Editor Component (simplified)
function CodeEditor({
  content,
  isEditing,
  onChange
}: {
  content: string;
  isEditing: boolean;
  onChange: (value: string) => void;
}) {
  const lines = content.split('\n');

  if (isEditing) {
    return (
      <div className="h-full flex">
        {/* Line numbers */}
        <div className="flex-shrink-0 w-12 bg-gray-800/50 text-right pr-2 py-4 select-none">
          {lines.map((_, i) => (
            <div key={i} className="text-xs text-gray-600 leading-6">
              {i + 1}
            </div>
          ))}
        </div>
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
    <div className="h-full flex overflow-auto">
      {/* Line numbers */}
      <div className="flex-shrink-0 w-12 bg-gray-800/50 text-right pr-2 py-4 select-none">
        {lines.map((_, i) => (
          <div key={i} className="text-xs text-gray-600 leading-6">
            {i + 1}
          </div>
        ))}
      </div>
      {/* Code */}
      <pre className="flex-1 font-mono text-sm text-gray-200 p-4 leading-6">
        <code>{content}</code>
      </pre>
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
          Select a file from the Explorer panel to view or edit its contents.
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

// Tab Bar Component
function TabBar({
  artifact,
  hasChanges,
  onClose,
  viewMode,
  setViewMode
}: {
  artifact: Artifact;
  hasChanges: boolean;
  onClose: () => void;
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
}) {
  const fileName = artifact.path.split('/').pop() || artifact.path;
  const ext = getFileExtension(artifact.path);

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
          <span className="text-sm">{fileName}</span>
          {hasChanges && <span className="w-2 h-2 rounded-full bg-blue-500" />}
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
          >
            <Code className="w-4 h-4" />
          </Button>
          <Button
            variant={viewMode === 'preview' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setViewMode('preview')}
          >
            <Eye className="w-4 h-4" />
          </Button>
          <Button
            variant={viewMode === 'split' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setViewMode('split')}
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
  artifact,
  isEditing,
  hasChanges,
  onEdit,
  onSave,
  onCancel,
  onCopy,
  onDownload
}: {
  artifact: Artifact;
  isEditing: boolean;
  hasChanges: boolean;
  onEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
  onCopy: () => void;
  onDownload: () => void;
}) {
  const canEdit = isEditable(artifact);

  return (
    <div className="flex-shrink-0 h-10 px-3 bg-gray-800/50 border-t border-gray-700 flex items-center justify-between">
      <div className="flex items-center gap-2">
        {isEditing ? (
          <>
            <Button variant="primary" size="sm" onClick={onSave} disabled={!hasChanges}>
              <Save className="w-4 h-4 mr-1.5" />
              Save
            </Button>
            <Button variant="ghost" size="sm" onClick={onCancel}>
              Cancel
            </Button>
          </>
        ) : (
          canEdit && (
            <Button variant="ghost" size="sm" onClick={onEdit}>
              <Edit3 className="w-4 h-4 mr-1.5" />
              Edit
            </Button>
          )
        )}
      </div>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="sm" onClick={onCopy}>
          <Copy className="w-4 h-4" />
        </Button>
        <Button variant="ghost" size="sm" onClick={onDownload}>
          <Download className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}

export function DisplayPanel() {
  const {
    selectedArtifact,
    isEditing,
    editedContent,
    selectArtifact,
    startEditing,
    saveEdit,
    cancelEdit,
    updateEditedContent
  } = useArtifactStore();
  const [viewMode, setViewMode] = useState<ViewMode>('preview');

  if (!selectedArtifact) {
    return <EmptyState />;
  }

  const ext = getFileExtension(selectedArtifact.path);
  const content = isEditing ? editedContent : (selectedArtifact.content || '');
  const hasChanges = isEditing && editedContent !== selectedArtifact.content;

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
    a.download = selectedArtifact.path.split('/').pop() || 'file';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleClose = () => {
    if (isEditing) {
      cancelEdit();
    }
    selectArtifact(null);
  };

  const handleEdit = () => {
    startEditing(selectedArtifact);
  };

  const handleSave = () => {
    saveEdit();
  };

  const handleCancel = () => {
    cancelEdit();
  };

  const handleContentChange = (newContent: string) => {
    updateEditedContent(newContent);
  };

  // Render content based on type
  const renderContent = () => {
    // Image files
    if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) {
      return <ImagePreview artifact={selectedArtifact} />;
    }

    // Markdown files
    if (ext === 'md') {
      if (viewMode === 'preview') {
        return (
          <div className="h-full overflow-auto p-6">
            <MarkdownPreview content={content} />
          </div>
        );
      }
      if (viewMode === 'split') {
        return (
          <div className="h-full flex">
            <div className="w-1/2 border-r border-gray-700 overflow-auto">
              <CodeEditor
                content={content}
                isEditing={isEditing}
                onChange={handleContentChange}
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
            isEditing={isEditing}
            onChange={handleContentChange}
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
    if (['tsx', 'ts', 'jsx', 'js', 'py', 'css', 'html'].includes(ext)) {
      return (
        <div className="h-full overflow-auto">
          <CodeEditor
            content={content}
            isEditing={isEditing}
            onChange={handleContentChange}
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
        artifact={selectedArtifact}
        hasChanges={hasChanges}
        onClose={handleClose}
        viewMode={viewMode}
        setViewMode={setViewMode}
      />

      <div className="flex-1 overflow-hidden">
        {renderContent()}
      </div>

      <ActionBar
        artifact={selectedArtifact}
        isEditing={isEditing}
        hasChanges={hasChanges}
        onEdit={handleEdit}
        onSave={handleSave}
        onCancel={handleCancel}
        onCopy={handleCopy}
        onDownload={handleDownload}
      />
    </div>
  );
}

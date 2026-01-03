import { useState, useMemo } from 'react';
import {
  ChevronRight,
  ChevronDown,
  File,
  FileText,
  FileImage,
  FileJson,
  FileCode,
  Folder,
  FolderOpen,
  Search,
  Plus,
  RefreshCw
} from 'lucide-react';
import { useArtifactStore } from '../../store/artifactStore';
import type { Artifact } from '../../types';
import { cn, formatFileSize } from '../../lib/utils';

// File type icons mapping
const getFileIcon = (artifact: Artifact) => {
  const ext = artifact.path.split('.').pop()?.toLowerCase();

  switch (ext) {
    case 'md':
    case 'txt':
      return FileText;
    case 'json':
      return FileJson;
    case 'png':
    case 'jpg':
    case 'jpeg':
    case 'gif':
    case 'webp':
    case 'svg':
      return FileImage;
    case 'tsx':
    case 'ts':
    case 'jsx':
    case 'js':
    case 'py':
    case 'css':
    case 'html':
      return FileCode;
    default:
      return File;
  }
};

// Group artifacts by folder
function groupArtifactsByFolder(artifacts: Artifact[]): Map<string, Artifact[]> {
  const groups = new Map<string, Artifact[]>();

  artifacts.forEach(artifact => {
    const parts = artifact.path.split('/');
    const folder = parts.length > 1 ? parts.slice(0, -1).join('/') : '/';

    if (!groups.has(folder)) {
      groups.set(folder, []);
    }
    groups.get(folder)!.push(artifact);
  });

  return groups;
}

interface FolderNodeProps {
  name: string;
  artifacts: Artifact[];
  level: number;
  isExpanded: boolean;
  onToggle: () => void;
}

function FolderNode({ name, artifacts, level, isExpanded, onToggle }: FolderNodeProps) {
  const { selectedArtifact, selectArtifact } = useArtifactStore();

  return (
    <div>
      {/* Folder header */}
      <button
        onClick={onToggle}
        className={cn(
          'w-full flex items-center gap-1.5 px-2 py-1 text-sm text-gray-300 hover:bg-gray-700/50 transition-colors',
        )}
        style={{ paddingLeft: `${level * 12 + 8}px` }}
      >
        {isExpanded ? (
          <ChevronDown className="w-4 h-4 text-gray-500 flex-shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-500 flex-shrink-0" />
        )}
        {isExpanded ? (
          <FolderOpen className="w-4 h-4 text-yellow-500 flex-shrink-0" />
        ) : (
          <Folder className="w-4 h-4 text-yellow-500 flex-shrink-0" />
        )}
        <span className="truncate font-medium">{name}</span>
        <span className="text-xs text-gray-500 ml-auto">{artifacts.length}</span>
      </button>

      {/* Folder contents */}
      {isExpanded && (
        <div>
          {artifacts.map(artifact => {
            const FileIcon = getFileIcon(artifact);
            const fileName = artifact.path.split('/').pop() || artifact.path;
            const isSelected = selectedArtifact?.id === artifact.id;

            return (
              <button
                key={artifact.id}
                onClick={() => selectArtifact(artifact)}
                className={cn(
                  'w-full flex items-center gap-1.5 px-2 py-1 text-sm transition-colors',
                  isSelected
                    ? 'bg-blue-600/30 text-white border-l-2 border-blue-500'
                    : 'text-gray-400 hover:bg-gray-700/50 hover:text-gray-200'
                )}
                style={{ paddingLeft: `${(level + 1) * 12 + 8}px` }}
              >
                <FileIcon className={cn(
                  'w-4 h-4 flex-shrink-0',
                  artifact.type === 'image' ? 'text-purple-400' :
                  artifact.type === 'json' ? 'text-yellow-400' :
                  artifact.type === 'markdown' ? 'text-blue-400' :
                  'text-gray-400'
                )} />
                <span className="truncate">{fileName}</span>
                {artifact.size && (
                  <span className="text-xs text-gray-600 ml-auto">
                    {formatFileSize(artifact.size)}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function ArtifactOutlinePanel() {
  const { artifacts, selectedArtifact } = useArtifactStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(['/']));

  // Filter and group artifacts
  const filteredArtifacts = useMemo(() => {
    if (!searchQuery.trim()) return artifacts;

    const query = searchQuery.toLowerCase();
    return artifacts.filter(a =>
      a.path.toLowerCase().includes(query) ||
      a.name?.toLowerCase().includes(query)
    );
  }, [artifacts, searchQuery]);

  const groupedArtifacts = useMemo(() =>
    groupArtifactsByFolder(filteredArtifacts),
    [filteredArtifacts]
  );

  const toggleFolder = (path: string) => {
    setExpandedFolders(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  // Sort folders: root first, then alphabetically
  const sortedFolders = useMemo(() => {
    const folders = Array.from(groupedArtifacts.keys());
    return folders.sort((a, b) => {
      if (a === '/') return -1;
      if (b === '/') return 1;
      return a.localeCompare(b);
    });
  }, [groupedArtifacts]);

  return (
    <div className="h-full flex flex-col">
      {/* Panel Header */}
      <div className="flex-shrink-0 h-9 px-3 flex items-center justify-between border-b border-gray-700 bg-gray-800/50">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Explorer
        </span>
        <div className="flex items-center gap-1">
          <button
            className="p-1 text-gray-500 hover:text-gray-300 transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            className="p-1 text-gray-500 hover:text-gray-300 transition-colors"
            title="New File"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="flex-shrink-0 p-2 border-b border-gray-700/50">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search files..."
            className="w-full pl-8 pr-3 py-1.5 text-sm bg-gray-800 border border-gray-700 rounded text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50"
          />
        </div>
      </div>

      {/* Artifacts Tree */}
      <div className="flex-1 overflow-y-auto py-1 custom-scrollbar">
        {artifacts.length === 0 ? (
          <div className="px-4 py-8 text-center text-gray-500 text-sm">
            <Folder className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No artifacts yet</p>
            <p className="text-xs mt-1">Artifacts will appear here as they are created</p>
          </div>
        ) : filteredArtifacts.length === 0 ? (
          <div className="px-4 py-8 text-center text-gray-500 text-sm">
            <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No matching files</p>
          </div>
        ) : (
          <div>
            {sortedFolders.map(folder => {
              const folderArtifacts = groupedArtifacts.get(folder)!;
              const folderName = folder === '/' ? 'Artifacts' : folder.split('/').pop() || folder;

              return (
                <FolderNode
                  key={folder}
                  name={folderName}
                  artifacts={folderArtifacts}
                  level={0}
                  isExpanded={expandedFolders.has(folder) || searchQuery.length > 0}
                  onToggle={() => toggleFolder(folder)}
                />
              );
            })}
          </div>
        )}
      </div>

      {/* Panel Footer - Selected file info */}
      {selectedArtifact && (
        <div className="flex-shrink-0 px-3 py-2 border-t border-gray-700 bg-gray-800/30">
          <div className="text-xs text-gray-400 truncate">
            <span className="text-gray-500">Selected:</span>{' '}
            <span className="text-gray-300">{selectedArtifact.path}</span>
          </div>
          {selectedArtifact.size && (
            <div className="text-xs text-gray-500 mt-0.5">
              {formatFileSize(selectedArtifact.size)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

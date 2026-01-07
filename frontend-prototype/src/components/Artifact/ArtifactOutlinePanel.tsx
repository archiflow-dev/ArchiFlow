import { useState, useMemo, useEffect } from 'react';
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
  RefreshCw
} from 'lucide-react';
import { useWorkspaceStore } from '../../store/workspaceStore';
import { useSessionStore } from '../../store/sessionStore';
import { cn, formatFileSize } from '../../lib/utils';

// File type icons mapping
const getFileIcon = (file: { name: string; extension?: string; type: string }) => {
  const ext = file.extension?.toLowerCase();

  if (file.type === 'directory') {
    return Folder;
  }

  switch (ext) {
    case 'md':
    case 'txt':
    case 'rst':
      return FileText;
    case 'json':
    case 'yaml':
    case 'yml':
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
    case 'scss':
      return FileCode;
    default:
      return File;
  }
};

interface FolderNodeProps {
  name: string;
  path: string;
  files: any[];
  level: number;
  isExpanded: boolean;
  onFileClick: (file: any) => void;
  selectedPath: string | null;
}

function FolderNode({ name, path, files, level, isExpanded, onFileClick, selectedPath }: FolderNodeProps) {
  const { expandedFolders, toggleFolder } = useWorkspaceStore();

  // Separate directories and files at the current level only
  const directories = files.filter(f => f.type === 'directory');

  // Only include files that are directly in this folder (not in subdirectories)
  const regularFiles = files.filter(f => {
    if (f.type !== 'file') return false;

    // For root folder (empty path), files should have no '/' in their path
    if (path === '') {
      return !f.path.includes('/');
    }

    // For subfolders, file path should be exactly {path}/{filename}
    // Remove the folder path prefix and check there are no additional '/'
    const relativePath = f.path.slice(path.length + 1); // +1 to skip the '/'
    return !relativePath.includes('/');
  });

  return (
    <div>
      {/* Folder header */}
      {name !== '/' && (
        <button
          onClick={() => toggleFolder(path)}
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
          <span className="text-xs text-gray-500 ml-auto">{files.length}</span>
        </button>
      )}

      {/* Folder contents */}
      {isExpanded && (
        <div>
          {/* Subdirectories */}
          {directories.map(dir => {
            const dirPath = dir.path;
            const dirExpanded = expandedFolders.has(dirPath);

            return (
              <FolderNode
                key={dirPath}
                name={dir.name}
                path={dirPath}
                files={files.filter(f => f.path.startsWith(dirPath + '/'))}
                level={name === '/' ? level : level + 1}
                isExpanded={dirExpanded}
                onFileClick={onFileClick}
                selectedPath={selectedPath}
              />
            );
          })}

          {/* Regular files */}
          {regularFiles.map(file => {
            const FileIcon = getFileIcon(file);
            const isSelected = selectedPath === file.path;

            return (
              <button
                key={file.path}
                onClick={() => onFileClick(file)}
                className={cn(
                  'w-full flex items-center gap-1.5 px-2 py-1 text-sm transition-colors',
                  isSelected
                    ? 'bg-blue-600/30 text-white border-l-2 border-blue-500'
                    : 'text-gray-400 hover:bg-gray-700/50 hover:text-gray-200'
                )}
                style={{ paddingLeft: `${(name === '/' ? level : level + 1) * 12 + 8}px` }}
              >
                <FileIcon className={cn(
                  'w-4 h-4 flex-shrink-0',
                  file.extension === 'md' || file.extension === 'txt' ? 'text-blue-400' :
                  file.extension === 'json' ? 'text-yellow-400' :
                  file.extension === 'png' || file.extension === 'jpg' || file.extension === 'svg' ? 'text-purple-400' :
                  ['tsx', 'ts', 'jsx', 'js', 'py', 'css', 'html'].includes(file.extension || '') ? 'text-green-400' :
                  'text-gray-400'
                )} />
                <span className="truncate">{file.name}</span>
                {file.size > 0 && (
                  <span className="text-xs text-gray-600 ml-auto">
                    {formatFileSize(file.size)}
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
  const { currentSession } = useSessionStore();
  const {
    files,
    selectedFile,
    isLoading,
    error,
    loadFiles,
    selectFile,
    setSessionId,
  } = useWorkspaceStore();

  const [searchQuery, setSearchQuery] = useState('');

  // Set session ID in workspace store when session changes
  useEffect(() => {
    if (currentSession?.session_id) {
      setSessionId(currentSession.session_id);
    }
  }, [currentSession?.session_id, setSessionId]);

  // Load files when session ID is set
  useEffect(() => {
    if (currentSession?.session_id) {
      loadFiles('', true);
    }
  }, [currentSession?.session_id]);

  // Filter files
  const filteredFiles = useMemo(() => {
    if (!searchQuery.trim()) return files;

    const query = searchQuery.toLowerCase();
    return files.filter(f =>
      f.path.toLowerCase().includes(query) ||
      f.name.toLowerCase().includes(query)
    );
  }, [files, searchQuery]);

  // Don't group files when using recursive listing - FolderNode handles hierarchy
  // groupFilesByFolder is only needed for non-recursive listings

  // Handle refresh
  const handleRefresh = () => {
    if (currentSession?.session_id) {
      loadFiles('', true);
    }
  };

  // Handle file click
  const handleFileClick = (file: any) => {
    if (file.type === 'file') {
      selectFile(file);
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Panel Header */}
      <div className="flex-shrink-0 h-9 px-3 flex items-center justify-between border-b border-gray-700 bg-gray-800/50">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Explorer
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className={cn(
              "p-1 transition-colors",
              isLoading
                ? "text-gray-600 animate-spin"
                : "text-gray-500 hover:text-gray-300"
            )}
            title="Refresh"
          >
            <RefreshCw className="w-3.5 h-3.5" />
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

      {/* Files Tree */}
      <div className="flex-1 overflow-y-auto py-1 custom-scrollbar">
        {isLoading ? (
          <div className="px-4 py-8 text-center text-gray-500 text-sm">
            <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
            <p>Loading files...</p>
          </div>
        ) : error ? (
          <div className="px-4 py-8 text-center text-red-400 text-sm">
            <p>{error}</p>
          </div>
        ) : files.length === 0 ? (
          <div className="px-4 py-8 text-center text-gray-500 text-sm">
            <Folder className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No files yet</p>
            <p className="text-xs mt-1">Files will appear here as they are created</p>
          </div>
        ) : filteredFiles.length === 0 ? (
          <div className="px-4 py-8 text-center text-gray-500 text-sm">
            <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No matching files</p>
          </div>
        ) : (
          <FolderNode
            name="/"
            path=""
            files={filteredFiles}
            level={0}
            isExpanded={true}
            onFileClick={handleFileClick}
            selectedPath={selectedFile?.path || null}
          />
        )}
      </div>

      {/* Panel Footer - Selected file info */}
      {selectedFile && (
        <div className="flex-shrink-0 px-3 py-2 border-t border-gray-700 bg-gray-800/30">
          <div className="text-xs text-gray-400 truncate">
            <span className="text-gray-500">Selected:</span>{' '}
            <span className="text-gray-300">{selectedFile.name}</span>
          </div>
          {selectedFile.size > 0 && (
            <div className="text-xs text-gray-500 mt-0.5">
              {formatFileSize(selectedFile.size)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

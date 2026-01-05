import { useEffect, useCallback } from 'react';
import { useArtifactStore, useUIStore } from '../../store';
import { useSessionStore } from '../../store/sessionStore';
import { useWebSocketStatus, useWebSocketEvent } from '../../hooks/useWebSocket';
import { Button, Card } from '../Common';
import {
  X,
  Edit3,
  Download,
  Eye,
  Loader2,
  RefreshCw,
  Wifi,
  WifiOff,
  AlertCircle,
  FolderOpen,
} from 'lucide-react';
import { cn, formatFileSize, formatTimestamp, getArtifactIcon } from '../../lib/utils';
import type { Artifact } from '../../types';
import type { ArtifactUpdateEvent } from '../../services/websocket';

export function ArtifactPanel() {
  const {
    artifacts,
    selectedArtifact,
    selectArtifact,
    isLoading,
    error,
    loadArtifacts,
    clearError,
  } = useArtifactStore();
  const { isArtifactPanelOpen, setArtifactPanelOpen } = useUIStore();
  const { currentSession } = useSessionStore();
  const connectionStatus = useWebSocketStatus();
  const isConnected = connectionStatus === 'connected';

  // Subscribe to artifact update events for real-time feedback
  const handleArtifactUpdate = useCallback((event: ArtifactUpdateEvent) => {
    // Artifact store will be auto-updated by useWebSocket hook
    // We can use this to show toast notifications or highlight new files
    console.log('Artifact update:', event);
  }, []);

  useWebSocketEvent<ArtifactUpdateEvent>('artifact_update', handleArtifactUpdate);

  // Load artifacts when session changes
  useEffect(() => {
    if (currentSession?.session_id && isArtifactPanelOpen) {
      loadArtifacts(currentSession.session_id);
    }
  }, [currentSession?.session_id, isArtifactPanelOpen, loadArtifacts]);

  // Handle refresh
  const handleRefresh = () => {
    if (currentSession?.session_id) {
      loadArtifacts(currentSession.session_id);
    }
  };

  if (!isArtifactPanelOpen) {
    return null;
  }

  // Group artifacts by folder
  const groupedArtifacts = artifacts.reduce((acc, artifact) => {
    if (artifact.type === 'folder') {
      return acc;
    }
    const parts = artifact.path.split('/');
    const folder = parts.length > 1 ? parts[0] : '/';
    if (!acc[folder]) {
      acc[folder] = [];
    }
    acc[folder].push(artifact);
    return acc;
  }, {} as Record<string, Artifact[]>);

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
              Artifacts
            </h2>
            {/* Connection indicator */}
            <div
              className={cn(
                'flex items-center gap-1',
                isConnected ? 'text-green-500' : 'text-gray-400'
              )}
              title={isConnected ? 'Connected' : 'Disconnected'}
            >
              {isConnected ? (
                <Wifi className="w-3.5 h-3.5" />
              ) : (
                <WifiOff className="w-3.5 h-3.5" />
              )}
            </div>
          </div>
          <div className="flex items-center gap-1">
            {/* Refresh button */}
            <button
              onClick={handleRefresh}
              disabled={isLoading}
              className={cn(
                'p-1 rounded transition-colors',
                isLoading ? 'text-gray-300' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200'
              )}
              title="Refresh artifacts"
            >
              <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
            </button>
            {/* Close button */}
            <button
              onClick={() => setArtifactPanelOpen(false)}
              className="p-1 hover:bg-gray-200 rounded transition-colors"
            >
              <X className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>

        {/* Artifact count */}
        <div className="mt-2 text-xs text-gray-500">
          {artifacts.length} {artifacts.length === 1 ? 'file' : 'files'}
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="px-3 py-2 bg-red-50 border-b border-red-200">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-red-700">{error}</p>
            </div>
            <button
              onClick={clearError}
              className="text-red-500 hover:text-red-700 p-0.5"
              title="Dismiss"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && artifacts.length === 0 && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Loader2 className="w-6 h-6 text-gray-400 animate-spin mx-auto mb-2" />
            <p className="text-sm text-gray-500">Loading artifacts...</p>
          </div>
        </div>
      )}

      {/* Content */}
      {(!isLoading || artifacts.length > 0) && (
        <div className="flex-1 overflow-y-auto">
          <ArtifactListView
            groupedArtifacts={groupedArtifacts}
            onSelect={selectArtifact}
            selectedId={selectedArtifact?.id ?? null}
          />
        </div>
      )}
    </div>
  );
}

interface ArtifactListViewProps {
  groupedArtifacts: Record<string, Artifact[]>;
  onSelect: (artifact: Artifact) => void;
  selectedId: string | null;
}

function ArtifactListView({ groupedArtifacts, onSelect, selectedId }: ArtifactListViewProps) {
  return (
    <div className="divide-y divide-gray-100">
      {Object.entries(groupedArtifacts).map(([folder, items]) => (
        <div key={folder}>
          {/* Folder Header */}
          <div className="px-4 py-2 bg-gray-50 text-xs font-medium text-gray-600">
            {folder === '/' ? 'Root' : folder}
          </div>

          {/* Artifacts */}
          {items.map(artifact => (
            <ArtifactListItem
              key={artifact.id}
              artifact={artifact}
              isSelected={selectedId === artifact.id}
              onSelect={() => onSelect(artifact)}
            />
          ))}
        </div>
      ))}

      {Object.keys(groupedArtifacts).length === 0 && (
        <div className="p-8 text-center text-gray-500 text-sm">
          No artifacts yet
        </div>
      )}
    </div>
  );
}

interface ArtifactListItemProps {
  artifact: Artifact;
  isSelected: boolean;
  onSelect: () => void;
}

function ArtifactListItem({ artifact, isSelected, onSelect }: ArtifactListItemProps) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        'w-full px-4 py-3 flex items-start gap-3 text-left hover:bg-gray-50 transition-colors',
        isSelected && 'bg-primary-50 hover:bg-primary-50'
      )}
    >
      {/* Icon */}
      <span className="flex-shrink-0 text-2xl">
        {getArtifactIcon(artifact.name)}
      </span>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-medium text-gray-900 truncate">
            {artifact.name}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span>{formatFileSize(artifact.size)}</span>
          <span>•</span>
          <span>{formatTimestamp(artifact.updated_at)}</span>
        </div>
      </div>

      {/* Preview Badge */}
      {artifact.preview && (
        <Eye className="w-4 h-4 text-gray-400 flex-shrink-0 mt-1" />
      )}
    </button>
  );
}

// Artifact Detail Modal (when an artifact is selected)
export function ArtifactDetailModal() {
  const {
    selectedArtifact,
    isEditing,
    isSaving,
    editedContent,
    startEditing,
    cancelEdit,
    saveEdit,
    updateEditedContent,
    selectArtifact,
  } = useArtifactStore();
  const { setArtifactPanelOpen } = useUIStore();

  if (!selectedArtifact) {
    return null;
  }

  const handleClose = () => {
    selectArtifact(null);
    setArtifactPanelOpen(true);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="max-w-3xl w-full max-h-[80vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">{getArtifactIcon(selectedArtifact.name)}</span>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">
                {selectedArtifact.name}
              </h3>
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <span>{selectedArtifact.path}</span>
                <span>•</span>
                <span>{formatFileSize(selectedArtifact.size)}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {!isEditing && (
              <>
                <Button variant="secondary" size="sm">
                  <Download className="w-4 h-4" />
                  Download
                </Button>
                <Button variant="secondary" size="sm" onClick={() => startEditing(selectedArtifact)}>
                  <Edit3 className="w-4 h-4" />
                  Edit
                </Button>
              </>
            )}
            <button
              onClick={handleClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {isEditing ? (
            <textarea
              value={editedContent}
              onChange={(e) => updateEditedContent(e.target.value)}
              className="w-full h-64 p-4 font-mono text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          ) : selectedArtifact.type === 'image' ? (
            <img
              src={selectedArtifact.url}
              alt={selectedArtifact.name}
              className="max-w-full mx-auto rounded-lg"
            />
          ) : selectedArtifact.type === 'json' ? (
            <pre className="json-preview overflow-x-auto">
              {selectedArtifact.content}
            </pre>
          ) : (
            <div className="markdown-preview prose max-w-none">
              {selectedArtifact.content}
            </div>
          )}
        </div>

        {/* Footer */}
        {isEditing && (
          <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex justify-end gap-2">
            <Button variant="secondary" onClick={cancelEdit} disabled={isSaving}>
              Cancel
            </Button>
            <Button onClick={saveEdit} disabled={isSaving}>
              {isSaving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Changes'
              )}
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}

import { useArtifactStore, useUIStore } from '../../store';
import { Button, Card } from '../Common';
import { X, Edit3, Download, Eye } from 'lucide-react';
import { cn, formatFileSize, formatTimestamp, getArtifactIcon } from '../../lib/utils';
import type { Artifact } from '../../types';

export function ArtifactPanel() {
  const { artifacts, selectedArtifact, selectArtifact } = useArtifactStore();
  const { isArtifactPanelOpen, setArtifactPanelOpen } = useUIStore();

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
      <div className="p-4 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
          Artifacts
        </h2>
        <button
          onClick={() => setArtifactPanelOpen(false)}
          className="p-1 hover:bg-gray-200 rounded transition-colors"
        >
          <X className="w-4 h-4 text-gray-500" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <ArtifactListView
          groupedArtifacts={groupedArtifacts}
          onSelect={selectArtifact}
          selectedId={selectedArtifact?.id ?? null}
        />
      </div>
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
  const { selectedArtifact, isEditing, editedContent, startEditing, cancelEdit, saveEdit, updateEditedContent } = useArtifactStore();
  const { setArtifactPanelOpen } = useUIStore();

  if (!selectedArtifact) {
    return null;
  }

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
              onClick={() => {
                selectArtifact(null);
                setArtifactPanelOpen(true);
              }}
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
            <Button variant="secondary" onClick={cancelEdit}>
              Cancel
            </Button>
            <Button onClick={saveEdit}>
              Save Changes
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}

// Helper to close modal
function selectArtifact(artifact: Artifact | null) {
  // This will be replaced with store call
  console.log('Select artifact:', artifact);
}

import { useUIStore, useWorkflowStore } from '../../store';
import { Button, Card } from './index';
import { X, Check, XCircle } from 'lucide-react';
import { getArtifactIcon } from '../../lib/utils';

export function ApprovalDialog() {
  const { approvalDialog, closeApprovalDialog } = useUIStore();
  const { updatePhaseStatus, advancePhase } = useWorkflowStore();

  const handleApprove = () => {
    if (approvalDialog.phase) {
      // Update phase status to approved
      updatePhaseStatus(approvalDialog.phase.phase_id, 'approved');

      // Advance to next phase
      advancePhase();

      // Close dialog
      closeApprovalDialog();
    }
  };

  const handleReject = () => {
    if (approvalDialog.phase) {
      // Update phase status to pending (user can request regeneration)
      updatePhaseStatus(approvalDialog.phase.phase_id, 'pending');

      // Close dialog
      closeApprovalDialog();
    }
  };

  if (!approvalDialog.isOpen || !approvalDialog.phase) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-yellow-50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-yellow-100 flex items-center justify-center">
              <span className="text-xl">⚠</span>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">
                Approval Required
              </h3>
              <p className="text-sm text-gray-600">
                {approvalDialog.phase.name}
              </p>
            </div>
          </div>
          <button
            onClick={closeApprovalDialog}
            className="p-2 hover:bg-yellow-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Phase Description */}
          {approvalDialog.phase.description && (
            <div className="mb-6">
              <h4 className="text-sm font-medium text-gray-700 mb-2">
                Phase Description
              </h4>
              <p className="text-sm text-gray-600">
                {approvalDialog.phase.description}
              </p>
            </div>
          )}

          {/* Approval Prompt */}
          {approvalDialog.phase.approval_prompt && (
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm text-blue-900">
                {approvalDialog.phase.approval_prompt}
              </p>
            </div>
          )}

          {/* Artifacts to Review */}
          {approvalDialog.artifacts.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-3">
                Artifacts to Review ({approvalDialog.artifacts.length})
              </h4>
              <div className="space-y-2">
                {approvalDialog.artifacts.map((artifact) => (
                  <ArtifactReviewCard key={artifact.id} artifact={artifact} />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex justify-between items-center">
          <div className="text-sm text-gray-600">
            Review the artifacts above before making a decision
          </div>
          <div className="flex gap-3">
            <Button
              variant="secondary"
              onClick={handleReject}
              className="text-red-600 hover:bg-red-50"
            >
              <XCircle className="w-4 h-4" />
              Reject
            </Button>
            <Button
              variant="success"
              onClick={handleApprove}
            >
              <Check className="w-4 h-4" />
              Approve & Continue
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

interface ArtifactReviewCardProps {
  artifact: {
    id: string;
    name: string;
    type: string;
    size?: number;
    preview?: string;
  };
}

function ArtifactReviewCard({ artifact }: ArtifactReviewCardProps) {
  return (
    <div className="flex items-center gap-3 p-3 bg-gray-50 border border-gray-200 rounded-lg hover:border-gray-300 transition-colors">
      {/* Icon / Thumbnail */}
      {artifact.type === 'image' ? (
        <div className="w-12 h-12 bg-gray-200 rounded flex items-center justify-center flex-shrink-0">
          <span className="text-2xl">{getArtifactIcon(artifact.name)}</span>
        </div>
      ) : (
        <div className="w-12 h-12 bg-gray-200 rounded flex items-center justify-center flex-shrink-0">
          <span className="text-xl">{getArtifactIcon(artifact.name)}</span>
        </div>
      )}

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-gray-900 truncate">
          {artifact.name}
        </div>
        <div className="text-xs text-gray-500">
          {artifact.type} • {artifact.size ? `${artifact.size} bytes` : 'Unknown size'}
        </div>
      </div>

      {/* Preview */}
      {artifact.preview && (
        <div className="text-xs text-gray-600 truncate max-w-xs">
          {artifact.preview}
        </div>
      )}
    </div>
  );
}

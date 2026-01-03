import { useWorkflowStore } from '../../store';
import { ProgressBar } from '../Common';

export function WorkflowProgressBar() {
  const { workflow, progress } = useWorkflowStore();

  if (!workflow) {
    return null;
  }

  const currentPhase = workflow.phases.find(p => p.phase_id === workflow.current_phase);

  // Only show for continuous phases
  if (!currentPhase || currentPhase.ui_behavior !== 'continuous_monitoring') {
    return null;
  }

  const displayProgress = progress ?? 0;

  return (
    <div className="bg-white border-b border-gray-200 px-4 py-3">
      <div className="flex items-center gap-3">
        {/* Current Phase Label */}
        <div className="flex-shrink-0">
          <span className="text-sm font-medium text-gray-700">
            {currentPhase.name}
          </span>
        </div>

        {/* Progress Bar */}
        <div className="flex-1 min-w-0">
          <ProgressBar
            value={displayProgress}
            size="sm"
            color="primary"
          />
        </div>

        {/* Percentage */}
        <div className="flex-shrink-0 text-sm font-medium text-gray-700 w-12 text-right">
          {Math.round(displayProgress)}%
        </div>
      </div>

      {/* Description */}
      {currentPhase.description && (
        <div className="mt-2 text-xs text-gray-600">
          {currentPhase.description}
        </div>
      )}
    </div>
  );
}

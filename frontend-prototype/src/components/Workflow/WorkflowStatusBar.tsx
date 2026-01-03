import { useMemo } from 'react';
import {
  CheckCircle,
  Circle,
  Loader2,
  AlertCircle,
  Clock,
  ChevronRight
} from 'lucide-react';
import { useWorkflowStore } from '../../store/workflowStore';
import { useUIStore } from '../../store/uiStore';
import type { PhaseStatus } from '../../types';
import { cn } from '../../lib/utils';

// Get status icon
const getStatusIcon = (status: PhaseStatus) => {
  switch (status) {
    case 'completed':
    case 'approved':
      return CheckCircle;
    case 'in_progress':
      return Loader2;
    case 'awaiting_approval':
      return Clock;
    case 'failed':
      return AlertCircle;
    default:
      return Circle;
  }
};

// Get status color
const getStatusColor = (status: PhaseStatus) => {
  switch (status) {
    case 'completed':
    case 'approved':
      return 'text-green-500';
    case 'in_progress':
      return 'text-blue-500';
    case 'awaiting_approval':
      return 'text-yellow-500';
    case 'failed':
      return 'text-red-500';
    default:
      return 'text-gray-500';
  }
};

export function WorkflowStatusBar() {
  const { workflow, progress } = useWorkflowStore();
  const { openApprovalDialog } = useUIStore();

  const stats = useMemo(() => {
    if (!workflow) return null;

    const total = workflow.phases.length;
    const completed = workflow.phases.filter(p => p.status === 'completed' || p.status === 'approved').length;
    const current = workflow.phases.find(p => p.phase_id === workflow.current_phase);
    const awaitingApproval = workflow.phases.find(p => p.status === 'awaiting_approval');

    return { total, completed, current, awaitingApproval };
  }, [workflow]);

  if (!workflow || !stats) return null;

  const progressPercent = (stats.completed / stats.total) * 100;

  return (
    <div className="flex items-center gap-4">
      {/* Phase indicators */}
      <div className="flex items-center gap-1">
        {workflow.phases.map((phase, idx) => {
          const StatusIcon = getStatusIcon(phase.status);
          const isActive = phase.phase_id === workflow.current_phase;
          const needsApproval = phase.status === 'awaiting_approval';

          return (
            <div key={phase.phase_id} className="flex items-center">
              <button
                onClick={() => needsApproval && openApprovalDialog(phase, phase.output_artifacts?.map(id => ({
                  id,
                  name: id,
                  type: 'markdown' as const,
                  path: id,
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString()
                })) || [])}
                className={cn(
                  'flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors',
                  isActive && 'bg-gray-700',
                  needsApproval && 'bg-yellow-500/20 hover:bg-yellow-500/30 cursor-pointer',
                  !isActive && !needsApproval && 'hover:bg-gray-700/50'
                )}
                title={phase.name}
              >
                <StatusIcon className={cn(
                  'w-3.5 h-3.5',
                  getStatusColor(phase.status),
                  phase.status === 'in_progress' && 'animate-spin'
                )} />
                <span className={cn(
                  'hidden xl:inline max-w-[80px] truncate',
                  isActive ? 'text-gray-200' : 'text-gray-400'
                )}>
                  {phase.name}
                </span>
              </button>
              {idx < workflow.phases.length - 1 && (
                <ChevronRight className="w-3 h-3 text-gray-600 mx-0.5" />
              )}
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div className="hidden md:flex items-center gap-2">
        <div className="w-24 h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-green-500 transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <span className="text-xs text-gray-400 min-w-[3rem]">
          {stats.completed}/{stats.total}
        </span>
      </div>

      {/* Continuous progress (for coding/research) */}
      {progress !== null && stats.current?.status === 'in_progress' && (
        <div className="flex items-center gap-2 px-2 py-1 bg-blue-500/20 rounded">
          <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />
          <span className="text-xs text-blue-400">{progress}%</span>
        </div>
      )}

      {/* Approval button */}
      {stats.awaitingApproval && (
        <button
          onClick={() => openApprovalDialog(
            stats.awaitingApproval!,
            stats.awaitingApproval!.output_artifacts?.map(id => ({
              id,
              name: id,
              type: 'markdown' as const,
              path: id,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString()
            })) || []
          )}
          className="flex items-center gap-1.5 px-3 py-1 bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-400 rounded text-xs font-medium transition-colors"
        >
          <Clock className="w-3.5 h-3.5" />
          Review Required
        </button>
      )}
    </div>
  );
}

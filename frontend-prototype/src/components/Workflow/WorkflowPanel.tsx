import { useWorkflowStore, useUIStore } from '../../store';
import { Badge } from '../Common';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '../../lib/utils';

export function WorkflowPanel() {
  const { workflow, currentPhase } = useWorkflowStore();
  const { expandedPhases, togglePhaseExpanded } = useUIStore();

  if (!workflow) {
    return (
      <div className="p-4 text-center text-gray-500">
        No workflow active
      </div>
    );
  }

  // Calculate progress percentage
  const completedPhases = workflow.phases.filter(
    p => p.status === 'approved' || p.status === 'completed'
  ).length;
  const progressPercentage = (completedPhases / workflow.total_phases) * 100;

  return (
    <div className="flex flex-col h-full bg-white border-r border-gray-200">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
          Workflow
        </h2>
        <div className="mt-2">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs text-gray-600">
              {completedPhases} of {workflow.total_phases} phases
            </span>
            <span className="text-xs font-medium text-gray-700">
              {Math.round(progressPercentage)}%
            </span>
          </div>
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-primary-600 transition-all duration-300 ease-out"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
        </div>
      </div>

      {/* Phases List */}
      <div className="flex-1 overflow-y-auto p-2">
        <div className="space-y-1">
          {workflow.phases.map((phase, index) => {
            const isExpanded = expandedPhases.has(phase.phase_id);
            const isCurrent = phase.phase_id === currentPhase;
            const hasDetails = phase.description || phase.input_artifacts.length > 0 || phase.output_artifacts.length > 0;

            return (
              <div
                key={phase.phase_id}
                className={cn(
                  'rounded-lg border transition-all',
                  isCurrent
                    ? 'border-primary-500 bg-primary-50'
                    : phase.status === 'approved' || phase.status === 'completed'
                    ? 'border-green-200 bg-green-50'
                    : phase.status === 'failed'
                    ? 'border-red-200 bg-red-50'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                )}
              >
                {/* Phase Header */}
                <button
                  onClick={() => hasDetails && togglePhaseExpanded(phase.phase_id)}
                  className={cn(
                    'w-full px-3 py-2 flex items-start gap-2 text-left',
                    !hasDetails && 'cursor-default'
                  )}
                >
                  {/* Phase Number */}
                  <div className={cn(
                    'flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold',
                    isCurrent
                      ? 'bg-primary-600 text-white'
                      : phase.status === 'approved' || phase.status === 'completed'
                      ? 'bg-green-500 text-white'
                      : phase.status === 'failed'
                      ? 'bg-red-500 text-white'
                      : 'bg-gray-300 text-gray-600'
                  )}>
                    {index + 1}
                  </div>

                  {/* Expand Icon */}
                  {hasDetails && (
                    <span className="flex-shrink-0 mt-0.5 text-gray-400">
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4" />
                      ) : (
                        <ChevronRight className="w-4 h-4" />
                      )}
                    </span>
                  )}

                  {/* Phase Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-gray-900 truncate">
                        {phase.name}
                      </span>
                      <Badge status={phase.status} showIcon={false} />
                    </div>

                    {/* Current Step Indicator for Continuous Phases */}
                    {isCurrent && phase.ui_behavior === 'continuous_monitoring' && (
                      <div className="text-xs text-primary-600">
                        {phase.status === 'in_progress' ? 'Working...' : 'Waiting...'}
                      </div>
                    )}
                  </div>
                </button>

                {/* Expanded Details */}
                {isExpanded && hasDetails && (
                  <div className="px-3 pb-3 ml-8 space-y-2">
                    {/* Description */}
                    {phase.description && (
                      <p className="text-xs text-gray-600">
                        {phase.description}
                      </p>
                    )}

                    {/* Input Artifacts */}
                    {phase.input_artifacts.length > 0 && (
                      <div>
                        <div className="text-xs font-medium text-gray-700 mb-1">
                          Input:
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {phase.input_artifacts.map(artifact => (
                            <span
                              key={artifact}
                              className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-700"
                            >
                              📄 {artifact}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Output Artifacts */}
                    {phase.output_artifacts.length > 0 && (
                      <div>
                        <div className="text-xs font-medium text-gray-700 mb-1">
                          Output:
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {phase.output_artifacts.map(artifact => (
                            <span
                              key={artifact}
                              className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-primary-100 text-primary-700"
                            >
                              📄 {artifact}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Approval Required Badge */}
                    {phase.requires_approval && (
                      <div className="inline-flex items-center gap-1 text-xs text-yellow-700">
                        <span>⚠</span>
                        <span>Requires approval</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-600">
            Agent: <span className="font-medium text-gray-900 capitalize">{workflow.agent_type}</span>
          </span>
          <span className={cn(
            'inline-flex items-center gap-1',
            workflow.workflow_type === 'phase_heavy' ? 'text-blue-600' : 'text-purple-600'
          )}>
            {workflow.workflow_type === 'phase_heavy' ? '📋 Phase-based' : '💬 Chat-based'}
          </span>
        </div>
      </div>
    </div>
  );
}

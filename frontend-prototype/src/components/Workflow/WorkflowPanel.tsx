import { useState, useCallback, useEffect } from 'react';
import { useWorkflowStore, useUIStore } from '../../store';
import { useSessionStore } from '../../store/sessionStore';
import { useWebSocketStatus, useWebSocketEvent } from '../../hooks/useWebSocket';
import { Badge } from '../Common';
import {
  ChevronDown,
  ChevronRight,
  Check,
  X,
  Loader2,
  Wifi,
  WifiOff,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import type { WorkflowUpdateEvent } from '../../services/websocket';

export function WorkflowPanel() {
  const {
    workflow,
    currentPhase,
    isPhaseTransitioning,
    isLoading,
    error,
    loadWorkflow,
    approvePhase,
    rejectPhase,
    clearError,
  } = useWorkflowStore();
  const { expandedPhases, togglePhaseExpanded } = useUIStore();
  const { currentSession } = useSessionStore();
  const connectionStatus = useWebSocketStatus();

  // Local state for approval dialog
  const [showApprovalDialog, setShowApprovalDialog] = useState<string | null>(null);
  const [approvalFeedback, setApprovalFeedback] = useState('');
  const [isApproving, setIsApproving] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);

  // Subscribe to workflow update events for real-time feedback
  const handleWorkflowUpdate = useCallback((event: WorkflowUpdateEvent) => {
    // Workflow store will be auto-updated by useWebSocket hook
    // We can use this to show toast notifications or animations
    console.log('Workflow update:', event);
  }, []);

  useWebSocketEvent<WorkflowUpdateEvent>('workflow_update', handleWorkflowUpdate);

  // Load workflow when session changes
  useEffect(() => {
    if (currentSession?.session_id) {
      loadWorkflow(currentSession.session_id);
    }
  }, [currentSession?.session_id, loadWorkflow]);

  // Handle approval
  const handleApprove = async (phaseId: string) => {
    setIsApproving(true);
    try {
      await approvePhase(phaseId, approvalFeedback || undefined);
      setShowApprovalDialog(null);
      setApprovalFeedback('');
    } finally {
      setIsApproving(false);
    }
  };

  // Handle rejection
  const handleReject = async (phaseId: string) => {
    if (!approvalFeedback.trim()) {
      // Feedback is required for rejection
      return;
    }
    setIsRejecting(true);
    try {
      await rejectPhase(phaseId, approvalFeedback);
      setShowApprovalDialog(null);
      setApprovalFeedback('');
    } finally {
      setIsRejecting(false);
    }
  };

  // Loading state
  if (isLoading && !workflow) {
    return (
      <div className="flex flex-col h-full bg-white border-r border-gray-200">
        <div className="p-4 border-b border-gray-200 bg-gray-50">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Workflow
          </h2>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Loader2 className="w-6 h-6 text-gray-400 animate-spin mx-auto mb-2" />
            <p className="text-sm text-gray-500">Loading workflow...</p>
          </div>
        </div>
      </div>
    );
  }

  // No workflow state
  if (!workflow) {
    return (
      <div className="flex flex-col h-full bg-white border-r border-gray-200">
        <div className="p-4 border-b border-gray-200 bg-gray-50">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Workflow
          </h2>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center text-gray-500">
            <p className="text-sm">No workflow active</p>
            <p className="text-xs mt-1 text-gray-400">
              {currentSession ? 'Start a session to begin' : 'Select a session first'}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Calculate progress percentage
  const completedPhases = workflow.phases.filter(
    p => p.status === 'approved' || p.status === 'completed'
  ).length;
  const progressPercentage = (completedPhases / workflow.total_phases) * 100;
  const isConnected = connectionStatus === 'connected';

  // Handle refresh
  const handleRefresh = () => {
    if (currentSession?.session_id) {
      loadWorkflow(currentSession.session_id);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white border-r border-gray-200">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Workflow
          </h2>
          <div className="flex items-center gap-2">
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
            {/* Refresh button */}
            <button
              onClick={handleRefresh}
              disabled={isLoading}
              className={cn(
                'p-1 rounded transition-colors',
                isLoading ? 'text-gray-300' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200'
              )}
              title="Refresh workflow"
            >
              <RefreshCw className={cn('w-3.5 h-3.5', isLoading && 'animate-spin')} />
            </button>
          </div>
        </div>
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

                    {/* Awaiting Approval Indicator */}
                    {isCurrent && phase.status === 'awaiting_approval' && (
                      <div className="text-xs text-yellow-600 flex items-center gap-1">
                        <AlertCircle className="w-3 h-3" />
                        Awaiting your approval
                      </div>
                    )}
                  </div>
                </button>

                {/* Approval Actions - shown for current phase awaiting approval */}
                {isCurrent && phase.status === 'awaiting_approval' && showApprovalDialog !== phase.phase_id && (
                  <div className="px-3 pb-3 flex gap-2">
                    <button
                      onClick={() => setShowApprovalDialog(phase.phase_id)}
                      disabled={isPhaseTransitioning}
                      className={cn(
                        'flex-1 px-3 py-1.5 rounded text-xs font-medium transition-colors flex items-center justify-center gap-1',
                        isPhaseTransitioning
                          ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                          : 'bg-green-500 text-white hover:bg-green-600'
                      )}
                    >
                      {isPhaseTransitioning ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Check className="w-3 h-3" />
                      )}
                      Approve
                    </button>
                    <button
                      onClick={() => setShowApprovalDialog(phase.phase_id)}
                      disabled={isPhaseTransitioning}
                      className={cn(
                        'flex-1 px-3 py-1.5 rounded text-xs font-medium transition-colors flex items-center justify-center gap-1',
                        isPhaseTransitioning
                          ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                          : 'bg-red-500 text-white hover:bg-red-600'
                      )}
                    >
                      <X className="w-3 h-3" />
                      Reject
                    </button>
                  </div>
                )}

                {/* Approval Dialog */}
                {showApprovalDialog === phase.phase_id && (
                  <div className="px-3 pb-3 space-y-2 bg-gray-50 rounded-b-lg">
                    <textarea
                      value={approvalFeedback}
                      onChange={(e) => setApprovalFeedback(e.target.value)}
                      placeholder="Feedback (required for rejection)..."
                      className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded resize-none focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                      rows={2}
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleApprove(phase.phase_id)}
                        disabled={isApproving || isRejecting}
                        className={cn(
                          'flex-1 px-3 py-1.5 rounded text-xs font-medium transition-colors flex items-center justify-center gap-1',
                          isApproving || isRejecting
                            ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                            : 'bg-green-500 text-white hover:bg-green-600'
                        )}
                      >
                        {isApproving ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Check className="w-3 h-3" />
                        )}
                        Approve
                      </button>
                      <button
                        onClick={() => handleReject(phase.phase_id)}
                        disabled={isApproving || isRejecting || !approvalFeedback.trim()}
                        className={cn(
                          'flex-1 px-3 py-1.5 rounded text-xs font-medium transition-colors flex items-center justify-center gap-1',
                          isApproving || isRejecting || !approvalFeedback.trim()
                            ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                            : 'bg-red-500 text-white hover:bg-red-600'
                        )}
                      >
                        {isRejecting ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <X className="w-3 h-3" />
                        )}
                        Reject
                      </button>
                      <button
                        onClick={() => {
                          setShowApprovalDialog(null);
                          setApprovalFeedback('');
                        }}
                        disabled={isApproving || isRejecting}
                        className="px-3 py-1.5 rounded text-xs font-medium text-gray-600 hover:bg-gray-200 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

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
                              {artifact}
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
                              {artifact}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Approval Required Badge */}
                    {phase.requires_approval && phase.status !== 'awaiting_approval' && (
                      <div className="inline-flex items-center gap-1 text-xs text-yellow-700">
                        <AlertCircle className="w-3 h-3" />
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

      {/* Error Display */}
      {error && (
        <div className="px-3 py-2 bg-red-50 border-t border-red-200">
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
            {workflow.workflow_type === 'phase_heavy' ? 'Phase-based' : 'Chat-based'}
          </span>
        </div>
      </div>
    </div>
  );
}

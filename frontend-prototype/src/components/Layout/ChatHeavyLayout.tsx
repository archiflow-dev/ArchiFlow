import { useEffect } from 'react';
import { useSessionStore, useWorkflowStore, useArtifactStore, useChatStore, useUIStore } from '../../store';
import { WorkflowProgressBar } from '../Workflow';
import { ChatPanel } from '../Chat';
import { PanelRightClose, PanelRightOpen } from 'lucide-react';

export function ChatHeavyLayout() {
  const { currentSession } = useSessionStore();
  const { setWorkflow, progress } = useWorkflowStore();
  const { setArtifacts } = useArtifactStore();
  const { setMessages } = useChatStore();
  const { isArtifactPanelOpen, setArtifactPanelOpen } = useUIStore();

  // Initialize session data
  useEffect(() => {
    if (currentSession) {
      if (currentSession.workflow) {
        setWorkflow(currentSession.workflow);
      }
      if (currentSession.artifacts) {
        setArtifacts(currentSession.artifacts);
      }
      if (currentSession.messages) {
        setMessages(currentSession.messages);
      }
    }
  }, [currentSession, setWorkflow, setArtifacts, setMessages]);

  if (!currentSession) {
    return null;
  }

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      {/* Top Bar with Progress */}
      <div className="bg-white border-b border-gray-200">
        <div className="px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-semibold text-gray-900">
              ArchiFlow - <span className="capitalize">{currentSession.agent_type}</span> Agent
            </h1>
            <span className="px-2 py-1 bg-purple-100 text-purple-800 rounded text-xs font-medium">
              Chat-Based Workflow
            </span>
          </div>

          <div className="flex items-center gap-4">
            {progress !== null && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-600">Progress:</span>
                <span className="text-sm font-medium text-primary-600">{Math.round(progress)}%</span>
              </div>
            )}

            <button
              onClick={() => setArtifactPanelOpen(!isArtifactPanelOpen)}
              className="p-2 hover:bg-gray-100 rounded-lg"
              title={isArtifactPanelOpen ? 'Hide Artifacts' : 'Show Artifacts'}
            >
              {isArtifactPanelOpen ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Progress Bar */}
        <WorkflowProgressBar />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Chat Panel (flex - Primary) */}
        <div className="flex-1">
          <ChatPanel />
        </div>

        {/* Right: Artifact Panel (300px - Collapsible) */}
        <div className={`w-[300px] flex-shrink-0 transition-all ${isArtifactPanelOpen ? '' : 'hidden'}`}>
          <div className="h-full flex flex-col bg-white border-l border-gray-200">
            <div className="p-4 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                Artifacts
              </h2>
              <button
                onClick={() => setArtifactPanelOpen(false)}
                className="p-1 hover:bg-gray-200 rounded"
              >
                ×
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <p className="text-sm text-gray-500">
                Artifact panel content would appear here.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Minimal Phase Indicator (Bottom) */}
      {currentSession.workflow && (
        <div className="bg-white border-t border-gray-200 px-4 py-2">
          <div className="flex items-center justify-center gap-6 text-xs text-gray-600">
            {currentSession.workflow.phases.map((phase, idx) => {
              const isCompleted = phase.status === 'approved' || phase.status === 'completed';
              const isCurrent = phase.phase_id === currentSession.workflow?.current_phase;

              return (
                <div key={phase.phase_id} className="flex items-center gap-2">
                  <div className={`flex items-center justify-center w-5 h-5 rounded-full text-xs font-semibold ${
                    isCompleted
                      ? 'bg-green-500 text-white'
                      : isCurrent
                      ? 'bg-primary-600 text-white'
                      : 'bg-gray-300 text-gray-600'
                  }`}>
                    {isCompleted ? '✓' : idx + 1}
                  </div>
                  <span className={isCurrent ? 'font-medium text-primary-700' : ''}>
                    {phase.name}
                  </span>
                  {idx < currentSession.workflow!.phases.length - 1 && (
                    <span className="text-gray-400">→</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

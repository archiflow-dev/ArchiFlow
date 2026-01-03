import { useEffect, useState } from 'react';
import { useSessionStore, useWorkflowStore, useArtifactStore, useChatStore, useUIStore } from '../../store';
import { WorkflowPanel } from '../Workflow';
import { ChatPanel } from '../Chat';
import { ApprovalDialog } from '../Common';
import { PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen } from 'lucide-react';

export function PhaseHeavyLayout() {
  const { currentSession } = useSessionStore();
  const { setWorkflow } = useWorkflowStore();
  const { setArtifacts } = useArtifactStore();
  const { setMessages, addMessage } = useChatStore();
  const {
    isArtifactPanelOpen,
    isChatPanelOpen,
    setArtifactPanelOpen,
    setChatPanelOpen,
    openApprovalDialog
  } = useUIStore();
  const [simulateApproval, setSimulateApproval] = useState(false);

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

      // Check if any phase is awaiting approval
      const awaitingPhase = currentSession.workflow?.phases.find(
        p => p.status === 'awaiting_approval'
      );
      if (awaitingPhase && currentSession.artifacts) {
        // Get artifacts relevant to this phase
        const relevantArtifacts = currentSession.artifacts.filter(a =>
          awaitingPhase.output_artifacts.some(output =>
            a.path.includes(output.replace('/', ''))
          )
        );
        openApprovalDialog(awaitingPhase, relevantArtifacts);
      }
    }
  }, [currentSession, setWorkflow, setArtifacts, setMessages, openApprovalDialog]);

  // Simulate phase progression for demo
  const handleSimulateProgress = () => {
    setSimulateApproval(true);

    // Add a mock message
    addMessage({
      id: `msg-${Date.now()}`,
      type: 'agent',
      content: 'Simulated: Phase progressing... (Demo mode)',
      timestamp: new Date().toISOString()
    });

    // After 2 seconds, trigger approval for next pending phase
    setTimeout(() => {
      setSimulateApproval(false);
    }, 2000);
  };

  if (!currentSession) {
    return null;
  }

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      {/* Top Bar */}
      <div className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-semibold text-gray-900">
            ArchiFlow - <span className="capitalize">{currentSession.agent_type}</span> Agent
          </h1>
          <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-medium">
            Phase-Based Workflow
          </span>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={handleSimulateProgress}
            disabled={simulateApproval}
            className="px-3 py-1.5 bg-primary-600 text-white rounded text-sm hover:bg-primary-700 disabled:opacity-50"
          >
            {simulateApproval ? 'Simulating...' : 'Simulate Progress'}
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setArtifactPanelOpen(!isArtifactPanelOpen)}
              className="p-2 hover:bg-gray-100 rounded-lg"
              title={isArtifactPanelOpen ? 'Hide Artifacts' : 'Show Artifacts'}
            >
              {isArtifactPanelOpen ? <PanelRightOpen className="w-4 h-4" /> : <PanelRightClose className="w-4 h-4" />}
            </button>
            <button
              onClick={() => setChatPanelOpen(!isChatPanelOpen)}
              className="p-2 hover:bg-gray-100 rounded-lg"
              title={isChatPanelOpen ? 'Hide Chat' : 'Show Chat'}
            >
              {isChatPanelOpen ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Workflow Panel (250px) */}
        <div className="w-[250px] flex-shrink-0">
          <WorkflowPanel />
        </div>

        {/* Middle: Chat Panel (flex) */}
        <div className={`flex-1 transition-all ${isChatPanelOpen ? '' : 'hidden'}`}>
          <ChatPanel />
        </div>

        {/* Right: Artifact Panel (400px) */}
        <div className={`w-[400px] flex-shrink-0 transition-all ${isArtifactPanelOpen ? '' : 'hidden'}`}>
          {/* Artifact panel would go here */}
          <div className="h-full flex flex-col bg-white border-l border-gray-200">
            <div className="p-4 border-b border-gray-200 bg-gray-50">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                Artifacts
              </h2>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <p className="text-sm text-gray-500">
                Artifact panel content would appear here.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Approval Dialog */}
      <ApprovalDialog />
    </div>
  );
}

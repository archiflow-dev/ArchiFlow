import { useState, useCallback, useEffect } from 'react';
import {
  MessageSquare,
  FolderTree,
  ChevronLeft,
  Settings,
  RotateCcw,
  Wifi,
  WifiOff,
  Loader2,
} from 'lucide-react';
import { useSessionStore } from '../../store/sessionStore';
import { useWorkflowStore } from '../../store/workflowStore';
import { useUIStore } from '../../store/uiStore';
import { useWebSocket } from '../../hooks/useWebSocket';
import { ArtifactOutlinePanel } from '../Artifact/ArtifactOutlinePanel';
import { DisplayPanel } from '../Display/DisplayPanel';
import { ChatPanel } from '../Chat/ChatPanel';
import { ResizablePanel } from '../Common/ResizablePanel';
import { StatusBadge } from '../Common/Badge';
import { Button } from '../Common/Button';
import { WorkflowStatusBar } from '../Workflow/WorkflowStatusBar';
import { getWorkflowType, cn } from '../../lib/utils';

// Panel configuration
const DEFAULT_LEFT_WIDTH = 260;
const DEFAULT_RIGHT_WIDTH = 380;
const MIN_PANEL_WIDTH = 200;
const MAX_LEFT_WIDTH = 400;
const MAX_RIGHT_WIDTH = 500;

export function VSCodeLayout() {
  const { currentSession, setCurrentSession } = useSessionStore();
  const { workflow, loadWorkflow } = useWorkflowStore();
  const { isArtifactPanelOpen, isChatPanelOpen, setArtifactPanelOpen, setChatPanelOpen } = useUIStore();

  // Initialize WebSocket at the layout level
  const {
    status: wsStatus,
    isConnected,
    isAgentProcessing,
    subscribeToSession,
    disconnect,
  } = useWebSocket({
    sessionId: currentSession?.session_id,
    autoConnect: true,
    syncStores: true,
  });

  // Panel widths
  const [leftWidth, setLeftWidth] = useState(DEFAULT_LEFT_WIDTH);
  const [rightWidth, setRightWidth] = useState(DEFAULT_RIGHT_WIDTH);

  // Handle panel resizing
  const handleLeftResize = useCallback((delta: number) => {
    setLeftWidth(prev => Math.max(MIN_PANEL_WIDTH, Math.min(MAX_LEFT_WIDTH, prev + delta)));
  }, []);

  const handleRightResize = useCallback((delta: number) => {
    setRightWidth(prev => Math.max(MIN_PANEL_WIDTH, Math.min(MAX_RIGHT_WIDTH, prev - delta)));
  }, []);

  // Subscribe to session when session changes
  useEffect(() => {
    if (currentSession?.session_id && isConnected) {
      subscribeToSession(currentSession.session_id);
    }
  }, [currentSession?.session_id, isConnected, subscribeToSession]);

  // Load workflow when session changes
  useEffect(() => {
    if (currentSession?.session_id) {
      loadWorkflow(currentSession.session_id);
    }
  }, [currentSession?.session_id, loadWorkflow]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  if (!currentSession) {
    return null;
  }

  const workflowType = getWorkflowType(currentSession.agent_type);
  const currentPhase = workflow?.phases.find(p => p.phase_id === workflow.current_phase);

  return (
    <div className="h-screen flex flex-col bg-gray-900 text-gray-100">
      {/* Top Bar */}
      <header className="flex-shrink-0 h-12 bg-gray-800 border-b border-gray-700 flex items-center px-4 justify-between">
        {/* Left section - Session info */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setCurrentSession(null)}
            className="text-gray-400 hover:text-white transition-colors"
            title="Back to sessions"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>

          <div className="flex items-center gap-2">
            <span className="font-semibold text-white">
              {currentSession.user_prompt.slice(0, 30)}
              {currentSession.user_prompt.length > 30 ? '...' : ''}
            </span>
            <StatusBadge status={currentSession.status} />
            <span className="text-xs text-gray-500 px-2 py-0.5 bg-gray-700 rounded">
              {workflowType === 'phase_heavy' ? 'Phase-Heavy' : 'Chat-Heavy'}
            </span>
          </div>
        </div>

        {/* Center section - Workflow progress */}
        {workflow && (
          <div className="flex items-center gap-4">
            <WorkflowStatusBar />
          </div>
        )}

        {/* Right section - Controls */}
        <div className="flex items-center gap-2">
          {/* Panel toggles */}
          <Button
            variant={isArtifactPanelOpen ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setArtifactPanelOpen(!isArtifactPanelOpen)}
          >
            <FolderTree className="w-4 h-4" />
          </Button>

          <Button
            variant={isChatPanelOpen ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setChatPanelOpen(!isChatPanelOpen)}
          >
            <MessageSquare className="w-4 h-4" />
          </Button>

          <div className="w-px h-6 bg-gray-700 mx-1" />

          {/* Session controls */}
          <Button variant="ghost" size="sm">
            <RotateCcw className="w-4 h-4" />
          </Button>

          <Button variant="ghost" size="sm">
            <Settings className="w-4 h-4" />
          </Button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Artifacts Outline */}
        {isArtifactPanelOpen && (
          <>
            <div
              className="flex-shrink-0 bg-gray-850 border-r border-gray-700 overflow-hidden"
              style={{ width: leftWidth }}
            >
              <ArtifactOutlinePanel />
            </div>
            <ResizablePanel
              direction="horizontal"
              onResize={handleLeftResize}
            />
          </>
        )}

        {/* Middle Panel - Display/Editor */}
        <div className="flex-1 min-w-0 bg-gray-900 overflow-hidden">
          <DisplayPanel />
        </div>

        {/* Right Panel - Chat */}
        {isChatPanelOpen && (
          <>
            <ResizablePanel
              direction="horizontal"
              onResize={handleRightResize}
            />
            <div
              className="flex-shrink-0 bg-gray-850 border-l border-gray-700 overflow-hidden"
              style={{ width: rightWidth }}
            >
              <ChatPanel />
            </div>
          </>
        )}
      </div>

      {/* Bottom Status Bar */}
      <footer className="flex-shrink-0 h-6 bg-gray-800 border-t border-gray-700 flex items-center px-4 text-xs text-gray-400 justify-between">
        <div className="flex items-center gap-4">
          {/* Connection Status */}
          <div
            className={cn(
              'flex items-center gap-1',
              wsStatus === 'connected' ? 'text-green-400' :
              wsStatus === 'connecting' ? 'text-yellow-400' :
              wsStatus === 'error' ? 'text-red-400' :
              'text-gray-500'
            )}
          >
            {wsStatus === 'connected' ? (
              <Wifi className="w-3 h-3" />
            ) : wsStatus === 'connecting' ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <WifiOff className="w-3 h-3" />
            )}
            <span className="capitalize">{wsStatus}</span>
          </div>

          {/* Agent Processing Indicator */}
          {isAgentProcessing && (
            <div className="flex items-center gap-1 text-blue-400">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Processing...</span>
            </div>
          )}

          {currentPhase && (
            <span>
              Phase: <span className="text-gray-300">{currentPhase.name}</span>
            </span>
          )}
          {workflow && (
            <span>
              Progress: <span className="text-gray-300">{workflow.phases.filter(p => p.status === 'completed').length}/{workflow.phases.length}</span>
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <span>ArchiFlow v0.1.0</span>
        </div>
      </footer>
    </div>
  );
}

import { create } from 'zustand';
import type { Artifact, WorkflowPhase } from '../types';

interface ApprovalDialogState {
  isOpen: boolean;
  phaseId: string | null;
  phase: WorkflowPhase | null;
  artifacts: Artifact[];
  onApprove?: () => void;
  onReject?: () => void;
}

interface UIState {
  // Approval Dialog
  approvalDialog: ApprovalDialogState;

  // Workflow Panel
  expandedPhases: Set<string>;

  // Artifact Panel
  isArtifactPanelOpen: boolean;

  // Chat Panel
  isChatPanelOpen: boolean;

  // Actions
  openApprovalDialog: (phase: WorkflowPhase, artifacts: Artifact[]) => void;
  closeApprovalDialog: () => void;
  approvePhase: () => void;
  rejectPhase: () => void;

  togglePhaseExpanded: (phaseId: string) => void;
  setPhaseExpanded: (phaseId: string, expanded: boolean) => void;

  toggleArtifactPanel: () => void;
  setArtifactPanelOpen: (open: boolean) => void;

  toggleChatPanel: () => void;
  setChatPanelOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>((set, get) => ({
  // Initial state
  approvalDialog: {
    isOpen: false,
    phaseId: null,
    phase: null,
    artifacts: []
  },
  expandedPhases: new Set<string>(),
  isArtifactPanelOpen: true,
  isChatPanelOpen: true,

  // Approval Dialog actions
  openApprovalDialog: (phase, artifacts) => {
    set({
      approvalDialog: {
        isOpen: true,
        phaseId: phase.phase_id,
        phase,
        artifacts
      }
    });
  },

  closeApprovalDialog: () => {
    set({
      approvalDialog: {
        isOpen: false,
        phaseId: null,
        phase: null,
        artifacts: []
      }
    });
  },

  approvePhase: () => {
    const { approvalDialog } = get();
    approvalDialog.onApprove?.();
    set({
      approvalDialog: {
        isOpen: false,
        phaseId: null,
        phase: null,
        artifacts: []
      }
    });
  },

  rejectPhase: () => {
    const { approvalDialog } = get();
    approvalDialog.onReject?.();
    set({
      approvalDialog: {
        isOpen: false,
        phaseId: null,
        phase: null,
        artifacts: []
      }
    });
  },

  // Workflow Panel actions
  togglePhaseExpanded: (phaseId) => {
    set(state => {
      const newExpanded = new Set(state.expandedPhases);
      if (newExpanded.has(phaseId)) {
        newExpanded.delete(phaseId);
      } else {
        newExpanded.add(phaseId);
      }
      return { expandedPhases: newExpanded };
    });
  },

  setPhaseExpanded: (phaseId, expanded) => {
    set(state => {
      const newExpanded = new Set(state.expandedPhases);
      if (expanded) {
        newExpanded.add(phaseId);
      } else {
        newExpanded.delete(phaseId);
      }
      return { expandedPhases: newExpanded };
    });
  },

  // Artifact Panel actions
  toggleArtifactPanel: () => {
    set(state => ({ isArtifactPanelOpen: !state.isArtifactPanelOpen }));
  },

  setArtifactPanelOpen: (open) => {
    set({ isArtifactPanelOpen: open });
  },

  // Chat Panel actions
  toggleChatPanel: () => {
    set(state => ({ isChatPanelOpen: !state.isChatPanelOpen }));
  },

  setChatPanelOpen: (open) => {
    set({ isChatPanelOpen: open });
  }
}));

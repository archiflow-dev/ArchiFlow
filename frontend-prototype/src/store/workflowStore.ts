import { create } from 'zustand';
import type { Workflow, PhaseStatus } from '../types';

interface WorkflowState {
  workflow: Workflow | null;
  currentPhase: string | null;
  isPhaseTransitioning: boolean;
  progress: number | null;

  // Actions
  setWorkflow: (workflow: Workflow) => void;
  updatePhaseStatus: (phaseId: string, status: PhaseStatus) => void;
  setCurrentPhase: (phaseId: string) => void;
  updateProgress: (progress: number) => void;
  advancePhase: () => void;
  reset: () => void;
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  workflow: null,
  currentPhase: null,
  isPhaseTransitioning: false,
  progress: null,

  setWorkflow: (workflow) => {
    set({
      workflow,
      currentPhase: workflow.current_phase,
      progress: workflow.progress ?? null
    });
  },

  updatePhaseStatus: (phaseId, status) => {
    const { workflow } = get();
    if (!workflow) return;

    const updatedPhases = workflow.phases.map(phase =>
      phase.phase_id === phaseId
        ? { ...phase, status }
        : phase
    );

    set({
      workflow: {
        ...workflow,
        phases: updatedPhases
      }
    });
  },

  setCurrentPhase: (phaseId) => {
    set({ currentPhase: phaseId });
  },

  updateProgress: (progress) => {
    set({ progress });
  },

  advancePhase: () => {
    const { workflow, currentPhase } = get();
    if (!workflow || !currentPhase) return;

    const currentPhaseIndex = workflow.phases.findIndex(
      p => p.phase_id === currentPhase
    );

    if (currentPhaseIndex < workflow.phases.length - 1) {
      const nextPhase = workflow.phases[currentPhaseIndex + 1];
      set({
        currentPhase: nextPhase.phase_id,
        workflow: {
          ...workflow,
          current_phase: nextPhase.phase_id
        }
      });
    }
  },

  reset: () => {
    set({
      workflow: null,
      currentPhase: null,
      isPhaseTransitioning: false,
      progress: null
    });
  }
}));

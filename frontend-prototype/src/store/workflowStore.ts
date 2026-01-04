import { create } from 'zustand';
import type { Workflow, PhaseStatus, WorkflowPhase } from '../types';
import { workflowApi, type WorkflowState as WorkflowStateApi } from '../services';

// ============================================================================
// Helper: Convert API response to frontend Workflow type
// ============================================================================

function mapWorkflowResponse(response: WorkflowStateApi): Workflow {
  return {
    agent_type: response.agent_type as Workflow['agent_type'],
    workflow_type: response.workflow_type as Workflow['workflow_type'],
    current_phase: response.current_phase ?? response.phases[0]?.id ?? '',
    phases: response.phases.map((p) => ({
      phase_id: p.id,
      name: p.name,
      description: p.description ?? '',
      order: p.order,
      status: p.status as PhaseStatus,
      input_artifacts: [],
      output_artifacts: p.artifacts,
      requires_approval: p.requires_approval,
      ui_behavior: p.requires_approval ? 'approval_required' as const : 'continuous_monitoring' as const,
    })),
    total_phases: response.total_phases,
    approval_phases: response.phases.filter((p) => p.requires_approval).map((p) => p.id),
    continuous_phases: response.phases.filter((p) => !p.requires_approval).map((p) => p.id),
    progress: Math.round((response.completed_phases / response.total_phases) * 100) || 0,
  };
}

// ============================================================================
// Store Interface
// ============================================================================

interface WorkflowStoreState {
  workflow: Workflow | null;
  currentPhase: string | null;
  isPhaseTransitioning: boolean;
  isLoading: boolean;
  error: string | null;
  progress: number | null;
  sessionId: string | null;

  // Actions
  setWorkflow: (workflow: Workflow) => void;
  loadWorkflow: (sessionId: string) => Promise<void>;
  updatePhaseStatus: (phaseId: string, status: PhaseStatus) => void;
  setCurrentPhase: (phaseId: string) => void;
  updateProgress: (progress: number) => void;
  advancePhase: () => void;
  reset: () => void;
  clearError: () => void;

  // API Actions
  approvePhase: (phaseId: string, feedback?: string) => Promise<void>;
  rejectPhase: (phaseId: string, feedback: string) => Promise<void>;
  startWorkflow: () => Promise<void>;
  resetWorkflow: () => Promise<void>;
}

// ============================================================================
// Store Implementation
// ============================================================================

export const useWorkflowStore = create<WorkflowStoreState>((set, get) => ({
  workflow: null,
  currentPhase: null,
  isPhaseTransitioning: false,
  isLoading: false,
  error: null,
  progress: null,
  sessionId: null,

  setWorkflow: (workflow) => {
    set({
      workflow,
      currentPhase: workflow.current_phase,
      progress: workflow.progress ?? null,
    });
  },

  loadWorkflow: async (sessionId) => {
    set({ isLoading: true, error: null, sessionId });

    try {
      const response = await workflowApi.get(sessionId);
      const workflow = mapWorkflowResponse(response);
      set({
        workflow,
        currentPhase: workflow.current_phase,
        progress: workflow.progress ?? null,
        isLoading: false,
      });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load workflow',
        isLoading: false,
      });
    }
  },

  updatePhaseStatus: (phaseId, status) => {
    const { workflow } = get();
    if (!workflow) return;

    const updatedPhases = workflow.phases.map((phase) =>
      phase.phase_id === phaseId ? { ...phase, status } : phase,
    );

    set({
      workflow: {
        ...workflow,
        phases: updatedPhases,
      },
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
      (p) => p.phase_id === currentPhase,
    );

    if (currentPhaseIndex < workflow.phases.length - 1) {
      const nextPhase = workflow.phases[currentPhaseIndex + 1];
      set({
        currentPhase: nextPhase.phase_id,
        workflow: {
          ...workflow,
          current_phase: nextPhase.phase_id,
        },
      });
    }
  },

  reset: () => {
    set({
      workflow: null,
      currentPhase: null,
      isPhaseTransitioning: false,
      isLoading: false,
      error: null,
      progress: null,
      sessionId: null,
    });
  },

  clearError: () => {
    set({ error: null });
  },

  approvePhase: async (phaseId, feedback) => {
    const { sessionId } = get();
    if (!sessionId) {
      set({ error: 'No session selected' });
      return;
    }

    set({ isPhaseTransitioning: true, error: null });

    try {
      const result = await workflowApi.approve(sessionId, phaseId, feedback);

      // Update local state
      get().updatePhaseStatus(phaseId, 'approved');

      if (result.next_phase) {
        get().setCurrentPhase(result.next_phase);
        get().updatePhaseStatus(result.next_phase, 'in_progress');
      }

      // Reload workflow to get fresh state
      await get().loadWorkflow(sessionId);
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to approve phase',
      });
    } finally {
      set({ isPhaseTransitioning: false });
    }
  },

  rejectPhase: async (phaseId, feedback) => {
    const { sessionId } = get();
    if (!sessionId) {
      set({ error: 'No session selected' });
      return;
    }

    set({ isPhaseTransitioning: true, error: null });

    try {
      await workflowApi.reject(sessionId, phaseId, feedback);

      // Update local state
      get().updatePhaseStatus(phaseId, 'in_progress');

      // Reload workflow to get fresh state
      await get().loadWorkflow(sessionId);
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to reject phase',
      });
    } finally {
      set({ isPhaseTransitioning: false });
    }
  },

  startWorkflow: async () => {
    const { sessionId } = get();
    if (!sessionId) {
      set({ error: 'No session selected' });
      return;
    }

    set({ isLoading: true, error: null });

    try {
      const response = await workflowApi.start(sessionId);
      const workflow = mapWorkflowResponse(response);
      set({
        workflow,
        currentPhase: workflow.current_phase,
        progress: workflow.progress ?? null,
        isLoading: false,
      });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to start workflow',
        isLoading: false,
      });
    }
  },

  resetWorkflow: async () => {
    const { sessionId } = get();
    if (!sessionId) {
      set({ error: 'No session selected' });
      return;
    }

    set({ isLoading: true, error: null });

    try {
      const response = await workflowApi.reset(sessionId);
      const workflow = mapWorkflowResponse(response);
      set({
        workflow,
        currentPhase: workflow.current_phase,
        progress: 0,
        isLoading: false,
      });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to reset workflow',
        isLoading: false,
      });
    }
  },
}));

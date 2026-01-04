/**
 * Workflow API client.
 *
 * Handles workflow state and phase management.
 */

import { api } from './api';

// ============================================================================
// Types
// ============================================================================

export type PhaseStatusApi =
  | 'pending'
  | 'in_progress'
  | 'awaiting_approval'
  | 'approved'
  | 'rejected'
  | 'completed'
  | 'failed';

export interface WorkflowPhase {
  id: string;
  name: string;
  description?: string;
  order: number;
  status: PhaseStatusApi;
  requires_approval: boolean;
  artifacts: string[];
}

export interface WorkflowState {
  session_id: string;
  agent_type: string;
  workflow_type: string;
  current_phase?: string;
  phases: WorkflowPhase[];
  total_phases: number;
  completed_phases: number;
  is_complete: boolean;
}

export interface ApprovalRequest {
  approved: boolean;
  feedback?: string;
}

export interface ApprovalResponse {
  phase_id: string;
  status: PhaseStatusApi;
  next_phase?: string;
  message: string;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get the current workflow state for a session.
 */
export async function getWorkflow(sessionId: string): Promise<WorkflowState> {
  return api.get<WorkflowState>(`/sessions/${sessionId}/workflow/`);
}

/**
 * Start the workflow.
 */
export async function startWorkflow(sessionId: string): Promise<WorkflowState> {
  return api.post<WorkflowState>(`/sessions/${sessionId}/workflow/start`);
}

/**
 * Approve or reject a workflow phase.
 */
export async function approvePhase(
  sessionId: string,
  phaseId: string,
  data: ApprovalRequest,
): Promise<ApprovalResponse> {
  return api.post<ApprovalResponse>(
    `/sessions/${sessionId}/workflow/phases/${phaseId}/approve`,
    data,
  );
}

/**
 * Approve a phase (convenience function).
 */
export async function approve(
  sessionId: string,
  phaseId: string,
  feedback?: string,
): Promise<ApprovalResponse> {
  return approvePhase(sessionId, phaseId, { approved: true, feedback });
}

/**
 * Reject a phase (convenience function).
 */
export async function reject(
  sessionId: string,
  phaseId: string,
  feedback: string,
): Promise<ApprovalResponse> {
  return approvePhase(sessionId, phaseId, { approved: false, feedback });
}

/**
 * Mark a phase as complete (for non-approval phases).
 */
export async function completePhase(
  sessionId: string,
  phaseId: string,
): Promise<WorkflowState> {
  return api.post<WorkflowState>(`/sessions/${sessionId}/workflow/phases/${phaseId}/complete`);
}

/**
 * Set a phase to awaiting approval status.
 */
export async function setPhaseAwaitingApproval(
  sessionId: string,
  phaseId: string,
): Promise<WorkflowState> {
  return api.post<WorkflowState>(
    `/sessions/${sessionId}/workflow/phases/${phaseId}/awaiting-approval`,
  );
}

/**
 * Get details about a specific phase.
 */
export async function getPhase(
  sessionId: string,
  phaseId: string,
): Promise<WorkflowPhase> {
  return api.get<WorkflowPhase>(`/sessions/${sessionId}/workflow/phases/${phaseId}`);
}

/**
 * Reset the workflow to its initial state.
 */
export async function resetWorkflow(sessionId: string): Promise<WorkflowState> {
  return api.post<WorkflowState>(`/sessions/${sessionId}/workflow/reset`);
}

// ============================================================================
// Namespace export
// ============================================================================

export const workflowApi = {
  get: getWorkflow,
  start: startWorkflow,
  approvePhase,
  approve,
  reject,
  completePhase,
  setPhaseAwaitingApproval,
  getPhase,
  reset: resetWorkflow,
};

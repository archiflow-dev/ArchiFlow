/**
 * Tests for the Workflow API client.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { workflowApi } from './workflowApi';
import { api } from './api';

// Mock the api module
vi.mock('./api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe('Workflow API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getWorkflow', () => {
    it('should get workflow state', async () => {
      const mockWorkflow = {
        session_id: 'session-123',
        agent_type: 'comic',
        workflow_type: 'phase_heavy',
        current_phase: 'script_generation',
        phases: [
          { id: 'script_generation', name: 'Script', status: 'in_progress', order: 0, requires_approval: true, artifacts: [] },
        ],
        total_phases: 5,
        completed_phases: 0,
        is_complete: false,
      };

      vi.mocked(api.get).mockResolvedValueOnce(mockWorkflow);

      const result = await workflowApi.get('session-123');

      expect(api.get).toHaveBeenCalledWith('/sessions/session-123/workflow/');
      expect(result).toEqual(mockWorkflow);
    });
  });

  describe('startWorkflow', () => {
    it('should start the workflow', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({ current_phase: 'script_generation' });

      await workflowApi.start('session-123');

      expect(api.post).toHaveBeenCalledWith('/sessions/session-123/workflow/start');
    });
  });

  describe('approvePhase', () => {
    it('should approve a phase', async () => {
      const mockResponse = {
        phase_id: 'script_generation',
        status: 'approved',
        next_phase: 'visual_specification',
        message: 'Phase approved',
      };

      vi.mocked(api.post).mockResolvedValueOnce(mockResponse);

      const result = await workflowApi.approvePhase('session-123', 'script_generation', {
        approved: true,
        feedback: 'Looks good!',
      });

      expect(api.post).toHaveBeenCalledWith(
        '/sessions/session-123/workflow/phases/script_generation/approve',
        { approved: true, feedback: 'Looks good!' },
      );
      expect(result).toEqual(mockResponse);
    });

    it('should reject a phase', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({
        phase_id: 'script_generation',
        status: 'rejected',
        message: 'Phase rejected',
      });

      await workflowApi.approvePhase('session-123', 'script_generation', {
        approved: false,
        feedback: 'Need more detail',
      });

      expect(api.post).toHaveBeenCalledWith(
        '/sessions/session-123/workflow/phases/script_generation/approve',
        { approved: false, feedback: 'Need more detail' },
      );
    });
  });

  describe('approve convenience function', () => {
    it('should approve with optional feedback', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({});

      await workflowApi.approve('session-123', 'phase-1', 'Great work!');

      expect(api.post).toHaveBeenCalledWith(
        '/sessions/session-123/workflow/phases/phase-1/approve',
        { approved: true, feedback: 'Great work!' },
      );
    });
  });

  describe('reject convenience function', () => {
    it('should reject with required feedback', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({});

      await workflowApi.reject('session-123', 'phase-1', 'Please revise');

      expect(api.post).toHaveBeenCalledWith(
        '/sessions/session-123/workflow/phases/phase-1/approve',
        { approved: false, feedback: 'Please revise' },
      );
    });
  });

  describe('completePhase', () => {
    it('should complete a phase', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({});

      await workflowApi.completePhase('session-123', 'phase-1');

      expect(api.post).toHaveBeenCalledWith(
        '/sessions/session-123/workflow/phases/phase-1/complete',
      );
    });
  });

  describe('setPhaseAwaitingApproval', () => {
    it('should set phase to awaiting approval', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({});

      await workflowApi.setPhaseAwaitingApproval('session-123', 'phase-1');

      expect(api.post).toHaveBeenCalledWith(
        '/sessions/session-123/workflow/phases/phase-1/awaiting-approval',
      );
    });
  });

  describe('getPhase', () => {
    it('should get phase details', async () => {
      const mockPhase = {
        id: 'script_generation',
        name: 'Script Generation',
        status: 'awaiting_approval',
        order: 0,
        requires_approval: true,
        artifacts: ['script.md'],
      };

      vi.mocked(api.get).mockResolvedValueOnce(mockPhase);

      const result = await workflowApi.getPhase('session-123', 'script_generation');

      expect(api.get).toHaveBeenCalledWith(
        '/sessions/session-123/workflow/phases/script_generation',
      );
      expect(result).toEqual(mockPhase);
    });
  });

  describe('resetWorkflow', () => {
    it('should reset the workflow', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({});

      await workflowApi.reset('session-123');

      expect(api.post).toHaveBeenCalledWith('/sessions/session-123/workflow/reset');
    });
  });
});
